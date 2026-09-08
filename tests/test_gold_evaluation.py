from __future__ import annotations

import json
from pathlib import Path

from ai_context_linker.gold_evaluation import build_gold_evaluation_report, evaluate_gold_suite


ROOT = Path(__file__).resolve().parents[1]
SUITE = ROOT / "examples" / "evaluation" / "gold-v02" / "gold-suite.json"


def test_gold_suite_covers_required_action_context_cases() -> None:
    raw = json.loads(SUITE.read_text(encoding="utf-8"))
    covered = {coverage for case in raw["cases"] for coverage in case["covers"]}

    assert covered == {
        "blocker-open-to-resolved",
        "blocker-superseded",
        "broad-goal-no-next-action",
        "deadline",
        "human-priority",
        "dependency-endpoint",
        "sensitive-path-secret-injection",
        "same-name-false-positive",
        "separate-by-design",
        "unapproved-ai-merge-candidate",
        "no-previous-snapshot",
        "disappeared-source",
        "stale-approved-state",
    }


def test_gold_suite_passes_v02_release_gates() -> None:
    report = evaluate_gold_suite(SUITE)

    assert report["all_gates_pass"] is True
    assert report["metrics"] == {
        "approved_next_action_transfer": 1.0,
        "blocker_precision": 1.0,
        "blocker_recall": 1.0,
        "resolved_blocker_false_positive_rate": 0.0,
        "semantic_diff_precision": 1.0,
        "semantic_diff_recall": 1.0,
        "factual_relationship_precision": 1.0,
        "published_relationship_evidence_coverage": 1.0,
        "configured_privacy_leaks": 0,
        "deterministic_output": 1.0,
    }
    assert report["case_results"]["sensitive-input"]["privacy_rejected"] is True
    assert report["case_results"]["ai-merge-candidate"]["published_relationships"] == []
    assert report["case_results"]["disappeared-source"]["open_blockers"] == []


def test_gold_report_files_are_deterministic_and_path_free(tmp_path: Path) -> None:
    first = build_gold_evaluation_report(SUITE, tmp_path / "first")
    second = build_gold_evaluation_report(SUITE, tmp_path / "second")

    first_json = first.json.read_text(encoding="utf-8")
    first_markdown = first.markdown.read_text(encoding="utf-8")
    assert first_json == second.json.read_text(encoding="utf-8")
    assert first_markdown == second.markdown.read_text(encoding="utf-8")
    assert str(tmp_path) not in first_json
    assert str(tmp_path) not in first_markdown
    assert "ALL GATES PASS" in first_markdown
