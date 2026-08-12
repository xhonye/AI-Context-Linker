from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError, build_bundle, validate_manifest


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
