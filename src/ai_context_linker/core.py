"""Strict manifest validation and deterministic context rendering.

The publisher accepts only a small, explicitly approved manifest and fails
closed when the payload contains an unknown field, a likely secret, or a
machine-specific absolute path. The optional scanner reads approved metadata by
default; a separately enabled relationship adapter may inspect bounded local
code/config files but cannot publish their text or absolute roots.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "0.1"

ROOT_KEYS = {
    "schema_version",
    "generated_at",
    "facts_sha256",
    "workspace",
    "projects",
    "relationships",
    "skills",
    "snapshot_changes",
}
WORKSPACE_KEYS = {"name", "summary", "current_focus", "decisions", "unknowns"}
PROJECT_KEYS = {
    "id",
    "name",
    "summary",
    "status",
    "signals",
    "constraints",
    "risks",
    "open_questions",
    "evidence",
}
RELATIONSHIP_KEYS = {"source", "target", "type", "summary", "evidence"}
SKILL_KEYS = {"source", "provider", "scope", "name", "summary", "evidence"}
SNAPSHOT_CHANGE_KEYS = {
    "changes_sha256",
    "baseline_available",
    "previous_facts_sha256",
    "added_projects",
    "removed_projects",
    "changed_projects",
    "workspace_changed",
    "relationships_changed",
    "skills_changed",
}
PROJECT_CHANGE_KEYS = {"id", "fields"}

SECRET_PATTERNS = (
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----", re.I),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I),
    re.compile(r"\b(?:password|passwd|api[_-]?key|secret|token)\s*[:=]\s*\S+", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}"),
    re.compile(r"\bgh[opusr]_[A-Za-z0-9]{20,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
)

ABSOLUTE_PATH_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s`]*"),
    re.compile(r"(?<![A-Za-z0-9])/(?:Users|home|mnt|var|etc|opt)/[^\s`]+", re.I),
)
SKILL_ADDRESS_PATTERNS = (
    re.compile(r"https?://\S+", re.I),
    re.compile(r"(?<![\w.-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
    re.compile(r"(?<!\d)(?:\d{1,3}\.){3}\d{1,3}(?::\d{1,5})?(?!\d)"),
    re.compile(r"\\\\[^\s\\]+\\[^\s]+"),
)

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


class ManifestError(ValueError):
    """Raised when a manifest is unsafe or outside the V0.1 contract."""


@dataclass(frozen=True)
class BundlePaths:
    markdown: Path
    graph: Path


def facts_sha256(manifest: dict[str, Any]) -> str:
    """Hash fact content while excluding observation time and the digest itself."""
    payload = dict(manifest)
    payload.pop("generated_at", None)
    payload.pop("facts_sha256", None)
    payload.pop("snapshot_changes", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_changes_sha256(changes: dict[str, Any]) -> str:
    """Hash the derived snapshot-change view independently from current facts."""
    payload = dict(changes)
    payload.pop("changes_sha256", None)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    return value


def _require_list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ManifestError(f"{label} must be an array")
    return value


def _require_string(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ManifestError(f"{label} must be a string")
    stripped = value.strip()
    if not allow_empty and not stripped:
        raise ManifestError(f"{label} must not be empty")
    if len(stripped) > 4000:
        raise ManifestError(f"{label} exceeds the 4000 character safety limit")
    return stripped


def _check_keys(mapping: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(mapping) - allowed)
    if unknown:
        raise ManifestError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _walk_strings(value: Any, label: str = "manifest") -> list[tuple[str, str]]:
    found: list[tuple[str, str]] = []
    if isinstance(value, str):
        found.append((label, value))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.extend(_walk_strings(item, f"{label}[{index}]"))
    elif isinstance(value, dict):
        for key, item in value.items():
            found.extend(_walk_strings(item, f"{label}.{key}"))
    return found


def _validate_safe_strings(manifest: dict[str, Any]) -> None:
    for label, text in _walk_strings(manifest):
        validate_publish_text(text, label)


def validate_publish_text(text: str, label: str = "text") -> None:
    """Reject text that must not enter a publishable context artifact."""
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise ManifestError(f"{label} contains a likely secret")
    for pattern in ABSOLUTE_PATH_PATTERNS:
        if pattern.search(text):
            raise ManifestError(f"{label} contains a machine-specific absolute path")


def validate_skill_summary(text: str, label: str = "skill summary") -> None:
    """Apply stricter checks to automatically published Skill descriptions."""
    validate_publish_text(text, label)
    for pattern in SKILL_ADDRESS_PATTERNS:
        if pattern.search(text):
            raise ManifestError(f"{label} contains a potentially sensitive address")


def _validate_string_list(value: Any, label: str) -> list[str]:
    return [_require_string(item, f"{label}[{index}]") for index, item in enumerate(_require_list(value, label))]


def _require_bool(value: Any, label: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestError(f"{label} must be a boolean")
    return value


def _validate_identifier_list(value: Any, label: str) -> list[str]:
    items = _validate_string_list(value, label)
    for index, item in enumerate(items):
        if not ID_PATTERN.fullmatch(item):
            raise ManifestError(f"{label}[{index}] must be a project identifier")
    return sorted(set(items))


def _validate_snapshot_changes(value: Any) -> dict[str, Any]:
    changes = _require_mapping(value, "snapshot_changes")
    _check_keys(changes, SNAPSHOT_CHANGE_KEYS, "snapshot_changes")
    previous_hash = changes.get("previous_facts_sha256")
    if previous_hash is not None:
        previous_hash = _require_string(previous_hash, "snapshot_changes.previous_facts_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", previous_hash):
            raise ManifestError("snapshot_changes.previous_facts_sha256 must be a lowercase SHA-256 digest")
    changed_projects: list[dict[str, Any]] = []
    for index, raw_change in enumerate(_require_list(changes.get("changed_projects", []), "snapshot_changes.changed_projects")):
        change = _require_mapping(raw_change, f"snapshot_changes.changed_projects[{index}]")
        _check_keys(change, PROJECT_CHANGE_KEYS, f"snapshot_changes.changed_projects[{index}]")
        project_id = _require_string(change.get("id"), f"snapshot_changes.changed_projects[{index}].id")
        if not ID_PATTERN.fullmatch(project_id):
            raise ManifestError(f"snapshot_changes.changed_projects[{index}].id must be a project identifier")
        fields = _validate_string_list(change.get("fields", []), f"snapshot_changes.changed_projects[{index}].fields")
        allowed_fields = PROJECT_KEYS - {"id"}
        unknown_fields = sorted(set(fields) - allowed_fields)
        if unknown_fields:
            raise ManifestError(
                f"snapshot_changes.changed_projects[{index}].fields contains unsupported fields: {', '.join(unknown_fields)}"
            )
        changed_projects.append({"id": project_id, "fields": sorted(set(fields))})
    supplied_hash = _require_string(changes.get("changes_sha256"), "snapshot_changes.changes_sha256")
    if not re.fullmatch(r"[0-9a-f]{64}", supplied_hash):
        raise ManifestError("snapshot_changes.changes_sha256 must be a lowercase SHA-256 digest")
    normalized = {
        "baseline_available": _require_bool(changes.get("baseline_available"), "snapshot_changes.baseline_available"),
        "previous_facts_sha256": previous_hash,
        "added_projects": _validate_identifier_list(changes.get("added_projects", []), "snapshot_changes.added_projects"),
        "removed_projects": _validate_identifier_list(changes.get("removed_projects", []), "snapshot_changes.removed_projects"),
        "changed_projects": sorted(changed_projects, key=lambda item: item["id"]),
        "workspace_changed": _require_bool(changes.get("workspace_changed"), "snapshot_changes.workspace_changed"),
        "relationships_changed": _require_bool(
            changes.get("relationships_changed"), "snapshot_changes.relationships_changed"
        ),
        **(
            {"skills_changed": _require_bool(changes.get("skills_changed"), "snapshot_changes.skills_changed")}
            if "skills_changed" in changes
            else {}
        ),
    }
    expected_hash = snapshot_changes_sha256(normalized)
    if supplied_hash != expected_hash:
        raise ManifestError("snapshot_changes.changes_sha256 does not match the snapshot change view")
    normalized["changes_sha256"] = supplied_hash
    return normalized


def validate_manifest(raw: Any) -> dict[str, Any]:
    manifest = _require_mapping(raw, "manifest")
    _check_keys(manifest, ROOT_KEYS, "manifest")
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise ManifestError(f"schema_version must be {SCHEMA_VERSION}")

    generated_at = _require_string(manifest.get("generated_at"), "generated_at")
    workspace = _require_mapping(manifest.get("workspace"), "workspace")
    _check_keys(workspace, WORKSPACE_KEYS, "workspace")
    normalized_workspace = {
        "name": _require_string(workspace.get("name"), "workspace.name"),
        "summary": _require_string(workspace.get("summary"), "workspace.summary"),
        "current_focus": _require_string(workspace.get("current_focus"), "workspace.current_focus"),
        "decisions": _validate_string_list(workspace.get("decisions", []), "workspace.decisions"),
        "unknowns": _validate_string_list(workspace.get("unknowns", []), "workspace.unknowns"),
    }

    projects_raw = _require_list(manifest.get("projects"), "projects")
    if not projects_raw:
        raise ManifestError("projects must contain at least one project")
    projects: list[dict[str, Any]] = []
    project_ids: set[str] = set()
    for index, item in enumerate(projects_raw):
        project = _require_mapping(item, f"projects[{index}]")
        _check_keys(project, PROJECT_KEYS, f"projects[{index}]")
        project_id = _require_string(project.get("id"), f"projects[{index}].id")
        if not ID_PATTERN.fullmatch(project_id):
            raise ManifestError(f"projects[{index}].id must use lowercase letters, numbers, and hyphens")
        if project_id in project_ids:
            raise ManifestError(f"duplicate project id: {project_id}")
        project_ids.add(project_id)
        projects.append(
            {
                "id": project_id,
                "name": _require_string(project.get("name"), f"projects[{index}].name"),
                "summary": _require_string(project.get("summary"), f"projects[{index}].summary"),
                "status": _require_string(project.get("status"), f"projects[{index}].status"),
                "signals": _validate_string_list(project.get("signals", []), f"projects[{index}].signals"),
                "risks": _validate_string_list(project.get("risks", []), f"projects[{index}].risks"),
                "open_questions": _validate_string_list(
                    project.get("open_questions", []), f"projects[{index}].open_questions"
                ),
                "evidence": _validate_string_list(project.get("evidence", []), f"projects[{index}].evidence"),
                **(
                    {
                        "constraints": _validate_string_list(
                            project.get("constraints", []), f"projects[{index}].constraints"
                        )
                    }
                    if "constraints" in project
                    else {}
                ),
            }
        )

    relationships_raw = _require_list(manifest.get("relationships", []), "relationships")
    relationships: list[dict[str, str]] = []
    for index, item in enumerate(relationships_raw):
        relationship = _require_mapping(item, f"relationships[{index}]")
        _check_keys(relationship, RELATIONSHIP_KEYS, f"relationships[{index}]")
        source = _require_string(relationship.get("source"), f"relationships[{index}].source")
        target = _require_string(relationship.get("target"), f"relationships[{index}].target")
        if source not in project_ids or target not in project_ids:
            raise ManifestError(f"relationships[{index}] references an unknown project")
        if source == target:
            raise ManifestError(f"relationships[{index}] must connect two different projects")
        relationship_type = _require_string(relationship.get("type"), f"relationships[{index}].type")
        if not ID_PATTERN.fullmatch(relationship_type):
            raise ManifestError(
                f"relationships[{index}].type must use lowercase letters, numbers, and hyphens"
            )
        relationships.append(
            {
                "source": source,
                "target": target,
                "type": relationship_type,
                "summary": _require_string(relationship.get("summary"), f"relationships[{index}].summary"),
                "evidence": _require_string(relationship.get("evidence"), f"relationships[{index}].evidence"),
            }
        )

    skills: list[dict[str, str]] = []
    for index, item in enumerate(_require_list(manifest.get("skills", []), "skills")):
        skill = _require_mapping(item, f"skills[{index}]")
        _check_keys(skill, SKILL_KEYS, f"skills[{index}]")
        source = _require_string(skill.get("source"), f"skills[{index}].source")
        provider = _require_string(skill.get("provider"), f"skills[{index}].provider")
        scope = _require_string(skill.get("scope"), f"skills[{index}].scope")
        if not ID_PATTERN.fullmatch(source) or not ID_PATTERN.fullmatch(provider):
            raise ManifestError(f"skills[{index}] source and provider must be identifiers")
        if scope not in {"user", "workspace", "custom"}:
            raise ManifestError(f"skills[{index}].scope must be user, workspace, or custom")
        skills.append(
            {
                "source": source,
                "provider": provider,
                "scope": scope,
                "name": _require_string(skill.get("name"), f"skills[{index}].name"),
                "summary": _require_string(skill.get("summary"), f"skills[{index}].summary"),
                "evidence": _require_string(skill.get("evidence"), f"skills[{index}].evidence"),
            }
        )
        validate_skill_summary(skills[-1]["name"], f"skills[{index}].name")
        validate_skill_summary(skills[-1]["summary"], f"skills[{index}].summary")

    normalized = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "workspace": normalized_workspace,
        "projects": sorted(projects, key=lambda project: project["id"]),
        "relationships": sorted(
            relationships,
            key=lambda relationship: (relationship["source"], relationship["target"], relationship["type"]),
        ),
        **(
            {
                "skills": sorted(
                    skills,
                    key=lambda skill: (skill["provider"], skill["scope"], skill["name"].casefold(), skill["source"]),
                )
            }
            if "skills" in manifest
            else {}
        ),
    }
    if "snapshot_changes" in manifest:
        normalized["snapshot_changes"] = _validate_snapshot_changes(manifest["snapshot_changes"])
    if "facts_sha256" in manifest:
        supplied_sha256 = _require_string(manifest["facts_sha256"], "facts_sha256")
        if not re.fullmatch(r"[0-9a-f]{64}", supplied_sha256):
            raise ManifestError("facts_sha256 must be a lowercase SHA-256 digest")
        expected_sha256 = facts_sha256(normalized)
        if supplied_sha256 != expected_sha256:
            raise ManifestError("facts_sha256 does not match the manifest facts")
        normalized["facts_sha256"] = supplied_sha256
    _validate_safe_strings(normalized)
    return normalized


def load_manifest(path: Path | str) -> dict[str, Any]:
    manifest_path = Path(path)
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {manifest_path.name}: {exc.msg}") from exc
    return validate_manifest(raw)


def build_graph(manifest: dict[str, Any]) -> dict[str, Any]:
    workspace = manifest["workspace"]
    nodes = [
        {
            "id": "workspace",
            "type": "workspace",
            "label": workspace["name"],
            "summary": workspace["summary"],
        }
    ]
    edges = []
    for project in manifest["projects"]:
        nodes.append(
            {
                "id": project["id"],
                "type": "project",
                "label": project["name"],
                "summary": project["summary"],
                "status": project["status"],
                "evidence": project["evidence"],
            }
        )
        edges.append(
            {
                "source": "workspace",
                "target": project["id"],
                "type": "contains",
                "evidence": "explicit project manifest membership",
            }
        )
    edges.extend(manifest["relationships"])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": manifest["generated_at"],
        "derived": True,
        "nodes": nodes,
        "edges": edges,
    }


def _bullet_section(title: str, items: list[str]) -> list[str]:
    lines = [f"### {title}", ""]
    if items:
        lines.extend(f"- {item}" for item in items)
    else:
        lines.append("- 未记录")
    lines.append("")
    return lines


def render_markdown(manifest: dict[str, Any]) -> str:
    workspace = manifest["workspace"]
    lines = [
        f"# {workspace['name']}项目简报",
        "",
        "> 这是供 ChatGPT 讨论项目发展使用的最小认知包。它不包含源码、diff、秘密或私有运行数据。",
        f"> 生成时间：{manifest['generated_at']} · schema {manifest['schema_version']}",
        "",
        "## 如何使用",
        "",
        "请先依据下列已记录事实理解项目，再参与方向讨论。证据不足时明确说未知；不要把关系图谱当作源码级依赖证明。",
        "",
        "## 工作区概览",
        "",
        workspace["summary"],
        "",
        f"**当前关注：** {workspace['current_focus']}",
        "",
    ]
    if manifest.get("facts_sha256"):
        lines.insert(4, f"> 事实快照：`{manifest['facts_sha256']}`")
    lines.extend(_bullet_section("已确认决策", workspace["decisions"]))
    lines.extend(_bullet_section("仍然未知", workspace["unknowns"]))

    if changes := manifest.get("snapshot_changes"):
        lines.extend(["## 与上次批准快照相比", ""])
        if not changes["baseline_available"]:
            lines.extend(["- 未提供上一份批准 manifest；本次只建立基线。", ""])
        else:
            lines.append(f"- 新增项目：{', '.join(changes['added_projects']) if changes['added_projects'] else '无'}")
            lines.append(f"- 移除项目：{', '.join(changes['removed_projects']) if changes['removed_projects'] else '无'}")
            for change in changes["changed_projects"]:
                lines.append(f"- `{change['id']}` 变化字段：{', '.join(change['fields'])}")
            lines.append(f"- 工作区描述变化：{'是' if changes['workspace_changed'] else '否'}")
            lines.append(f"- 关系变化：{'是' if changes['relationships_changed'] else '否'}")
            if "skills_changed" in changes:
                lines.append(f"- Skill 清单变化：{'是' if changes['skills_changed'] else '否'}")
            lines.append("")

    lines.extend(["## 项目", ""])
    for project in manifest["projects"]:
        lines.extend(
            [
                f"### {project['name']} (`{project['id']}`)",
                "",
                project["summary"],
                "",
                f"**记录状态：** {project['status']}",
                "",
            ]
        )
        lines.extend(_bullet_section("可观测信号", project["signals"]))
        lines.extend(_bullet_section("已确认约束", project.get("constraints", [])))
        lines.extend(_bullet_section("风险", project["risks"]))
        lines.extend(_bullet_section("开放问题", project["open_questions"]))
        lines.extend(_bullet_section("证据", project["evidence"]))

    if "skills" in manifest:
        lines.extend(
            [
                "## 可用 Skills",
                "",
                "> 仅包含 Skill 名称与 frontmatter 摘要；指令正文、脚本和本机目录未进入本简报。",
                "",
            ]
        )
        if manifest["skills"]:
            for skill in manifest["skills"]:
                lines.append(
                    f"- **{skill['name']}** · `{skill['provider']}` / `{skill['scope']}`：{skill['summary']}"
                )
        else:
            lines.append("- 未发现经过批准的 Skill 元数据")
        lines.append("")

    lines.extend(["## 项目关系图谱", "", "> 本节是由显式清单派生的可重建视图，不是独立真源。", ""])
    if manifest["relationships"]:
        for relationship in manifest["relationships"]:
            lines.append(
                f"- `{relationship['source']}` --{relationship['type']}--> `{relationship['target']}`："
                f"{relationship['summary']}（证据：{relationship['evidence']}）"
            )
    else:
        lines.append("- 暂无已确认的跨项目关系")
    lines.extend(
        [
            "",
            "## 对 ChatGPT 的讨论合同",
            "",
            "- 可以提出机会、风险、优先级和组合方案，但必须标明哪些是推断。",
            "- 不得从提交数、文件数或开发活跃度推断项目价值和真实使用效果。",
            "- 不得要求上传整个仓库；需要更多证据时，只请求最小必要的脱敏补丁。",
            "- 当事实和图谱冲突时，以事实与证据为准，并指出需要重新生成图谱。",
            "",
        ]
    )
    return "\n".join(lines)


def _atomic_write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    except Exception:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def build_bundle(manifest_path: Path | str, output_dir: Path | str) -> BundlePaths:
    manifest = load_manifest(manifest_path)
    markdown = render_markdown(manifest)
    graph = build_graph(manifest)
    destination = Path(output_dir)
    markdown_path = destination / "ai_context_linker.md"
    graph_path = destination / "ai_context_linker.graph.json"
    _atomic_write_text(markdown_path, markdown)
    _atomic_write_text(graph_path, json.dumps(graph, ensure_ascii=False, indent=2) + "\n")
    return BundlePaths(markdown=markdown_path, graph=graph_path)
