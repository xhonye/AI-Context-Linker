from __future__ import annotations

import copy

import pytest

from ai_context_linker.core import ManifestError, facts_sha256, validate_manifest
from ai_context_linker.slicing import render_question_context
from ai_context_linker.state_records import make_state_record


def _record(project_id: str, kind: str, text: str, *, status: str = "open") -> dict:
    return make_state_record(
        project_id=project_id,
        kind=kind,
        text=text,
        source_kind="approved-review",
        source_ref=f"{project_id}:approved-review:{kind}",
        observed_at="2026-08-28T09:00:00+08:00",
        status=status,
    )


def _project(project_id: str, records: list[dict], *, summary: str | None = None) -> dict:
    return {
        "id": project_id,
        "name": project_id.title(),
        "summary": summary or f"Synthetic {project_id} project.",
        "status": "unknown; no approved activity state",
        "signals": ["Git reports recent activity; this must not establish priority."],
        "constraints": [f"Unrelated {project_id} GUI and brand constraint."],
        "risks": [],
        "open_questions": [],
        "state_items": records,
        "evidence": [f"{project_id}:file:README.md"],
    }


def manifest() -> dict:
    projects = [
        _project(
            "today",
            [
                _record("today", "attention", "today"),
                _record("today", "activity", "active"),
                _record("today", "why-now", "The approved acceptance window closes soon."),
                _record("today", "current-goal", "Ship the approved action slice."),
                _record("today", "blocker", "Waiting for dependency."),
                _record("today", "next-action", "Run the priority fixture."),
                _record("today", "done-when", "The fixed output is complete."),
            ],
        ),
        _project("deadline", [_record("deadline", "deadline", "2026-08-29")]),
        _project("blocked", [_record("blocked", "blocker", "Waiting for an approved decision.")]),
        _project(
            "active-next",
            [_record("active-next", "activity", "active"), _record("active-next", "next-action", "Run later.")],
        ),
        _project("dependency", [], summary="Private brand and GUI details that must not enter endpoint output."),
        _project("git-only", []),
    ]
    raw = {
        "schema_version": "0.2",
        "generated_at": "2026-08-28T12:00:00+08:00",
        "workspace": {
            "name": "Priority fixture",
            "summary": "Synthetic action-priority workspace.",
            "current_focus": "Use approved action records.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": projects,
        "relationships": [
            {
                "source": "today",
                "target": "dependency",
                "type": "blocked-by",
                "layer": "observed",
                "summary": "The main project waits for the dependency.",
                "evidence": "today:approved-review:blocker",
            }
        ],
        "skills": [
            {
                "source": "synthetic-skills",
                "provider": "codex",
                "scope": "workspace",
                "name": "private-skill-list",
                "summary": "Must not appear in the default priority slice.",
                "evidence": "skill-frontmatter:codex:workspace",
            }
        ],
    }
    normalized = validate_manifest(raw)
    normalized["facts_sha256"] = facts_sha256(normalized)
    return validate_manifest(normalized)


def test_priority_v2_uses_fixed_order_three_project_cap_and_minimal_endpoint() -> None:
    rendered = render_question_context(manifest(), "今天推进什么，卡在哪里，下一步是什么？")

    assert rendered.index("Today (`today`)") < rendered.index("Deadline (`deadline`)")
    assert rendered.index("Deadline (`deadline`)") < rendered.index("Blocked (`blocked`)")
    assert "Active-Next (`active-next`)" not in rendered
    assert "Git-Only (`git-only`)" not in rendered
    assert "## 依赖端点" in rendered
    assert "Dependency (`dependency`)" in rendered
    assert "Private brand and GUI details" not in rendered
    assert "Unrelated dependency GUI and brand constraint" not in rendered
    assert "private-skill-list" not in rendered
    assert "排序依据：`approved-priority`" in rendered


def test_priority_v2_renders_fixed_action_fields_and_evidence() -> None:
    rendered = render_question_context(manifest(), "今天应该推进什么？")

    assert "- 当前状态：active" in rendered
    assert "- 入选原因：approved attention=today" in rendered
    assert "- 为什么现在做：The approved acceptance window closes soon." in rendered
    assert "today:approved-review:why-now" in rendered
    assert "- 当前目标：Ship the approved action slice." in rendered
    assert "- 当前卡点：Waiting for dependency." in rendered
    assert "- 下一步：Run the priority fixture." in rendered
    assert "- 完成标准：The fixed output is complete." in rendered
    assert "- 依赖：`today` --blocked-by--> `dependency`" in rendered
    assert "- 未知：未记录" in rendered
    assert "- 证据：" in rendered
    assert "## 今日不选" in rendered
    assert "`active-next`：active 且有 next_action，但位于三项目上限之后" in rendered
    assert "其余 1 个项目：没有获批的当前优先级或行动证据" in rendered


def test_explicit_p0_priority_ranks_before_attention_today() -> None:
    approved = manifest()
    deadline = next(project for project in approved["projects"] if project["id"] == "deadline")
    deadline["state_items"].append(_record("deadline", "priority", "P0"))
    approved.pop("facts_sha256", None)
    approved = validate_manifest(approved)

    rendered = render_question_context(approved, "今天应该推进什么？")

    assert rendered.index("Deadline (`deadline`)") < rendered.index("Today (`today`)")
    assert "- 人工优先级：P0" in rendered
    assert "- 入选原因：approved priority=P0" in rendered


def test_more_than_three_p0_p1_projects_fails_closed() -> None:
    approved = manifest()
    for project in approved["projects"][:4]:
        project["state_items"].append(_record(project["id"], "priority", "P1"))
    approved.pop("facts_sha256", None)
    approved = validate_manifest(approved)

    with pytest.raises(ManifestError, match="more than three projects"):
        render_question_context(approved, "今天应该推进什么？")


def test_priority_v2_marks_non_human_order_as_derived_recommendation() -> None:
    approved = manifest()
    today = next(project for project in approved["projects"] if project["id"] == "today")
    today["state_items"] = [record for record in today["state_items"] if record["kind"] != "attention"]
    approved.pop("facts_sha256", None)
    approved = validate_manifest(approved)

    rendered = render_question_context(approved, "今天应该推进什么？")

    assert "排序依据：`derived-recommendation`" in rendered


def test_resolved_blocker_is_not_selected_and_output_is_deterministic() -> None:
    approved = manifest()
    blocked = next(project for project in approved["projects"] if project["id"] == "blocked")
    blocked["state_items"][0]["status"] = "resolved"
    approved.pop("facts_sha256", None)
    approved = validate_manifest(approved)

    first = render_question_context(approved, "今天应该推进什么？")
    second = render_question_context(copy.deepcopy(approved), "今天应该推进什么？")

    assert "Blocked (`blocked`)" not in first
    assert first == second


def test_priority_slice_resolves_expiry_before_selection() -> None:
    approved = manifest()
    blocked = next(project for project in approved["projects"] if project["id"] == "blocked")
    blocked["state_items"][0]["expires_at"] = "2026-08-28T10:00:00+08:00"
    approved.pop("facts_sha256", None)
    approved = validate_manifest(approved)

    rendered = render_question_context(approved, "今天应该推进什么？")

    assert "Blocked (`blocked`)" not in rendered


@pytest.mark.parametrize("status", ["resolved", "superseded", "stale", "needs_review"])
def test_priority_why_now_does_not_promote_closed_or_unreviewed_reason(status: str) -> None:
    approved = manifest()
    today = next(project for project in approved["projects"] if project["id"] == "today")
    reason = next(item for item in today["state_items"] if item["kind"] == "why-now")
    reason["status"] = status
    approved.pop("facts_sha256", None)

    rendered = render_question_context(validate_manifest(approved), "今天应该推进什么？")

    assert "- 为什么现在做：unknown" in rendered
    assert "The approved acceptance window closes soon." not in rendered


def test_priority_why_now_expires_before_rendering() -> None:
    approved = manifest()
    today = next(project for project in approved["projects"] if project["id"] == "today")
    reason = next(item for item in today["state_items"] if item["kind"] == "why-now")
    reason["expires_at"] = "2026-08-28T10:00:00+08:00"
    approved.pop("facts_sha256", None)

    rendered = render_question_context(validate_manifest(approved), "今天应该推进什么？")

    assert "- 为什么现在做：unknown" in rendered
    assert "The approved acceptance window closes soon." not in rendered
