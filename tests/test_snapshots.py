from __future__ import annotations

import json
from pathlib import Path

from ai_context_linker.core import build_bundle, facts_sha256, validate_manifest
from ai_context_linker.scanner import scan_workspace
from ai_context_linker.snapshots import approve_snapshot, load_approved_snapshot


def _manifest() -> dict[str, object]:
    raw: dict[str, object] = {
        "schema_version": "0.1",
        "generated_at": "2026-08-28T09:00:00+08:00",
        "workspace": {
            "name": "Snapshot fixture",
            "summary": "Synthetic approved snapshot.",
            "current_focus": "Verify explicit approval.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [
            {
                "id": "sample",
                "name": "Sample",
                "summary": "Synthetic project.",
                "status": "unknown",
                "signals": [],
                "risks": [],
                "open_questions": [],
                "evidence": ["sample:file:README.md"],
            }
        ],
        "relationships": [],
    }
    normalized = validate_manifest(raw)
    normalized["facts_sha256"] = facts_sha256(normalized)
    return validate_manifest(normalized)


def test_build_does_not_approve_snapshot(tmp_path: Path) -> None:
    manifest_path = tmp_path / "candidate.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")

    build_bundle(manifest_path, tmp_path / "publish")

    assert not list(tmp_path.rglob("approved-snapshot*.json"))


def test_approve_snapshot_writes_immutable_history_and_latest_pointer(tmp_path: Path) -> None:
    manifest_path = tmp_path / "candidate.json"
    manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")

    paths = approve_snapshot(
        manifest_path,
        tmp_path / "private-history",
        approved_at="2026-08-28T12:00:00+08:00",
    )
    loaded = load_approved_snapshot(paths.history)

    assert paths.history.is_file()
    assert paths.latest.is_file()
    assert paths.history.read_bytes() == paths.latest.read_bytes()
    assert loaded["facts_sha256"] == _manifest()["facts_sha256"]
    assert loaded["manifest"]["projects"][0]["id"] == "sample"


def test_scan_with_previous_approved_snapshot_writes_semantic_changes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Sample\n\nChanged synthetic summary.\n", encoding="utf-8")
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Snapshot fixture",
            "summary": "Synthetic approved snapshot.",
            "current_focus": "Verify explicit approval.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [{"id": "sample", "path": str(project), "sensitivity": "public", "cloud_visibility": "allow", "redaction_profile": "standard", "allow_files": ["README.md"]}],
        "relationships": [],
    }
    config_path = tmp_path / "workspace.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    old_manifest_path = tmp_path / "old.json"
    old_manifest_path.write_text(json.dumps(_manifest()), encoding="utf-8")
    approved = approve_snapshot(
        old_manifest_path,
        tmp_path / "private-history",
        approved_at="2026-08-28T10:00:00+08:00",
    )

    paths = scan_workspace(
        config_path,
        tmp_path / "review",
        previous_snapshot=approved.latest,
        observed_at="2026-08-28T12:00:00+08:00",
    )
    changes = json.loads(paths.changes_json.read_text(encoding="utf-8"))
    markdown = paths.changes_markdown.read_text(encoding="utf-8")

    assert changes["baseline_available"] is True
    assert changes["projects"]["changed"] == ["sample"]
    assert changes["semantic_state_changes"] == []
    assert "Git activity appendix" in markdown
    assert paths.changes_json.parent == paths.candidate_manifest.parent


def test_no_previous_snapshot_establishes_baseline_without_claiming_change(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Sample\n\nSynthetic summary.\n", encoding="utf-8")
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Baseline fixture",
            "summary": "Synthetic baseline.",
            "current_focus": "Establish a baseline.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [{"id": "sample", "path": str(project), "sensitivity": "public", "cloud_visibility": "allow", "redaction_profile": "standard", "allow_files": ["README.md"]}],
        "relationships": [],
    }
    config_path = tmp_path / "workspace.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    paths = scan_workspace(config_path, tmp_path / "review", observed_at="2026-08-28T12:00:00+08:00")
    changes = json.loads(paths.changes_json.read_text(encoding="utf-8"))

    assert changes["baseline_available"] is False
    assert changes["projects"] == {"added": [], "removed": [], "changed": []}
    assert changes["semantic_state_changes"] == []
