"""Synthetic monorepo dependency discovery without per-child setup."""
import json
import subprocess
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ai_context_linker.core import build_bundle
from ai_context_linker.scanner import collect_candidate
from ai_context_linker.slicing import render_question_context


def configuration(tmp_path, projects):
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps({"schema_version": "0.2", "workspace": {
        "name": "Synthetic monorepo", "summary": "Shared dependency evidence.",
        "current_focus": "Verify scoped metadata.", "decisions": [], "unknowns": []},
        "projects": [{"sensitivity": "public", "cloud_visibility": "allow",
                      "redaction_profile": "standard", "allow_files": [], **project}
                     for project in projects], "relationships": []}), encoding="utf-8")
    return path


def repository(tmp_path):
    root = tmp_path / "repo"
    child = root / "skills/sample"
    child.mkdir(parents=True)
    subprocess.run(["git", "init", str(root)], check=True, capture_output=True)
    return root, child


def test_default_discovers_shared_names_without_child_edges(tmp_path):
    root, child = repository(tmp_path)
    (root / "pyproject.toml").write_text('[project]\nname="parent"\ndependencies=["shared-lib>=1", "requests"]\n', encoding="utf-8")
    library = tmp_path / "library"
    library.mkdir()
    (library / "pyproject.toml").write_text('[project]\nname="shared-lib"\n', encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}, {"id": "library", "path": str(library)}])
    candidate, report = collect_candidate(config)
    project = next(p for p in candidate["projects"] if p["id"] == "skill")
    assert "shared-lib" in project["signals"][0] and "requests" in project["signals"][0]
    assert "Child usage is unknown" in project["signals"][0]
    assert not candidate["relationships"]
    skill_report = next(p for p in report["projects"] if p["id"] == "skill")
    assert skill_report["shared_dependency_metadata"] == [
        {"path": "pyproject.toml", "scope": "repository-shared", "status": "read", "omitted_names": 0}]
    assert report["projects"][0]["source_code_bodies_read"] == 0
    manifest = tmp_path / "candidate.json"
    manifest.write_text(json.dumps(candidate), encoding="utf-8")
    bundle = build_bundle(manifest, tmp_path / "publish")
    for text in (bundle.markdown.read_text(encoding="utf-8"),
                 render_question_context(candidate, "Show skill dependencies", as_of=candidate["generated_at"])):
        assert "shared-lib" in text and "Child usage is unknown" in text
        assert str(root) not in text
    schema = json.loads((Path(__file__).parents[1] / "schema/context-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(candidate)


@pytest.mark.parametrize("visibility", ["deny", "summary-only"])
def test_denied_ancestor_is_not_read(tmp_path, visibility, monkeypatch):
    root, child = repository(tmp_path)
    target = root / "pyproject.toml"
    target.write_text("should not be read", encoding="utf-8")
    original = Path.read_bytes
    def guarded(path):
        assert path != target
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", guarded)
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)},
        {"id": "parent", "path": str(root), "cloud_visibility": visibility, "approved_summary": "Private parent summary."}])
    candidate, report = collect_candidate(config)
    assert not next(p for p in candidate["projects"] if p["id"] == "skill")["signals"]
    assert next(p for p in report["projects"] if p["id"] == "skill")["shared_dependency_metadata"] == [{"status": "withheld-by-policy"}]


def test_opt_out_and_non_git_do_not_read_ancestors(tmp_path):
    root, child = repository(tmp_path)
    (root / "pyproject.toml").write_text('[project]\ndependencies=["shared-lib"]\n', encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child), "discover_shared_dependencies": False}])
    candidate, _ = collect_candidate(config)
    assert not candidate["projects"][0]["signals"]
    outside = tmp_path / "outside/child"
    outside.mkdir(parents=True)
    (outside.parent / "pyproject.toml").write_text('[project]\ndependencies=["outside-lib"]\n', encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(outside)}])
    candidate, _ = collect_candidate(config)
    assert not candidate["projects"][0]["signals"]


def test_nearest_file_wins_and_nested_repository_stops_search(tmp_path):
    root, child = repository(tmp_path)
    (root / "pyproject.toml").write_text('[project]\ndependencies=["outer-lib"]\n', encoding="utf-8")
    (child.parent / "pyproject.toml").write_text('[project]\ndependencies=["near-lib"]\n', encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}])
    candidate, _ = collect_candidate(config)
    text = json.dumps(candidate)
    assert "near-lib" in text and "outer-lib" not in text
    subprocess.run(["git", "init", str(child)], check=True, capture_output=True)
    candidate, _ = collect_candidate(config)
    assert "near-lib" not in json.dumps(candidate) and "outer-lib" not in json.dumps(candidate)


@pytest.mark.parametrize("body", ["invalid toml PRIVATE_SECRET", "x" * (128 * 1024 + 1)], ids=["malformed", "oversized"])
def test_bad_metadata_is_visible_as_unknown_without_source_leak(tmp_path, body):
    root, child = repository(tmp_path)
    (root / "pyproject.toml").write_text(body, encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}])
    candidate, report = collect_candidate(config)
    assert "remain unknown" in candidate["projects"][0]["signals"][0]
    assert report["projects"][0]["shared_dependency_metadata"][0]["status"] == "unavailable"
    assert "PRIVATE_SECRET" not in json.dumps([candidate, report])


def test_shared_link_is_not_followed(tmp_path, monkeypatch):
    root, child = repository(tmp_path)
    target = root / "package.json"
    target.write_text('{"dependencies":{"private-lib":"1"}}', encoding="utf-8")
    monkeypatch.setattr("ai_context_linker.shared_dependencies.is_link_or_reparse", lambda path: path == target)
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}])
    candidate, report = collect_candidate(config)
    assert "private-lib" not in json.dumps([candidate, report])
    assert report["projects"][0]["shared_dependency_metadata"][0]["status"] == "unavailable"


def test_shared_versions_urls_scripts_and_unknown_fields_are_not_exported(tmp_path):
    root, child = repository(tmp_path)
    (root / "package.json").write_text(json.dumps({"dependencies": {"shared-lib": "https://user:password@private.example/source"},
        "scripts": {"postinstall": "PRIVATE_SCRIPT"}, "private": "PRIVATE_FIELD"}), encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}])
    candidate, report = collect_candidate(config)
    text = json.dumps([candidate, report])
    assert "shared-lib" in text
    assert all(value not in text for value in ("password", "private.example", "PRIVATE_SCRIPT", "PRIVATE_FIELD"))


def test_local_dependencies_keep_direct_ownership_alongside_shared(tmp_path):
    root, child = repository(tmp_path)
    (root / "pyproject.toml").write_text('[project]\nname="parent"\ndependencies=["parent-only"]\n', encoding="utf-8")
    (child / "pyproject.toml").write_text('[project]\nname="child"\ndependencies=["shared-lib"]\n', encoding="utf-8")
    library = tmp_path / "library"
    library.mkdir()
    (library / "pyproject.toml").write_text('[project]\nname="shared-lib"\n', encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}, {"id": "library", "path": str(library)}])
    candidate, _ = collect_candidate(config)
    assert [(r["source"], r["target"]) for r in candidate["relationships"]] == [("skill", "library")]
    assert "parent-only" in next(p for p in candidate["projects"] if p["id"] == "skill")["signals"][0]


def test_git_worktree_boundary_does_not_include_main_checkout(tmp_path):
    root, _ = repository(tmp_path)
    subprocess.run(["git", "-C", str(root), "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                    "commit", "--allow-empty", "-m", "Synthetic baseline"], check=True, capture_output=True)
    worktree = tmp_path / "worktree"
    subprocess.run(["git", "-C", str(root), "worktree", "add", "--detach", str(worktree)], check=True, capture_output=True)
    child = worktree / "skills/sample"
    child.mkdir(parents=True)
    (root / "pyproject.toml").write_text('[project]\ndependencies=["main-only"]\n', encoding="utf-8")
    (worktree / "pyproject.toml").write_text('[project]\ndependencies=["worktree-only"]\n', encoding="utf-8")
    (tmp_path / "package.json").write_text('{"dependencies":{"outside-repo":"1"}}', encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child), "dependency_files": []}])
    candidate, _ = collect_candidate(config)
    text = json.dumps(candidate)
    assert "worktree-only" in text and "main-only" not in text and "outside-repo" not in text


def test_invalid_nearer_declaration_does_not_fall_back(tmp_path):
    root, child = repository(tmp_path)
    (root / "pyproject.toml").write_text('[project]\ndependencies=["outer-lib"]\n', encoding="utf-8")
    (child.parent / "pyproject.toml").write_text("bad = [", encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}])
    candidate, report = collect_candidate(config)
    assert "outer-lib" not in json.dumps(candidate)
    assert report["projects"][0]["shared_dependency_metadata"] == [
        {"path": "skills/pyproject.toml", "scope": "repository-shared", "status": "unavailable"}]


def test_large_inventory_is_bounded_and_reports_omission(tmp_path):
    root, child = repository(tmp_path)
    (root / "package.json").write_text(json.dumps({"dependencies": {f"package-{i:03d}": "1" for i in range(200)}}), encoding="utf-8")
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}])
    candidate, report = collect_candidate(config)
    assert "Some names were omitted" in candidate["projects"][0]["signals"][0]
    assert "package-099" in candidate["projects"][0]["signals"][0]
    assert "package-100" not in json.dumps(candidate)
    assert report["projects"][0]["shared_dependency_metadata"][0]["omitted_names"] == 100


def test_hidden_ancestor_metadata_is_not_read(tmp_path, monkeypatch):
    root, _ = repository(tmp_path)
    child = root / ".private/child"
    child.mkdir(parents=True)
    target = child.parent / "pyproject.toml"
    target.write_text('[project]\ndependencies=["not-for-export"]\n', encoding="utf-8")
    original = Path.read_bytes
    def guarded(path):
        assert path != target
        return original(path)
    monkeypatch.setattr(Path, "read_bytes", guarded)
    config = configuration(tmp_path, [{"id": "skill", "path": str(child)}])
    candidate, _ = collect_candidate(config)
    assert "not-for-export" not in json.dumps(candidate)
