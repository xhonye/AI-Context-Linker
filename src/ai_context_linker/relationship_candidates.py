"""Private relationship candidate intake; candidates never become formal facts automatically."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .adapters import is_link_or_reparse
from .core import ManifestError, SEMANTIC_RELATIONSHIP_TYPES, validate_publish_text


MAX_RELATIONSHIP_CANDIDATE_BYTES = 64 * 1024
MAX_RELATIONSHIP_CANDIDATE_FILES = 32
MAX_RELATIONSHIP_CANDIDATES = 64
CANDIDATE_KEYS = {"candidate_id", "source", "target", "type", "summary"}


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label} must be a non-empty string")
    normalized = value.strip()
    if (
        len(normalized) > 63
        or not normalized[0].isalnum()
        or not normalized.replace("-", "").isalnum()
        or normalized.casefold() != normalized
    ):
        raise ManifestError(f"{label} must use lowercase letters, numbers, and hyphens")
    return normalized


def read_relationship_candidates(path: Path, *, project_ids: set[str]) -> list[dict[str, str]]:
    """Read a bounded private AI proposal file into a review-only queue."""
    if is_link_or_reparse(path):
        raise ManifestError("relationship candidate file must not be a link or reparse point")
    if path.suffix.casefold() != ".json" or not path.is_file():
        raise ManifestError("relationship candidate file must be an existing JSON file")
    if path.stat().st_size > MAX_RELATIONSHIP_CANDIDATE_BYTES:
        raise ManifestError("relationship candidate file exceeds the size limit")
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("relationship candidate file must be valid UTF-8 JSON") from exc
    if not isinstance(raw, dict) or set(raw) - {"schema_version", "candidates"}:
        raise ManifestError("relationship candidate file contains unsupported fields")
    if raw.get("schema_version") != "0.2" or not isinstance(raw.get("candidates"), list):
        raise ManifestError("relationship candidate file must use schema 0.2 with a candidates array")
    if len(raw["candidates"]) > MAX_RELATIONSHIP_CANDIDATES:
        raise ManifestError("relationship candidate file exceeds the candidate limit")
    output: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, item in enumerate(raw["candidates"]):
        if not isinstance(item, dict) or set(item) != CANDIDATE_KEYS:
            raise ManifestError(f"relationship candidates[{index}] must contain exactly the approved fields")
        candidate_id = _identifier(item["candidate_id"], f"relationship candidates[{index}].candidate_id")
        if candidate_id in seen:
            raise ManifestError(f"duplicate relationship candidate_id: {candidate_id}")
        seen.add(candidate_id)
        source = _identifier(item["source"], f"relationship candidates[{index}].source")
        target = _identifier(item["target"], f"relationship candidates[{index}].target")
        relationship_type = _identifier(item["type"], f"relationship candidates[{index}].type")
        if source not in project_ids or target not in project_ids or source == target:
            raise ManifestError(f"relationship candidates[{index}] must connect two approved projects")
        if relationship_type not in SEMANTIC_RELATIONSHIP_TYPES:
            raise ManifestError(f"relationship candidates[{index}].type must be semantic")
        summary = item["summary"]
        if not isinstance(summary, str):
            raise ManifestError(f"relationship candidates[{index}].summary must be a string")
        summary = " ".join(summary.split())
        if not summary or len(summary) > 500:
            raise ManifestError(f"relationship candidates[{index}].summary must contain 1 to 500 characters")
        validate_publish_text(summary, f"relationship candidates[{index}].summary")
        output.append(
            {
                "candidate_id": candidate_id,
                "source": source,
                "target": target,
                "type": relationship_type,
                "layer": "ai-candidate",
                "summary": summary,
                "evidence": f"ai-candidate:{candidate_id}",
            }
        )
    return sorted(output, key=lambda item: (item["source"], item["target"], item["type"], item["candidate_id"]))


def candidate_queue(candidates: list[dict[str, str]]) -> dict[str, Any]:
    payload: dict[str, Any] = {"schema_version": "0.2", "requires_human_approval": True, "candidates": candidates}
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    payload["queue_sha256"] = hashlib.sha256(encoded).hexdigest()
    return payload
