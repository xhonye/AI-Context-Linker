from __future__ import annotations

from pathlib import Path

from ai_context_linker.adapters import classify_changed_path, collect_filename_inventory


def test_filename_inventory_reports_entry_points_and_tests_without_contents(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "server.py").write_text("api_key=sk-example0123456789012345", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_server.py").write_text("assert False", encoding="utf-8")

    signals, evidence, report = collect_filename_inventory(tmp_path, "sample")
    rendered = " ".join(signals)

    assert "server.py" in rendered
    assert "1 test file" in rendered
    assert "sk-example" not in rendered
    assert report["source_code_bodies_read"] == 0
    assert evidence == ["sample:inventory:entry-points", "sample:inventory:test-files"]


def test_filename_inventory_prunes_dependency_directories(tmp_path: Path) -> None:
    dependency = tmp_path / "node_modules" / "package" / "tests"
    dependency.mkdir(parents=True)
    (dependency / "test_noise.js").write_text("throw new Error()", encoding="utf-8")

    _, _, report = collect_filename_inventory(tmp_path, "sample")

    assert report["test_file_count"] == 0


def test_filename_inventory_does_not_count_fixtures_as_tests(tmp_path: Path) -> None:
    fixtures = tmp_path / "tests" / "fixtures"
    fixtures.mkdir(parents=True)
    (fixtures / "sample.json").write_text("{}", encoding="utf-8")

    _, _, report = collect_filename_inventory(tmp_path, "sample")

    assert report["test_file_count"] == 0


def test_filename_inventory_stops_at_safety_limit(tmp_path: Path) -> None:
    for index in range(5):
        (tmp_path / f"file-{index}.txt").write_text("x", encoding="utf-8")

    signals, evidence, report = collect_filename_inventory(tmp_path, "sample", max_entries=3)

    assert report["truncated"] is True
    assert any("safety limit" in signal for signal in signals)
    assert evidence == ["sample:inventory:truncated"]


def test_changed_path_classification_is_coarse() -> None:
    assert classify_changed_path("src/app.py") == "source"
    assert classify_changed_path("tests/test_app.py") == "tests"
    assert classify_changed_path("docs/plan.md") == "docs"
    assert classify_changed_path("pyproject.toml") == "config"
    assert classify_changed_path("assets/logo.png") == "other"
