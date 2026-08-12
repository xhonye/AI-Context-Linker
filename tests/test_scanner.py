from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError, build_bundle
from ai_context_linker.scanner import collect_candidate, scan_workspace


def write_config(tmp_path: Path, project: Path, **project_overrides: object) -> Path:
    project_config: dict[str, object] = {
        "id": "sample",
        "path": str(project),
        "allow_files": ["README.md"],
        "observe_paths": ["tests"],
    }
    project_config.update(project_overrides)
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Scanner test",
            "summary": "A synthetic scanner test.",
            "current_focus": "Verify deterministic collection.",
            "decisions": ["Only allowlisted metadata may be read."],
            "unknowns": [],
        },
        "projects": [project_config],
        "relationships": [],
    }
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_scanner_builds_candidate_without_reading_source_bodies(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Safe Name\n\nA safe project summary.\n", encoding="utf-8")
    (project / "src").mkdir()
    (project / "src" / "private.py").write_text("api_key=sk-example0123456789012345", encoding="utf-8")
    (project / "tests").mkdir()
    config = write_config(tmp_path, project)

    candidate, report = collect_candidate(config, observed_at="2026-08-12T12:00:00+08:00")

    assert candidate["projects"][0]["name"] == "Safe Name"
    assert candidate["projects"][0]["summary"] == "A safe project summary."
    assert candidate["facts_sha256"]
    assert report["source_code_bodies_read"] == 0
    assert report["projects"][0]["metadata_files_read"] == ["README.md"]
    assert "private.py" not in json.dumps(candidate)


def test_candidate_hash_ignores_observation_time(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Stable\n\nStable summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)

    first, _ = collect_candidate(config, observed_at="2026-08-12T12:00:00+08:00")
    second, _ = collect_candidate(config, observed_at="2026-08-12T13:00:00+08:00")

    assert first["generated_at"] != second["generated_at"]
    assert first["facts_sha256"] == second["facts_sha256"]


def test_scanner_rejects_path_traversal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = write_config(tmp_path, project, allow_files=["../private.md"])

    with pytest.raises(ManifestError, match="relative path"):
        collect_candidate(config)


def test_scanner_rejects_source_code_even_when_explicitly_listed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('private')", encoding="utf-8")
    config = write_config(tmp_path, project, allow_files=["main.py"])

    with pytest.raises(ManifestError, match="allowed metadata filename"):
        collect_candidate(config)


def test_scanner_fails_closed_when_allowlisted_metadata_contains_secret(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Unsafe\n\napi_key=sk-example0123456789012345\n",
        encoding="utf-8",
    )
    config = write_config(tmp_path, project)

    with pytest.raises(ManifestError, match="likely secret"):
        collect_candidate(config)


def test_scan_then_build_is_a_two_step_approval_flow(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Review Me\n\nReviewable summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)

    scan_paths = scan_workspace(config, tmp_path / "review", observed_at="2026-08-12T12:00:00+08:00")
    bundle_paths = build_bundle(scan_paths.candidate_manifest, tmp_path / "publish")

    assert scan_paths.candidate_manifest.exists()
    assert scan_paths.report.exists()
    assert bundle_paths.markdown.exists()
    assert "Review Me" in bundle_paths.markdown.read_text(encoding="utf-8")
    assert str(project) not in scan_paths.candidate_manifest.read_text(encoding="utf-8")


def test_scan_report_compares_with_previous_approved_manifest(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("# First\n\nFirst summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)
    first = scan_workspace(config, tmp_path / "first", observed_at="2026-08-12T12:00:00+08:00")

    readme.write_text("# First\n\nChanged summary.\n", encoding="utf-8")
    second = scan_workspace(
        config,
        tmp_path / "second",
        previous_manifest=first.candidate_manifest,
        observed_at="2026-08-12T13:00:00+08:00",
    )
    report = json.loads(second.report.read_text(encoding="utf-8"))

    assert report["changes"]["baseline_available"] is True
    assert report["changes"]["changed"] is True
    assert report["changes"]["changed_projects"] == ["sample"]
    assert report["previous_facts_sha256"]
