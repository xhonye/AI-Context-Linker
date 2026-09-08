from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError
from ai_context_linker.review_state import read_review_state
from ai_context_linker.scanner import collect_candidate
from ai_context_linker.state import extract_state_items


OBSERVED_AT = datetime.fromisoformat("2026-08-28T12:00:00+08:00")


def _workspace_config(tmp_path: Path, project: Path, *, review_state_files: list[str] | None = None) -> Path:
    config: dict[str, object] = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Action review",
            "summary": "Synthetic action context review.",
            "current_focus": "Use approved action state only.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [
            {
                "id": "sample",
                "path": str(project),
                "sensitivity": "public",
                "cloud_visibility": "allow",
                "redaction_profile": "standard",
                "allow_files": ["README.md"],
                "state_files": ["STATUS.md"],
            }
        ],
        "relationships": [],
    }
    if review_state_files is not None:
        config["review_state_files"] = review_state_files
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_review_state_v02_has_priority_without_deleting_extracted_facts(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Sample\n\nSynthetic project.\n", encoding="utf-8")
    (project / "STATUS.md").write_text(
        "# Status\n\n## Next action\n\n- Run the automatically extracted check.\n",
        encoding="utf-8",
    )
    review = tmp_path / "review-state.json"
    review.write_text(
        json.dumps(
            {
                "schema_version": "0.2",
                "projects": [
                    {
                        "project_id": "sample",
                        "priority": "P0",
                        "activity": "active",
                        "attention": "today",
                        "why_now": "The approved deadline is near.",
                        "current_goal": "Validate the complete action contract.",
                        "next_action": "Run the approved end-to-end fixture.",
                        "done_when": "The deterministic report passes every gate.",
                        "owner": "maintainer",
                        "due_at": "2026-08-30",
                        "blockers": ["Waiting for the synthetic dependency."],
                        "updated_at": "2026-08-28T09:00:00+08:00",
                        "expires_at": "2026-09-04T09:00:00+08:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = _workspace_config(tmp_path, project, review_state_files=[str(review)])

    candidate, report = collect_candidate(config, observed_at="2026-08-28T12:00:00+08:00")
    items = candidate["projects"][0]["state_items"]

    assert items[0]["provenance"] == "approved-review"
    assert items[0]["kind"] == "priority"
    assert items[0]["text"] == "P0"
    assert any(item["kind"] == "next-action" and item["provenance"] == "approved-review" for item in items)
    assert any(item["kind"] == "next-action" and item["provenance"] == "project-state" for item in items)
    assert report["review_state"]["files_read"] == 1
    assert report["review_state"]["projects_approved"] == 1


def test_review_state_v01_is_migrated_without_guessing_missing_fields(tmp_path: Path) -> None:
    path = tmp_path / "review-v01.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.1",
                "projects": [
                    {
                        "project_id": "sample",
                        "status": "active",
                        "current_goal": "Preserve the legacy approved goal.",
                        "next_action": "Migrate the fixture.",
                        "blockers": [],
                        "updated_at": "2026-08-27T10:00:00+08:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    records, report = read_review_state(path, project_ids={"sample"}, observed_at=OBSERVED_AT)

    assert report["input_schema_version"] == "0.1"
    assert report["normalized_schema_version"] == "0.2"
    assert {item["kind"] for item in records["sample"]} == {"activity", "current-goal", "next-action"}
    assert not any(item["kind"] in {"priority", "attention", "why-now", "done-when", "owner"} for item in records["sample"])


def test_review_state_rejects_sensitive_approved_text(tmp_path: Path) -> None:
    path = tmp_path / "unsafe-review.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.2",
                "projects": [
                    {
                        "project_id": "sample",
                        "next_action": "Read C:/Users/example/private.txt",
                        "updated_at": "2026-08-28T09:00:00+08:00",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ManifestError, match="absolute path"):
        read_review_state(path, project_ids={"sample"}, observed_at=OBSERVED_AT)


def test_review_state_accepts_explicit_lifecycle_record(tmp_path: Path) -> None:
    path = tmp_path / "lifecycle-review.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "0.2",
                "projects": [
                    {
                        "project_id": "sample",
                        "updated_at": "2026-08-28T09:00:00+08:00",
                        "records": [
                            {
                                "record_id": "state-1111111111111111",
                                "kind": "blocker",
                                "text": "The earlier blocker is explicitly resolved.",
                                "status": "resolved",
                                "supersedes": ["state-2222222222222222"],
                            }
                        ],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    records, _ = read_review_state(path, project_ids={"sample"}, observed_at=OBSERVED_AT)

    assert records["sample"][0]["record_id"] == "state-1111111111111111"
    assert records["sample"][0]["status"] == "resolved"
    assert records["sample"][0]["supersedes"] == ["state-2222222222222222"]


def test_multiline_markdown_state_is_joined_without_half_sentence_truncation() -> None:
    text = (
        "# Status\n\n## Current goal\n\n"
        "Build a deterministic action context that preserves\n"
        "approved facts across snapshot refreshes.\n\n"
        "## Next action\n\n"
        "- Add lifecycle fixtures that cover\n"
        "  blocker resolution and supersession.\n"
    )

    items = extract_state_items(
        text,
        project_id="sample",
        relative_name="STATUS.md",
        observed_at=OBSERVED_AT,
    )

    assert items[0]["text"] == "Build a deterministic action context that preserves approved facts across snapshot refreshes."
    assert items[1]["text"] == "Add lifecycle fixtures that cover blocker resolution and supersession."


def test_state_filename_does_not_define_state_kind() -> None:
    items = extract_state_items(
        "# Findings\n\nThis paragraph is merely a finding.\n",
        project_id="sample",
        relative_name="findings.md",
        observed_at=OBSERVED_AT,
    )

    assert items == []


def test_phase_heading_and_completed_control_lines_do_not_become_current_goal() -> None:
    text = (
        "# Task plan\n\n"
        "### Phase 17: Current Action Contract\n\n"
        "- [x] approved-review state takes precedence\n"
        "- [x] preserve automatically extracted evidence\n"
        "- **Status:** complete\n\n"
        "## Current goal\n\n"
        "Ship the real action parity slice.\n"
    )

    items = extract_state_items(
        text,
        project_id="sample",
        relative_name="task_plan.md",
        observed_at=OBSERVED_AT,
    )

    assert [(item["kind"], item["text"]) for item in items] == [
        ("current-goal", "Ship the real action parity slice."),
    ]


def test_checked_items_under_action_heading_are_completed_and_control_lines_are_skipped() -> None:
    text = (
        "# Status\n\n"
        "## Next action\n\n"
        "- [x] Finish the earlier migration.\n"
        "- [ ] Run the current parity check.\n\n"
        "## Deadline\n\n"
        "- Status: complete\n"
        "- Files created/modified: report.md\n"
        "- 2026-08-30\n"
    )

    items = extract_state_items(
        text,
        project_id="sample",
        relative_name="STATUS.md",
        observed_at=OBSERVED_AT,
    )

    assert any(item["kind"] == "completed" and item["text"] == "Finish the earlier migration." for item in items)
    assert any(item["kind"] == "next-action" and item["text"] == "Run the current parity check." for item in items)
    assert any(item["kind"] == "deadline" and item["text"] == "2026-08-30" for item in items)
    assert not any("Status:" in item["text"] or "Files created" in item["text"] for item in items)


def test_git_activity_does_not_replace_unknown_without_approved_state(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Sample\n\nSynthetic project.\n", encoding="utf-8")
    (project / "STATUS.md").write_text("# Status\n", encoding="utf-8")
    config = _workspace_config(tmp_path, project)

    candidate, _ = collect_candidate(config, observed_at="2026-08-28T12:00:00+08:00")

    assert candidate["projects"][0]["status"].startswith("unknown")
    assert candidate["projects"][0]["state_items"] == []
