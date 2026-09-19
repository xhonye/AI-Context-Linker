from __future__ import annotations

import pytest

from ai_context_linker.changes import SEMANTIC_KINDS, render_changes_markdown, semantic_changes
from ai_context_linker.core import STATE_KINDS
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


def _pending_state(kind: str, text: str) -> dict[str, object]:
    """A repository-native state record that no human has approved yet."""
    return make_state_record(
        project_id="sample",
        kind=kind,
        text=text,
        source_kind="project-state",
        source_ref=f"sample:STATUS.md:{kind}",
        observed_at="2026-08-28T09:00:00+08:00",
        status="needs_review",
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
         "change": "updated", "status": "open", "source_kind": "approved-review", "fields": [field]}
    ]
    assert value not in str(changes)


def test_diff_universe_matches_the_state_model() -> None:
    """The diff must not drift away from the kinds the state model can emit."""
    assert SEMANTIC_KINDS == set(STATE_KINDS)


@pytest.mark.parametrize("kind", sorted(STATE_KINDS))
def test_every_state_kind_addition_is_reported(kind: str) -> None:
    changes = semantic_changes(
        _manifest([_state(kind, "Added.")], []), _manifest([], []), git_activity_appendix=[]
    )

    assert [item["change"] for item in changes["semantic_state_changes"]] == ["added"]


@pytest.mark.parametrize("kind", sorted(STATE_KINDS))
def test_every_state_kind_edit_is_reported(kind: str) -> None:
    record = _state(kind, "Original text.")

    changes = semantic_changes(
        _manifest([{**record, "text": "Revised text."}], []),
        _manifest([record], []),
        git_activity_appendix=[],
    )

    assert [item["change"] for item in changes["semantic_state_changes"]] == ["updated"]


@pytest.mark.parametrize("kind", sorted(STATE_KINDS))
def test_every_state_kind_disappearance_is_reported(kind: str) -> None:
    changes = semantic_changes(
        _manifest([], []), _manifest([_state(kind, "Gone.")], []), git_activity_appendix=[]
    )

    assert [item["change"] for item in changes["semantic_state_changes"]] == ["missing-needs-review"]


def test_state_change_entries_carry_status_and_source_kind() -> None:
    """Pending repository state must not be indistinguishable from approved state."""
    changes = semantic_changes(
        _manifest([_pending_state("current-goal", "Pending goal.")], []),
        _manifest([], []),
        git_activity_appendix=[],
    )

    entry = changes["semantic_state_changes"][0]
    assert entry["status"] == "needs_review"
    assert entry["source_kind"] == "project-state"


def test_every_change_type_carries_provenance() -> None:
    approved = _state("blocker", "Approved blocker.")
    previous = _manifest([approved, _state("next-action", "Old next action.")], [])
    current = _manifest(
        [
            _pending_state("blocker", "Pending blocker."),
            {**_state("next-action", "New next action."), "status": "resolved"},
        ],
        [],
    )

    changes = semantic_changes(current, previous, git_activity_appendix=[])

    assert changes["semantic_state_changes"]
    for entry in changes["semantic_state_changes"]:
        assert entry["status"]
        assert entry["source_kind"]


def test_rendered_changes_distinguish_pending_from_approved_state() -> None:
    changes = semantic_changes(
        _manifest([_pending_state("current-goal", "Pending goal."), _state("blocker", "Approved blocker.")], []),
        _manifest([], []),
        git_activity_appendix=[],
    )

    rendered = render_changes_markdown(changes)

    assert "## State changes" in rendered
    assert "`needs_review`" in rendered
    assert "`project-state`" in rendered
    assert "`open`" in rendered
    assert "`approved-review`" in rendered
