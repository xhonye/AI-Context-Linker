from __future__ import annotations

from pathlib import Path

from ai_context_linker.architecture_evaluation import (
    build_architecture_evaluation_report,
    evaluate_architecture_fixture,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
GOLD_ROOT = PROJECT_ROOT / "examples" / "evaluation" / "architecture-gold"


def test_architecture_gold_fixture_passes_all_release_gates() -> None:
    report = evaluate_architecture_fixture(GOLD_ROOT / "project", GOLD_ROOT / "expected.json")

    assert report["all_gates_pass"] is True
    assert report["metrics"]["modules"]["recall"] == 1.0
    assert report["metrics"]["symbols"]["recall"] == 1.0
    assert report["metrics"]["internal_calls"]["precision"] == 1.0
    assert report["configured_privacy_leaks"] == 0


def test_architecture_gold_report_is_generated_without_local_paths(tmp_path: Path) -> None:
    paths = build_architecture_evaluation_report(
        GOLD_ROOT / "project",
        GOLD_ROOT / "expected.json",
        tmp_path / "report",
    )

    assert paths.json.exists()
    markdown = paths.markdown.read_text(encoding="utf-8")
    assert "ALL GATES PASS" in markdown
    assert ":/" not in markdown
