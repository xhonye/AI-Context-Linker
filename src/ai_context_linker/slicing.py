from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import ManifestError, load_manifest, validate_publish_text


CHANGE_TERMS = ("变化", "变更", "最近", "上次", "changed", "change", "recent", "since")
RELATIONSHIP_TERMS = (
    "关系",
    "重复",
    "合并",
    "依赖",
    "关联",
    "relationship",
    "duplicate",
    "merge",
    "dependency",
    "related",
)
PRIORITY_TERMS = (
    "今天",
    "推进",
    "下一步",
    "优先",
    "先做",
    "today",
    "next",
    "priority",
    "prioritize",
)
SKILL_TERMS = ("skill", "skills", "技能", "能力", "工具", "capability", "tooling")


@dataclass(frozen=True)
class QuestionContextPaths:
    markdown: Path


def _normalized_question(question: str) -> str:
    normalized = " ".join(question.split())
    if not normalized:
        raise ManifestError("question must not be empty")
    if len(normalized) > 500:
        raise ManifestError("question must be at most 500 characters")
    validate_publish_text(normalized, "question")
    return normalized


def _mentions_project(question: str, project: dict[str, Any]) -> bool:
    lowered = question.casefold()
    candidates = {project["id"].casefold(), project["name"].casefold()}
    for candidate in candidates:
        if len(candidate) < 3:
            continue
        if re.search(rf"(?<![\w-]){re.escape(candidate)}(?![\w-])", lowered):
            return True
    return False


def _mode_and_projects(manifest: dict[str, Any], question: str) -> tuple[str, list[dict[str, Any]]]:
    projects = manifest["projects"]
    mentioned = {project["id"] for project in projects if _mentions_project(question, project)}
    lowered = question.casefold()

    if mentioned:
        selected = set(mentioned)
        for relationship in manifest["relationships"]:
            if relationship["source"] in mentioned or relationship["target"] in mentioned:
                selected.update((relationship["source"], relationship["target"]))
        return "project", [project for project in projects if project["id"] in selected]

    if any(term in lowered for term in SKILL_TERMS):
        return "skills", []

    if any(term in lowered for term in CHANGE_TERMS):
        changes = manifest.get("snapshot_changes")
        changed_ids: set[str] = set()
        if changes:
            changed_ids.update(changes["added_projects"])
            changed_ids.update(change["id"] for change in changes["changed_projects"])
        return "changes", [project for project in projects if project["id"] in changed_ids]

    if any(term in lowered for term in RELATIONSHIP_TERMS):
        connected = {
            project_id
            for relationship in manifest["relationships"]
            for project_id in (relationship["source"], relationship["target"])
        }
        return "relationships", [project for project in projects if project["id"] in connected]

    if any(term in lowered for term in PRIORITY_TERMS):
        return "priority", projects

    return "overview", projects


def _inline_items(items: list[str]) -> str:
    return "；".join(items) if items else "未记录"


def _render_changes(changes: dict[str, Any] | None) -> list[str]:
    lines = ["## 已确认的快照变化", ""]
    if not changes:
        return lines + ["- 当前批准 manifest 没有变化视图，变化未知。", ""]
    if not changes["baseline_available"]:
        return lines + ["- 没有上一份批准快照，本次仅建立基线，不能声称发生了变化。", ""]
    lines.extend(
        [
            f"- 新增项目：{_inline_items(changes['added_projects'])}",
            f"- 移除项目：{_inline_items(changes['removed_projects'])}",
            f"- 工作区描述变化：{'是' if changes['workspace_changed'] else '否'}",
            f"- 派生关系变化：{'是' if changes['relationships_changed'] else '否'}",
        ]
    )
    for change in changes["changed_projects"]:
        lines.append(f"- `{change['id']}` 的变化字段：{', '.join(change['fields'])}")
    lines.append("")
    return lines


def render_question_context(manifest: dict[str, Any], question: str) -> str:
    question = _normalized_question(question)
    mode, projects = _mode_and_projects(manifest, question)
    selected_ids = {project["id"] for project in projects}
    workspace = manifest["workspace"]
    facts_hash = manifest.get("facts_sha256", "未提供")
    lines = [
        f"# {workspace['name']}问题定向简报",
        "",
        "> 本文件由已批准 manifest 确定性裁剪，不读取源码，也不包含 AI 总结。",
        f"> 来源事实快照：`{facts_hash}`",
        f"> 选择模式：`{mode}`",
        "",
        "## 当前问题",
        "",
        f"> {question}",
        "",
        "## 已确认的工作区事实",
        "",
        workspace["summary"],
        "",
        f"- 当前关注：{workspace['current_focus']}",
        f"- 已确认决策：{_inline_items(workspace['decisions'])}",
        "",
    ]
    if mode == "changes":
        lines.extend(_render_changes(manifest.get("snapshot_changes")))

    if mode == "skills":
        lines.extend(
            [
                "## 可用 Skills",
                "",
                "> 仅列出批准发布的名称与摘要，不包含 Skill 指令正文或本机目录。",
                "",
            ]
        )
        if manifest.get("skills"):
            for skill in manifest["skills"]:
                lines.append(
                    f"- **{skill['name']}** · `{skill['provider']}` / `{skill['scope']}`：{skill['summary']}"
                )
        else:
            lines.append("- 当前批准 manifest 没有 Skill 清单。")
        lines.append("")

    lines.extend(["## 与问题相关的项目事实", ""])
    if projects:
        for project in projects:
            lines.extend(
                [
                    f"### {project['name']} (`{project['id']}`)",
                    "",
                    project["summary"],
                    "",
                    f"- 记录状态：{project['status']}",
                    f"- 可观测信号：{_inline_items(project['signals'])}",
                    f"- 已确认约束：{_inline_items(project.get('constraints', []))}",
                    f"- 风险：{_inline_items(project['risks'])}",
                    f"- 开放问题：{_inline_items(project['open_questions'])}",
                    f"- 证据锚点：{_inline_items(project['evidence'])}",
                    "",
                ]
            )
    else:
        lines.extend(["- 当前批准事实中没有可确定性选中的项目。", ""])

    if mode in {"relationships", "project"}:
        lines.extend(["## 派生关系视图", "", "> 关系由批准事实派生，可重建，不等同于源码级依赖证明。", ""])
        relevant = [
            relationship
            for relationship in manifest["relationships"]
            if relationship["source"] in selected_ids and relationship["target"] in selected_ids
        ]
        if relevant:
            for relationship in relevant:
                lines.append(
                    f"- `{relationship['source']}` --{relationship['type']}--> `{relationship['target']}`："
                    f"{relationship['summary']}（证据：{relationship['evidence']}）"
                )
        else:
            lines.append("- 没有与本题匹配的已确认关系。")
        lines.append("")

    lines.extend(
        [
            "## 未知与讨论边界",
            "",
            f"- 工作区未知：{_inline_items(workspace['unknowns'])}",
            "- 项目优先级、价值和真实使用效果不是扫描事实；如需排序，ChatGPT 必须明确标为推断并说明依据。",
            "- 不得仅从提交数、文件数、测试文件数或未完成事项推断项目价值。",
            "- 证据不足时应回答未知，并只请求最小必要的脱敏补充。",
            "",
        ]
    )
    rendered = "\n".join(lines)
    validate_publish_text(rendered, "question context")
    return rendered


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    file_descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent, text=True)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary_name, path)
    except Exception:
        Path(temporary_name).unlink(missing_ok=True)
        raise


def build_question_context(
    manifest_path: Path | str,
    question: str,
    output_dir: Path | str,
) -> QuestionContextPaths:
    manifest = load_manifest(manifest_path)
    markdown = render_question_context(manifest, question)
    destination = Path(output_dir).resolve() / "ai_context_linker.question.md"
    _atomic_write_text(destination, markdown)
    return QuestionContextPaths(markdown=destination)
