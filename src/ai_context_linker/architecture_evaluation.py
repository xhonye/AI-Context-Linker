"""Synthetic gold evaluation for the opt-in Architecture Index."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .architecture_index import collect_architecture_index
from .core import ManifestError, _atomic_write_text, validate_publish_text


@dataclass(frozen=True)
class ArchitectureEvaluationPaths:
    json: Path
    markdown: Path


def _string_set(value: Any, label: str) -> set[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
        raise ManifestError(f"{label} must be an array of non-empty strings")
    return set(value)


def _load_expected(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("architecture gold expectations must be valid UTF-8 JSON") from exc
    if not isinstance(raw, dict) or set(raw) != {
        "schema_version",
        "project_id",
        "mode",
        "modules",
        "symbols",
        "test_modules",
        "internal_calls",
        "forbidden_output_tokens",
    }:
        raise ManifestError("architecture gold expectations contain unsupported fields")
    if raw["schema_version"] != "0.2":
        raise ManifestError("architecture gold schema_version must be 0.2")
    if raw["mode"] not in {"modules-only", "modules-symbols"}:
        raise ManifestError("architecture gold mode is unsupported")
    if not isinstance(raw["project_id"], str) or not raw["project_id"]:
        raise ManifestError("architecture gold project_id must be a non-empty string")
    for field in ("modules", "symbols", "test_modules", "internal_calls", "forbidden_output_tokens"):
        _string_set(raw[field], f"architecture gold {field}")
    return raw


def _precision_recall(actual: set[str], expected: set[str]) -> dict[str, float | int]:
    true_positive = len(actual & expected)
    precision = true_positive / len(actual) if actual else (1.0 if not expected else 0.0)
    recall = true_positive / len(expected) if expected else 1.0
    return {
        "actual": len(actual),
        "expected": len(expected),
        "true_positive": true_positive,
        "precision": round(precision, 6),
        "recall": round(recall, 6),
    }


def evaluate_architecture_fixture(
    fixture_dir: Path | str,
    expected_path: Path | str,
) -> dict[str, Any]:
    fixture = Path(fixture_dir).resolve()
    expected = _load_expected(Path(expected_path).resolve())
    first, first_scan = collect_architecture_index(
        fixture,
        project_id=expected["project_id"],
        mode=expected["mode"],
    )
    second, _ = collect_architecture_index(
        fixture,
        project_id=expected["project_id"],
        mode=expected["mode"],
    )
    actual_modules = {module["id"] for module in first["modules"]}
    actual_symbols = {
        f"{module['id']}::{symbol}"
        for module in first["modules"]
        for symbol in module.get("symbols", [])
    }
    actual_tests = {module["id"] for module in first["modules"] if module["test_module"]}
    actual_calls = {
        f"{module['id']}->{call}"
        for module in first["modules"]
        for call in module.get("internal_calls", [])
    }
    metrics = {
        "modules": _precision_recall(actual_modules, _string_set(expected["modules"], "modules")),
        "symbols": _precision_recall(actual_symbols, _string_set(expected["symbols"], "symbols")),
        "test_modules": _precision_recall(
            actual_tests, _string_set(expected["test_modules"], "test_modules")
        ),
        "internal_calls": _precision_recall(
            actual_calls, _string_set(expected["internal_calls"], "internal_calls")
        ),
    }
    serialized = json.dumps(first, ensure_ascii=False, sort_keys=True)
    forbidden_hits = sum(token in serialized for token in expected["forbidden_output_tokens"])
    try:
        validate_publish_text(serialized, "architecture gold output")
    except ManifestError:
        forbidden_hits += 1
    evidence_coverage = (
        sum(bool(module.get("evidence")) for module in first["modules"]) / len(first["modules"])
        if first["modules"]
        else 1.0
    )
    gates = {
        "module_recall_at_least_95": metrics["modules"]["recall"] >= 0.95,
        "symbol_recall_at_least_95": metrics["symbols"]["recall"] >= 0.95,
        "test_module_recall_100": metrics["test_modules"]["recall"] == 1.0,
        "internal_call_precision_at_least_95": metrics["internal_calls"]["precision"] >= 0.95,
        "structural_evidence_coverage_100": evidence_coverage == 1.0,
        "configured_privacy_leaks_zero": forbidden_hits == 0,
        "source_bodies_published_zero": first_scan["source_bodies_published"] == 0,
        "deterministic_output_100": first == second,
    }
    report = {
        "schema_version": "0.2",
        "suite": "architecture-index",
        "metrics": metrics,
        "evidence_coverage": round(evidence_coverage, 6),
        "configured_privacy_leaks": forbidden_hits,
        "parse_failures": first["parse_failures"],
        "truncated": first["truncated"],
        "map_sha256": first["map_sha256"],
        "gates": gates,
        "all_gates_pass": all(gates.values()),
    }
    validate_publish_text(json.dumps(report, ensure_ascii=False), "architecture gold report")
    return report


def render_architecture_evaluation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI Context Linker Architecture Index synthetic gold evaluation",
        "",
        f"- Result: {'ALL GATES PASS' if report['all_gates_pass'] else 'GATE FAILURE'}",
        f"- Map: `{report['map_sha256']}`",
        f"- Parse failures: {report['parse_failures']}",
        f"- Truncated: {report['truncated']}",
        "",
        "## Metrics",
        "",
    ]
    for name, metric in report["metrics"].items():
        lines.append(
            f"- {name}: precision={metric['precision']:.3f}; recall={metric['recall']:.3f}; "
            f"tp={metric['true_positive']}/{metric['expected']}"
        )
    lines.extend(["", "## Gates", ""])
    for name, passed in report["gates"].items():
        lines.append(f"- {'PASS' if passed else 'FAIL'} · {name}")
    lines.append("")
    rendered = "\n".join(lines)
    validate_publish_text(rendered, "architecture gold Markdown")
    return rendered


def build_architecture_evaluation_report(
    fixture_dir: Path | str,
    expected_path: Path | str,
    output_dir: Path | str,
) -> ArchitectureEvaluationPaths:
    report = evaluate_architecture_fixture(fixture_dir, expected_path)
    destination = Path(output_dir).resolve()
    json_path = destination / "architecture-evaluation.json"
    markdown_path = destination / "architecture-evaluation.md"
    _atomic_write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(markdown_path, render_architecture_evaluation_markdown(report))
    return ArchitectureEvaluationPaths(json=json_path, markdown=markdown_path)
