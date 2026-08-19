"""Bounded Skill metadata discovery without reading instruction bodies."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .adapters import is_link_or_reparse
from .core import ManifestError, validate_skill_summary


MAX_SKILL_FRONTMATTER_BYTES = 16 * 1024
MAX_SKILLS_PER_ROOT = 500


def default_user_skill_roots(home: Path | None = None) -> list[dict[str, str]]:
    """Return existing common user Skill roots as private config records."""
    user_home = (home or Path.home()).resolve()
    candidates = (
        ("agent-skills-user", "agent-skills", user_home / ".agents" / "skills"),
        ("codex-user", "codex", user_home / ".codex" / "skills"),
        ("claude-code-user", "claude-code", user_home / ".claude" / "skills"),
        ("gemini-cli-user", "gemini-cli", user_home / ".gemini" / "skills"),
    )
    return [
        {"id": root_id, "provider": provider, "scope": "user", "path": str(path)}
        for root_id, provider, path in candidates
        if path.is_dir() and not is_link_or_reparse(path)
    ]


def project_skill_roots(projects: list[dict[str, object]]) -> list[dict[str, str]]:
    """Return existing cross-tool Skill roots beneath approved project roots."""
    roots: list[dict[str, str]] = []
    layouts = (
        ("agent-skills", Path(".agents/skills")),
        ("claude-code", Path(".claude/skills")),
        ("gemini-cli", Path(".gemini/skills")),
    )
    used_ids: set[str] = set()
    for project in projects:
        project_id = str(project["id"])
        project_root = Path(str(project["path"]))
        for provider, relative in layouts:
            candidate = project_root / relative
            if candidate.is_dir() and not is_link_or_reparse(candidate):
                base = re.sub(r"[^a-z0-9]+", "-", f"{project_id}-{provider}".lower()).strip("-")[:63]
                root_id = base
                suffix = 2
                while root_id in used_ids:
                    ending = f"-{suffix}"
                    root_id = f"{base[: 63 - len(ending)].rstrip('-')}{ending}"
                    suffix += 1
                used_ids.add(root_id)
                roots.append(
                    {
                        "id": root_id,
                        "provider": provider,
                        "scope": "workspace",
                        "path": str(candidate),
                    }
                )
    return roots


def _frontmatter_lines(path: Path) -> list[str] | None:
    """Read only the bounded YAML frontmatter; stop before the Markdown body."""
    lines: list[str] = []
    consumed = 0
    with path.open("rb") as handle:
        first = handle.readline(8)
        consumed += len(first)
        if first.decode("utf-8-sig", errors="strict").strip() != "---":
            return None
        while consumed < MAX_SKILL_FRONTMATTER_BYTES:
            remaining = MAX_SKILL_FRONTMATTER_BYTES - consumed
            raw = handle.readline(remaining)
            if not raw:
                return None
            consumed += len(raw)
            line = raw.decode("utf-8", errors="strict").rstrip("\r\n")
            if line.strip() == "---":
                return lines
            lines.append(line)
    raise ManifestError(f"Skill frontmatter in {path.name} exceeds the safety limit")


def _scalar(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, str) else value
        except json.JSONDecodeError:
            return value[1:-1]
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def parse_skill_frontmatter(path: Path) -> tuple[str | None, str | None] | None:
    """Extract only top-level name and description from a SKILL.md frontmatter."""
    lines = _frontmatter_lines(path)
    if lines is None:
        return None
    values: dict[str, str] = {}
    index = 0
    while index < len(lines):
        match = re.match(r"^(name|description):(?:\s*(.*))?$", lines[index], re.I)
        if not match:
            index += 1
            continue
        key = match.group(1).lower()
        raw_value = (match.group(2) or "").strip()
        if raw_value in {"|", "|-", "|+", ">", ">-", ">+"}:
            block: list[str] = []
            index += 1
            while index < len(lines) and (not lines[index].strip() or lines[index][0].isspace()):
                block.append(lines[index].strip())
                index += 1
            separator = "\n" if raw_value.startswith("|") else " "
            values[key] = separator.join(part for part in block if part).strip()
            continue
        values[key] = _scalar(raw_value)
        index += 1
    return values.get("name") or None, values.get("description") or None


def collect_skill_root(
    root: Path,
    *,
    root_id: str,
    provider: str,
    scope: str,
) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """Collect Skill names and summaries from direct child directories only."""
    report: dict[str, Any] = {
        "id": root_id,
        "provider": provider,
        "scope": scope,
        "status": "missing",
        "entries_inspected": 0,
        "skills_collected": 0,
        "skipped": [],
        "instruction_bodies_read": 0,
    }
    if not root.exists():
        return [], report
    if not root.is_dir() or is_link_or_reparse(root):
        raise ManifestError(f"skill_roots.{root_id} must be a real directory, not a link or reparse point")
    report["status"] = "scanned"
    skills: list[dict[str, str]] = []
    try:
        children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
    except OSError as exc:
        raise ManifestError(f"skill_roots.{root_id} cannot be enumerated") from exc
    for child in children[:MAX_SKILLS_PER_ROOT]:
        report["entries_inspected"] += 1
        if child.name.startswith(".") or not child.is_dir() or is_link_or_reparse(child):
            report["skipped"].append({"entry": child.name, "reason": "hidden, non-directory, or linked"})
            continue
        skill_file = child / "SKILL.md"
        if not skill_file.is_file() or is_link_or_reparse(skill_file):
            report["skipped"].append({"entry": child.name, "reason": "safe SKILL.md not found"})
            continue
        try:
            parsed = parse_skill_frontmatter(skill_file)
        except (OSError, UnicodeError, ManifestError) as exc:
            report["skipped"].append({"entry": child.name, "reason": str(exc)})
            continue
        if parsed is None:
            report["skipped"].append({"entry": child.name, "reason": "valid bounded frontmatter not found"})
            continue
        declared_name, description = parsed
        name = (declared_name or child.name).strip()[:200]
        summary = (description or "No public Skill summary is declared.").strip()[:1000]
        validate_skill_summary(name, f"skill_roots.{root_id}.{child.name}.name")
        try:
            validate_skill_summary(summary, f"skill_roots.{root_id}.{child.name}.summary")
        except ManifestError as exc:
            if "likely secret" in str(exc):
                raise
            summary = "Summary omitted because it failed publish-safety checks."
            report["skipped"].append({"entry": child.name, "reason": "unsafe summary omitted"})
        skills.append(
            {
                "source": root_id,
                "provider": provider,
                "scope": scope,
                "name": name,
                "summary": summary,
                "evidence": f"skill-frontmatter:{provider}:{scope}",
            }
        )
    report["truncated"] = len(children) > MAX_SKILLS_PER_ROOT
    report["skills_collected"] = len(skills)
    return skills, report
