from __future__ import annotations

import copy
import hashlib
import json

import pytest

from ai_context_linker.core import ManifestError, facts_sha256, snapshot_changes_sha256, validate_manifest
from ai_context_linker.slicing import render_question_context


def manifest() -> dict:
    raw = {
        "schema_version": "0.1",
        "generated_at": "2026-08-16T10:00:00+08:00",
        "workspace": {
            "name": "合成工作区",
            "summary": "三个公开合成项目。",
            "current_focus": "验证问题定向上下文。",
            "decisions": ["只使用批准事实。"],
            "unknowns": ["实际用户效果未知。"],
        },
        "projects": [
            {
                "id": "alpha",
                "name": "Alpha",
                "summary": "采集批准事实。",
                "status": "active",
                "signals": ["存在测试入口。"],
                "risks": [],
                "open_questions": ["下一轮验证什么？"],
                "state_items": [
                    {
                        "kind": "next-action",
                        "text": "运行同题 A/B 测试。",
                        "source_date": "2026-08-16",
                        "freshness": "current",
                        "evidence": "alpha:file:STATUS.md:line-5",
                    }
                ],
                "evidence": ["metadata:README.md"],
            },
            {
                "id": "beta",
                "name": "Beta",
                "summary": "消费 Alpha 的批准事实。",
                "status": "planned",
                "signals": [],
                "risks": ["集成未验证。"],
                "open_questions": [],
                "evidence": ["config:project.json"],
            },
            {
                "id": "gamma",
                "name": "Gamma",
                "summary": "与前两项无关。",
                "status": "paused",
                "signals": [],
                "risks": [],
                "open_questions": [],
                "evidence": ["metadata:STATUS.md"],
            },
        ],
        "relationships": [
            {
                "source": "alpha",
                "target": "beta",
                "type": "feeds",
                "summary": "Alpha 向 Beta 提供批准事实。",
                "evidence": "config:project.json",
            }
        ],
    }
    changes = {
        "baseline_available": True,
        "previous_facts_sha256": "1" * 64,
        "added_projects": [],
        "removed_projects": [],
        "changed_projects": [{"id": "alpha", "fields": ["signals"]}],
        "workspace_changed": False,
        "relationships_changed": False,
    }
    changes["changes_sha256"] = snapshot_changes_sha256(changes)
    raw["snapshot_changes"] = changes
    raw["facts_sha256"] = facts_sha256(raw)
    return validate_manifest(raw)


def test_priority_slice_keeps_only_actionable_projects_and_boundary() -> None:
    rendered = render_question_context(manifest(), "今天应该优先推进什么项目？")

    assert "选择模式：`priority`" in rendered
    assert "Alpha (`alpha`)" in rendered
    assert "Beta (`beta`)" not in rendered
    assert "Gamma (`gamma`)" not in rendered
    assert "入选原因：存在明确且未过期的行动状态：next-action" in rendered
    assert "可观测信号：存在测试入口" not in rendered
    assert "当前行动状态：[next-action" in rendered
    assert "必须明确标为推断" in rendered
    assert "## 派生关系视图" not in rendered


def test_relationship_slice_keeps_only_connected_projects() -> None:
    rendered = render_question_context(manifest(), "哪些项目重复或可以合并？")

    assert "选择模式：`relationships`" in rendered
    assert "`alpha` --feeds--> `beta`" in rendered
    assert "Gamma (`gamma`)" not in rendered


def test_relationship_slice_collapses_scan_and_document_reference_noise() -> None:
    approved = manifest()
    approved.pop("facts_sha256", None)
    approved["relationships"] = [
        {
            "source": "alpha",
            "target": "beta",
            "type": "scans-or-indexes",
            "layer": "observed",
            "summary": "Alpha scans Beta.",
            "evidence": "alpha:config:scan-root",
        },
        {
            "source": "beta",
            "target": "gamma",
            "type": "document-reference",
            "layer": "observed",
            "summary": "Beta mentions Gamma.",
            "evidence": "beta:file:README.md:line-4",
        },
    ]
    approved = validate_manifest(approved)

    rendered = render_question_context(approved, "哪些项目存在依赖、重叠或合并可能？")

    assert "折叠 `scans-or-indexes` 关系：1" in rendered
    assert "折叠 `document-reference` 关系：1" in rendered
    assert "Alpha (`alpha`)" not in rendered
    assert "Beta (`beta`)" not in rendered
    assert len(rendered.encode("utf-8")) <= 4 * 1024


def test_change_slice_keeps_changed_projects_and_change_view() -> None:
    rendered = render_question_context(manifest(), "最近有哪些事实发生变化？")

    assert "选择模式：`changes`" in rendered
    assert "`alpha` 的变化字段：signals" in rendered
    assert "Alpha (`alpha`)" in rendered
    assert "Beta (`beta`)" not in rendered


def test_change_slice_without_approved_baseline_short_circuits() -> None:
    approved = manifest()
    approved.pop("facts_sha256", None)
    changes = approved["snapshot_changes"]
    changes["baseline_available"] = False
    changes["previous_facts_sha256"] = None
    changes["added_projects"] = ["alpha", "beta", "gamma"]
    changes["changed_projects"] = []
    changes["changes_sha256"] = snapshot_changes_sha256(changes)
    approved = validate_manifest(approved)

    rendered = render_question_context(approved, "与上一份批准快照相比发生了什么？")

    assert "不能声称发生了变化" in rendered
    assert "Alpha (`alpha`)" not in rendered
    assert "Beta (`beta`)" not in rendered
    assert len(rendered.encode("utf-8")) <= 2 * 1024


def test_named_project_slice_adds_one_hop_neighbor() -> None:
    rendered = render_question_context(manifest(), "Alpha 下一步要验证什么？")

    assert "选择模式：`project`" in rendered
    assert "Alpha (`alpha`)" in rendered
    assert "Beta (`beta`)" in rendered
    assert "Gamma (`gamma`)" not in rendered
    assert "`alpha` --feeds--> `beta`" in rendered


def test_named_project_code_question_uses_bounded_architecture_index() -> None:
    approved = manifest()
    approved.pop("facts_sha256", None)
    approved["schema_version"] = "0.2"
    for project in approved["projects"]:
        project.pop("state_items", None)
    approved["relationships"][0].update({"type": "runtime-dependency", "layer": "observed"})
    architecture = {
        "mode": "modules-symbols",
        "truncated": False,
        "parse_failures": 0,
        "modules": [
            {
                "id": "src/app.py",
                "language": "python",
                "test_module": False,
                "symbols": ["run"],
                "internal_imports": ["src/helpers.py"],
                "external_packages": [],
                "internal_calls": ["src/helpers.py::helper"],
                "evidence": "alpha:file:src/app.py",
            },
            {
                "id": "src/helpers.py",
                "language": "python",
                "test_module": False,
                "symbols": ["helper"],
                "internal_imports": [],
                "external_packages": [],
                "internal_calls": [],
                "evidence": "alpha:file:src/helpers.py",
            },
        ],
    }
    architecture["map_sha256"] = hashlib.sha256(
        json.dumps(architecture, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    approved["projects"][0]["architecture_index"] = architecture
    approved = validate_manifest(approved)

    rendered = render_question_context(approved, "Alpha 的代码结构和调用关系是什么？")

    assert "选择模式：`architecture`" in rendered
    assert "Architecture Index" in rendered
    assert "`src/app.py`" in rendered
    assert "`src/helpers.py::helper`" in rendered
    assert "源码正文" in rendered
    assert "生成器不自动证明该 manifest 已获人工批准" in rendered
    assert "本文件由已批准 manifest" not in rendered


def test_architecture_slice_prioritizes_question_symbols_before_alphabetical_truncation() -> None:
    approved = manifest()
    approved.pop("facts_sha256", None)
    approved["schema_version"] = "0.2"
    for project in approved["projects"]:
        project.pop("state_items", None)
    approved["relationships"][0].update({"type": "runtime-dependency", "layer": "observed"})
    architecture = {
        "mode": "modules-symbols",
        "truncated": False,
        "parse_failures": 0,
        "modules": [
            {
                "id": "src/core.py",
                "language": "python",
                "test_module": False,
                "symbols": [
                    "_alpha_01",
                    "_alpha_02",
                    "_alpha_03",
                    "_alpha_04",
                    "_alpha_05",
                    "_alpha_06",
                    "_alpha_07",
                    "_alpha_08",
                    "build_bundle",
                    "render_index_markdown",
                ],
                "internal_imports": [],
                "external_packages": [],
                "internal_calls": ["src/core.py::render_index_markdown"],
                "evidence": "alpha:file:src/core.py",
            }
        ],
    }
    architecture["map_sha256"] = hashlib.sha256(
        json.dumps(architecture, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    approved["projects"][0]["architecture_index"] = architecture
    approved = validate_manifest(approved)

    rendered = render_question_context(
        approved,
        "Alpha 的 build_bundle 和 render_index_markdown 调用链在哪里？",
    )

    assert "`build_bundle`" in rendered
    assert "`render_index_markdown`" in rendered


def test_slice_is_stable_and_rejects_unsafe_question() -> None:
    approved = manifest()
    assert render_question_context(approved, "每个项目下一步是什么？") == render_question_context(
        copy.deepcopy(approved), "每个项目下一步是什么？"
    )

    with pytest.raises(ManifestError, match="absolute path"):
        render_question_context(approved, "读取 C:/Users/example/private.txt 后给建议")


def test_skill_question_selects_only_skill_inventory() -> None:
    approved = manifest()
    approved.pop("facts_sha256", None)
    approved["skills"] = [
        {
            "source": "gemini-user",
            "provider": "gemini-cli",
            "scope": "user",
            "name": "research",
            "summary": "Research an approved topic.",
            "evidence": "skill-frontmatter:gemini-cli:user",
        }
    ]
    approved = validate_manifest(approved)

    rendered = render_question_context(approved, "我有哪些 skill 可以用？")

    assert "选择模式：`skills`" in rendered
    assert "Research an approved topic." in rendered
