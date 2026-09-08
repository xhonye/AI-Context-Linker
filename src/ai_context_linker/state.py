"""Bounded deterministic extraction from explicitly approved project state files."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from .core import ManifestError, validate_skill_summary


STATE_FILENAMES = {
    "STATUS.md",
    "progress.md",
    "task_plan.md",
    "findings.md",
    "ROADMAP.md",
    "DECISIONS.md",
}
MAX_STATE_ITEMS_PER_FILE = 8
MAX_STATE_ITEMS_PER_PROJECT = 24
MAX_STATE_CANDIDATES_PER_FILE = 200

HEADING_TERMS = (
    ("blocker", ("blocker", "blockers", "blocked", "blocking", "阻塞", "卡点", "受阻")),
    ("next-action", ("next action", "next step", "next", "todo", "to do", "下一步", "下一行动", "待办")),
    ("decision", ("decision", "decisions", "决定", "决策")),
    ("deadline", ("deadline", "due", "截止", "期限")),
    ("completed", ("completed", "done", "recent progress", "已完成", "完成情况", "近期进展")),
    ("current-goal", ("current goal", "current goals", "current focus", "current", "focus", "goal", "goals", "目标", "当前目标", "当前关注", "当前主线")),
)
DATE_PATTERN = re.compile(r"(?<!\d)(20\d{2}-\d{2}-\d{2})(?!\d)")
CONTROL_ITEM_PATTERNS = (
    re.compile(r"^status\s*[:：]", re.IGNORECASE),
    re.compile(r"^files?\s+(?:created|modified|created\s*/\s*modified)\s*[:：]", re.IGNORECASE),
    re.compile(r"^actions?\s+taken\s*[:：]", re.IGNORECASE),
    re.compile(r"^(?:test\s+results?|outputs?)\s*[:：]", re.IGNORECASE),
    re.compile(r"^(?:状态|文件(?:创建|修改|变更)|测试结果|执行记录)\s*[:：]"),
)


def _kind_for_heading(heading: str) -> str | None:
    normalized = " ".join(re.sub(r"[`*_]", "", heading).casefold().split()).strip(" :：-—")
    for kind, terms in HEADING_TERMS:
        for term in terms:
            if normalized == term:
                return kind
            suffix = normalized[len(term) :] if normalized.startswith(term) else ""
            if suffix and re.match(r"^(?:\s*[:：—-]\s*|\s*\(|\s+20\d{2}(?:-|年))", suffix):
                return kind
    return None


def _clean_item(text: str) -> str:
    text = re.sub(r"^[-*+]\s+", "", text.strip())
    text = re.sub(r"^\d+[.)]\s+", "", text)
    text = re.sub(r"^\[[ xX]\]\s+", "", text)
    text = re.sub(r"!\[[^]]*\]\([^)]*\)", "", text)
    text = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", text)
    return " ".join(re.sub(r"[`*_]", "", text).strip().split())


def _is_control_item(text: str) -> bool:
    return any(pattern.search(text) for pattern in CONTROL_ITEM_PATTERNS)


def _date_and_freshness(text: str, observed_at: datetime) -> tuple[str | None, str]:
    match = DATE_PATTERN.search(text)
    if not match:
        return None, "undated"
    try:
        source_date = date.fromisoformat(match.group(1))
    except ValueError:
        return None, "undated"
    age_days = (observed_at.date() - source_date).days
    if age_days < 0:
        return source_date.isoformat(), "future-dated"
    return source_date.isoformat(), "current" if age_days <= 45 else "stale"


def extract_state_items(
    text: str,
    *,
    project_id: str,
    relative_name: str,
    observed_at: datetime,
) -> list[dict[str, Any]]:
    """Extract only items under recognized headings; free-form files yield no facts."""
    candidates: list[dict[str, Any]] = []
    current_kind: str | None = None
    heading_text = ""
    paragraph_taken = False
    heading_dates: dict[int, str] = {}
    in_fence = False
    pending_lines: list[str] = []
    pending_line_number = 0
    pending_is_list = False
    pending_kind: str | None = None

    def flush_pending() -> None:
        nonlocal pending_lines, pending_line_number, pending_is_list, pending_kind, paragraph_taken
        if not pending_lines or pending_kind is None:
            pending_lines = []
            pending_kind = None
            return
        raw_text = " ".join(line.strip() for line in pending_lines if line.strip())
        validate_skill_summary(raw_text, f"state item at {relative_name}:line-{pending_line_number}")
        clean = _clean_item(raw_text)
        if len(clean) > 500:
            raise ManifestError(
                f"state item at {relative_name}:line-{pending_line_number} exceeds the 500 character limit"
            )
        if clean and not _is_control_item(clean):
            inherited_date = heading_dates[max(heading_dates)] if heading_dates else ""
            source_date, freshness = _date_and_freshness(
                f"{inherited_date} {heading_text} {clean}", observed_at
            )
            item: dict[str, Any] = {
                "kind": pending_kind,
                "text": clean,
                "freshness": freshness,
                "evidence": f"{project_id}:file:{relative_name}:line-{pending_line_number}",
                "provenance": "project-state",
                "_line": pending_line_number,
            }
            if source_date:
                item["source_date"] = source_date
            candidates.append(item)
        if clean and not _is_control_item(clean) and not pending_is_list:
            paragraph_taken = True
        pending_lines = []
        pending_kind = None
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            flush_pending()
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        heading = re.match(r"^#{1,6}\s+(.+?)\s*$", stripped)
        if heading:
            flush_pending()
            heading_text = heading.group(1)
            level = len(stripped) - len(stripped.lstrip("#"))
            heading_dates = {key: value for key, value in heading_dates.items() if key < level}
            date_match = DATE_PATTERN.search(heading_text)
            if date_match:
                try:
                    date.fromisoformat(date_match.group(1))
                    heading_dates[level] = date_match.group(1)
                except ValueError:
                    pass
            current_kind = _kind_for_heading(heading_text)
            paragraph_taken = False
            continue
        if not current_kind or not stripped or stripped.startswith((">", "|", "<")):
            if not stripped:
                flush_pending()
            continue
        is_list_item = bool(re.match(r"^(?:[-*+]|\d+[.)])\s+", stripped))
        if re.fullmatch(r"[-*_]{3,}", stripped):
            flush_pending()
            continue
        if is_list_item:
            flush_pending()
            pending_lines = [stripped]
            pending_line_number = line_number
            pending_is_list = True
            pending_kind = (
                "completed"
                if re.match(r"^(?:[-*+]\s+|\d+[.)]\s+)\[[xX]\]\s+", stripped)
                else current_kind
            )
            continue
        if pending_lines and pending_is_list:
            if raw_line[:1].isspace():
                pending_lines.append(stripped)
            continue
        if paragraph_taken or stripped.startswith(("!", "[")):
            continue
        if not pending_lines:
            pending_lines = [stripped]
            pending_line_number = line_number
            pending_is_list = False
            pending_kind = current_kind
        else:
            pending_lines.append(stripped)
        if len(candidates) >= MAX_STATE_CANDIDATES_PER_FILE:
            break
    flush_pending()
    kind_rank = {"current-goal": 0, "blocker": 1, "next-action": 2, "deadline": 3, "decision": 4, "completed": 5}
    freshness_rank = {"current": 0, "undated": 1, "stale": 2, "future-dated": 3}
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in candidates:
        key = (item["kind"], item["text"].casefold())
        previous = unique.get(key)
        if previous is None or item["_line"] > previous["_line"]:
            unique[key] = item
    selected = sorted(
        unique.values(),
        key=lambda item: (
            kind_rank[item["kind"]],
            freshness_rank[item["freshness"]],
            -date.fromisoformat(item["source_date"]).toordinal() if item.get("source_date") else 0,
            -item["_line"],
        ),
    )[:MAX_STATE_ITEMS_PER_FILE]
    for item in selected:
        item.pop("_line", None)
    return selected
