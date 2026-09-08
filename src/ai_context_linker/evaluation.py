"""Offline, privacy-aware A/B evaluation for action-oriented context quality."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import is_link_or_reparse
from .core import (
    ABSOLUTE_PATH_PATTERNS, SECRET_PATTERNS, ManifestError, _atomic_write_text,
    validate_output_directory, validate_publish_text,
)


SCHEMA_VERSION = "0.1"
MAX_ANSWER_BYTES = 2 * 1024 * 1024
CONDITIONS = ("full_workspace", "linker")
DIMENSIONS = (
    "factual_grounding",
    "current_state_freshness",
    "blocker_recall",
    "next_action_recall",
    "relationship_usefulness",
    "uncertainty_discipline",
)
FIXED_QUESTIONS = {
    "advance-today": "What should I advance today, and why?",
    "active-blockers": "Where is each active project blocked?",
    "next-actions": "What is the next concrete action?",
    "relationships": "Which projects depend on, overlap with, or may consolidate into another?",
    "snapshot-changes": "What changed since the previous approved snapshot?",
}
ACTION_QUESTION_IDS = {"advance-today", "active-blockers", "next-actions"}


class EvaluationError(ManifestError):
    """Raised when a private evaluation scorecard is invalid or unsafe to summarize."""


@dataclass(frozen=True)
class EvaluationPaths:
    markdown: Path
    json: Path


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise EvaluationError(f"{label} must be an object")
    return value


def _keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise EvaluationError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _string(value: Any, label: str, *, max_length: int = 2_000) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvaluationError(f"{label} must be a non-empty string")
    normalized = value.strip()
    if len(normalized) > max_length:
        raise EvaluationError(f"{label} exceeds {max_length} characters")
    return normalized


def _boolean(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise EvaluationError(f"{label} must be a boolean")
    return value


def _resolve_answer(scorecard_dir: Path, raw: Any, label: str) -> Path:
    relative = Path(_string(raw, label, max_length=1_000))
    if relative.is_absolute() or ".." in relative.parts:
        raise EvaluationError(f"{label} must be relative to the private scorecard directory")
    unresolved = scorecard_dir / relative
    if is_link_or_reparse(unresolved):
        raise EvaluationError(f"{label} must not be a link or reparse point")
    resolved = unresolved.resolve()
    if not resolved.is_relative_to(scorecard_dir):
        raise EvaluationError(f"{label} resolves outside the private scorecard directory")
    if not resolved.is_file():
        raise EvaluationError(f"{label} is not an existing answer file")
    if resolved.stat().st_size > MAX_ANSWER_BYTES:
        raise EvaluationError(f"{label} exceeds the {MAX_ANSWER_BYTES} byte answer limit")
    return resolved


def _read_answer(path: Path, label: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise EvaluationError(f"{label} must be UTF-8 text") from exc


def _pattern_hits(text: str, patterns: tuple[re.Pattern[str], ...]) -> int:
    return sum(1 for pattern in patterns for _ in pattern.finditer(text))


def _answer_metrics(text: str) -> dict[str, Any]:
    return {
        "bytes": len(text.encode("utf-8")),
        "characters": len(text),
        "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "absolute_path_hits": _pattern_hits(text, ABSOLUTE_PATH_PATTERNS),
        "likely_secret_hits": _pattern_hits(text, SECRET_PATTERNS),
    }


def _rating(raw: Any, label: str) -> dict[str, Any]:
    rating = _mapping(raw, label)
    _keys(rating, {"score", "note"}, label)
    score = rating.get("score")
    if isinstance(score, bool) or not isinstance(score, int) or not 0 <= score <= 4:
        raise EvaluationError(f"{label}.score must be an integer from 0 to 4")
    note = _string(rating.get("note"), f"{label}.note", max_length=4_000)
    return {"score": score, "note": note}


def _load_scorecard(path: Path | str) -> tuple[dict[str, Any], Path]:
    unresolved = Path(path)
    if is_link_or_reparse(unresolved):
        raise EvaluationError("scorecard must not be a link or reparse point")
    scorecard_path = unresolved.resolve()
    if not scorecard_path.is_file():
        raise EvaluationError("scorecard must be a real JSON file")
    try:
        raw = json.loads(scorecard_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvaluationError(f"invalid JSON in {scorecard_path.name}: {exc.msg}") from exc
    scorecard = _mapping(raw, "scorecard")
    _keys(
        scorecard,
        {"schema_version", "evaluation_id", "model", "project_set", "conditions", "questions"},
        "scorecard",
    )
    if scorecard.get("schema_version") != SCHEMA_VERSION:
        raise EvaluationError(f"scorecard.schema_version must be {SCHEMA_VERSION}")
    return scorecard, scorecard_path.parent


def _normalize_scorecard(path: Path | str) -> tuple[dict[str, Any], Path]:
    scorecard, scorecard_dir = _load_scorecard(path)
    evaluation_id = _string(scorecard.get("evaluation_id"), "scorecard.evaluation_id", max_length=100)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", evaluation_id):
        raise EvaluationError("scorecard.evaluation_id must be a lowercase identifier")
    model = _string(scorecard.get("model"), "scorecard.model", max_length=200)
    project_set = _string(scorecard.get("project_set"), "scorecard.project_set", max_length=200)
    validate_publish_text(model, "scorecard.model")
    validate_publish_text(project_set, "scorecard.project_set")

    conditions = _mapping(scorecard.get("conditions"), "scorecard.conditions")
    _keys(conditions, set(CONDITIONS), "scorecard.conditions")
    expected_flags = {
        "full_workspace": {"local_access": True, "full_context_budget": True, "bundle_only": False},
        "linker": {"local_access": False, "full_context_budget": True, "bundle_only": True},
    }
    normalized_conditions: dict[str, dict[str, bool]] = {}
    for condition in CONDITIONS:
        config = _mapping(conditions.get(condition), f"scorecard.conditions.{condition}")
        _keys(config, {"local_access", "full_context_budget", "bundle_only"}, f"scorecard.conditions.{condition}")
        normalized_conditions[condition] = {
            field: _boolean(config.get(field), f"scorecard.conditions.{condition}.{field}")
            for field in expected_flags[condition]
        }
        if normalized_conditions[condition] != expected_flags[condition]:
            raise EvaluationError(f"scorecard.conditions.{condition} does not preserve the controlled comparison")

    raw_questions = scorecard.get("questions")
    if not isinstance(raw_questions, list):
        raise EvaluationError("scorecard.questions must be an array")
    normalized_questions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, raw_question in enumerate(raw_questions):
        label = f"scorecard.questions[{index}]"
        question = _mapping(raw_question, label)
        _keys(question, {"id", "text", "answers", "ratings", "material_loss", "notes"}, label)
        question_id = _string(question.get("id"), f"{label}.id", max_length=100)
        if question_id not in FIXED_QUESTIONS:
            raise EvaluationError(f"{label}.id is not in the fixed question set")
        if question_id in seen:
            raise EvaluationError(f"duplicate fixed question id: {question_id}")
        seen.add(question_id)
        text = _string(question.get("text"), f"{label}.text", max_length=500)
        if text != FIXED_QUESTIONS[question_id]:
            raise EvaluationError(f"{label}.text does not match the fixed question")

        answers = _mapping(question.get("answers"), f"{label}.answers")
        _keys(answers, set(CONDITIONS), f"{label}.answers")
        answer_paths = {
            condition: _resolve_answer(scorecard_dir, answers.get(condition), f"{label}.answers.{condition}")
            for condition in CONDITIONS
        }

        raw_ratings = _mapping(question.get("ratings"), f"{label}.ratings")
        _keys(raw_ratings, set(DIMENSIONS), f"{label}.ratings")
        ratings: dict[str, dict[str, dict[str, Any]]] = {}
        for dimension in DIMENSIONS:
            by_condition = _mapping(raw_ratings.get(dimension), f"{label}.ratings.{dimension}")
            _keys(by_condition, set(CONDITIONS), f"{label}.ratings.{dimension}")
            ratings[dimension] = {
                condition: _rating(
                    by_condition.get(condition),
                    f"{label}.ratings.{dimension}.{condition}",
                )
                for condition in CONDITIONS
            }

        normalized_questions.append(
            {
                "id": question_id,
                "text": text,
                "answer_paths": answer_paths,
                "ratings": ratings,
                "material_loss": _boolean(question.get("material_loss"), f"{label}.material_loss"),
                "notes": _string(question.get("notes"), f"{label}.notes", max_length=4_000),
            }
        )

    missing = sorted(set(FIXED_QUESTIONS) - seen)
    if missing:
        raise EvaluationError(f"scorecard.questions is missing fixed questions: {', '.join(missing)}")
    return {
        "schema_version": SCHEMA_VERSION,
        "evaluation_id": evaluation_id,
        "model": model,
        "project_set": project_set,
        "conditions": normalized_conditions,
        "questions": normalized_questions,
    }, scorecard_dir


def _average(values: list[int]) -> float:
    return round(sum(values) / len(values), 2)


def evaluate_scorecard(path: Path | str) -> dict[str, Any]:
    """Evaluate private paired answers and return a path-free aggregate report."""
    scorecard, _ = _normalize_scorecard(path)
    aggregates = {
        condition: {dimension: [] for dimension in DIMENSIONS}
        for condition in CONDITIONS
    }
    question_reports: list[dict[str, Any]] = []
    action_parity = True
    linker_absolute_path_hits = 0
    linker_secret_hits = 0

    for question in scorecard["questions"]:
        conditions: dict[str, dict[str, Any]] = {}
        for condition in CONDITIONS:
            answer = _read_answer(question["answer_paths"][condition], f"{question['id']}.{condition}")
            metrics = _answer_metrics(answer)
            scores = {
                dimension: question["ratings"][dimension][condition]["score"]
                for dimension in DIMENSIONS
            }
            for dimension, score in scores.items():
                aggregates[condition][dimension].append(score)
            conditions[condition] = {
                **metrics,
                "scores": scores,
                "average_score": _average(list(scores.values())),
            }
        if question["id"] in ACTION_QUESTION_IDS:
            if question["material_loss"] or any(
                conditions["linker"]["scores"][dimension]
                < conditions["full_workspace"]["scores"][dimension]
                for dimension in DIMENSIONS
            ):
                action_parity = False
        linker_absolute_path_hits += conditions["linker"]["absolute_path_hits"]
        linker_secret_hits += conditions["linker"]["likely_secret_hits"]
        question_reports.append(
            {
                "id": question["id"],
                "text": question["text"],
                "material_loss": question["material_loss"],
                "conditions": conditions,
            }
        )

    dimension_averages = {
        condition: {
            dimension: _average(aggregates[condition][dimension])
            for dimension in DIMENSIONS
        }
        for condition in CONDITIONS
    }
    overall_averages = {
        condition: _average(
            [score for dimension in DIMENSIONS for score in aggregates[condition][dimension]]
        )
        for condition in CONDITIONS
    }
    privacy_pass = linker_absolute_path_hits == 0 and linker_secret_hits == 0
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evaluation_id": scorecard["evaluation_id"],
        "model": scorecard["model"],
        "project_set": scorecard["project_set"],
        "question_count": len(question_reports),
        "dimensions": list(DIMENSIONS),
        "dimension_averages": dimension_averages,
        "overall_averages": overall_averages,
        "action_parity": action_parity,
        "linker_privacy": {
            "absolute_path_hits": linker_absolute_path_hits,
            "likely_secret_hits": linker_secret_hits,
            "pass": privacy_pass,
        },
        "evaluation_scope": "single-pair-diagnostic",
        "paired_answer_checks_pass": action_parity and privacy_pass and not any(
            question["material_loss"] for question in question_reports
        ),
        # A v0.1 scorecard cannot prove same-window captures, Q6, both orders,
        # objective gates or two real semantic refreshes. Never imply it can.
        "replacement_ready": False,
        "questions": question_reports,
    }


def render_evaluation_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# AI Context Linker parity evaluation",
        "",
        f"- Evaluation: `{report['evaluation_id']}`",
        f"- Model: `{report['model']}`",
        f"- Project set: `{report['project_set']}`",
        f"- Questions: {report['question_count']}",
        f"- Action parity: {'PASS' if report['action_parity'] else 'FAIL'}",
        f"- Linker privacy: {'PASS' if report['linker_privacy']['pass'] else 'FAIL'}",
        f"- Replacement ready: {'YES' if report['replacement_ready'] else 'NO'}",
        "- Scope: single-pair diagnostic only; not two-refresh replacement acceptance.",
        "",
        "## Aggregate scores",
        "",
        "| Dimension | Full workspace | Linker | Delta |",
        "|---|---:|---:|---:|",
    ]
    for dimension in DIMENSIONS:
        baseline = report["dimension_averages"]["full_workspace"][dimension]
        linker = report["dimension_averages"]["linker"][dimension]
        lines.append(f"| `{dimension}` | {baseline:.2f} | {linker:.2f} | {linker - baseline:+.2f} |")
    lines.extend(
        [
            f"| **overall** | **{report['overall_averages']['full_workspace']:.2f}** | **{report['overall_averages']['linker']:.2f}** | **{report['overall_averages']['linker'] - report['overall_averages']['full_workspace']:+.2f}** |",
            "",
            "## Fixed-question results",
            "",
            "| Question | Full workspace | Linker | Material loss |",
            "|---|---:|---:|---|",
        ]
    )
    for question in report["questions"]:
        baseline = question["conditions"]["full_workspace"]["average_score"]
        linker = question["conditions"]["linker"]["average_score"]
        lines.append(
            f"| {question['text']} | {baseline:.2f} | {linker:.2f} | {'yes' if question['material_loss'] else 'no'} |"
        )
    privacy = report["linker_privacy"]
    lines.extend(
        [
            "",
            "## Linker leakage checks",
            "",
            f"- Absolute-path hits: {privacy['absolute_path_hits']}",
            f"- Likely-secret hits: {privacy['likely_secret_hits']}",
            "",
            "> Raw answers, local paths, and private scoring notes are intentionally omitted from this aggregate report.",
            "",
        ]
    )
    markdown = "\n".join(lines)
    validate_publish_text(markdown, "evaluation report")
    return markdown


def build_evaluation_report(scorecard_path: Path | str, output_dir: Path | str) -> EvaluationPaths:
    report = evaluate_scorecard(scorecard_path)
    markdown = render_evaluation_markdown(report)
    destination = validate_output_directory(output_dir)
    markdown_path = destination / "ai_context_linker.evaluation.md"
    json_path = destination / "ai_context_linker.evaluation.json"
    json_text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    validate_publish_text(json_text, "evaluation JSON report")
    _atomic_write_text(markdown_path, markdown)
    _atomic_write_text(json_path, json_text)
    return EvaluationPaths(markdown=markdown_path, json=json_path)
