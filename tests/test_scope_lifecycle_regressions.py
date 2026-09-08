from __future__ import annotations

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest

from ai_context_linker import scanner
from ai_context_linker.core import ManifestError, render_index_markdown, render_project_card, validate_manifest
from ai_context_linker.state_records import make_state_record, resolve_state_records


NOW = datetime.fromisoformat("2026-08-30T12:00:00+08:00")


def _record(text: str, *, status: str = "open", supersedes: list[str] | None = None) -> dict:
    return make_state_record(
        project_id="restricted",
        kind="blocker",
        text=text,
        source_kind="approved-review",
        source_ref="restricted:approved-review:blocker",
        observed_at="2026-08-30T10:00:00+08:00",
        status=status,
        supersedes=supersedes,
    )


def _project(project_id: str, *, visibility: str = "allow", records: list[dict] | None = None) -> dict:
    return {
        "id": project_id,
        "name": project_id,
        "summary": "Approved neutral summary.",
        "status": "summary-only; detailed project context withheld by policy" if visibility == "summary-only" else "unknown",
        "sensitivity": "internal",
        "cloud_visibility": visibility,
        "redaction_profile": "standard",
        "signals": [],
        "constraints": [],
        "risks": [],
        "open_questions": [],
        "state_items": records or [],
        "evidence": [],
    }


def _manifest(projects: list[dict], relationships: list[dict] | None = None) -> dict:
    return validate_manifest(
        {
            "schema_version": "0.2",
            "generated_at": NOW.isoformat(),
            "workspace": {
                "name": "Scope fixture",
                "summary": "Synthetic policy transition.",
                "current_focus": "Unknown",
                "decisions": [],
                "unknowns": [],
            },
            "projects": projects,
            "relationships": relationships or [],
        }
    )


def _relationship() -> dict:
    return {
        "source": "restricted",
        "target": "survivor",
        "type": "blocked-by",
        "layer": "observed",
        "summary": "Synthetic approved blocker.",
        "evidence": "restricted:approved-review:blocker",
    }


def _scan_previous(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    current: dict,
    previous: dict,
    *,
    denied: bool = False,
) -> tuple[dict, dict]:
    private_before = copy.deepcopy(previous)
    project_reports = [
        {"id": project["id"], "cloud_visibility": project["cloud_visibility"]}
        for project in current["projects"]
    ]
    if denied:
        project_reports.append({"id": "restricted", "cloud_visibility": "deny"})
    monkeypatch.setattr(scanner, "collect_candidate", lambda *args, **kwargs: (copy.deepcopy(current), {"projects": project_reports}))
    monkeypatch.setattr(scanner, "load_manifest", lambda path: previous)
    paths = scanner.scan_workspace("unused.json", tmp_path / "review", previous_manifest="previous.json")
    assert previous == private_before
    return (
        json.loads(paths.candidate_manifest.read_text(encoding="utf-8")),
        json.loads(paths.changes_json.read_text(encoding="utf-8")),
    )


def test_visibility_downgrade_does_not_restore_old_detailed_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    record = _record("SYNTHETIC_DETAIL_MUST_BE_WITHHELD")
    previous = _manifest([_project("restricted", records=[record]), _project("survivor")], [_relationship()])
    current = _manifest([_project("restricted", visibility="summary-only"), _project("survivor")])

    candidate, changes = _scan_previous(monkeypatch, tmp_path, current, previous)

    restricted = next(project for project in candidate["projects"] if project["id"] == "restricted")
    assert restricted["state_items"] == []
    assert record["text"] not in render_project_card(candidate, restricted)
    assert record["record_id"] not in json.dumps(changes)
    assert changes["relationships"] == {"added": [], "removed": []}


def test_denied_project_is_withheld_from_candidate_and_publishable_changes(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    previous = _manifest([_project("restricted", records=[_record("Private synthetic detail.")]), _project("survivor")], [_relationship()])
    current = _manifest([_project("survivor")])

    candidate, changes = _scan_previous(monkeypatch, tmp_path, current, previous, denied=True)

    assert "restricted" not in json.dumps(candidate)
    assert "restricted" not in json.dumps(changes)
    assert "restricted" not in render_index_markdown(candidate)


def test_ordinary_project_removal_is_still_reported(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    previous = _manifest([_project("restricted"), _project("survivor")])
    current = _manifest([_project("survivor")])

    candidate, changes = _scan_previous(monkeypatch, tmp_path, current, previous)

    assert candidate["snapshot_changes"]["removed_projects"] == ["restricted"]
    assert changes["projects"]["removed"] == ["restricted"]


@pytest.mark.parametrize("status", ["needs_review", "resolved", "superseded", "stale"])
def test_non_open_blocker_does_not_derive_factual_relationship(status: str) -> None:
    source = _project("restricted", records=[_record("Waiting for survivor.", status=status)])

    assert scanner._derive_state_relationships([source, _project("survivor")]) == []


def test_open_blocker_still_derives_relationship() -> None:
    source = _project("restricted", records=[_record("Waiting for survivor.")])

    assert len(scanner._derive_state_relationships([source, _project("survivor")])) == 1


@pytest.mark.parametrize("previous_available", [False, True])
def test_explicit_supersedes_also_closes_record_still_in_current_input(previous_available: bool) -> None:
    old = _record("Waiting for the old dependency.")
    new = _record("Waiting for the replacement.", supersedes=[old["record_id"]])
    original = copy.deepcopy(old)

    resolved = resolve_state_records([old, new], [old] if previous_available else [], observed_at=NOW)
    by_id = {record["record_id"]: record for record in resolved}

    assert by_id[old["record_id"]]["status"] == "superseded"
    assert by_id[new["record_id"]]["status"] == "open"
    assert old == original


@pytest.mark.parametrize(
    ("source_time", "expected_freshness"),
    [("2027-01-01T00:00:00+08:00", "future-dated"), ("2025-01-01T00:00:00+08:00", "stale")],
)
def test_lifecycle_rechecks_approved_record_observation_time(source_time: str, expected_freshness: str) -> None:
    record = _record("Synthetic timing blocker.")
    record["observed_at"] = source_time

    resolved = resolve_state_records([record], [], observed_at=NOW)

    assert resolved[0]["freshness"] == expected_freshness
    assert scanner._derive_state_relationships([_project("restricted", records=resolved), _project("survivor")]) == []


@pytest.mark.parametrize("status", ["resolved", "superseded"])
def test_expiry_preserves_explicit_closed_lifecycle(status: str) -> None:
    record = _record("Closed synthetic blocker.", status=status)
    record["expires_at"] = "2026-08-30T11:00:00+08:00"

    resolved = resolve_state_records([record], [], observed_at=NOW)

    assert resolved[0]["status"] == status
    assert resolved[0]["freshness"] == "stale"


def test_future_superseding_record_cannot_close_current_blocker() -> None:
    old = _record("Waiting for the current dependency.")
    future = _record("A future replacement.", supersedes=[old["record_id"]])
    future["observed_at"] = "2027-01-01T00:00:00+08:00"

    resolved = resolve_state_records([old, future], [old], observed_at=NOW)
    by_id = {record["record_id"]: record for record in resolved}

    assert by_id[old["record_id"]]["status"] == "open"
    assert by_id[future["record_id"]]["freshness"] == "future-dated"


@pytest.mark.parametrize("reference_field", ["text", "source_ref", "evidence"])
@pytest.mark.parametrize("alias", ["restricted", "Hidden Project Name"])
def test_denied_alias_in_surviving_history_fails_without_writing_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, reference_field: str, alias: str
) -> None:
    historical_record = make_state_record(
        project_id="survivor",
        kind="blocker",
        text="Waiting for a synthetic approval.",
        source_kind="approved-review",
        source_ref="survivor:approved-review:blocker",
        observed_at="2026-08-30T10:00:00+08:00",
        status="open",
    )
    if reference_field == "text":
        historical_record["text"] = f"Waiting for {alias} approval."
    else:
        historical_record["source_ref"] = f"survivor:approved-review:{alias}"
        historical_record["evidence"] = historical_record["source_ref"]
    denied_project = _project("restricted")
    denied_project["name"] = "Hidden Project Name"
    previous = _manifest([denied_project, _project("survivor", records=[historical_record])])
    current = _manifest([_project("survivor")])

    with pytest.raises(ManifestError, match="withheld|visibility") as error:
        _scan_previous(monkeypatch, tmp_path, current, previous, denied=True)

    assert alias not in str(error.value)
    assert not (tmp_path / "review" / "candidate-manifest.json").exists()


def test_known_denied_alias_in_current_candidate_also_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    previous = _manifest([_project("restricted"), _project("survivor")])
    current = _manifest([_project("survivor")])
    current["projects"][0]["summary"] = "This project uses restricted for private processing."

    with pytest.raises(ManifestError, match="withheld|visibility"):
        _scan_previous(monkeypatch, tmp_path, current, previous, denied=True)

    assert not (tmp_path / "review" / "candidate-manifest.json").exists()


def test_summary_only_identity_reference_remains_allowed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    historical_record = make_state_record(
        project_id="survivor",
        kind="decision",
        text="Keep the restricted project separate.",
        source_kind="approved-review",
        source_ref="survivor:approved-review:decision",
        observed_at="2026-08-30T10:00:00+08:00",
        status="open",
    )
    previous = _manifest([_project("restricted"), _project("survivor", records=[historical_record])])
    current = _manifest([_project("restricted", visibility="summary-only"), _project("survivor")])

    candidate, _ = _scan_previous(monkeypatch, tmp_path, current, previous)

    survivor = next(project for project in candidate["projects"] if project["id"] == "survivor")
    assert survivor["state_items"][0]["text"] == historical_record["text"]


@pytest.mark.parametrize("previous_time", ["2026-08-30T10:00:00+08:00", "2025-01-01T00:00:00+08:00"])
def test_future_same_id_cannot_resolve_a_known_open_record(previous_time: str) -> None:
    previous = _record("Waiting for current approval.")
    previous["observed_at"] = previous_time
    future = copy.deepcopy(previous)
    future["observed_at"] = "2027-01-01T00:00:00+08:00"
    future["status"] = "resolved"

    with pytest.raises(ManifestError, match="future.*conflict|conflict.*future"):
        resolve_state_records([future], [previous], observed_at=NOW)

    assert previous["status"] == "open"
