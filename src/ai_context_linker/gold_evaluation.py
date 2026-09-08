"""Deterministic synthetic gold evaluation for the v0.2 action-context contract."""

from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .changes import semantic_changes
from .core import (
    ManifestError,
    _atomic_write_text,
    build_graph,
    facts_sha256,
    validate_manifest,
    validate_publish_text,
)
from .relationships import derive_document_relationships
from .slicing import _priority_selection, render_question_context
from .state_records import make_state_record, resolve_state_records


SUITE_KEYS = {"schema_version", "observed_at", "cases"}
CASE_KEYS = {
    "id",
    "covers",
    "workspace_summary",
    "projects",
    "previous_projects",
    "relationships",
    "previous_relationships",
    "documents",
    "expected",
}
EXPECTED_LIST_FIELDS = (
    "approved_next_actions",
    "open_blockers",
    "priority_main",
    "dependency_endpoints",
    "semantic_changes",
    "published_relationships",
)


@dataclass(frozen=True)
class GoldEvaluationPaths:
    json: Path
    markdown: Path


def _load_suite(path: Path | str) -> dict[str, Any]:
    suite_path = Path(path)
    try:
        raw = json.loads(suite_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("gold suite must be valid UTF-8 JSON") from exc
    if not isinstance(raw, dict) or set(raw) != SUITE_KEYS:
        raise ManifestError("gold suite must contain exactly schema_version, observed_at, and cases")
    if raw["schema_version"] != "0.2":
        raise ManifestError("gold suite schema_version must be 0.2")
    try:
        observed_at = datetime.fromisoformat(raw["observed_at"])
    except (TypeError, ValueError) as exc:
        raise ManifestError("gold suite observed_at must be an ISO 8601 timestamp") from exc
    if observed_at.tzinfo is None:
        raise ManifestError("gold suite observed_at must include a timezone")
    if not isinstance(raw["cases"], list) or not raw["cases"]:
        raise ManifestError("gold suite cases must be a non-empty array")
    ids: set[str] = set()
    for index, case in enumerate(raw["cases"]):
        if not isinstance(case, dict) or set(case) - CASE_KEYS:
            raise ManifestError(f"gold suite cases[{index}] contains unsupported fields")
        if not isinstance(case.get("id"), str) or not case["id"] or case["id"] in ids:
            raise ManifestError(f"gold suite cases[{index}].id must be unique")
        ids.add(case["id"])
        if not isinstance(case.get("covers"), list) or not case["covers"]:
            raise ManifestError(f"gold suite cases[{index}].covers must be a non-empty array")
        if not isinstance(case.get("projects"), list) or not case["projects"]:
            raise ManifestError(f"gold suite cases[{index}].projects must be a non-empty array")
        if not isinstance(case.get("expected"), dict):
            raise ManifestError(f"gold suite cases[{index}].expected must be an object")
    return raw


def _record(project_id: str, raw: dict[str, Any], observed_at: str) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ManifestError("gold record must be an object")
    return make_state_record(
        project_id=project_id,
        kind=str(raw["kind"]),
        text=str(raw["text"]),
        source_kind=str(raw.get("source_kind", "approved-review")),
        source_ref=str(raw.get("source_ref", f"{project_id}:approved-review:{raw['kind']}")),
        observed_at=str(raw.get("observed_at", observed_at)),
        expires_at=str(raw["expires_at"]) if raw.get("expires_at") else None,
        status=str(raw.get("status", "open")),
        record_id=str(raw["record_id"]) if raw.get("record_id") else None,
        supersedes=[str(value) for value in raw.get("supersedes", [])],
    )


def _project(raw: dict[str, Any], observed_at: str) -> dict[str, Any]:
    if not isinstance(raw, dict) or set(raw) - {"id", "records"}:
        raise ManifestError("gold project must contain only id and records")
    project_id = str(raw["id"])
    records = raw.get("records", [])
    if not isinstance(records, list):
        raise ManifestError("gold project records must be an array")
    return {
        "id": project_id,
        "name": project_id.replace("-", " ").title(),
        "summary": f"Synthetic project {project_id}.",
        "status": "unknown; only approved action records establish current status",
        "signals": [],
        "constraints": [],
        "risks": [],
        "open_questions": [],
        "state_items": [_record(project_id, item, observed_at) for item in records],
        "evidence": [f"{project_id}:synthetic:project-card"],
    }


def _manifest(
    case: dict[str, Any],
    observed_at: str,
    *,
    previous: bool = False,
) -> dict[str, Any] | None:
    project_key = "previous_projects" if previous else "projects"
    if previous and project_key not in case:
        return None
    relationship_key = "previous_relationships" if previous else "relationships"
    relationships = copy.deepcopy(case.get(relationship_key, []))
    projects = [_project(item, observed_at) for item in case[project_key]]
    if not previous:
        documents = case.get("documents", {})
        if not isinstance(documents, dict):
            raise ManifestError("gold case documents must be an object")
        project_ids = {project["id"] for project in projects}
        for source_id, source_documents in sorted(documents.items()):
            if source_id not in project_ids or not isinstance(source_documents, dict):
                raise ManifestError("gold case documents must map approved project IDs to document objects")
            relationships.extend(
                derive_document_relationships(source_id, source_documents, project_ids)
            )
    raw = {
        "schema_version": "0.2",
        "generated_at": observed_at,
        "workspace": {
            "name": f"Synthetic gold case {case['id']}",
            "summary": case.get("workspace_summary", "Synthetic action-context evaluation case."),
            "current_focus": "Evaluate the fixed action-context contract.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": projects,
        "relationships": relationships,
    }
    normalized = validate_manifest(raw)
    normalized["facts_sha256"] = facts_sha256(normalized)
    return validate_manifest(normalized)


def _resolve_lifecycle(
    current: dict[str, Any], previous: dict[str, Any] | None, observed_at: str
) -> dict[str, Any]:
    resolved = copy.deepcopy(current)
    previous_projects = {project["id"]: project for project in previous["projects"]} if previous else {}
    timestamp = datetime.fromisoformat(observed_at)
    for project in resolved["projects"]:
        old = previous_projects.get(project["id"])
        project["state_items"] = resolve_state_records(
            project.get("state_items", []),
            old.get("state_items", []) if old else [],
            observed_at=timestamp,
        )
    resolved.pop("facts_sha256", None)
    resolved = validate_manifest(resolved)
    resolved["facts_sha256"] = facts_sha256(resolved)
    return validate_manifest(resolved)


def _semantic_tokens(changes: dict[str, Any]) -> list[str]:
    tokens: list[str] = []
    for item in changes["semantic_state_changes"]:
        prefix = f"state|{item['project_id']}|{item['kind']}|{item['record_id']}|{item['change']}"
        if item["change"] == "status":
            prefix += f"|{item['from']}->{item['to']}"
        tokens.append(prefix)
    for change in ("added", "removed"):
        tokens.extend(f"project|{change}|{project_id}" for project_id in changes["projects"][change])
        tokens.extend(
            f"relationship|{change}|{relationship}"
            for relationship in changes["relationships"][change]
        )
    return sorted(tokens)


def _evaluate_case_once(case: dict[str, Any], observed_at: str) -> dict[str, Any]:
    expected_rejection = bool(case["expected"].get("privacy_rejected", False))
    try:
        current = _manifest(case, observed_at)
        previous = _manifest(case, observed_at, previous=True)
        assert current is not None
        current = _resolve_lifecycle(current, previous, observed_at)
        changes = semantic_changes(current, previous, git_activity_appendix=[])
        selection = _priority_selection(current)
        rendered = render_question_context(
            current, "What should I advance today, where is it blocked, and what is the next action?"
        )
        graph = build_graph(current)
        validate_publish_text(rendered, "gold rendered context")
        validate_publish_text(json.dumps(graph, ensure_ascii=False), "gold graph")
    except ManifestError:
        if not expected_rejection:
            raise
        return {
            "privacy_rejected": True,
            "privacy_leaks": 0,
            "approved_next_actions": [],
            "open_blockers": [],
            "priority_main": [],
            "dependency_endpoints": [],
            "semantic_changes": [],
            "published_relationships": [],
            "published_relationships_with_evidence": 0,
            "baseline_available": False,
        }

    open_records = [
        (project["id"], record)
        for project in current["projects"]
        for record in project.get("state_items", [])
        if record.get("status") == "open" and record.get("freshness") not in {"stale", "future-dated"}
    ]
    published_edges = [edge for edge in graph["edges"] if edge["source"] != "workspace"]
    return {
        "privacy_rejected": False,
        "privacy_leaks": 0,
        "approved_next_actions": sorted(
            record["text"]
            for _, record in open_records
            if record["kind"] == "next-action"
            and record.get("source_kind") == "approved-review"
            and record["text"] in rendered
        ),
        "open_blockers": sorted(
            f"{project_id}|{record['record_id']}"
            for project_id, record in open_records
            if record["kind"] == "blocker"
        ),
        "priority_main": [project["id"] for project in selection.main_projects],
        "dependency_endpoints": [project["id"] for project in selection.endpoint_projects],
        "semantic_changes": _semantic_tokens(changes),
        "published_relationships": sorted(
            f"{edge['source']}|{edge['type']}|{edge['target']}" for edge in published_edges
        ),
        "published_relationships_with_evidence": sum(bool(edge.get("evidence")) for edge in published_edges),
        "baseline_available": changes["baseline_available"],
    }


def _ratio(numerator: int, denominator: int) -> float:
    return round(numerator / denominator, 6) if denominator else 1.0


def _precision(predicted: set[str], expected: set[str]) -> float:
    return _ratio(len(predicted & expected), len(predicted))


def _recall(predicted: set[str], expected: set[str]) -> float:
    return _ratio(len(predicted & expected), len(expected))


def evaluate_gold_suite(path: Path | str) -> dict[str, Any]:
    suite = _load_suite(path)
    observed_at = suite["observed_at"]
    case_results: dict[str, dict[str, Any]] = {}
    deterministic_cases = 0
    scenario_mismatches: list[str] = []
    expected_next: set[str] = set()
    actual_next: set[str] = set()
    expected_blockers: set[str] = set()
    actual_blockers: set[str] = set()
    expected_non_open_blockers: set[str] = set()
    expected_semantic: set[str] = set()
    actual_semantic: set[str] = set()
    expected_relationships: set[str] = set()
    actual_relationships: set[str] = set()
    relationship_count = 0
    relationship_evidence_count = 0
    privacy_leaks = 0

    for case in suite["cases"]:
        case_id = case["id"]
        first = _evaluate_case_once(case, observed_at)
        second = _evaluate_case_once(case, observed_at)
        if first == second:
            deterministic_cases += 1
        case_results[case_id] = first
        expected = case["expected"]
        for field in EXPECTED_LIST_FIELDS:
            wanted = sorted(expected.get(field, []))
            if first[field] != wanted:
                scenario_mismatches.append(f"{case_id}:{field}")
        if "privacy_rejected" in expected and first["privacy_rejected"] != expected["privacy_rejected"]:
            scenario_mismatches.append(f"{case_id}:privacy_rejected")
        if "baseline_available" in expected and first["baseline_available"] != expected["baseline_available"]:
            scenario_mismatches.append(f"{case_id}:baseline_available")
        for blocker in expected.get("resolved_blockers", []):
            if blocker in first["open_blockers"]:
                scenario_mismatches.append(f"{case_id}:resolved_blocker_open")

        expected_next.update(f"{case_id}|{item}" for item in expected.get("approved_next_actions", []))
        actual_next.update(f"{case_id}|{item}" for item in first["approved_next_actions"])
        expected_blockers.update(f"{case_id}|{item}" for item in expected.get("open_blockers", []))
        actual_blockers.update(f"{case_id}|{item}" for item in first["open_blockers"])
        expected_non_open_blockers.update(
            f"{case_id}|{item}" for item in expected.get("resolved_blockers", [])
        )
        expected_semantic.update(f"{case_id}|{item}" for item in expected.get("semantic_changes", []))
        actual_semantic.update(f"{case_id}|{item}" for item in first["semantic_changes"])
        expected_relationships.update(
            f"{case_id}|{item}" for item in expected.get("published_relationships", [])
        )
        actual_relationships.update(
            f"{case_id}|{item}" for item in first["published_relationships"]
        )
        relationship_count += len(first["published_relationships"])
        relationship_evidence_count += first["published_relationships_with_evidence"]
        privacy_leaks += first["privacy_leaks"]
        if expected.get("privacy_rejected") and not first["privacy_rejected"]:
            privacy_leaks += 1

    metrics = {
        "approved_next_action_transfer": _recall(actual_next, expected_next),
        "blocker_precision": _precision(actual_blockers, expected_blockers),
        "blocker_recall": _recall(actual_blockers, expected_blockers),
        "resolved_blocker_false_positive_rate": _ratio(
            len(actual_blockers & expected_non_open_blockers), len(expected_non_open_blockers)
        ),
        "semantic_diff_precision": _precision(actual_semantic, expected_semantic),
        "semantic_diff_recall": _recall(actual_semantic, expected_semantic),
        "factual_relationship_precision": _precision(actual_relationships, expected_relationships),
        "published_relationship_evidence_coverage": _ratio(relationship_evidence_count, relationship_count),
        "configured_privacy_leaks": privacy_leaks,
        "deterministic_output": _ratio(deterministic_cases, len(suite["cases"])),
    }
    gate_specs = {
        "approved_next_action_transfer": (">=", 1.0),
        "blocker_precision": (">=", 0.9),
        "blocker_recall": (">=", 0.9),
        "resolved_blocker_false_positive_rate": ("<=", 0.05),
        "semantic_diff_precision": (">=", 0.95),
        "semantic_diff_recall": (">=", 0.95),
        "factual_relationship_precision": (">=", 0.95),
        "published_relationship_evidence_coverage": (">=", 1.0),
        "configured_privacy_leaks": ("=", 0),
        "deterministic_output": (">=", 1.0),
    }
    gates: dict[str, dict[str, Any]] = {}
    for name, (operator, threshold) in gate_specs.items():
        value = metrics[name]
        passed = value >= threshold if operator == ">=" else value <= threshold if operator == "<=" else value == threshold
        gates[name] = {"value": value, "operator": operator, "threshold": threshold, "pass": passed}
    scenario_expectations_pass = not scenario_mismatches
    return {
        "schema_version": "0.2",
        "suite_observed_at": observed_at,
        "case_count": len(suite["cases"]),
        "scenario_expectations_pass": scenario_expectations_pass,
        "scenario_mismatches": sorted(scenario_mismatches),
        "metrics": metrics,
        "gates": gates,
        "all_gates_pass": scenario_expectations_pass and all(gate["pass"] for gate in gates.values()),
        "case_results": case_results,
    }


def render_gold_evaluation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI Context Linker v0.2 synthetic gold evaluation",
        "",
        f"> {'ALL GATES PASS' if report['all_gates_pass'] else 'GATES FAILED'}",
        f"> Fixed suite observation time: {report['suite_observed_at']}",
        "",
        "## Release gates",
        "",
        "| Gate | Result | Required | Status |",
        "|---|---:|---:|---|",
    ]
    for name, gate in report["gates"].items():
        lines.append(
            f"| `{name}` | {gate['value']} | {gate['operator']} {gate['threshold']} | {'PASS' if gate['pass'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## Scenario contract",
            "",
            f"- Cases: {report['case_count']}",
            f"- Expected behaviors: {'PASS' if report['scenario_expectations_pass'] else 'FAIL'}",
            f"- Mismatches: {', '.join(report['scenario_mismatches']) if report['scenario_mismatches'] else 'none'}",
            "",
            "> The suite uses only synthetic projects and fixed timestamps. It contains no real manifest, path, source text, or private runtime data.",
            "",
        ]
    )
    rendered = "\n".join(lines)
    validate_publish_text(rendered, "gold evaluation Markdown")
    return rendered


def build_gold_evaluation_report(path: Path | str, output_dir: Path | str) -> GoldEvaluationPaths:
    report = evaluate_gold_suite(path)
    destination = Path(output_dir)
    json_path = destination / "gold-evaluation.json"
    markdown_path = destination / "gold-evaluation.md"
    _atomic_write_text(json_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(markdown_path, render_gold_evaluation_markdown(report))
    return GoldEvaluationPaths(json=json_path, markdown=markdown_path)
