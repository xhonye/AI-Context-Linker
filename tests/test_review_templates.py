from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError
from ai_context_linker.review_state import read_review_state
from ai_context_linker.review_templates import init_review_state


def _manifest(tmp_path: Path) -> Path:
    raw = {
        "schema_version": "0.2",
        "generated_at": "2026-08-29T12:00:00+08:00",
        "workspace": {
            "name": "Synthetic workspace",
            "summary": "Synthetic projects for a review template.",
            "current_focus": "Prepare explicit review state.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [
            {
                "id": project_id,
                "name": project_id.title(),
                "summary": "Synthetic project.",
                "status": "unknown",
                "sensitivity": "public",
                "cloud_visibility": "allow",
                "redaction_profile": "standard",
                "signals": [],
                "constraints": [],
                "risks": [],
                "open_questions": [],
                "state_items": [],
                "evidence": [f"{project_id}:file:README.md"],
            }
            for project_id in ("alpha", "beta", "gamma", "delta")
        ],
        "relationships": [],
    }
    path = tmp_path / "candidate-manifest.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    return path


def test_init_review_state_writes_safe_non_actionable_skeleton(tmp_path: Path) -> None:
    destination = tmp_path / "private" / "review-state-v0.2.json"
    result = init_review_state(
        _manifest(tmp_path),
        ["alpha", "beta", "gamma"],
        destination,
        observed_at=datetime.fromisoformat("2026-08-29T12:00:00+08:00"),
    )

    raw = json.loads(result.read_text(encoding="utf-8"))
    assert [project["project_id"] for project in raw["projects"]] == ["alpha", "beta", "gamma"]
    assert all(set(project) == {"project_id", "updated_at", "expires_at"} for project in raw["projects"])

    records, report = read_review_state(
        result,
        project_ids={"alpha", "beta", "gamma"},
        observed_at=datetime.fromisoformat("2026-08-29T12:00:00+08:00"),
    )
    assert records == {"alpha": [], "beta": [], "gamma": []}
    assert report["state_items_added"] == 0


def test_init_review_state_rejects_more_than_three_unknown_or_duplicate_projects(tmp_path: Path) -> None:
    manifest = _manifest(tmp_path)

    with pytest.raises(ManifestError, match="one to three"):
        init_review_state(manifest, ["alpha", "beta", "gamma", "delta"], tmp_path / "too-many.json")
    with pytest.raises(ManifestError, match="unknown project"):
        init_review_state(manifest, ["missing"], tmp_path / "unknown.json")
    with pytest.raises(ManifestError, match="duplicate project"):
        init_review_state(manifest, ["alpha", "alpha"], tmp_path / "duplicate.json")


def test_init_review_state_refuses_overwrite_without_force(tmp_path: Path) -> None:
    destination = tmp_path / "review-state-v0.2.json"
    destination.write_text("preserve", encoding="utf-8")

    with pytest.raises(ManifestError, match="already exists"):
        init_review_state(_manifest(tmp_path), ["alpha"], destination)

    assert destination.read_text(encoding="utf-8") == "preserve"
