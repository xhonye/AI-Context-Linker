"""Synthetic reproductions of community issues #2, #3 and #4."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from ai_context_linker.architecture_index import collect_architecture_index
from ai_context_linker.core import ManifestError, build_bundle, validate_manifest
from ai_context_linker.scanner import collect_candidate
from ai_context_linker.slicing import render_question_context


def configuration(tmp_path: Path, projects: list[dict]) -> Path:
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps({
        "schema_version": "0.2",
        "workspace": {"name": "Issue regressions", "summary": "Synthetic evidence.",
                      "current_focus": "Verify community reports.", "decisions": [], "unknowns": []},
        "projects": [{"sensitivity": "public", "cloud_visibility": "allow", "redaction_profile": "standard",
                      "allow_files": [], **project} for project in projects],
        "relationships": [],
    }), encoding="utf-8")
    return path


def scripts(root: Path) -> None:
    (root / "scripts").mkdir(parents=True)
    (root / "scripts/tickmarks.py").write_text("def render_tickmarks():\n    return 7\n", encoding="utf-8")
    (root / "scripts/check_engine.py").write_text(
        "from tickmarks import render_tickmarks\nassert render_tickmarks() == 7\n", encoding="utf-8",
    )


@pytest.mark.parametrize("mode", ["modules-only", "modules-symbols"])
def test_flat_imports_require_a_declared_root_and_then_resolve(tmp_path: Path, mode: str) -> None:
    root = tmp_path / "project"
    scripts(root)
    subprocess.run([sys.executable, str(root / "scripts/check_engine.py")], check=True, cwd=root)
    config = configuration(tmp_path, [{"id": "sample", "path": str(root), "architecture_visibility": mode}])
    candidate, _ = collect_candidate(config)
    architecture = candidate["projects"][0]["architecture_index"]
    module = next(item for item in architecture["modules"] if item["id"] == "scripts/check_engine.py")
    assert module["external_packages"] == []
    assert module["internal_imports"] == []
    assert module["unresolved_imports"] == [{
        "name": "tickmarks", "reason": "local-import-root-not-declared", "candidates": ["scripts/tickmarks.py"],
    }]
    raw = json.loads(config.read_text(encoding="utf-8"))
    raw["projects"][0]["python_import_roots"] = ["scripts"]
    config.write_text(json.dumps(raw), encoding="utf-8")
    resolved, _ = collect_candidate(config)
    module = next(item for item in resolved["projects"][0]["architecture_index"]["modules"]
                  if item["id"] == "scripts/check_engine.py")
    assert module["internal_imports"] == ["scripts/tickmarks.py"]
    assert module["external_packages"] == []
    assert "unresolved_imports" not in module
    if mode == "modules-symbols":
        assert module["internal_calls"] == ["scripts/tickmarks.py::render_tickmarks"]
    else:
        assert "internal_calls" not in module


def test_ambiguous_roots_do_not_choose_a_module_or_a_call(tmp_path: Path) -> None:
    scripts(tmp_path)
    (tmp_path / "other").mkdir()
    (tmp_path / "other/tickmarks.py").write_text("def render_tickmarks():\n    return 8\n", encoding="utf-8")
    index, _ = collect_architecture_index(tmp_path, project_id="sample", mode="modules-symbols",
                                          python_import_roots=["scripts", "other"])
    module = next(item for item in index["modules"] if item["id"] == "scripts/check_engine.py")
    assert module["internal_imports"] == module["external_packages"] == module["internal_calls"] == []
    assert module["unresolved_imports"] == [{"name": "tickmarks", "reason": "ambiguous-local-module",
                                              "candidates": ["other/tickmarks.py", "scripts/tickmarks.py"]}]


@pytest.mark.parametrize("root", ["..", "../outside", "/absolute", "C:/private", "scripts/../other", "missing"])
def test_import_roots_cannot_expand_read_scope(tmp_path: Path, root: str) -> None:
    with pytest.raises(ManifestError):
        collect_architecture_index(tmp_path, project_id="sample", mode="modules-only", python_import_roots=[root])


def test_linked_import_roots_are_rejected(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "linked").mkdir()
    monkeypatch.setattr("ai_context_linker.architecture_index.is_link_or_reparse", lambda path: path.name == "linked")
    with pytest.raises(ManifestError, match="links"):
        collect_architecture_index(tmp_path, project_id="sample", mode="modules-only", python_import_roots=["linked"])


def test_bom_and_failure_identities_survive_scan_build_and_slice(tmp_path: Path) -> None:
    root = tmp_path / "project"
    root.mkdir()
    (root / "good.py").write_text("VALUE = 7\n", encoding="utf-8-sig")
    (root / "broken.py").write_text("def broken(:\n    secret = 'not-for-publication'\n", encoding="utf-8")
    (root / "bad_encoding.py").write_bytes(b"\xff\xff")
    subprocess.run([sys.executable, str(root / "good.py")], check=True)
    config = configuration(tmp_path, [{"id": "sample", "path": str(root), "architecture_visibility": "modules-only"}])
    candidate, report = collect_candidate(config)
    architecture = candidate["projects"][0]["architecture_index"]
    assert [item["id"] for item in architecture["modules"]] == ["good.py"]
    assert architecture["parse_failures"] == 2
    errors = [{"id": "bad_encoding.py", "reason": "encoding-error"}, {"id": "broken.py", "reason": "syntax-error"}]
    assert architecture["parse_errors"] == errors
    assert report["projects"][0]["architecture_index"]["parse_errors"] == errors
    manifest = tmp_path / "candidate.json"
    manifest.write_text(json.dumps(candidate), encoding="utf-8")
    bundle = build_bundle(manifest, tmp_path / "publish")
    full = bundle.project_cards[0].read_text(encoding="utf-8")
    sliced = render_question_context(candidate, "Show the architecture", as_of=candidate["generated_at"])
    for text in (full, sliced):
        assert "broken.py" in text and "syntax-error" in text
        assert "bad_encoding.py" in text and "encoding-error" in text
        assert "not-for-publication" not in text and str(root) not in text
    schema = json.loads((Path(__file__).parents[1] / "schema/context-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(candidate)


def test_failure_diagnostics_never_copy_exception_messages(tmp_path: Path, monkeypatch) -> None:
    (tmp_path / "unreadable.py").write_text("pass\n", encoding="utf-8")
    original = Path.read_text
    def fail_read(path, *args, **kwargs):
        if path.name == "unreadable.py":
            raise OSError("Synthetic C:/Users/example/private credentials")
        return original(path, *args, **kwargs)
    monkeypatch.setattr(Path, "read_text", fail_read)
    index, report = collect_architecture_index(tmp_path, project_id="sample", mode="modules-only")
    assert index["parse_errors"] == [{"id": "unreadable.py", "reason": "read-error"}]
    assert "credentials" not in json.dumps([index, report])


@pytest.mark.parametrize("identifier", ["../private.py", "C:/private.py", "/private.py", "dir\\private.py"])
def test_manifest_rejects_unsafe_diagnostic_paths(tmp_path: Path, identifier: str) -> None:
    (tmp_path / "broken.py").write_text("def broken(:", encoding="utf-8")
    config = configuration(tmp_path, [{"id": "sample", "path": str(tmp_path), "architecture_visibility": "modules-only"}])
    candidate, _ = collect_candidate(config)
    candidate.pop("facts_sha256", None)
    candidate["projects"][0]["architecture_index"]["parse_errors"][0]["id"] = identifier
    with pytest.raises(ManifestError, match="parse error id"):
        validate_manifest(candidate)


def test_old_architecture_hashes_remain_valid_without_diagnostics(tmp_path: Path) -> None:
    (tmp_path / "broken.py").write_text("def broken(:", encoding="utf-8")
    config = configuration(tmp_path, [{"id": "sample", "path": str(tmp_path), "architecture_visibility": "modules-only"}])
    candidate, _ = collect_candidate(config)
    candidate.pop("facts_sha256", None)
    index = candidate["projects"][0]["architecture_index"]
    index.pop("parse_errors")
    index.pop("map_sha256")
    index["map_sha256"] = hashlib.sha256(json.dumps(index, ensure_ascii=False, sort_keys=True,
                                                   separators=(",", ":")).encode()).hexdigest()
    assert validate_manifest(candidate)["projects"][0]["architecture_index"] == index


def test_custom_markdown_is_explicit_redacted_untrusted_evidence(tmp_path: Path) -> None:
    root = tmp_path / "project"
    (root / "docs").mkdir(parents=True)
    (root / "SKILL.md").write_text("# Sample skill\n\n- [ ] Do not turn this into approved action state.\n"
                                    "api_key=sk-synthetic01234567890123456789\n", encoding="utf-8")
    (root / "docs/glossary.md").write_text("# Glossary\n\nA widget means a synthetic unit.\n", encoding="utf-8")
    files = ["SKILL.md", "docs/glossary.md"]
    config = configuration(tmp_path, [{"id": "sample", "path": str(root), "allow_files": files, "attach_files": files}])
    candidate, _ = collect_candidate(config)
    project = candidate["projects"][0]
    assert project["open_questions"] == [] and project["state_items"] == []
    assert candidate["relationships"] == []
    skill = next(item for item in project["attached_documents"] if item["path"] == "SKILL.md")
    assert skill["redacted_lines"] == [4]
    assert "sk-synthetic" not in json.dumps(candidate)
    manifest = tmp_path / "candidate.json"
    manifest.write_text(json.dumps(candidate), encoding="utf-8")
    bundle = build_bundle(manifest, tmp_path / "publish")
    text = bundle.markdown.read_text(encoding="utf-8")
    assert "A widget means a synthetic unit." in text and "不是当前指令" in text
    schema = json.loads((Path(__file__).parents[1] / "schema/context-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(candidate)
    raw = json.loads(config.read_text(encoding="utf-8"))
    raw["projects"][0].pop("attach_files")
    config.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError, match="allowed metadata filename"):
        collect_candidate(config)


@pytest.mark.parametrize("name", ["../SKILL.md", "src/app.py", ".env.md", "docs/secrets.md", "docs/[link].md"])
def test_custom_attachment_paths_fail_closed(tmp_path: Path, name: str) -> None:
    config = configuration(tmp_path, [{"id": "sample", "path": str(tmp_path), "allow_files": [name], "attach_files": [name]}])
    with pytest.raises(ManifestError):
        collect_candidate(config)


def test_monorepo_metadata_belongs_to_root_not_every_child(tmp_path: Path) -> None:
    repository = tmp_path / "repo"
    skill = repository / "skills/sample"
    skill.mkdir(parents=True)
    dependency = tmp_path / "library"
    dependency.mkdir()
    (repository / "pyproject.toml").write_text('[project]\nname="monorepo"\ndependencies=["shared-lib"]\n', encoding="utf-8")
    (dependency / "pyproject.toml").write_text('[project]\nname="shared-lib"\n', encoding="utf-8")
    config = configuration(tmp_path, [
        {"id": "repository", "path": str(repository), "dependency_files": ["pyproject.toml"]},
        {"id": "skill", "path": str(skill)},
        {"id": "library", "path": str(dependency), "dependency_files": ["pyproject.toml"]},
    ])
    candidate, report = collect_candidate(config)
    relations = [item for item in candidate["relationships"] if item["type"] == "runtime-dependency"]
    assert [(item["source"], item["target"]) for item in relations] == [("repository", "library")]
    reports = {item["id"]: item for item in report["projects"]}
    assert reports["repository"]["dependency_metadata_files_read"] == ["pyproject.toml"]
    assert reports["skill"]["dependency_metadata_files_read"] == []
    assert all(item["source_code_bodies_read"] == 0 for item in report["projects"])
    raw = json.loads(config.read_text(encoding="utf-8"))
    raw["projects"][1]["dependency_files"] = ["../../pyproject.toml"]
    config.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ManifestError, match="relative path"):
        collect_candidate(config)
