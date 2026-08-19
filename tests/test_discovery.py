from __future__ import annotations

import json
import os
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
