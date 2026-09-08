from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ai_context_linker import cli


def test_scan_cli_prints_every_private_review_artifact(monkeypatch, capsys, tmp_path: Path) -> None:
    paths = SimpleNamespace(
        candidate_manifest=tmp_path / "candidate-manifest.json",
        report=tmp_path / "scan-report.json",
        changes_json=tmp_path / "changes.json",
        changes_markdown=tmp_path / "changes.md",
        relationship_review_queue=tmp_path / "relationship-review-queue.json",
    )
    monkeypatch.setattr(cli, "scan_workspace", lambda *args, **kwargs: paths)

    result = cli.main(
        ["scan", "--config", str(tmp_path / "workspace.json"), "--review-dir", str(tmp_path / "review")]
    )
    output = capsys.readouterr().out

    assert result == 0
    assert "candidate-manifest.json" in output
    assert "scan-report.json" in output
    assert "changes.json" in output
    assert "changes.md" in output
    assert "relationship-review-queue.json" in output


def test_init_review_state_cli_writes_unapproved_three_project_skeleton(monkeypatch, capsys, tmp_path: Path) -> None:
    output = tmp_path / "review-state-v0.2.json"
    monkeypatch.setattr(cli, "init_review_state", lambda *args, **kwargs: output)

    result = cli.main(
        [
            "init-review-state",
            "--manifest",
            str(tmp_path / "candidate-manifest.json"),
            "--project",
            "alpha",
            "--project",
            "beta",
            "--project",
            "gamma",
            "--output",
            str(output),
        ]
    )

    assert result == 0
    assert str(output.resolve()) in capsys.readouterr().out


def test_evaluate_architecture_cli_prints_both_reports(monkeypatch, capsys, tmp_path: Path) -> None:
    paths = SimpleNamespace(
        markdown=tmp_path / "architecture-evaluation.md",
        json=tmp_path / "architecture-evaluation.json",
    )
    monkeypatch.setattr(cli, "build_architecture_evaluation_report", lambda *args, **kwargs: paths)

    result = cli.main(
        [
            "evaluate-architecture",
            "--fixture-dir",
            str(tmp_path / "fixture"),
            "--expected",
            str(tmp_path / "expected.json"),
            "--output-dir",
            str(tmp_path / "report"),
        ]
    )
    output = capsys.readouterr().out

    assert result == 0
    assert "architecture-evaluation.md" in output
    assert "architecture-evaluation.json" in output
