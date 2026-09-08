from __future__ import annotations

from datetime import datetime

from ai_context_linker.state_records import make_state_record, resolve_state_records


NOW = datetime.fromisoformat("2026-08-28T12:00:00+08:00")


def _record(
    text: str,
    *,
    status: str = "open",
    record_id: str | None = None,
    supersedes: list[str] | None = None,
    expires_at: str | None = None,
) -> dict[str, object]:
    return make_state_record(
        project_id="sample",
        kind="blocker",
        text=text,
        source_kind="approved-review",
        source_ref="sample:approved-review:blockers",
        observed_at="2026-08-28T09:00:00+08:00",
        expires_at=expires_at,
        status=status,
        record_id=record_id,
        supersedes=supersedes or [],
    )


def test_same_stable_record_id_can_resolve_open_blocker() -> None:
    previous = _record("Waiting for review.")
    current = _record("Waiting for review.", status="resolved", record_id=str(previous["record_id"]))

    resolved = resolve_state_records([current], [previous], observed_at=NOW)

    assert len(resolved) == 1
    assert resolved[0]["record_id"] == previous["record_id"]
    assert resolved[0]["status"] == "resolved"


def test_explicit_supersedes_closes_old_record_without_deleting_it() -> None:
    previous = _record("Waiting for the old dependency.")
    current = _record("Waiting for the replacement dependency.", supersedes=[str(previous["record_id"])])

    resolved = resolve_state_records([current], [previous], observed_at=NOW)
    by_id = {record["record_id"]: record for record in resolved}

    assert by_id[previous["record_id"]]["status"] == "superseded"
    assert by_id[current["record_id"]]["status"] == "open"


def test_resolved_record_with_different_id_does_not_close_old_record() -> None:
    previous = _record("Waiting for the original dependency.")
    unrelated_resolution = _record("A different dependency was resolved.", status="resolved")

    resolved = resolve_state_records([unrelated_resolution], [previous], observed_at=NOW)
    by_id = {record["record_id"]: record for record in resolved}

    assert by_id[previous["record_id"]]["status"] == "needs_review"
    assert by_id[unrelated_resolution["record_id"]]["status"] == "resolved"


def test_disappeared_source_becomes_needs_review_not_resolved() -> None:
    previous = _record("Waiting for a source that later disappeared.")

    resolved = resolve_state_records([], [previous], observed_at=NOW)

    assert len(resolved) == 1
    assert resolved[0]["status"] == "needs_review"


def test_expired_approved_record_becomes_stale() -> None:
    record = _record("Waiting for an expired approval.", expires_at="2026-08-28T10:00:00+08:00")

    resolved = resolve_state_records([record], [], observed_at=NOW)

    assert resolved[0]["status"] == "stale"


def test_state_record_id_is_stable_when_only_source_line_moves() -> None:
    first = make_state_record(
        project_id="sample",
        kind="next-action",
        text="Run the deterministic fixture.",
        source_kind="project-state",
        source_ref="sample:file:STATUS.md:line-5",
        observed_at="2026-08-28T09:00:00+08:00",
        status="needs_review",
    )
    moved = make_state_record(
        project_id="sample",
        kind="next-action",
        text="Run the deterministic fixture.",
        source_kind="project-state",
        source_ref="sample:file:STATUS.md:line-12",
        observed_at="2026-08-28T11:00:00+08:00",
        status="needs_review",
    )

    assert first["record_id"] == moved["record_id"]
