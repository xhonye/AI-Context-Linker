"""Create private review-state skeletons and readable previews, never approvals."""

from __future__ import annotations

import hashlib
import html
import json
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from .core import (
    ManifestError, UNTRUSTED_DATA_NOTICE, _atomic_write_text, _check_output_path,
    _walk_strings, facts_sha256, load_manifest, validate_publish_text,
)
from .review_state import (
    _freshness, _normalize_project, _parse_review_state, _read_review_state_payload, _timestamp,
)
from .snapshots import SYNC_DIRECTORY_MARKERS


MAX_TEMPLATE_PROJECTS = 3

_REVIEW_FIELDS = (
    ("priority", "人工优先级"),
    ("activity", "当前状态"),
    ("attention", "何时关注"),
    ("why_now", "为什么现在做"),
    ("current_goal", "当前目标"),
    ("blockers", "当前卡点"),
    ("next_action", "下一步"),
    ("done_when", "完成标准"),
    ("owner", "负责人"),
    ("due_at", "截止时间"),
    ("updated_at", "记录更新时间"),
    ("expires_at", "有效期至"),
)
_VALUE_LABELS = {
    "activity": {
        "active": "进行中", "paused": "已暂停", "blocked": "受阻",
        "maintaining": "维护中", "inactive": "未活跃", "unknown": "未知",
    },
    "attention": {
        "today": "今天", "this-week": "本周", "later": "以后",
        "none": "暂不关注", "unknown": "未知",
    },
}
_DRAFT_STATUS_LABELS = {
    "open": "拟记为未解决（open）", "resolved": "拟记为已解决（resolved）",
    "superseded": "拟记为已替代（superseded）", "stale": "已过期（stale）",
    "needs_review": "待核对（needs_review）",
}


def _preview_text(value: str) -> str:
    """Keep input Markdown/HTML inert, including multiline instruction-like prose."""
    escaped = html.escape(value, quote=False)
    return re.sub(r"([\\`*_{}\[\]()#+.!|\-])", r"\\\1", escaped)


def _preview_field(label: str, value: str) -> list[str]:
    return [f"**{label}**", "", *[f"> {_preview_text(line)}" for line in value.splitlines()], ""]


def _preview_destination(output_path: Path | str) -> Path:
    unresolved = Path(output_path)
    _check_output_path(unresolved)
    destination = unresolved.resolve()
    if destination.suffix.casefold() != ".md":
        raise ManifestError("review preview output must be a Markdown file")
    for parent in destination.parents:
        lowered = parent.name.casefold()
        if (
            any(marker in lowered for marker in SYNC_DIRECTORY_MARKERS)
            or lowered in {"sol_context", "ai_context_linker"}
            or any((parent / name).exists() for name in (
                "ai_context.md", "sol_context.md", "ai_context_linker.bundle.json",
            ))
        ):
            raise ManifestError("review preview must remain outside cloud-synced or publish directories")
        if (parent / ".git").exists():
            raise ManifestError("review preview must remain outside repositories in a private directory")
    return destination


def preview_review_state(
    manifest_path: Path | str,
    project_ids: list[str],
    review_state_path: Path | str,
    output_path: Path | str,
) -> Path:
    """Render exact draft data in Chinese without changing state, scope, or approval.

    Freshness is evaluated at the input manifest's timestamp, never at the wall
    clock, so identical inputs are deterministic. Values are not translated or
    summarized; only fixed labels and enums have Chinese display names.
    """
    if not 1 <= len(project_ids) <= MAX_TEMPLATE_PROJECTS:
        raise ManifestError("review preview requires one to three explicitly selected projects")
    if len(set(project_ids)) != len(project_ids):
        raise ManifestError("review preview contains a duplicate project")
    _check_output_path(Path(manifest_path))
    _check_output_path(Path(review_state_path))
    manifest = load_manifest(manifest_path)
    available = {project["id"]: project for project in manifest["projects"]}
    if any(project_id not in available for project_id in project_ids):
        raise ManifestError("review preview names an unknown project")
    if any(available[project_id].get("cloud_visibility") != "allow" for project_id in project_ids):
        raise ManifestError("review preview requires explicitly allowed detailed projects")

    observed_at = datetime.fromisoformat(manifest["generated_at"])
    raw, content = _read_review_state_payload(Path(review_state_path))
    # Reuse the existing adapter's strict schema and lifecycle validation. Its
    # normalized records are deliberately discarded, not imported into facts.
    _parse_review_state(raw, project_ids=set(available), observed_at=observed_at)
    for label, value in _walk_strings(raw, "review state"):
        validate_publish_text(value, label)
    drafts = {
        item["project_id"]: _normalize_project(item, schema_version=raw["schema_version"], index=index)
        for index, item in enumerate(raw["projects"])
    }
    if any(project_id not in drafts for project_id in project_ids):
        raise ManifestError("review preview selected project has no draft entry")

    lines = [
        "# 项目行动状态：中文核对单", "",
        "> UNAPPROVED_PREVIEW：只供本地核对，所有字段均未在此获批；不得作为正式事实或同步简报。",
        UNTRUSTED_DATA_NOTICE,
        "> 这张核对单不修改输入、不登记批准、不上传，也不会把 AI 建议变成人工事实。",
        "> 下文按原值呈现；英文原文不经 AI 翻译或改写。", "",
        f"- 核对时点（输入 manifest 时间，并非当前实时状态）：{manifest['generated_at']}",
        f"- 草稿 schema：{raw['schema_version']}",
        f"- 草稿文件指纹（不是批准）：`{hashlib.sha256(content).hexdigest()}`",
        f"- 参考事实指纹：`{facts_sha256(manifest)}`", "",
    ]
    for project_id in sorted(project_ids):
        project = drafts[project_id]
        updated_at = _timestamp(project["updated_at"], "review preview updated_at")
        expires_at = _timestamp(project["expires_at"], "review preview expires_at") if "expires_at" in project else None
        freshness = _freshness(updated_at, expires_at, observed_at)
        freshness_label = {
            "current": "在核对时点内有效（不代表已批准）",
            "stale": "已过期（stale）",
            "future-dated": "未来日期（future-dated），不能作为当前状态",
        }[freshness]
        lines.extend([
            f"## {_preview_text(available[project_id]['name'])} (`{project_id}`)", "",
            f"- 草稿新鲜度：{freshness_label}",
            "- 有效期不自动延长；缺失时需要人工确认使用期限。", "",
        ])
        for field, label in _REVIEW_FIELDS:
            value: Any = project.get(field)
            if field == "blockers":
                text = "\n".join(value) if value else "未知（没有记录不等于没有卡点）"
            elif value is None:
                text = "未知（未填写）"
            else:
                text = str(value)
                translated = _VALUE_LABELS.get(field, {}).get(text)
                if translated:
                    text = f"{translated}（{text}）"
            lines.extend(_preview_field(label, text))
        if project.get("records"):
            lines.extend(["### 补充记录（草稿声明，均待人工确认）", ""])
            for record in project["records"]:
                status = record.get("status", "open")
                fields = [
                    ("记录 ID", record.get("record_id", "未填写")),
                    ("类型", record["kind"]),
                    ("草稿状态", _DRAFT_STATUS_LABELS[status]),
                    ("内容", record["text"]),
                    ("证据引用", record.get("source_ref", "未填写")),
                    ("观察时间", record.get("observed_at", project["updated_at"])),
                    ("有效期至", record.get("expires_at", project.get("expires_at", "未填写"))),
                    ("替代旧记录", "、".join(record.get("supersedes", [])) or "未填写"),
                ]
                for label, value in fields:
                    lines.extend(_preview_field(label, value))
    lines.extend([
        "## 你只需要核对这些", "",
        "- 目标、卡点和下一步是否真是现在的情况？空卡点不代表没有卡点。",
        "- 完成标准是否具体，时间是否仍有效？哪些内容只是助手建议？",
        "- 即使没有密钥或路径，业务名称与目标是否仍然敏感？",
        "- 如需修改，可以用中文告诉本地助手代填草稿，再生成新核对单；无需自己编辑 JSON。",
        "- 只有明确批准对应版本及用途后，才可将状态纳入私有配置、重新扫描并审阅候选。",
        "- 发布批准仍由独立 approve-snapshot 记录；本核对单不替代它，也不得复制进同步目录。", "",
    ])
    rendered = "\n".join(lines)
    validate_publish_text(rendered, "review preview")
    destination = _preview_destination(output_path)
    if destination.exists():
        if destination.is_file() and destination.read_bytes() == rendered.encode("utf-8"):
            return destination
        raise ManifestError("review preview output already exists; choose a new private filename")
    _atomic_write_text(destination, rendered)
    return destination


def init_review_state(
    manifest_path: Path | str,
    project_ids: list[str],
    output_path: Path | str,
    *,
    observed_at: datetime | None = None,
    overwrite: bool = False,
) -> Path:
    """Write a valid but non-actionable v0.2 skeleton for one to three projects."""
    if not 1 <= len(project_ids) <= MAX_TEMPLATE_PROJECTS:
        raise ManifestError("init-review-state requires one to three explicitly selected projects")
    if len(set(project_ids)) != len(project_ids):
        raise ManifestError("init-review-state contains a duplicate project")

    manifest = load_manifest(manifest_path)
    available = {project["id"] for project in manifest["projects"]}
    unknown = sorted(set(project_ids) - available)
    if unknown:
        raise ManifestError(f"init-review-state names an unknown project: {', '.join(unknown)}")

    _check_output_path(Path(output_path))
    destination = Path(output_path).resolve()
    if destination.suffix.casefold() != ".json":
        raise ManifestError("init-review-state output must be a JSON file")
    if destination.exists() and not overwrite:
        raise ManifestError("init-review-state output already exists; pass --force to replace it")

    timestamp = observed_at or datetime.now().astimezone()
    if timestamp.tzinfo is None:
        raise ManifestError("init-review-state observed_at must include a timezone")
    expires_at = timestamp + timedelta(days=7)
    payload: dict[str, object] = {
        "schema_version": "0.2",
        "projects": [
            {
                "project_id": project_id,
                "updated_at": timestamp.isoformat(),
                "expires_at": expires_at.isoformat(),
            }
            for project_id in project_ids
        ],
    }
    _atomic_write_text(destination, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    return destination
