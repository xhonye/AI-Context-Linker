"""Private, explicit action-state review adapter with v0.1 migration support."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .adapters import is_link_or_reparse
from .core import ManifestError, STATE_KINDS, validate_publish_text


MAX_REVIEW_STATE_BYTES = 64 * 1024
MAX_REVIEW_STATE_FILES = 32
MAX_BLOCKERS_PER_PROJECT = 8
PROJECT_KEYS_V02 = {
    "project_id",
    "priority",
    "activity",
    "attention",
    "why_now",
    "current_goal",
    "next_action",
    "done_when",
    "owner",
    "due_at",
    "blockers",
    "updated_at",
    "expires_at",
    "records",
}
PROJECT_KEYS_V01 = {
    "project_id",
    "status",
    "current_goal",
    "next_action",
    "blockers",
    "updated_at",
}
ACTIVITIES = {"active", "paused", "blocked", "maintaining", "inactive", "unknown"}
ATTENTION_LEVELS = {"today", "this-week", "later", "none", "unknown"}
PRIORITY_LEVELS = {"P0", "P1", "P2", "P3", "unknown"}
FIELD_ORDER = (
    ("priority", "priority"),
    ("attention", "attention"),
    ("activity", "activity"),
    ("why_now", "why-now"),
    ("current_goal", "current-goal"),
    ("blockers", "blocker"),
    ("next_action", "next-action"),
    ("done_when", "done-when"),
    ("owner", "owner"),
    ("due_at", "deadline"),
)
RECORD_KEYS = {"record_id", "kind", "text", "status", "source_ref", "observed_at", "expires_at", "supersedes"}


def _timestamp(raw: Any, label: str) -> datetime:
    if not isinstance(raw, str) or not raw.strip():
        raise ManifestError(f"{label} must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(raw.strip())
    except ValueError as exc:
        raise ManifestError(f"{label} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ManifestError(f"{label} must include a timezone")
    return parsed


def _due_at(raw: Any, label: str) -> str:
    if not isinstance(raw, str) or not raw.strip():
        raise ManifestError(f"{label} must be an ISO 8601 date or timestamp")
    value = raw.strip()
    try:
        if "T" in value:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                raise ManifestError(f"{label} timestamp must include a timezone")
        else:
            date.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError(f"{label} must be an ISO 8601 date or timestamp") from exc
    return value


def _safe_text(raw: Any, label: str) -> str:
    if not isinstance(raw, str):
        raise ManifestError(f"{label} must be a string")
    value = " ".join(raw.split())
    if not value or len(value) > 500:
        raise ManifestError(f"{label} must contain 1 to 500 characters")
    validate_publish_text(value, label)
    return value


def _freshness(updated_at: datetime, expires_at: datetime | None, observed_at: datetime) -> str:
    if updated_at > observed_at:
        return "future-dated"
    if expires_at is not None and expires_at <= observed_at:
        return "stale"
    return "current" if (observed_at.date() - updated_at.date()).days <= 45 else "stale"


def _normalize_project(raw: Any, *, schema_version: str, index: int) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ManifestError(f"review_state.projects[{index}] must be an object")
    allowed = PROJECT_KEYS_V01 if schema_version == "0.1" else PROJECT_KEYS_V02
    unknown = sorted(set(raw) - allowed)
    if unknown:
        raise ManifestError(
            f"review_state.projects[{index}] contains unsupported fields: {', '.join(unknown)}"
        )
    normalized = dict(raw)
    if schema_version == "0.1" and "status" in normalized:
        normalized["activity"] = normalized.pop("status")
    return normalized


def read_review_state(
    path: Path,
    *,
    project_ids: set[str],
    observed_at: datetime,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    """Read one explicitly supplied private review-state file and emit safe state items."""
    raw, _ = _read_review_state_payload(path)
    return _parse_review_state(raw, project_ids=project_ids, observed_at=observed_at)


def _read_review_state_payload(path: Path) -> tuple[Any, bytes]:
    """Read once so a preview's fingerprint binds exactly the validated bytes."""
    if is_link_or_reparse(path):
        raise ManifestError("review state must not be a link or reparse point")
    if path.suffix.casefold() != ".json" or not path.is_file():
        raise ManifestError("review state must be an existing JSON file")
    if path.stat().st_size > MAX_REVIEW_STATE_BYTES:
        raise ManifestError(f"review state exceeds the {MAX_REVIEW_STATE_BYTES} byte limit")
    with path.open("rb") as handle:
        content = handle.read(MAX_REVIEW_STATE_BYTES + 1)
    if len(content) > MAX_REVIEW_STATE_BYTES:
        raise ManifestError(f"review state exceeds the {MAX_REVIEW_STATE_BYTES} byte limit")
    try:
        raw = json.loads(content.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("review state must be valid UTF-8 JSON") from exc
    return raw, content


def _parse_review_state(
    raw: Any,
    *,
    project_ids: set[str],
    observed_at: datetime,
) -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    """Share adapter validation with private previews; parsing records no approval."""
    if not isinstance(raw, dict):
        raise ManifestError("review state must be an object")
    unknown = sorted(set(raw) - {"schema_version", "projects"})
    if unknown:
        raise ManifestError(f"review state contains unsupported fields: {', '.join(unknown)}")
    schema_version = raw.get("schema_version")
    if schema_version not in {"0.1", "0.2"}:
        raise ManifestError("review state schema_version must be 0.1 or 0.2")
    projects = raw.get("projects")
    if not isinstance(projects, list):
        raise ManifestError("review_state.projects must be an array")

    output: dict[str, list[dict[str, str]]] = {}
    for index, raw_project in enumerate(projects):
        project = _normalize_project(raw_project, schema_version=schema_version, index=index)
        project_id = project.get("project_id")
        if not isinstance(project_id, str) or project_id not in project_ids:
            raise ManifestError(f"review_state.projects[{index}].project_id must name an approved project")
        if project_id in output:
            raise ManifestError(f"review state contains duplicate project_id: {project_id}")
        updated_at = _timestamp(project.get("updated_at"), f"review_state.projects[{index}].updated_at")
        expires_at = (
            _timestamp(project["expires_at"], f"review_state.projects[{index}].expires_at")
            if "expires_at" in project
            else None
        )
        if expires_at is not None and expires_at <= updated_at:
            raise ManifestError(f"review_state.projects[{index}].expires_at must be after updated_at")
        freshness = _freshness(updated_at, expires_at, observed_at)
        activity = project.get("activity")
        if activity is not None and (not isinstance(activity, str) or activity not in ACTIVITIES):
            raise ManifestError(f"review_state.projects[{index}].activity is unsupported")
        attention = project.get("attention")
        if attention is not None and (not isinstance(attention, str) or attention not in ATTENTION_LEVELS):
            raise ManifestError(f"review_state.projects[{index}].attention is unsupported")
        priority = project.get("priority")
        if priority is not None and (not isinstance(priority, str) or priority not in PRIORITY_LEVELS):
            raise ManifestError(f"review_state.projects[{index}].priority is unsupported")
        blockers = project.get("blockers", [])
        if not isinstance(blockers, list) or len(blockers) > MAX_BLOCKERS_PER_PROJECT:
            raise ManifestError(
                f"review_state.projects[{index}].blockers must be an array with at most {MAX_BLOCKERS_PER_PROJECT} items"
            )

        items: list[dict[str, str]] = []
        for field, kind in FIELD_ORDER:
            values = blockers if field == "blockers" else ([project[field]] if field in project else [])
            for value_index, raw_value in enumerate(values):
                label = f"review_state.projects[{index}].{field}"
                if field == "blockers":
                    label += f"[{value_index}]"
                if field == "due_at":
                    text = _due_at(raw_value, label)
                elif field in {"priority", "activity", "attention"}:
                    text = str(raw_value)
                else:
                    text = _safe_text(raw_value, label)
                item = {
                    "kind": kind,
                    "text": text,
                    "source_date": updated_at.date().isoformat(),
                    "freshness": freshness,
                    "evidence": f"{project_id}:approved-review:{field}",
                    "provenance": "approved-review",
                    "_observed_at": updated_at.isoformat(),
                    "_status": "stale" if freshness == "stale" else "open",
                }
                if expires_at is not None:
                    item["_expires_at"] = expires_at.isoformat()
                items.append(item)
        records = project.get("records", [])
        if not isinstance(records, list):
            raise ManifestError(f"review_state.projects[{index}].records must be an array")
        from .state_records import make_state_record

        for record_index, raw_record in enumerate(records):
            if not isinstance(raw_record, dict):
                raise ManifestError(f"review_state.projects[{index}].records[{record_index}] must be an object")
            record_unknown = sorted(set(raw_record) - RECORD_KEYS)
            if record_unknown:
                raise ManifestError(
                    f"review_state.projects[{index}].records[{record_index}] contains unsupported fields: {', '.join(record_unknown)}"
                )
            record_observed = (
                _timestamp(
                    raw_record["observed_at"],
                    f"review_state.projects[{index}].records[{record_index}].observed_at",
                )
                if "observed_at" in raw_record
                else updated_at
            )
            record_expiry = (
                _timestamp(
                    raw_record["expires_at"],
                    f"review_state.projects[{index}].records[{record_index}].expires_at",
                )
                if "expires_at" in raw_record
                else expires_at
            )
            record_status = raw_record.get("status", "open")
            if not isinstance(record_status, str):
                raise ManifestError(f"review_state.projects[{index}].records[{record_index}].status must be a string")
            record_kind = raw_record.get("kind")
            if not isinstance(record_kind, str) or record_kind not in STATE_KINDS:
                raise ManifestError(f"review_state.projects[{index}].records[{record_index}].kind is unsupported")
            record_text = _safe_text(
                raw_record.get("text"), f"review_state.projects[{index}].records[{record_index}].text"
            )
            source_ref = raw_record.get("source_ref", f"{project_id}:approved-review:records:{record_index + 1}")
            if not isinstance(source_ref, str):
                raise ManifestError(
                    f"review_state.projects[{index}].records[{record_index}].source_ref must be a string"
                )
            supersedes = raw_record.get("supersedes", [])
            if not isinstance(supersedes, list) or any(not isinstance(value, str) for value in supersedes):
                raise ManifestError(
                    f"review_state.projects[{index}].records[{record_index}].supersedes must be an array of record IDs"
                )
            items.append(
                make_state_record(
                    project_id=project_id,
                    kind=record_kind,
                    text=record_text,
                    source_kind="approved-review",
                    source_ref=source_ref,
                    observed_at=record_observed.isoformat(),
                    expires_at=record_expiry.isoformat() if record_expiry else None,
                    status=record_status,
                    record_id=raw_record.get("record_id"),
                    supersedes=supersedes,
                    freshness=_freshness(record_observed, record_expiry, observed_at),
                )
            )
        output[project_id] = items

    return output, {
        "input_schema_version": schema_version,
        "normalized_schema_version": "0.2",
        "projects_approved": len(output),
        "state_items_added": sum(len(items) for items in output.values()),
    }
