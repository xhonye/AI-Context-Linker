from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_context_linker.evaluation import (
    CONDITIONS,
    DIMENSIONS,
    FIXED_QUESTIONS,
    EvaluationError,
    build_evaluation_report,
    evaluate_scorecard,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def write_scorecard(
    root: Path,
    *,
    full_score: int = 4,
    linker_score: int = 4,
    linker_answer: str = "The reviewed synthetic evidence supports one next action.",
) -> Path:
    answers = root / "answers"
    answers.mkdir(parents=True)
    (answers / "full.md").write_text(
        "The synthetic workspace evidence supports one current goal and one next action.",
        encoding="utf-8",
    )
    (answers / "linker.md").write_text(linker_answer, encoding="utf-8")
    questions = []
    for question_id, text in FIXED_QUESTIONS.items():
        questions.append(
            {
                "id": question_id,
                "text": text,
                "answers": {
                    "full_workspace": "answers/full.md",
                    "linker": "answers/linker.md",
                },
                "ratings": {
                    dimension: {
                        "full_workspace": {"score": full_score, "note": "Synthetic baseline evidence."},
                        "linker": {"score": linker_score, "note": "Synthetic Linker evidence."},
                    }
                    for dimension in DIMENSIONS
                },
                "material_loss": False,
                "notes": "Synthetic fixed-question comparison.",
            }
        )
    scorecard = {
        "schema_version": "0.1",
        "evaluation_id": "synthetic-parity-run",
        "model": "gpt-5.6-sol",
        "project_set": "synthetic-approved-projects",
        "conditions": {
            "full_workspace": {
                "local_access": True,
                "full_context_budget": True,
                "bundle_only": False,
            },
            "linker": {
                "local_access": False,
                "full_context_budget": True,
                "bundle_only": True,
            },
        },
        "questions": questions,
    }
    path = root / "scorecard.json"
    path.write_text(json.dumps(scorecard, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def test_evaluation_builds_path_free_aggregate_without_raw_answers(tmp_path: Path) -> None:
    scorecard = write_scorecard(tmp_path)

    paths = build_evaluation_report(scorecard, tmp_path / "publish")

    report = json.loads(paths.json.read_text(encoding="utf-8"))
    markdown = paths.markdown.read_text(encoding="utf-8")
    assert report["replacement_ready"] is False
    assert report["paired_answer_checks_pass"] is True
    assert report["question_count"] == len(FIXED_QUESTIONS)
    assert report["dimensions"] == list(DIMENSIONS)
    assert report["linker_privacy"] == {
        "absolute_path_hits": 0,
        "likely_secret_hits": 0,
        "pass": True,
    }
    assert str(tmp_path) not in markdown
    assert "Synthetic Linker evidence" not in markdown
    assert "The reviewed synthetic evidence" not in markdown


def test_evaluation_reports_linker_leakage_without_copying_leaked_text(tmp_path: Path) -> None:
    leaked = "Read C:/Users/example/private.md with api_key=sk-example0123456789012345"
    scorecard = write_scorecard(tmp_path, linker_answer=leaked)

    paths = build_evaluation_report(scorecard, tmp_path / "publish")
    report_text = paths.json.read_text(encoding="utf-8")
    report = json.loads(report_text)

    assert report["linker_privacy"]["absolute_path_hits"] > 0
    assert report["linker_privacy"]["likely_secret_hits"] > 0
    assert report["linker_privacy"]["pass"] is False
    assert report["replacement_ready"] is False
    assert "C:/Users/example" not in report_text
    assert "sk-example" not in report_text


def test_lower_action_scores_fail_parity(tmp_path: Path) -> None:
    scorecard = write_scorecard(tmp_path, full_score=4, linker_score=3)

    report = evaluate_scorecard(scorecard)

    assert report["action_parity"] is False
    assert report["replacement_ready"] is False


def test_scorecard_must_include_every_fixed_question(tmp_path: Path) -> None:
    scorecard = write_scorecard(tmp_path)
    raw = json.loads(scorecard.read_text(encoding="utf-8"))
    raw["questions"] = raw["questions"][:-1]
    scorecard.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(EvaluationError, match="missing fixed questions"):
        evaluate_scorecard(scorecard)


def test_answer_path_cannot_escape_private_scorecard_directory(tmp_path: Path) -> None:
    scorecard = write_scorecard(tmp_path)
    raw = json.loads(scorecard.read_text(encoding="utf-8"))
    raw["questions"][0]["answers"][CONDITIONS[0]] = "../outside.md"
    scorecard.write_text(json.dumps(raw), encoding="utf-8")

    with pytest.raises(EvaluationError, match="must be relative"):
        evaluate_scorecard(scorecard)


def test_public_synthetic_scorecard_runs() -> None:
    scorecard = PROJECT_ROOT / "examples" / "evaluation" / "scorecard.json"

    report = evaluate_scorecard(scorecard)

    assert report["replacement_ready"] is False
    assert report["paired_answer_checks_pass"] is True
    assert report["linker_privacy"]["pass"] is True


def test_single_scorecard_cannot_establish_two_real_refresh_replacement(tmp_path: Path) -> None:
    report = evaluate_scorecard(write_scorecard(tmp_path))
    assert report["replacement_ready"] is False
    assert report["paired_answer_checks_pass"] is True
    assert report["evaluation_scope"] == "single-pair-diagnostic"
