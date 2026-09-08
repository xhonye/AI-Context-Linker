"""Offline, anonymous two-order diagnostic auditing; never a replacement gate.

Hashes bind local files to a frozen input declaration, not to an authenticated
model invocation. The helper cannot prove when a judge ran or establish truth.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from .adapters import is_link_or_reparse
from .core import ManifestError, _atomic_write_text, validate_publish_text


MAX_BYTES = 2 * 1024 * 1024
QUESTIONS = tuple(f"Q{index}" for index in range(1, 7))
CONDITIONS = ("A", "B")
ORDERS = ("order-ab", "order-ba")
SCOPE = "local-subagent-diagnostic"


def _canonical(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _keys(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ManifestError(f"{label} must contain exactly the required fields")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label} must be a nonempty string")
    return value


def _bounded(value: bytes, label: str) -> bytes:
    if len(value) > MAX_BYTES:
        raise ManifestError(f"{label} exceeds the {MAX_BYTES} byte limit")
    return value


def _checked_path(value: Path | str, label: str) -> Path:
    try:
        path = Path(value).absolute()
        if ".." in path.parts:
            raise ManifestError(f"{label} must stay inside its declared directory")
        for candidate in (path, *path.parents):
            if (candidate.exists() or candidate.is_symlink()) and is_link_or_reparse(candidate):
                raise ManifestError(f"{label} must not contain a link or reparse point")
        return path.resolve()
    except OSError as exc:
        raise ManifestError(f"{label} cannot be safely inspected") from exc


def _read_bytes(path: Path, label: str) -> bytes:
    checked = _checked_path(path, label)
    try:
        if not checked.is_file():
            raise ManifestError(f"{label} must be an existing regular file")
        if checked.stat().st_size > MAX_BYTES:
            raise ManifestError(f"{label} exceeds the {MAX_BYTES} byte limit")
        with checked.open("rb") as handle:
            return _bounded(handle.read(MAX_BYTES + 1), label)
    except OSError as exc:
        raise ManifestError(f"{label} cannot be read") from exc


def _json_bytes(value: bytes, label: str) -> Any:
    def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, item in pairs:
            if key in result:
                raise ManifestError(f"{label} contains duplicate JSON fields")
            result[key] = item
        return result

    try:
        return json.loads(value.decode("utf-8"), object_pairs_hook=unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError(f"{label} must be valid UTF-8 JSON") from exc


def _protocol(value: Any) -> dict[str, Any]:
    protocol = _keys(value, {"questions", "dimensions", "rubric"}, "protocol")
    questions = _keys(protocol["questions"], set(QUESTIONS), "protocol questions Q1-Q6")
    normalized_questions = {question: _text(questions[question], "protocol question") for question in QUESTIONS}
    dimensions = protocol["dimensions"]
    if (
        not isinstance(dimensions, list)
        or not dimensions
        or any(not isinstance(item, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", item) for item in dimensions)
        or len(set(dimensions)) != len(dimensions)
    ):
        raise ManifestError("protocol dimensions must be unique nonempty identifiers")
    rubric = _keys(protocol["rubric"], {str(score) for score in range(5)}, "protocol rubric 0-4")
    normalized_rubric = {str(score): _text(rubric[str(score)], "protocol rubric label") for score in range(5)}
    normalized = {"questions": normalized_questions, "dimensions": list(dimensions), "rubric": normalized_rubric}
    encoded = _bounded(_canonical(normalized), "protocol")
    validate_publish_text(encoded.decode("utf-8"), "protocol")
    return normalized


def freeze_blind_run(output_dir: Path | str, *, protocol: dict, conditions: dict[str, str]) -> Path:
    """Write a new immutable-by-convention input directory; never overwrite one."""
    destination = _checked_path(output_dir, "output directory")
    if destination.exists():
        raise ManifestError("output directory already exists; frozen inputs cannot be overwritten")
    normalized = _protocol(protocol)
    contexts = _keys(conditions, set(CONDITIONS), "conditions A/B")
    context_bytes: dict[str, bytes] = {}
    for condition in CONDITIONS:
        text = _text(contexts[condition], "condition context")
        context_bytes[condition] = _bounded(text.encode("utf-8"), "condition context")
        validate_publish_text(text, "condition context")
    protocol_bytes = _canonical(normalized)
    frozen = {
        "schema_version": "0.1",
        "scope": SCOPE,
        "protocol_sha256": _sha256(protocol_bytes),
        "context_sha256": {condition: _sha256(context_bytes[condition]) for condition in CONDITIONS},
    }
    try:
        destination.mkdir(parents=True, exist_ok=False)
    except FileExistsError as exc:
        raise ManifestError("output directory already exists; frozen inputs cannot be overwritten") from exc
    except OSError as exc:
        raise ManifestError("output directory cannot be created") from exc
    _atomic_write_text(destination / "protocol.json", protocol_bytes.decode("utf-8"))
    for condition in CONDITIONS:
        _atomic_write_text(destination / f"condition-{condition.lower()}.md", context_bytes[condition].decode("utf-8"))
    index = destination / "frozen-inputs.json"
    _atomic_write_text(index, _canonical(frozen).decode("utf-8"))
    return index


def _frozen_inputs(run_dir: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    index_bytes = _read_bytes(run_dir / "frozen-inputs.json", "frozen input index")
    index = _keys(
        _json_bytes(index_bytes, "frozen input index"),
        {"schema_version", "scope", "protocol_sha256", "context_sha256"},
        "frozen input index",
    )
    if index["schema_version"] != "0.1" or index["scope"] != SCOPE:
        raise ManifestError("frozen input index has an unsupported schema or scope")
    context_hashes = _keys(index["context_sha256"], set(CONDITIONS), "frozen context hashes")
    for digest in [index["protocol_sha256"], *context_hashes.values()]:
        if not isinstance(digest, str) or not re.fullmatch(r"[a-f0-9]{64}", digest):
            raise ManifestError("frozen input hash must be a lowercase SHA-256 digest")
    protocol_bytes = _read_bytes(run_dir / "protocol.json", "frozen protocol")
    if _sha256(protocol_bytes) != index["protocol_sha256"]:
        raise ManifestError("frozen protocol hash mismatch")
    protocol = _protocol(_json_bytes(protocol_bytes, "frozen protocol"))
    if protocol_bytes != _canonical(protocol):
        raise ManifestError("frozen protocol bytes must be canonical")
    for condition in CONDITIONS:
        encoded = _read_bytes(run_dir / f"condition-{condition.lower()}.md", "frozen context")
        if _sha256(encoded) != context_hashes[condition]:
            raise ManifestError("frozen context hash mismatch")
        try:
            text = encoded.decode("utf-8")
        except UnicodeError as exc:
            raise ManifestError("frozen context must be valid UTF-8") from exc
        validate_publish_text(_text(text, "frozen context"), "frozen context")
    return protocol, {
        "frozen_inputs": _sha256(index_bytes),
        "protocol": index["protocol_sha256"],
        "conditions": dict(context_hashes),
    }


def _response(value: Any, dimensions: list[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or "conditions" not in value or set(value) - {"conditions", "winner_q6", "limitations"}:
        raise ManifestError("response must contain conditions and only optional winner_q6/limitations")
    conditions = _keys(value["conditions"], set(CONDITIONS), "response conditions A/B")
    normalized: dict[str, Any] = {"conditions": {}}
    for condition in CONDITIONS:
        questions = _keys(conditions[condition], set(QUESTIONS), "response questions Q1-Q6")
        normalized["conditions"][condition] = {}
        for question in QUESTIONS:
            entry = _keys(questions[question], {"answer", "scores", "failures"}, "response question")
            if not isinstance(entry["answer"], str):
                raise ManifestError("response answer must be a string")
            scores = _keys(entry["scores"], set(dimensions), "response dimension scores")
            if any(type(score) is not int or not 0 <= score <= 4 for score in scores.values()):
                raise ManifestError("response score must be an integer from 0 to 4")
            failures = entry["failures"]
            if not isinstance(failures, list) or any(not isinstance(item, str) for item in failures):
                raise ManifestError("response failures must be a list of strings")
            normalized["conditions"][condition][question] = {
                "scores": {dimension: scores[dimension] for dimension in dimensions},
                "failure_count": len(failures),
            }
    winner = value.get("winner_q6", "unknown")
    if isinstance(winner, dict):
        if "condition" not in winner or set(winner) - {"condition", "reason", "confidence"}:
            raise ManifestError("response winner_q6 object requires condition and only optional reason/confidence")
        if any(not isinstance(winner[key], str) for key in ("reason", "confidence") if key in winner):
            raise ManifestError("response winner_q6 reason/confidence must be strings")
        winner = winner["condition"]
    if not isinstance(winner, str) or winner not in {"A", "B", "tie", "unknown"}:
        raise ManifestError("response winner_q6 must be A, B, tie, or unknown")
    limitations = value.get("limitations", [])
    if not isinstance(limitations, list) or any(not isinstance(item, str) for item in limitations):
        raise ManifestError("response limitations must be a list of strings")
    normalized["winner_q6"] = winner
    normalized["limitation_count"] = len(limitations)
    return normalized


def evaluate_blind_run(run_dir: Path | str, *, responses: dict[str, Path]) -> dict[str, Any]:
    """Audit exact frozen bytes and two local response files; return no raw prose."""
    directory = _checked_path(run_dir, "run directory")
    if not directory.is_dir():
        raise ManifestError("run directory must exist")
    response_paths = _keys(responses, set(ORDERS), "response orders")
    checked_paths: dict[str, Path] = {}
    for order in ORDERS:
        path = _checked_path(response_paths[order], "response file")
        if not path.is_relative_to(directory) or path.suffix.lower() != ".json":
            raise ManifestError("response JSON files must stay inside the run directory")
        checked_paths[order] = path
    if checked_paths[ORDERS[0]] == checked_paths[ORDERS[1]]:
        raise ManifestError("response orders must use distinct files")
    try:
        if checked_paths[ORDERS[0]].samefile(checked_paths[ORDERS[1]]):
            raise ManifestError("response orders must use distinct files")
    except OSError as exc:
        raise ManifestError("response files cannot be safely inspected") from exc
    protocol, input_hashes = _frozen_inputs(directory)
    normalized: dict[str, dict[str, Any]] = {}
    answer_hashes: dict[str, str] = {}
    answer_bytes: dict[str, int] = {}
    for order in ORDERS:
        encoded = _read_bytes(checked_paths[order], "response file")
        answer_hashes[order] = _sha256(encoded)
        answer_bytes[order] = len(encoded)
        normalized[order] = _response(_json_bytes(encoded, "response file"), protocol["dimensions"])
    if len(set(answer_hashes.values())) != len(ORDERS):
        raise ManifestError("response orders contain identical raw bytes; duplicate replay is not independent evidence")
    questions: dict[str, Any] = {}
    for question in QUESTIONS:
        scores = {
            order: {condition: normalized[order]["conditions"][condition][question]["scores"] for condition in CONDITIONS}
            for order in ORDERS
        }
        failures = {
            order: {condition: normalized[order]["conditions"][condition][question]["failure_count"] for condition in CONDITIONS}
            for order in ORDERS
        }
        questions[question] = {
            "scores_by_order": scores,
            "failure_counts_by_order": failures,
            "order_disagreement": scores[ORDERS[0]] != scores[ORDERS[1]] or failures[ORDERS[0]] != failures[ORDERS[1]],
        }
    winners = {order: normalized[order]["winner_q6"] for order in ORDERS}
    return {
        "schema_version": "0.1",
        "scope": SCOPE,
        "replacement_ready": False,
        "both_orders_present": True,
        "model_settings_verified": False,
        "origin_verified": False,
        "truth_verified": False,
        "input_sha256": input_hashes,
        "answer_sha256": answer_hashes,
        "answer_bytes": answer_bytes,
        "questions": questions,
        "winner_q6_by_order": winners,
        "winner_q6_disagreement": winners[ORDERS[0]] != winners[ORDERS[1]],
        "limitation_counts_by_order": {order: normalized[order]["limitation_count"] for order in ORDERS},
    }
