"""Explicit private approval history for reviewed context manifests."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import ManifestError, _atomic_write_text, _check_output_path, load_manifest, validate_manifest


SYNC_DIRECTORY_MARKERS = {"dropbox", "google drive", "googledrive", "icloud", "onedrive"}


@dataclass(frozen=True)
class ApprovedSnapshotPaths:
    history: Path
    latest: Path


def _approved_at(raw: str | None) -> datetime:
    value = raw or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ManifestError("approved_at must be an ISO 8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ManifestError("approved_at must include a timezone")
    return parsed


def approve_snapshot(
    manifest_path: Path | str,
    history_dir: Path | str,
    *,
    approved_at: str | None = None,
) -> ApprovedSnapshotPaths:
    manifest = load_manifest(manifest_path)
    if not manifest.get("facts_sha256"):
        raise ManifestError("approved snapshot manifest must contain a verified facts_sha256")
    approved = _approved_at(approved_at)
    _check_output_path(Path(history_dir))
    destination = Path(history_dir).resolve()
    if any(marker in part.casefold() for part in destination.parts for marker in SYNC_DIRECTORY_MARKERS):
        raise ManifestError("approved snapshot history must remain outside cloud-synced directories")
    wrapper: dict[str, Any] = {
        "schema_version": "0.2",
        "approved_at": approved.isoformat(),
        "facts_sha256": manifest["facts_sha256"],
        "manifest": manifest,
    }
    canonical = json.dumps(wrapper, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    wrapper["approval_sha256"] = hashlib.sha256(canonical).hexdigest()
    content = json.dumps(wrapper, ensure_ascii=False, indent=2) + "\n"
    stamp = approved.strftime("%Y%m%dT%H%M%S%z")
    history = destination / f"approved-snapshot-{stamp}-{manifest['facts_sha256'][:12]}.json"
    latest = destination / "approved-snapshot-latest.json"
    if history.exists():
        if history.read_text(encoding="utf-8") != content:
            raise ManifestError("approved snapshot history entry already exists with different content")
    else:
        _atomic_write_text(history, content)
    _atomic_write_text(latest, content)
    return ApprovedSnapshotPaths(history=history, latest=latest)


def load_approved_snapshot(path: Path | str) -> dict[str, Any]:
    snapshot_path = Path(path)
    try:
        raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("approved snapshot must be valid UTF-8 JSON") from exc
    if not isinstance(raw, dict):
        raise ManifestError("approved snapshot must be an object")
    unknown = sorted(set(raw) - {"schema_version", "approved_at", "facts_sha256", "approval_sha256", "manifest"})
    if unknown:
        raise ManifestError(f"approved snapshot contains unsupported fields: {', '.join(unknown)}")
    if raw.get("schema_version") != "0.2":
        raise ManifestError("approved snapshot schema_version must be 0.2")
    manifest = raw.get("manifest")
    if not isinstance(manifest, dict):
        raise ManifestError("approved snapshot manifest must be an object")
    normalized = validate_manifest(manifest)
    if raw.get("facts_sha256") != normalized.get("facts_sha256"):
        raise ManifestError("approved snapshot facts_sha256 does not match its manifest")
    payload = {key: value for key, value in raw.items() if key != "approval_sha256"}
    expected = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    if raw.get("approval_sha256") != expected:
        raise ManifestError("approved snapshot approval_sha256 does not match its contents")
    return {**raw, "manifest": normalized}
