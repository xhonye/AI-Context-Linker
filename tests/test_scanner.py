from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError, build_bundle
from ai_context_linker.scanner import collect_candidate, scan_workspace


def write_config(tmp_path: Path, project: Path, **project_overrides: object) -> Path:
    project_config: dict[str, object] = {
        "id": "sample",
        "path": str(project),
        "allow_files": ["README.md"],
        "observe_paths": ["tests"],
    }
    project_config.update(project_overrides)
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Scanner test",
            "summary": "A synthetic scanner test.",
            "current_focus": "Verify deterministic collection.",
            "decisions": ["Only allowlisted metadata may be read."],
            "unknowns": [],
        },
        "projects": [project_config],
        "relationships": [],
    }
    path = tmp_path / "workspace.json"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_scanner_builds_candidate_without_reading_source_bodies(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Safe Name\n\nA safe project summary.\n", encoding="utf-8")
    (project / "src").mkdir()
    (project / "src" / "private.py").write_text("api_key=sk-example0123456789012345", encoding="utf-8")
    (project / "tests").mkdir()
    config = write_config(tmp_path, project)

    candidate, report = collect_candidate(config, observed_at="2026-08-12T12:00:00+08:00")

    assert candidate["projects"][0]["name"] == "Safe Name"
    assert candidate["projects"][0]["summary"] == "A safe project summary."
    assert candidate["facts_sha256"]
    assert report["source_code_bodies_read"] == 0
    assert report["projects"][0]["metadata_files_read"] == ["README.md"]
    assert "private.py" not in json.dumps(candidate)


def test_scanner_collects_cross_tool_skill_frontmatter_only(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Safe\n\nSafe project.\n", encoding="utf-8")
    skill_root = tmp_path / "claude-skills"
    skill_dir = skill_root / "project-review"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(
        "---\nname: project-review\ndescription: Review project direction.\n---\n"
        "Secret instruction body at C:/Users/example/private.\n",
        encoding="utf-8",
    )
    config = json.loads(write_config(tmp_path, project).read_text(encoding="utf-8"))
    config["skill_roots"] = [
        {"id": "claude-user", "provider": "claude-code", "scope": "user", "path": str(skill_root)}
    ]
    config_path = tmp_path / "skills-workspace.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    candidate, report = collect_candidate(config_path)

    assert candidate["skills"][0]["name"] == "project-review"
    assert candidate["skills"][0]["summary"] == "Review project direction."
    assert "C:/Users" not in json.dumps(candidate)
    assert report["skills"]["instruction_bodies_read"] == 0
    assert report["skills"]["skills_collected"] == 1


def test_candidate_hash_ignores_observation_time(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Stable\n\nStable summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)

    first, _ = collect_candidate(config, observed_at="2026-08-12T12:00:00+08:00")
    second, _ = collect_candidate(config, observed_at="2026-08-12T13:00:00+08:00")

    assert first["generated_at"] != second["generated_at"]
    assert first["facts_sha256"] == second["facts_sha256"]


def test_scanner_skips_markdown_rule_when_deriving_summary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Project\n\n---\n\nActual summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)

    candidate, _ = collect_candidate(config)

    assert candidate["projects"][0]["summary"] == "Actual summary."


def test_scanner_uses_approved_agents_metadata_when_readme_is_missing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text("# Agent-governed project\n\nSafe project overview.\n", encoding="utf-8")
    config = write_config(tmp_path, project, allow_files=["AGENTS.md"])

    candidate, _ = collect_candidate(config)

    assert candidate["projects"][0]["name"] == "Agent-governed project"
    assert candidate["projects"][0]["summary"] == "Safe project overview."


def test_scanner_reports_coarse_git_activity_without_changed_filenames(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Git facts\n\nSafe summary.\n", encoding="utf-8")
    (project / "app.py").write_text("print('first')\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=project, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=project, check=True)
    subprocess.run(["git", "add", "."], cwd=project, check=True)
    subprocess.run(["git", "commit", "-qm", "initial"], cwd=project, check=True)
    (project / "app.py").write_text("print('changed')\n", encoding="utf-8")
    (project / "docs").mkdir()
    (project / "docs" / "private-plan.md").write_text("private", encoding="utf-8")
    config = write_config(tmp_path, project)

    candidate, report = collect_candidate(config)
    rendered = json.dumps(candidate)

    assert "source=1" in rendered
    assert "docs=1" in rendered
    assert "private-plan.md" not in rendered
    assert "commit(s) in the last 30 days" in rendered
    assert report["projects"][0]["git"]["changed_path_categories"]["source"] == 1


def test_scanner_rejects_path_traversal(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = write_config(tmp_path, project, allow_files=["../private.md"])

    with pytest.raises(ManifestError, match="relative path"):
        collect_candidate(config)


def test_scanner_rejects_project_root_directory_link(tmp_path: Path) -> None:
    private = tmp_path / "private"
    private.mkdir()
    (private / "README.md").write_text("# Private\n", encoding="utf-8")
    linked = tmp_path / "linked"
    try:
        os.symlink(private, linked, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlinks are unavailable in this environment")
    config = write_config(tmp_path, linked)

    with pytest.raises(ManifestError, match="symlink or reparse point"):
        collect_candidate(config)


def test_scanner_rejects_source_code_even_when_explicitly_listed(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "main.py").write_text("print('private')", encoding="utf-8")
    config = write_config(tmp_path, project, allow_files=["main.py"])

    with pytest.raises(ManifestError, match="allowed metadata filename"):
        collect_candidate(config)


@pytest.mark.parametrize(
    "observed_path",
    [".env", ".env.local", ".git/config", "credentials.json", "private.sqlite3", "secrets/token.txt"],
)
def test_scanner_rejects_sensitive_observed_path_names(tmp_path: Path, observed_path: str) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = write_config(tmp_path, project, observe_paths=[observed_path])

    with pytest.raises(ManifestError, match="sensitive path"):
        collect_candidate(config)


def test_scanner_fails_closed_when_allowlisted_metadata_contains_secret(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Unsafe\n\napi_key=sk-example0123456789012345\n",
        encoding="utf-8",
    )
    config = write_config(tmp_path, project)

    with pytest.raises(ManifestError, match="likely secret"):
        collect_candidate(config)


def test_scanner_omits_unsafe_automatically_derived_summary(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Safe title\n\nRun from C:/Users/example/private/project before starting.\n",
        encoding="utf-8",
    )
    config = write_config(tmp_path, project)

    candidate, report = collect_candidate(config)

    assert "C:/Users" not in json.dumps(candidate)
    assert "no approved summary" in candidate["projects"][0]["summary"]
    assert report["projects"][0]["warnings"]


def test_scanner_extracts_bounded_open_items_from_approved_metadata_only(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Planned project\n\nSafe summary.\n\n- [ ] Ship the reviewed workflow\n- [x] Completed work\n",
        encoding="utf-8",
    )
    (project / "private.py").write_text("# TODO: must never be read", encoding="utf-8")
    config = write_config(tmp_path, project)

    candidate, report = collect_candidate(config)
    rendered = json.dumps(candidate)

    assert "Ship the reviewed workflow" in rendered
    assert "Completed work" not in rendered
    assert "must never be read" not in rendered
    assert "sample:file:README.md:line-5" in rendered
    assert candidate["projects"][0]["open_questions"] == [
        "Approved metadata open item from `README.md`: Ship the reviewed workflow"
    ]
    assert not any("Ship the reviewed workflow" in signal for signal in candidate["projects"][0]["signals"])
    assert report["projects"][0]["metadata_open_item_count"] == 1


def test_scanner_omits_absolute_path_from_metadata_open_item(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text(
        "# Safe\n\nSafe summary.\n\n- [ ] Open C:/Users/example/private.txt\n",
        encoding="utf-8",
    )
    config = write_config(tmp_path, project)

    candidate, report = collect_candidate(config)

    assert "C:/Users" not in json.dumps(candidate)
    assert report["projects"][0]["metadata_open_item_count"] == 0
    assert report["projects"][0]["warnings"]


def test_scanner_extracts_only_bounded_constraints_from_approved_sections(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "AGENTS.md").write_text(
        "# Agent contract\n\n## Product boundary\n\n- Never publish source code.\n"
        "- Keep facts and inference separate.\n\n## Workflow\n\n- Run an internal deployment command.\n",
        encoding="utf-8",
    )
    config = write_config(tmp_path, project, allow_files=["AGENTS.md"])

    candidate, _ = collect_candidate(config)

    assert candidate["projects"][0]["constraints"] == [
        "Never publish source code.",
        "Keep facts and inference separate.",
    ]
    assert "internal deployment" not in json.dumps(candidate)


def test_code_relationship_scan_flag_must_be_boolean(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Safe\n\nSafe summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project, code_relationship_scan="yes")

    with pytest.raises(ManifestError, match="must be a boolean"):
        collect_candidate(config)


def test_scan_then_build_is_a_two_step_approval_flow(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Review Me\n\nReviewable summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)

    scan_paths = scan_workspace(config, tmp_path / "review", observed_at="2026-08-12T12:00:00+08:00")
    bundle_paths = build_bundle(scan_paths.candidate_manifest, tmp_path / "publish")

    assert scan_paths.candidate_manifest.exists()
    assert scan_paths.report.exists()
    assert bundle_paths.markdown.exists()
    assert "Review Me" in bundle_paths.markdown.read_text(encoding="utf-8")
    assert str(project) not in scan_paths.candidate_manifest.read_text(encoding="utf-8")


def test_scanner_derives_graded_relationships_without_publishing_dependency_contents(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "README.md").write_text(
        "# Source\n\nSafe source.\n\nUses `target-project` for one documented workflow.\n",
        encoding="utf-8",
    )
    (target / "README.md").write_text("# Target\n\nSafe target.\n", encoding="utf-8")
    (source / "package.json").write_text(
        json.dumps(
            {
                "name": "source-project",
                "scripts": {"private": "run C:/Users/example/private.js"},
                "dependencies": {"target-project": "workspace:*"},
            }
        ),
        encoding="utf-8",
    )
    (target / "package.json").write_text(json.dumps({"name": "target-project"}), encoding="utf-8")
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Relationships",
            "summary": "Synthetic relationship test.",
            "current_focus": "Verify graded evidence.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [
            {
                "id": "source-project",
                "path": str(source),
                "allow_files": ["README.md"],
                "dependency_files": ["package.json"],
            },
            {
                "id": "target-project",
                "path": str(target),
                "allow_files": ["README.md"],
                "dependency_files": ["package.json"],
            },
        ],
        "relationships": [],
    }
    config_path = tmp_path / "relationships.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    candidate, report = collect_candidate(config_path)
    rendered = json.dumps(candidate)

    assert {(item["type"], item["target"]) for item in candidate["relationships"]} == {
        ("declared-dependency", "target-project"),
        ("document-reference", "target-project"),
    }
    assert "C:/Users" not in rendered
    assert report["relationships"]["declared_dependency"] == 1
    assert report["relationships"]["document_reference"] == 1
    assert report["source_code_bodies_read"] == 0


def test_scanner_rejects_nested_dependency_metadata_path(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = write_config(tmp_path, project, dependency_files=["nested/package.json"])

    with pytest.raises(ManifestError, match="root dependency metadata"):
        collect_candidate(config)


def test_scan_report_compares_with_previous_approved_manifest(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    readme = project / "README.md"
    readme.write_text("# First\n\nFirst summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)
    first = scan_workspace(config, tmp_path / "first", observed_at="2026-08-12T12:00:00+08:00")

    readme.write_text("# First\n\nChanged summary.\n", encoding="utf-8")
    second = scan_workspace(
        config,
        tmp_path / "second",
        previous_manifest=first.candidate_manifest,
        observed_at="2026-08-12T13:00:00+08:00",
    )
    report = json.loads(second.report.read_text(encoding="utf-8"))
    candidate = json.loads(second.candidate_manifest.read_text(encoding="utf-8"))

    assert report["changes"]["baseline_available"] is True
    assert report["changes"]["changed"] is True
    assert report["changes"]["changed_projects"] == ["sample"]
    assert report["changes"]["changed_project_fields"]["sample"] == ["summary"]
    assert report["previous_facts_sha256"]
    assert candidate["snapshot_changes"]["changed_projects"] == [{"id": "sample", "fields": ["summary"]}]
    assert candidate["snapshot_changes"]["previous_facts_sha256"] == report["previous_facts_sha256"]


def test_build_rejects_candidate_changed_after_hashing(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Original\n\nOriginal summary.\n", encoding="utf-8")
    config = write_config(tmp_path, project)
    scan_paths = scan_workspace(config, tmp_path / "review", observed_at="2026-08-12T12:00:00+08:00")
    candidate = json.loads(scan_paths.candidate_manifest.read_text(encoding="utf-8"))
    candidate["projects"][0]["summary"] = "Changed after review."
    scan_paths.candidate_manifest.write_text(json.dumps(candidate), encoding="utf-8")

    with pytest.raises(ManifestError, match="does not match"):
        build_bundle(scan_paths.candidate_manifest, tmp_path / "publish")


def test_scan_rejects_obvious_cloud_synced_review_directory(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "README.md").write_text("# Private review\n\nReview locally first.\n", encoding="utf-8")
    config = write_config(tmp_path, project)

    with pytest.raises(ManifestError, match="cloud-synced"):
        scan_workspace(config, tmp_path / "OneDrive" / "review")
