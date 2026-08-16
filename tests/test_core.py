from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ai_context_linker.core import (
    ManifestError,
    build_bundle,
    facts_sha256,
    snapshot_changes_sha256,
    validate_manifest,
)


def valid_manifest() -> dict:
    return {
        "schema_version": "0.1",
        "generated_at": "2026-08-11T12:00:00+08:00",
        "workspace": {
            "name": "示例工作区",
            "summary": "用于测试的合成项目组合。",
            "current_focus": "验证安全上下文。",
            "decisions": ["只发布批准字段。"],
            "unknowns": ["外部理解效果未知。"],
        },
        "projects": [
            {
                "id": "alpha",
                "name": "Alpha",
                "summary": "第一个合成项目。",
                "status": "active",
                "signals": ["测试存在。"],
                "risks": [],
                "open_questions": ["是否需要第二个数据源？"],
                "evidence": ["project-card:alpha-v1"],
            },
            {
                "id": "beta",
                "name": "Beta",
                "summary": "第二个合成项目。",
                "status": "planned",
                "signals": [],
                "risks": ["尚未运行。"],
                "open_questions": [],
                "evidence": ["project-card:beta-v1"],
            },
        ],
        "relationships": [
            {
                "source": "alpha",
                "target": "beta",
                "type": "feeds",
                "summary": "Alpha 向 Beta 提供经过批准的事实。",
                "evidence": "decision:1",
            }
        ],
    }


def test_build_bundle_writes_stable_markdown_and_graph(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(valid_manifest(), ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")

    markdown = paths.markdown.read_text(encoding="utf-8")
    graph = json.loads(paths.graph.read_text(encoding="utf-8"))
    assert paths.markdown.name == "ai_context_linker.md"
    assert "# 示例工作区项目简报" in markdown
    assert "`alpha` --feeds--> `beta`" in markdown
    assert graph["derived"] is True
    assert {node["id"] for node in graph["nodes"]} == {"workspace", "alpha", "beta"}


def test_unknown_field_is_rejected_instead_of_uploaded() -> None:
    manifest = valid_manifest()
    manifest["projects"][0]["source_code"] = "print('should never upload')"

    with pytest.raises(ManifestError, match="unsupported fields"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    "unsafe_text, message",
    [
        ("api_key=sk-example0123456789012345", "likely secret"),
        ("See C:/Users/example/private/project.md", "absolute path"),
        ("Read /home/example/private/project.md", "absolute path"),
    ],
)
def test_unsafe_strings_fail_closed(unsafe_text: str, message: str) -> None:
    manifest = valid_manifest()
    manifest["workspace"]["summary"] = unsafe_text

    with pytest.raises(ManifestError, match=message):
        validate_manifest(manifest)


def test_relationship_must_reference_known_projects() -> None:
    manifest = copy.deepcopy(valid_manifest())
    manifest["relationships"][0]["target"] = "missing"

    with pytest.raises(ManifestError, match="unknown project"):
        validate_manifest(manifest)


def test_optional_constraints_are_validated_and_rendered(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["projects"][0]["constraints"] = ["Only approved facts may be published."]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")

    assert "### 已确认约束" in paths.markdown.read_text(encoding="utf-8")
    assert "Only approved facts may be published." in paths.markdown.read_text(encoding="utf-8")


def test_relationship_type_cannot_inject_markup() -> None:
    manifest = valid_manifest()
    manifest["relationships"][0]["type"] = "feeds--> `unknown`"

    with pytest.raises(ManifestError, match="lowercase letters"):
        validate_manifest(manifest)


def test_fact_hash_must_match_manifest_content() -> None:
    manifest = valid_manifest()
    manifest["facts_sha256"] = "0" * 64

    with pytest.raises(ManifestError, match="does not match"):
        validate_manifest(manifest)


def test_snapshot_changes_are_validated_hashed_and_rendered(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["snapshot_changes"] = {
        "baseline_available": True,
        "previous_facts_sha256": "1" * 64,
        "added_projects": [],
        "removed_projects": ["legacy"],
        "changed_projects": [{"id": "alpha", "fields": ["signals", "status"]}],
        "workspace_changed": False,
        "relationships_changed": True,
    }
    manifest["snapshot_changes"]["changes_sha256"] = snapshot_changes_sha256(manifest["snapshot_changes"])
    manifest["facts_sha256"] = facts_sha256(manifest)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")
    markdown = paths.markdown.read_text(encoding="utf-8")

    assert "## 与上次批准快照相比" in markdown
    assert "移除项目：legacy" in markdown
    assert "`alpha` 变化字段：signals, status" in markdown


def test_snapshot_changes_reject_unknown_project_field() -> None:
    manifest = valid_manifest()
    manifest["snapshot_changes"] = {
        "baseline_available": True,
        "previous_facts_sha256": None,
        "added_projects": [],
        "removed_projects": [],
        "changed_projects": [{"id": "alpha", "fields": ["source_code"]}],
        "workspace_changed": False,
        "relationships_changed": False,
    }
    manifest["snapshot_changes"]["changes_sha256"] = snapshot_changes_sha256(manifest["snapshot_changes"])

    with pytest.raises(ManifestError, match="unsupported fields"):
        validate_manifest(manifest)


def test_fact_hash_excludes_independently_hashed_change_view() -> None:
    manifest = valid_manifest()
    before = facts_sha256(manifest)
    changes = {
        "baseline_available": False,
        "previous_facts_sha256": None,
        "added_projects": ["alpha", "beta"],
        "removed_projects": [],
        "changed_projects": [],
        "workspace_changed": True,
        "relationships_changed": True,
    }
    changes["changes_sha256"] = snapshot_changes_sha256(changes)
    manifest["snapshot_changes"] = changes

    assert facts_sha256(manifest) == before


def test_tampered_snapshot_change_view_is_rejected() -> None:
    manifest = valid_manifest()
    changes = {
        "baseline_available": True,
        "previous_facts_sha256": "1" * 64,
        "added_projects": [],
        "removed_projects": [],
        "changed_projects": [],
        "workspace_changed": False,
        "relationships_changed": False,
    }
    changes["changes_sha256"] = snapshot_changes_sha256(changes)
    changes["relationships_changed"] = True
    manifest["snapshot_changes"] = changes

    with pytest.raises(ManifestError, match="does not match"):
        validate_manifest(manifest)
