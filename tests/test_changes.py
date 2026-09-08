from __future__ import annotations

import pytest

from ai_context_linker.changes import semantic_changes
from ai_context_linker.state_records import make_state_record


def _state(kind: str, text: str) -> dict[str, object]:
    return make_state_record(
        project_id="sample",
        kind=kind,
        text=text,
        source_kind="approved-review",
        source_ref=f"sample:approved-review:{kind}",
        observed_at="2026-08-28T09:00:00+08:00",
        status="open",
    )


def _manifest(records: list[dict[str, object]], relationships: list[dict[str, str]]) -> dict[str, object]:
    return {
        "facts_sha256": "a" * 64,
        "projects": [
            {
                "id": "sample",
                "name": "Sample",
                "summary": "Synthetic project.",
                "status": "unknown",
                "constraints": [],
                "risks": [],
                "open_questions": [],
                "state_items": records,
            },
            {
                "id": "dependency",
                "name": "Dependency",
                "summary": "Synthetic dependency.",
                "status": "unknown",
                "constraints": [],
                "risks": [],
                "open_questions": [],
                "state_items": [],
            },
        ],
        "relationships": relationships,
    }


def test_semantic_diff_covers_action_kinds_and_relationships() -> None:
    previous = _manifest(
        [
            _state("current-goal", "Old goal."),
            _state("next-action", "Old next action."),
            _state("blocker", "Old blocker."),
            _state("deadline", "2026-08-29"),
        ],
        [
            {
                "source": "sample",
                "target": "dependency",
                "type": "blocked-by",
                "summary": "Synthetic blocker.",
                "evidence": "sample:approved-review:blocker",
            }
        ],
    )
    current = _manifest(
        [
            _state("current-goal", "New goal."),
            _state("next-action", "New next action."),
            _state("blocker", "New blocker."),
            _state("deadline", "2026-08-30"),
        ],
        [],
    )

    changes = semantic_changes(current, previous, git_activity_appendix=[])

    changed_kinds = {item["kind"] for item in changes["semantic_state_changes"]}
    assert changed_kinds == {"current-goal", "next-action", "blocker", "deadline"}
    assert changes["relationships"]["removed"] == ["sample|blocked-by|dependency"]


def test_architecture_map_hash_change_is_semantic_project_change() -> None:
    previous = _manifest([], [])
    current = _manifest([], [])
    previous["projects"][0]["architecture_index"] = {
        "mode": "modules-only",
        "map_sha256": "a" * 64,
        "truncated": False,
        "parse_failures": 0,
        "modules": [],
    }
    current["projects"][0]["architecture_index"] = {
        "mode": "modules-only",
        "map_sha256": "b" * 64,
        "truncated": False,
        "parse_failures": 0,
        "modules": [],
    }

    changes = semantic_changes(current, previous, git_activity_appendix=[])

    assert changes["projects"]["changed"] == ["sample"]
    assert changes["architecture_changes"] == [
        {"project_id": "sample", "from": "a" * 64, "to": "b" * 64}
    ]


@pytest.mark.parametrize(
    ("field", "value"),
    [("text", "Updated next action."), ("expires_at", "2026-09-10T12:00:00+08:00")],
)
def test_same_record_id_field_change_is_reported_without_publishing_values(field: str, value: str) -> None:
    record = _state("next-action", "Original next action.")
    previous = _manifest([record], [])
    current = _manifest([{**record, field: value}], [])
    changes = semantic_changes(current, previous, git_activity_appendix=[])
    assert changes["semantic_state_changes"] == [
        {"project_id": "sample", "record_id": record["record_id"], "kind": "next-action",
         "change": "updated", "fields": [field]}
    ]
    assert value not in str(changes)
