from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError
from ai_context_linker.discovery import discover_projects, discover_workspace


def test_discovery_finds_direct_projects_without_reading_source_bodies(tmp_path: Path) -> None:
    first = tmp_path / "First Project"
    first.mkdir()
    (first / ".git").mkdir()
    (first / "README.md").write_text("# First\n", encoding="utf-8")
    (first / "private.py").write_text("api_key=sk-example0123456789012345", encoding="utf-8")
    ignored = tmp_path / "notes"
    ignored.mkdir()
    (ignored / "private.py").write_text("print('not a project marker')", encoding="utf-8")

    result = discover_workspace([tmp_path], tmp_path / "private" / "workspace.json")
    raw = result.config.read_text(encoding="utf-8")
    config = json.loads(raw)

    assert result.project_count == 1
    assert config["projects"][0]["id"] == "first-project"
    assert config["projects"][0]["allow_files"] == ["README.md"]
    assert config["projects"][0]["state_files"] == []
    assert config["projects"][0]["sensitivity"] == "private"
    assert config["projects"][0]["cloud_visibility"] == "deny"
    assert config["projects"][0]["redaction_profile"] == "standard"
    assert "sk-example" not in raw
    assert "private.py" not in raw


def test_discovery_can_add_project_skill_roots_without_reading_skill_body(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    project = workspace / "project"
    skill_dir = project / ".agents" / "skills" / "safe-skill"
    skill_dir.mkdir(parents=True)
    (project / "README.md").write_text("# Project\n", encoding="utf-8")
    (skill_dir / "SKILL.md").write_text(
        "---\nname: safe-skill\ndescription: Safe summary.\n---\nprivate body\n",
        encoding="utf-8",
    )

    result = discover_workspace(
        [workspace],
        tmp_path / "private" / "workspace.json",
        include_skills=True,
    )
    config = json.loads(result.config.read_text(encoding="utf-8"))

    assert any(root["provider"] == "agent-skills" for root in config["skill_roots"])
    assert "private body" not in result.config.read_text(encoding="utf-8")


def test_discovery_deduplicates_overlapping_explicit_roots(tmp_path: Path) -> None:
    container = tmp_path / "Projects"
    container.mkdir()
    (container / "README.md").write_text("# Container, not a project\n", encoding="utf-8")
    project = container / "sample"
    project.mkdir()
    (project / "pyproject.toml").write_text("[project]\nname='sample'\n", encoding="utf-8")

    projects = discover_projects([tmp_path, container, container])

    assert [item["id"] for item in projects] == ["sample"]


def test_discovery_is_shallow_and_excludes_generated_directories(tmp_path: Path) -> None:
    outer = tmp_path / "outer"
    outer.mkdir()
    nested = outer / "nested"
    nested.mkdir()
    (nested / ".git").mkdir()
    output = tmp_path / "output"
    output.mkdir()
    (output / ".git").mkdir()

    with pytest.raises(ManifestError, match="no project candidates"):
        discover_workspace([tmp_path], tmp_path / "private" / "workspace.json")


def test_discovery_accepts_a_top_level_project_document_without_git(tmp_path: Path) -> None:
    legacy = tmp_path / "legacy-tool"
    legacy.mkdir()
    (legacy / "FEATURE_SUMMARY.md").write_text("# Legacy tool\n", encoding="utf-8")

    projects = discover_projects([tmp_path])

    assert [item["id"] for item in projects] == ["legacy-tool"]


def test_discovery_lists_state_candidates_without_approving_them(tmp_path: Path) -> None:
    project = tmp_path / "stateful"
    project.mkdir()
    (project / "README.md").write_text("# Stateful\n", encoding="utf-8")
    (project / "progress.md").write_text("# Progress\n", encoding="utf-8")

    projects = discover_projects([tmp_path])

    assert projects[0]["state_file_candidates"] == ["progress.md"]
    assert projects[0]["state_files"] == []


def test_discovery_skips_directory_links_that_escape_the_root(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    root.mkdir()
    private = tmp_path / "private-data"
    private.mkdir()
    (private / "README.md").write_text("# Must stay private\n", encoding="utf-8")
    linked = root / "linked-private"
    try:
        os.symlink(private, linked, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable in this environment")

    with pytest.raises(ManifestError, match="no project candidates"):
        discover_workspace([root], tmp_path / "private" / "workspace.json")


def test_discovery_refuses_to_overwrite_reviewed_config(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    project.mkdir()
    (project / ".git").mkdir()
    destination = tmp_path / "workspace.json"
    destination.write_text("keep me", encoding="utf-8")

    with pytest.raises(ManifestError, match="already exists"):
        discover_workspace([tmp_path], destination)

    assert destination.read_text(encoding="utf-8") == "keep me"


def test_discovery_rejects_cloud_synced_config_output(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    project.mkdir()
    (project / ".git").mkdir()

    with pytest.raises(ManifestError, match="cloud-synced"):
        discover_workspace([tmp_path], tmp_path / "Google Drive" / "workspace.json")


def test_discovery_reuses_stable_id_after_git_project_moves(tmp_path: Path) -> None:
    first_root = tmp_path / "first"
    first_root.mkdir()
    project = first_root / "old-folder"
    project.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(
        ["git", "remote", "add", "origin", "https://example.invalid/team/stable-project.git"],
        cwd=project,
        check=True,
    )
    (project / "README.md").write_text("# Stable\n", encoding="utf-8")
    previous = discover_workspace([first_root], tmp_path / "private" / "first.json").config
    previous_raw = json.loads(previous.read_text(encoding="utf-8"))
    previous_raw["projects"][0]["id"] = "human-approved-id"
    previous_raw["projects"][0]["summary"] = "Human-approved summary."
    previous_raw["projects"][0]["code_relationship_scan"] = True
    previous.write_text(json.dumps(previous_raw), encoding="utf-8")

    second_root = tmp_path / "second"
    second_root.mkdir()
    moved = second_root / "renamed-folder"
    project.rename(moved)
    result = discover_workspace(
        [second_root],
        tmp_path / "private" / "second.json",
        previous_config=previous,
    )
    config = json.loads(result.config.read_text(encoding="utf-8"))

    assert config["projects"][0]["id"] == "human-approved-id"
    assert config["projects"][0]["summary"] == "Human-approved summary."
    assert config["projects"][0]["code_relationship_scan"] is True
    assert config["projects"][0]["registry_key"].startswith("git-origin-sha256:")
    assert "example.invalid" not in result.config.read_text(encoding="utf-8")


def test_rediscovery_preserves_explicit_architecture_visibility(tmp_path: Path) -> None:
    project = tmp_path / "sample"
    project.mkdir()
    (project / "README.md").write_text("# Sample\n", encoding="utf-8")
    previous = tmp_path / "private" / "workspace.json"
    discovered = discover_workspace([tmp_path], previous)
    config = json.loads(discovered.config.read_text(encoding="utf-8"))
    config["projects"][0]["architecture_visibility"] = "modules-symbols"
    previous.write_text(json.dumps(config), encoding="utf-8")
    assert discover_projects([tmp_path], previous_config=previous)[0]["architecture_visibility"] == "modules-symbols"


def test_rediscovery_preserves_workspace_and_private_sources_across_directories(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    project = root / "sample"
    project.mkdir(parents=True)
    (project / "README.md").write_text("# Sample", encoding="utf-8")
    first = discover_workspace([root], tmp_path / "private" / "first.json").config
    config = json.loads(first.read_text(encoding="utf-8"))
    config["workspace"]["summary"] = "Reviewed workspace purpose."
    config["workspace"]["name"] = "Reviewed workspace"
    config["projects"][0].update(cloud_visibility="allow", sensitivity="internal", path="../workspace/sample")
    for key, filename in [
        ("review_state_files", "actions.json"),
        ("session_summary_files", "session.json"),
        ("relationship_candidate_files", "relations.json"),
    ]:
        config[key] = [filename]
    config["skill_roots"] = [{"id": "custom", "provider": "codex", "scope": "custom",
                             "path": "skills", "approved_summaries": {"sample": "Reviewed capability."}}]
    config["relationships"] = [{"source": "sample", "target": "sample", "type": "document-reference",
                               "summary": "Preserve configured review data.", "evidence": "sample:file:README.md"}]
    first.write_text(json.dumps(config), encoding="utf-8")
    before = first.read_bytes()
    result = discover_workspace([root], tmp_path / "next" / "second.json", previous_config=first)
    restored = json.loads(result.config.read_text(encoding="utf-8"))
    assert restored["workspace"] == config["workspace"]
    assert restored["relationships"] == config["relationships"]
    assert restored["projects"][0]["cloud_visibility"] == "allow"
    for key in ("review_state_files", "session_summary_files", "relationship_candidate_files"):
        assert Path(restored[key][0]) == first.parent / config[key][0]
    assert Path(restored["skill_roots"][0]["path"]) == first.parent / "skills"
    assert restored["skill_roots"][0]["approved_summaries"] == {"sample": "Reviewed capability."}
    assert first.read_bytes() == before


def test_rediscovery_name_override_keeps_reviewed_workspace_meaning(tmp_path: Path) -> None:
    project = tmp_path / "workspace" / "sample"
    project.mkdir(parents=True)
    (project / "README.md").write_text("# Sample", encoding="utf-8")
    first = discover_workspace([project.parent], tmp_path / "private" / "first.json").config
    config = json.loads(first.read_text(encoding="utf-8"))
    config["workspace"]["summary"] = "Reviewed purpose."
    first.write_text(json.dumps(config), encoding="utf-8")
    result = discover_workspace([project.parent], tmp_path / "next.json",
                                previous_config=first, workspace_name="New name")
    restored = json.loads(result.config.read_text(encoding="utf-8"))
    assert restored["workspace"]["name"] == "New name"
    assert restored["workspace"]["summary"] == "Reviewed purpose."


def test_new_project_name_cannot_inherit_existing_project_permissions(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    known = root / "zeta"
    known.mkdir(parents=True)
    (known / "README.md").write_text("# Known", encoding="utf-8")
    previous = discover_workspace([root], tmp_path / "private" / "old.json").config
    config = json.loads(previous.read_text(encoding="utf-8"))
    config["projects"][0].update(id="alpha", cloud_visibility="allow",
                                 code_relationship_scan=True, architecture_visibility="modules-symbols")
    previous.write_text(json.dumps(config), encoding="utf-8")
    newcomer = root / "alpha"
    newcomer.mkdir()
    (newcomer / "README.md").write_text("# New", encoding="utf-8")
    projects = discover_projects([root], previous_config=previous)
    by_folder = {Path(item["path"]).name: item for item in projects}
    assert by_folder["zeta"]["id"] == "alpha"
    assert by_folder["zeta"]["cloud_visibility"] == "allow"
    assert by_folder["alpha"]["id"] != "alpha"
    assert by_folder["alpha"]["cloud_visibility"] == "deny"
    assert "architecture_visibility" not in by_folder["alpha"]
    assert "code_relationship_scan" not in by_folder["alpha"]
