"""Strict neutral session-summary adapter; never discovers or reads raw transcripts."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any

from .adapters import is_link_or_reparse
from .core import ManifestError, validate_publish_text, validate_skill_summary


MAX_SESSION_SUMMARY_BYTES = 64 * 1024
MAX_ITEMS_PER_FIELD = 8
MAX_SESSION_SUMMARY_FILES = 32
MAX_SESSION_ITEMS_PER_PROJECT = 24
SUMMARY_KEYS = {
    "schema_version",
    "project_id",
    "session_date",
    "completed_work",
    "decisions",
    "blockers",
    "next_actions",
    "unresolved_questions",
}
ITEM_KEYS = {"text", "evidence"}
STATE_FIELDS = {
    "completed_work": "completed",
    "decisions": "decision",
    "blockers": "blocker",
    "next_actions": "next-action",
}


def _freshness(session_date: date, observed_at: datetime) -> str:
    age_days = (observed_at.date() - session_date).days
    if age_days < 0:
        return "future-dated"
    return "current" if age_days <= 14 else "stale"


def _safe_evidence(raw: str, *, project_id: str, fallback: str) -> str:
    candidate = Path(raw)
    if candidate.is_absolute() or ".." in candidate.parts or not candidate.parts:
        raise ManifestError("session summary evidence must be a project-relative reference")
    normalized = candidate.as_posix()
    validate_publish_text(normalized, "session summary evidence")
    return f"{project_id}:file:{normalized}" if normalized else fallback


def _items(raw: Any, *, label: str, project_id: str, session_date: str) -> list[dict[str, str]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ManifestError(f"{label} must be an array")
    if len(raw) > MAX_ITEMS_PER_FIELD:
        raise ManifestError(f"{label} exceeds the {MAX_ITEMS_PER_FIELD} item limit")
    output: list[dict[str, str]] = []
    for index, value in enumerate(raw):
        fallback = f"{project_id}:session-summary:{session_date}:{label}:{index + 1}"
        if isinstance(value, str):
            text = value.strip()
            evidence = fallback
        elif isinstance(value, dict):
            unknown = sorted(set(value) - ITEM_KEYS)
            if unknown:
                raise ManifestError(f"{label}[{index}] contains unsupported fields: {', '.join(unknown)}")
            text = value.get("text", "")
            if not isinstance(text, str):
                raise ManifestError(f"{label}[{index}].text must be a string")
            text = text.strip()
            raw_evidence = value.get("evidence")
            if raw_evidence is not None and not isinstance(raw_evidence, str):
                raise ManifestError(f"{label}[{index}].evidence must be a string")
            evidence = _safe_evidence(raw_evidence, project_id=project_id, fallback=fallback) if raw_evidence else fallback
        else:
            raise ManifestError(f"{label}[{index}] must be a string or object")
        if not text or len(text) > 500:
            raise ManifestError(f"{label}[{index}].text must contain 1 to 500 characters")
        validate_skill_summary(text, f"{label}[{index}].text")
        output.append({"text": text, "evidence": evidence})
    return output


def read_session_summary(
    path: Path,
    *,
    project_ids: set[str],
    observed_at: datetime,
) -> tuple[str, list[dict[str, str]], list[str]]:
    if is_link_or_reparse(path):
        raise ManifestError("session summary must not be a link or reparse point")
    if path.suffix.casefold() != ".json" or not path.is_file():
        raise ManifestError("session summary must be an existing JSON file")
    if path.stat().st_size > MAX_SESSION_SUMMARY_BYTES:
        raise ManifestError(f"session summary exceeds the {MAX_SESSION_SUMMARY_BYTES} byte limit")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("session summary must be valid UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise ManifestError("session summary must be an object")
    unknown = sorted(set(raw) - SUMMARY_KEYS)
    if unknown:
        raise ManifestError(f"session summary contains unsupported fields: {', '.join(unknown)}")
    if raw.get("schema_version") != "0.1":
        raise ManifestError("session summary schema_version must be 0.1")
    project_id = raw.get("project_id")
    if not isinstance(project_id, str) or project_id not in project_ids:
        raise ManifestError("session summary project_id must name an approved project")
    raw_date = raw.get("session_date")
    if not isinstance(raw_date, str):
        raise ManifestError("session summary session_date must be YYYY-MM-DD")
    try:
        parsed_date = date.fromisoformat(raw_date)
    except ValueError as exc:
        raise ManifestError("session summary session_date must be YYYY-MM-DD") from exc
    freshness = _freshness(parsed_date, observed_at)
    state_items: list[dict[str, str]] = []
    for field, kind in STATE_FIELDS.items():
        for item in _items(raw.get(field), label=field, project_id=project_id, session_date=raw_date):
            state_items.append(
                {
                    "kind": kind,
                    "text": item["text"],
                    "source_date": raw_date,
                    "freshness": freshness,
                    "evidence": item["evidence"],
                    "provenance": "session-summary",
                }
            )
    questions = [
        f"Session-reported unresolved question: {item['text']}"
        for item in _items(
            raw.get("unresolved_questions"),
            label="unresolved_questions",
            project_id=project_id,
            session_date=raw_date,
        )
    ]
    return project_id, state_items, questions
