from __future__ import annotations

import copy

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


def test_priority_slice_keeps_all_project_facts_and_boundary() -> None:
    rendered = render_question_context(manifest(), "今天应该优先推进什么项目？")

    assert "选择模式：`priority`" in rendered
    assert all(project_id in rendered for project_id in ("alpha", "beta", "gamma"))
    assert "必须明确标为推断" in rendered
    assert "## 派生关系视图" not in rendered


def test_relationship_slice_keeps_only_connected_projects() -> None:
    rendered = render_question_context(manifest(), "哪些项目重复或可以合并？")

    assert "选择模式：`relationships`" in rendered
    assert "`alpha` --feeds--> `beta`" in rendered
    assert "Gamma (`gamma`)" not in rendered


def test_change_slice_keeps_changed_projects_and_change_view() -> None:
    rendered = render_question_context(manifest(), "最近有哪些事实发生变化？")

    assert "选择模式：`changes`" in rendered
    assert "`alpha` 的变化字段：signals" in rendered
    assert "Alpha (`alpha`)" in rendered
    assert "Beta (`beta`)" not in rendered


def test_named_project_slice_adds_one_hop_neighbor() -> None:
    rendered = render_question_context(manifest(), "Alpha 下一步要验证什么？")

    assert "选择模式：`project`" in rendered
    assert "Alpha (`alpha`)" in rendered
    assert "Beta (`beta`)" in rendered
    assert "Gamma (`gamma`)" not in rendered
    assert "`alpha` --feeds--> `beta`" in rendered


def test_slice_is_stable_and_rejects_unsafe_question() -> None:
    approved = manifest()
    assert render_question_context(approved, "每个项目下一步是什么？") == render_question_context(
        copy.deepcopy(approved), "每个项目下一步是什么？"
    )

    with pytest.raises(ManifestError, match="absolute path"):
        render_question_context(approved, "读取 C:/Users/example/private.txt 后给建议")
