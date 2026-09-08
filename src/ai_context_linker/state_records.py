"""Unified deterministic StateRecord construction and lifecycle resolution."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from typing import Any

from .core import ManifestError, STATE_STATUSES, STATE_SOURCE_KINDS, validate_publish_text


RECORD_ID_PATTERN = re.compile(r"^state-[0-9a-f]{16}$")


def _timestamp(raw: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(raw)
    except (TypeError, ValueError) as exc:
        raise ManifestError(f"{label} must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ManifestError(f"{label} must include a timezone")
    return parsed


def context_time(manifest: dict[str, Any], as_of: str | None = None) -> str:
    """Choose a lifecycle time without changing the source snapshot timestamp."""
    snapshot_time = manifest["generated_at"]
    if as_of is None:
        return snapshot_time
    if manifest.get("schema_version") != "0.2":
        raise ManifestError("--as-of requires a v0.2 manifest with lifecycle records")
    parsed = _timestamp(as_of, "--as-of")
    if parsed < _timestamp(snapshot_time, "manifest.generated_at"):
        raise ManifestError("--as-of must not precede the source snapshot")
    return parsed.isoformat()


def _stable_record_id(project_id: str, kind: str, source_kind: str, text: str) -> str:
    payload = json.dumps(
        {
            "project_id": project_id,
            "kind": kind,
            "source_kind": source_kind,
            "text": " ".join(text.casefold().split()),
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"state-{hashlib.sha256(payload).hexdigest()[:16]}"


def make_state_record(
    *,
    project_id: str,
    kind: str,
    text: str,
    source_kind: str,
    source_ref: str,
    observed_at: str,
    status: str,
    expires_at: str | None = None,
    record_id: str | None = None,
    supersedes: list[str] | None = None,
    source_date: str | None = None,
    freshness: str | None = None,
) -> dict[str, Any]:
    normalized_text = " ".join(text.split())
    if not normalized_text or len(normalized_text) > 500:
        raise ManifestError("StateRecord.text must contain 1 to 500 characters")
    validate_publish_text(normalized_text, "StateRecord.text")
    validate_publish_text(source_ref, "StateRecord.source_ref")
    if source_kind not in STATE_SOURCE_KINDS:
        raise ManifestError("StateRecord.source_kind is unsupported")
    if status not in STATE_STATUSES:
        raise ManifestError("StateRecord.status is unsupported")
    observed = _timestamp(observed_at, "StateRecord.observed_at")
    expiry = _timestamp(expires_at, "StateRecord.expires_at") if expires_at else None
    if expiry is not None and expiry <= observed:
        raise ManifestError("StateRecord.expires_at must be after observed_at")
    stable_id = record_id or _stable_record_id(project_id, kind, source_kind, normalized_text)
    if not RECORD_ID_PATTERN.fullmatch(stable_id):
        raise ManifestError("StateRecord.record_id must be state- followed by 16 lowercase hex characters")
    superseded_ids = sorted(set(supersedes or []))
    if any(not RECORD_ID_PATTERN.fullmatch(item) for item in superseded_ids):
        raise ManifestError("StateRecord.supersedes contains an invalid record ID")
    if stable_id in superseded_ids:
        raise ManifestError("StateRecord cannot supersede itself")
    effective_freshness = freshness or ("stale" if status == "stale" else "current")
    record: dict[str, Any] = {
        "record_id": stable_id,
        "kind": kind,
        "text": normalized_text,
        "status": status,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "observed_at": observed.isoformat(),
        "supersedes": superseded_ids,
        "freshness": effective_freshness,
        "evidence": source_ref,
        "provenance": source_kind,
    }
    if expiry is not None:
        record["expires_at"] = expiry.isoformat()
    if source_date:
        record["source_date"] = source_date
    return record


def upgrade_state_item(project_id: str, item: dict[str, Any], *, observed_at: datetime) -> dict[str, Any]:
    """Normalize a legacy adapter item into a v0.2 StateRecord."""
    source_kind = str(item.get("source_kind") or item.get("provenance") or "project-state")
    source_ref = str(item.get("source_ref") or item.get("evidence") or f"{project_id}:state:unknown")
    item_observed_at = str(item.get("observed_at") or item.get("_observed_at") or observed_at.isoformat())
    expires_at = item.get("expires_at") or item.get("_expires_at")
    status = str(
        item.get("status")
        or item.get("_status")
        or ("open" if source_kind == "approved-review" else "needs_review")
    )
    return make_state_record(
        project_id=project_id,
        kind=str(item["kind"]),
        text=str(item["text"]),
        source_kind=source_kind,
        source_ref=source_ref,
        observed_at=item_observed_at,
        expires_at=str(expires_at) if expires_at else None,
        status=status,
        record_id=str(item["record_id"]) if item.get("record_id") else None,
        supersedes=[str(value) for value in item.get("supersedes", [])],
        source_date=str(item["source_date"]) if item.get("source_date") else None,
        freshness=str(item["freshness"]) if item.get("freshness") else None,
    )


def _apply_expiry(record: dict[str, Any], observed_at: datetime) -> dict[str, Any]:
    updated = dict(record)
    source_observed = _timestamp(str(updated["observed_at"]), "StateRecord.observed_at")
    if source_observed > observed_at:
        updated["freshness"] = "future-dated"
        return updated
    if updated.get("freshness") == "future-dated":
        updated["freshness"] = "current"
    expires_at = updated.get("expires_at")
    expired = bool(expires_at and _timestamp(str(expires_at), "StateRecord.expires_at") <= observed_at)
    aged_approval = (
        updated.get("source_kind") == "approved-review"
        and (observed_at.date() - source_observed.date()).days > 45
    )
    if expired or aged_approval:
        if updated["status"] not in {"resolved", "superseded"}:
            updated["status"] = "stale"
        updated["freshness"] = "stale"
    return updated


def resolve_state_records(
    current_records: list[dict[str, Any]],
    previous_records: list[dict[str, Any]],
    *,
    observed_at: datetime,
) -> list[dict[str, Any]]:
    """Resolve current records against the approved predecessor without inferring disappearance as resolution."""
    current = [_apply_expiry(record, observed_at) for record in current_records]
    previous = [_apply_expiry(record, observed_at) for record in previous_records]
    current_by_id = {str(record["record_id"]): record for record in current}
    if len(current_by_id) != len(current):
        raise ManifestError("current StateRecords contain duplicate record_id values")
    previous_by_id = {str(record["record_id"]): record for record in previous}
    if len(previous_by_id) != len(previous):
        raise ManifestError("previous StateRecords contain duplicate record_id values")
    for record_id, record in current_by_id.items():
        old_record = previous_by_id.get(record_id)
        if (
            record.get("freshness") == "future-dated"
            and old_record is not None
            and old_record.get("freshness") != "future-dated"
        ):
            raise ManifestError("future-dated StateRecord conflicts with a known previous record; review the source timestamp")

    superseded_ids = {
        superseded
        for record in current
        if record.get("freshness") != "future-dated"
        for superseded in record.get("supersedes", [])
        if superseded in previous_by_id or superseded in current_by_id
    }
    resolved = list(current)
    for record in resolved:
        if record["record_id"] in superseded_ids:
            record["status"] = "superseded"
    for record_id, old_record in previous_by_id.items():
        if record_id in current_by_id:
            continue
        retained = dict(old_record)
        if record_id in superseded_ids:
            retained["status"] = "superseded"
        elif retained["status"] not in {"resolved", "superseded", "stale"}:
            retained["status"] = "needs_review"
        resolved.append(retained)

    status_rank = {"open": 0, "needs_review": 1, "stale": 2, "resolved": 3, "superseded": 4}
    return sorted(
        resolved,
        key=lambda record: (
            status_rank[str(record["status"])],
            str(record["kind"]),
            str(record["record_id"]),
        ),
    )
