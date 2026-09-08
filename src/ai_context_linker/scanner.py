"""Deterministic, allowlist-only local workspace scanner.

The scanner produces a candidate manifest for human review. It never publishes
the bundle. Source-code bodies are unread by default; an explicit per-project
relationship adapter may inspect bounded files without publishing their text.
Local paths remain confined to the private scanner configuration.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import classify_changed_path, collect_filename_inventory, is_link_or_reparse
from .architecture_index import ARCHITECTURE_MODES, collect_architecture_index
from .changes import render_changes_markdown, semantic_changes
from .core import (
    ManifestError,
    DOCUMENT_NAMES,
    CONFIGURATION_FIELDS,
    MAX_ATTACHED_DOCUMENTS,
    MAX_DOCUMENT_BYTES,
    MAX_PROJECT_DOCUMENT_BYTES,
    prepare_document,
    _atomic_write_text,
    facts_sha256,
    load_manifest,
    snapshot_changes_sha256,
    validate_manifest,
    validate_publish_text,
    validate_skill_summary,
)
from .relationships import (
    DEPENDENCY_METADATA_FILENAMES,
    derive_code_path_relationships,
    derive_dependency_relationships,
    derive_document_relationships,
    parse_dependency_metadata,
    repeated_reference_fragments,
)
from .relationship_candidates import (
    MAX_RELATIONSHIP_CANDIDATE_FILES,
    candidate_queue,
    read_relationship_candidates,
)
from .review_state import MAX_REVIEW_STATE_FILES, read_review_state
from .snapshots import load_approved_snapshot
from .state_records import resolve_state_records, upgrade_state_item
from .skills import collect_skill_root
from .state import MAX_STATE_ITEMS_PER_PROJECT, STATE_FILENAMES, extract_state_items
from .session_summaries import MAX_SESSION_ITEMS_PER_PROJECT, MAX_SESSION_SUMMARY_FILES, read_session_summary


CONFIG_KEYS = {
    "schema_version",
    "workspace",
    "projects",
    "relationships",
    "skill_roots",
    "review_state_files",
    "session_summary_files",
    "relationship_candidate_files",
}
CONFIG_PROJECT_KEYS = {
    "id",
    "path",
    "registry_key",
    "name",
    "summary",
    "status",
    "sensitivity",
    "cloud_visibility",
    "redaction_profile",
    "approved_summary",
    "allow_files",
    "attach_files",
    "dependency_files",
    "observe_paths",
    "state_files",
    "state_file_candidates",
    "risks",
    "constraints",
    "code_relationship_scan",
    "architecture_visibility",
    "open_questions",
}
WORKSPACE_KEYS = {"name", "summary", "current_focus", "decisions", "unknowns"}
RELATIONSHIP_KEYS = {"source", "target", "type", "layer", "summary", "evidence"}
SKILL_ROOT_KEYS = {"id", "provider", "scope", "path", "approved_summaries"}
DEFAULT_ALLOW_FILES = (
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "ROADMAP.md",
    "TODO.md",
    "STATUS.md",
    "CHANGELOG.md",
    "PROJECT_CHARTER.md",
)
ALLOWED_METADATA_NAMES = DOCUMENT_NAMES
MAX_METADATA_BYTES = MAX_DOCUMENT_BYTES
MAX_METADATA_OPEN_ITEMS = 5
MAX_METADATA_CONSTRAINTS = 8
FORBIDDEN_OBSERVED_PARTS = {".git", ".ssh"}
FORBIDDEN_OBSERVED_MARKERS = {"credential", "secret", "token"}
FORBIDDEN_OBSERVED_SUFFIXES = {".db", ".key", ".p12", ".pem", ".sqlite", ".sqlite3"}
SYNC_DIRECTORY_MARKERS = {"dropbox", "google drive", "googledrive", "icloud", "onedrive"}


@dataclass(frozen=True)
class ScanPaths:
    candidate_manifest: Path
    report: Path
    changes_json: Path
    changes_markdown: Path
    relationship_review_queue: Path


def _mapping(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{label} must be an object")
    return value


def _list(value: Any, label: str) -> list[Any]:
    if not isinstance(value, list):
        raise ManifestError(f"{label} must be an array")
    return value


def _string(value: Any, label: str, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        raise ManifestError(f"{label} must be a non-empty string")
    return value.strip()


def _keys(value: dict[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise ManifestError(f"{label} contains unsupported fields: {', '.join(unknown)}")


def _strings(value: Any, label: str) -> list[str]:
    return [str(_string(item, f"{label}[{index}]")) for index, item in enumerate(_list(value, label))]


def _string_mapping(value: Any, label: str) -> dict[str, str]:
    mapping = _mapping(value, label)
    return {
        str(_string(key, f"{label}.key")): str(_string(item, f"{label}.{key}"))
        for key, item in mapping.items()
    }


def _boolean(value: Any, label: str, *, default: bool = False) -> bool:
    if value is None:
        return default
    if not isinstance(value, bool):
        raise ManifestError(f"{label} must be a boolean")
    return value


def _safe_relative_path(raw: str, label: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() or not candidate.parts or ".." in candidate.parts:
        raise ManifestError(f"{label} must be a relative path without '..'")
    return candidate


def _metadata_path(raw: str, label: str) -> Path:
    candidate = _safe_relative_path(raw, label)
    if candidate.name not in ALLOWED_METADATA_NAMES:
        allowed = ", ".join(sorted(ALLOWED_METADATA_NAMES))
        raise ManifestError(f"{label} is not an allowed metadata filename; choose one of: {allowed}")
    return candidate


def _observable_path(raw: str, label: str) -> Path:
    candidate = _safe_relative_path(raw, label)
    lowered_parts = [part.lower() for part in candidate.parts]
    sensitive_name = any(
        part in FORBIDDEN_OBSERVED_PARTS
        or part.startswith(".env")
        or any(marker in part for marker in FORBIDDEN_OBSERVED_MARKERS)
        for part in lowered_parts
    )
    if sensitive_name or candidate.suffix.lower() in FORBIDDEN_OBSERVED_SUFFIXES:
        raise ManifestError(f"{label} names a sensitive path that must not enter the publish surface")
    return candidate


def _dependency_path(raw: str, label: str) -> Path:
    candidate = _safe_relative_path(raw, label)
    if candidate.parent != Path(".") or candidate.name not in DEPENDENCY_METADATA_FILENAMES:
        allowed = ", ".join(DEPENDENCY_METADATA_FILENAMES)
        raise ManifestError(f"{label} must be a root dependency metadata file chosen from: {allowed}")
    return candidate


def _state_path(raw: str, label: str) -> Path:
    candidate = _safe_relative_path(raw, label)
    if candidate.parent != Path(".") or candidate.name not in STATE_FILENAMES:
        allowed = ", ".join(sorted(STATE_FILENAMES))
        raise ManifestError(f"{label} must be a root state file chosen from: {allowed}")
    return candidate


def _resolve_inside(root: Path, relative: Path, label: str) -> Path:
    resolved = (root / relative).resolve()
    if not resolved.is_relative_to(root):
        raise ManifestError(f"{label} resolves outside its project root")
    return resolved


def _read_metadata(path: Path, label: str) -> str:
    if path.stat().st_size > MAX_METADATA_BYTES:
        raise ManifestError(f"{label} exceeds the {MAX_METADATA_BYTES} byte metadata limit")
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ManifestError(f"{label} must be UTF-8 text") from exc


def _markdown_title(text: str) -> str | None:
    for line in text.splitlines():
        match = re.match(r"^#\s+(.+?)\s*$", line)
        if match:
            return re.sub(r"[`*_]", "", match.group(1)).strip()
    return None


def _markdown_summary(text: str) -> str | None:
    paragraph: list[str] = []
    in_fence = False
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if not line:
            if paragraph:
                break
            continue
        if re.fullmatch(r"[-*_]{3,}", line):
            continue
        if line.startswith(("#", "!", "<", ">", "- ", "* ", "+ ")) or re.match(r"^\d+\.\s", line):
            continue
        if line.startswith("[") and "](" in line:
            continue
        line = re.sub(r"!\[[^]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"[`*_]", "", line).strip()
        if line:
            paragraph.append(line)
    return " ".join(paragraph) or None


def _markdown_open_items(text: str) -> list[tuple[str, int]]:
    items: list[tuple[str, int]] = []
    in_fence = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if line.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^[-*+]\s+\[\s\]\s+(.+?)\s*$", line)
        if not match:
            continue
        item = re.sub(r"!\[[^]]*\]\([^)]*\)", "", match.group(1))
        item = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", item)
        item = re.sub(r"[`*_]", "", item).strip()[:500]
        if item:
            items.append((item, line_number))
        if len(items) >= MAX_METADATA_OPEN_ITEMS:
            break
    return items


def _markdown_constraints(text: str) -> list[tuple[str, int]]:
    heading_terms = (
        "boundary",
        "contract",
        "principle",
        "security",
        "safety",
        "non-goal",
        "storage",
        "约束",
        "原则",
        "边界",
        "合同",
        "安全",
        "非目标",
        "存储",
    )
    constraints: list[tuple[str, int]] = []
    in_selected_section = False
    in_fence = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        stripped = raw_line.strip()
        if stripped.startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith("#"):
            heading = stripped.lstrip("#").strip().casefold()
            in_selected_section = any(term in heading for term in heading_terms)
            continue
        if not in_selected_section:
            continue
        match = re.match(r"^[-*+]\s+(.+)$", stripped)
        if not match:
            continue
        item = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", match.group(1))
        item = re.sub(r"[`*_]", "", item).strip()
        if item:
            constraints.append((item[:400], line_number))
        if len(constraints) >= MAX_METADATA_CONSTRAINTS:
            break
    return constraints


def _safe_derived_text(text: str | None, fallback: str, label: str, warnings: list[str]) -> str:
    if not text:
        return fallback
    try:
        validate_publish_text(text, label)
    except ManifestError as exc:
        if "likely secret" in str(exc):
            raise
        warnings.append(f"{label} was omitted because automatically derived text failed publish-safety checks.")
        return fallback
    return text


def _run_git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            [
                "git",
                "-c",
                "core.quotepath=false",
                "-c",
                "core.fsmonitor=false",
                "-c",
                "submodule.recurse=false",
                *args,
            ],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _git_facts(root: Path, project_id: str) -> tuple[list[str], list[str], dict[str, Any]]:
    if not (root / ".git").exists():
        return [], [], {"repository": False}
    if is_link_or_reparse(root / ".git"):
        return (
            ["Git metadata was skipped because `.git` is a link or reparse point."],
            [f"{project_id}:git:skipped-reparse-point"],
            {"repository": False, "skipped_reparse_point": True},
        )
    signals = ["A Git repository is present."]
    evidence = [f"{project_id}:git:repository"]
    report: dict[str, Any] = {"repository": True}
    branch = _run_git(root, "branch", "--show-current")
    if branch:
        signals.append(f"The current Git branch is `{branch}`.")
        evidence.append(f"{project_id}:git:branch")
        report["branch_available"] = True
    status = _run_git(root, "status", "--porcelain=v1", "-z")
    if status is not None:
        entries = [item for item in status.split("\0") if item]
        changed = 0
        categories = {"config": 0, "docs": 0, "other": 0, "source": 0, "tests": 0}
        index = 0
        while index < len(entries):
            entry = entries[index]
            changed += 1
            status_code = entry[:2]
            category = classify_changed_path(entry[3:] if len(entry) > 3 else "")
            categories[category] += 1
            index += 2 if "R" in status_code or "C" in status_code else 1
        signals.append(f"The working tree reports {changed} changed path(s); this is activity evidence, not value evidence.")
        evidence.append(f"{project_id}:git:status")
        active_categories = ", ".join(f"{name}={count}" for name, count in categories.items() if count)
        if active_categories:
            signals.append(
                f"Changed paths are classified without publishing filenames: {active_categories}; categories do not establish priority."
            )
            evidence.append(f"{project_id}:git:change-categories")
        report["changed_path_count"] = changed
        report["changed_path_categories"] = categories
    head_date = _run_git(root, "log", "-1", "--format=%cI")
    if head_date:
        signals.append(f"The latest recorded commit date is {head_date}; recency does not establish project importance.")
        evidence.append(f"{project_id}:git:head-date")
        report["head_date_available"] = True
    commits_30d = _run_git(root, "rev-list", "--count", "--since=30 days ago", "HEAD")
    if commits_30d and commits_30d.isdigit():
        signals.append(
            f"Git reports {int(commits_30d)} commit(s) in the last 30 days; activity does not establish usage or value."
        )
        evidence.append(f"{project_id}:git:commits-30d")
        report["commits_30d"] = int(commits_30d)
    return signals, evidence, report


def _derive_state_relationships(projects: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Derive only explicit blocker references between approved project aliases."""
    relationships: list[dict[str, str]] = []
    for source in projects:
        for item in source.get("state_items", []):
            if (
                item["kind"] != "blocker"
                or item.get("status") != "open"
                or item["freshness"] in {"stale", "future-dated"}
                or item.get("provenance") not in {"project-state", "approved-review"}
            ):
                continue
            lowered = item["text"].casefold()
            for target in projects:
                if target["id"] == source["id"]:
                    continue
                aliases = {target["id"].casefold(), target["name"].casefold()}
                if not any(
                    len(alias) >= 3 and re.search(rf"(?<![\w-]){re.escape(alias)}(?![\w-])", lowered)
                    for alias in aliases
                ):
                    continue
                relationships.append(
                    {
                        "source": source["id"],
                        "target": target["id"],
                        "type": "blocked-by",
                        "layer": "observed",
                        "summary": "An approved current-state blocker explicitly names the target project.",
                        "evidence": item["evidence"],
                    }
                )
    return relationships


def _load_config(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ManifestError(f"invalid JSON in {path.name}: {exc.msg}") from exc
    config = _mapping(raw, "config")
    _keys(config, CONFIG_KEYS, "config")
    if config.get("schema_version") != "0.2":
        raise ManifestError("workspace config schema_version must be 0.2")
    return config


def collect_candidate(config_path: Path | str, *, observed_at: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    path = Path(config_path).resolve()
    config = _load_config(path)
    workspace = _mapping(config.get("workspace"), "workspace")
    _keys(workspace, WORKSPACE_KEYS, "workspace")
    normalized_workspace = {
        "name": _string(workspace.get("name"), "workspace.name"),
        "summary": _string(workspace.get("summary"), "workspace.summary"),
        "current_focus": _string(workspace.get("current_focus"), "workspace.current_focus"),
        "decisions": _strings(workspace.get("decisions", []), "workspace.decisions"),
        "unknowns": _strings(workspace.get("unknowns", []), "workspace.unknowns"),
    }

    skills: list[dict[str, str]] = []
    skill_reports: list[dict[str, Any]] = []
    skill_root_ids: set[str] = set()
    for index, raw_skill_root in enumerate(_list(config.get("skill_roots", []), "skill_roots")):
        skill_root = _mapping(raw_skill_root, f"skill_roots[{index}]")
        _keys(skill_root, SKILL_ROOT_KEYS, f"skill_roots[{index}]")
        root_id = str(_string(skill_root.get("id"), f"skill_roots[{index}].id"))
        provider = str(_string(skill_root.get("provider"), f"skill_roots[{index}].provider"))
        scope = str(_string(skill_root.get("scope"), f"skill_roots[{index}].scope"))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", root_id):
            raise ManifestError(f"skill_roots[{index}].id must be an identifier")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", provider):
            raise ManifestError(f"skill_roots[{index}].provider must be an identifier")
        if scope not in {"user", "workspace", "custom"}:
            raise ManifestError(f"skill_roots[{index}].scope must be user, workspace, or custom")
        if root_id in skill_root_ids:
            raise ManifestError(f"duplicate skill root id: {root_id}")
        skill_root_ids.add(root_id)
        raw_root = str(_string(skill_root.get("path"), f"skill_roots[{index}].path"))
        root_candidate = Path(raw_root).expanduser()
        unresolved_root = path.parent / root_candidate if not root_candidate.is_absolute() else root_candidate
        if unresolved_root.exists() and is_link_or_reparse(unresolved_root):
            raise ManifestError(f"skill_roots[{index}].path must not be a link or reparse point")
        root = unresolved_root.resolve()
        collected, root_report = collect_skill_root(
            root,
            root_id=root_id,
            provider=provider,
            scope=scope,
            approved_summaries=_string_mapping(
                skill_root.get("approved_summaries", {}), f"skill_roots[{index}].approved_summaries"
            ),
        )
        skills.extend(collected)
        skill_reports.append(root_report)

    timestamp = observed_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    try:
        observation_time = datetime.fromisoformat(timestamp)
    except ValueError as exc:
        raise ManifestError("observed_at must be an ISO 8601 timestamp") from exc
    projects: list[dict[str, Any]] = []
    report_projects: list[dict[str, Any]] = []
    relationship_inputs: dict[str, dict[str, Any]] = {}
    project_roots: dict[str, Path] = {}
    code_relationship_projects: set[str] = set()
    configured_project_ids: set[str] = set()
    detail_allowed_ids: set[str] = set()
    denied_project_count = 0
    summary_only_project_count = 0
    for index, raw_project in enumerate(_list(config.get("projects"), "projects")):
        project = _mapping(raw_project, f"projects[{index}]")
        _keys(project, CONFIG_PROJECT_KEYS, f"projects[{index}]")
        project_id = str(_string(project.get("id"), f"projects[{index}].id"))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", project_id):
            raise ManifestError(f"projects[{index}].id must be an identifier")
        if project_id in configured_project_ids:
            raise ManifestError(f"duplicate project id: {project_id}")
        configured_project_ids.add(project_id)
        registry_key = _string(project.get("registry_key"), f"projects[{index}].registry_key", optional=True)
        if registry_key and not re.fullmatch(r"(?:git-origin|path)-sha256:[0-9a-f]{64}", registry_key):
            raise ManifestError(f"projects[{index}].registry_key must be an opaque SHA-256 registry key")
        raw_root = str(_string(project.get("path"), f"projects[{index}].path"))
        root_candidate = Path(raw_root).expanduser()
        unresolved_root = path.parent / root_candidate if not root_candidate.is_absolute() else root_candidate
        if is_link_or_reparse(unresolved_root):
            raise ManifestError(f"projects[{index}].path must not be a symlink or reparse point")
        root = (path.parent / root_candidate).resolve() if not root_candidate.is_absolute() else root_candidate.resolve()
        if not root.is_dir():
            raise ManifestError(f"projects[{index}].path is not an existing directory")

        cloud_visibility = str(
            _string(
                project.get("cloud_visibility", "deny"),
                f"projects[{index}].cloud_visibility",
            )
        )
        sensitivity = str(
            _string(project.get("sensitivity", "private"), f"projects[{index}].sensitivity")
        )
        redaction_profile = str(
            _string(project.get("redaction_profile", "standard"), f"projects[{index}].redaction_profile")
        )
        approved_summary = _string(
            project.get("approved_summary"), f"projects[{index}].approved_summary", optional=True
        )
        if cloud_visibility not in {"allow", "summary-only", "deny"}:
            raise ManifestError(f"projects[{index}].cloud_visibility is unsupported")
        if sensitivity not in {"public", "internal", "private", "highly-sensitive"}:
            raise ManifestError(f"projects[{index}].sensitivity is unsupported")
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", redaction_profile):
            raise ManifestError(f"projects[{index}].redaction_profile must be an identifier")
        if cloud_visibility in {"allow", "summary-only"} and (
            "sensitivity" not in project or "redaction_profile" not in project
        ):
            raise ManifestError(
                f"projects[{index}] with cloud visibility requires explicit sensitivity and redaction_profile"
            )
        if cloud_visibility == "summary-only" and approved_summary is None:
            raise ManifestError(
                f"projects[{index}] with cloud_visibility=summary-only requires approved_summary"
            )
        if approved_summary is not None:
            validate_skill_summary(approved_summary, f"projects[{index}].approved_summary")
        architecture_visibility = str(
            _string(
                project.get("architecture_visibility", "disabled"),
                f"projects[{index}].architecture_visibility",
            )
        )
        if architecture_visibility not in ARCHITECTURE_MODES:
            raise ManifestError(f"projects[{index}].architecture_visibility is unsupported")
        if architecture_visibility != "disabled" and cloud_visibility != "allow":
            raise ManifestError(
                f"projects[{index}].architecture_visibility requires cloud_visibility=allow"
            )
        if project.get("attach_files") and cloud_visibility != "allow":
            raise ManifestError(f"projects[{index}].attach_files requires cloud_visibility=allow")
        if cloud_visibility == "deny":
            denied_project_count += 1
            report_projects.append(
                {
                    "id": project_id,
                    "cloud_visibility": "deny",
                    "sensitivity": sensitivity,
                    "redaction_profile": redaction_profile,
                    "metadata_files_read": [],
                    "observed_paths": [],
                    "warnings": ["Project excluded from the publishable candidate by cloud visibility policy."],
                    "git": {"repository": False},
                    "filename_inventory": {"files_inspected": 0},
                    "metadata_open_item_count": 0,
                    "state_files_read": [],
                    "state_item_count": 0,
                    "dependency_metadata_files_read": [],
                    "source_code_bodies_read": 0,
                    "architecture_index": {"status": "withheld-by-policy", "mode": architecture_visibility},
                }
            )
            continue
        if cloud_visibility == "summary-only":
            summary_only_project_count += 1
            configured_name = _string(project.get("name"), f"projects[{index}].name", optional=True)
            projects.append(
                {
                    "id": project_id,
                    "name": configured_name or project_id,
                    "summary": approved_summary,
                    "status": "summary-only; detailed project context withheld by policy",
                    "sensitivity": sensitivity,
                    "cloud_visibility": "summary-only",
                    "redaction_profile": redaction_profile,
                    "signals": [],
                    "constraints": [],
                    "risks": [],
                    "open_questions": [],
                    "state_items": [],
                    "evidence": [],
                }
            )
            relationship_inputs[project_id] = {
                "documents": {},
                "identities": set(),
                "dependencies": {},
                "dependency_sources": {},
            }
            report_projects.append(
                {
                    "id": project_id,
                    "cloud_visibility": "summary-only",
                    "sensitivity": sensitivity,
                    "redaction_profile": redaction_profile,
                    "metadata_files_read": [],
                    "observed_paths": [],
                    "warnings": ["Only the explicit approved summary was eligible for publication."],
                    "git": {"repository": False},
                    "filename_inventory": {"files_inspected": 0},
                    "metadata_open_item_count": 0,
                    "state_files_read": [],
                    "state_item_count": 0,
                    "dependency_metadata_files_read": [],
                    "source_code_bodies_read": 0,
                    "architecture_index": {"status": "withheld-by-policy", "mode": architecture_visibility},
                }
            )
            continue

        detail_allowed_ids.add(project_id)
        project_roots[project_id] = root
        if _boolean(project.get("code_relationship_scan"), f"projects[{index}].code_relationship_scan"):
            code_relationship_projects.add(project_id)

        allow_files = _strings(project.get("allow_files", list(DEFAULT_ALLOW_FILES)), f"projects[{index}].allow_files")
        attach_files = _strings(project.get("attach_files", []), f"projects[{index}].attach_files")
        if len(attach_files) > MAX_ATTACHED_DOCUMENTS or len(set(attach_files)) != len(attach_files):
            raise ManifestError(f"projects[{index}].attach_files must contain at most {MAX_ATTACHED_DOCUMENTS} unique paths")
        if not set(attach_files).issubset(allow_files):
            raise ManifestError(f"projects[{index}].attach_files must be selected from allow_files")
        dependency_files = _strings(project.get("dependency_files", []), f"projects[{index}].dependency_files")
        observed_paths = _strings(project.get("observe_paths", []), f"projects[{index}].observe_paths")
        state_files = _strings(project.get("state_files", []), f"projects[{index}].state_files")
        state_file_candidates = _strings(
            project.get("state_file_candidates", []), f"projects[{index}].state_file_candidates"
        )
        for item_index, raw_relative in enumerate(state_file_candidates):
            _state_path(raw_relative, f"projects[{index}].state_file_candidates[{item_index}]")
        documents: dict[str, str] = {}
        evidence: list[str] = []
        signals: list[str] = []
        metadata_warnings: list[str] = []
        observed_present: list[str] = []
        dependency_identities: set[str] = set()
        dependencies: dict[str, set[str]] = {}
        dependency_sources: dict[tuple[str, str], set[str]] = {}
        dependency_files_read: list[str] = []
        state_items: list[dict[str, Any]] = []
        state_files_read: list[str] = []
        for item_index, raw_relative in enumerate(allow_files):
            relative = _metadata_path(raw_relative, f"projects[{index}].allow_files[{item_index}]")
            unresolved = root / relative
            if is_link_or_reparse(unresolved):
                raise ManifestError(f"projects[{index}].allow_files[{item_index}] must not be a symlink")
            if raw_relative in attach_files:
                for parent in relative.parents:
                    if parent != Path(".") and is_link_or_reparse(root / parent):
                        raise ManifestError(f"projects[{index}].attach_files must not traverse links")
            target = _resolve_inside(root, relative, f"projects[{index}].allow_files[{item_index}]")
            if target.is_file():
                documents[relative.as_posix()] = _read_metadata(target, f"projects[{index}].allow_files[{item_index}]")
                signals.append(f"The allowlisted metadata file `{relative.as_posix()}` is present.")
                evidence.append(f"{project_id}:file:{relative.as_posix()}")

        attached_documents = []
        for name in sorted(attach_files):
            normalized_name = _metadata_path(name, "attach_files").as_posix()
            if normalized_name not in documents:
                raise ManifestError(f"projects[{index}].attach_files references a missing document")
            attached_documents.append(prepare_document(normalized_name, documents[normalized_name]))
        if sum(len(documents[document["path"]].encode("utf-8")) for document in attached_documents) > MAX_PROJECT_DOCUMENT_BYTES:
            raise ManifestError(f"projects[{index}].attach_files exceeds the {MAX_PROJECT_DOCUMENT_BYTES} byte project limit")

        for item_index, raw_relative in enumerate(dependency_files):
            relative = _dependency_path(raw_relative, f"projects[{index}].dependency_files[{item_index}]")
            unresolved = root / relative
            if is_link_or_reparse(unresolved):
                raise ManifestError(f"projects[{index}].dependency_files[{item_index}] must not be a link")
            target = _resolve_inside(root, relative, f"projects[{index}].dependency_files[{item_index}]")
            if not target.is_file():
                continue
            try:
                identities, declared = parse_dependency_metadata(target)
            except (OSError, UnicodeError, ValueError):
                metadata_warnings.append(
                    f"Dependency metadata `{relative.as_posix()}` could not be parsed; no relationship facts were derived from it."
                )
                continue
            dependency_files_read.append(relative.as_posix())
            dependency_identities.update(identities)
            for kind, names in declared.items():
                dependencies.setdefault(kind, set()).update(names)
                for dependency in names:
                    dependency_sources.setdefault((kind, dependency), set()).add(relative.as_posix())

        for item_index, raw_relative in enumerate(observed_paths):
            relative = _observable_path(raw_relative, f"projects[{index}].observe_paths[{item_index}]")
            unresolved = root / relative
            if unresolved.is_symlink():
                raise ManifestError(f"projects[{index}].observe_paths[{item_index}] must not be a symlink")
            target = _resolve_inside(root, relative, f"projects[{index}].observe_paths[{item_index}]")
            if target.exists():
                kind = "directory" if target.is_dir() else "file"
                signals.append(f"The allowlisted observed {kind} `{relative.as_posix()}` is present.")
                evidence.append(f"{project_id}:path:{relative.as_posix()}")
                observed_present.append(relative.as_posix())

        for item_index, raw_relative in enumerate(state_files):
            relative = _state_path(raw_relative, f"projects[{index}].state_files[{item_index}]")
            unresolved = root / relative
            if is_link_or_reparse(unresolved):
                raise ManifestError(f"projects[{index}].state_files[{item_index}] must not be a link")
            target = _resolve_inside(root, relative, f"projects[{index}].state_files[{item_index}]")
            if not target.is_file():
                continue
            state_text = _read_metadata(target, f"projects[{index}].state_files[{item_index}]")
            extracted = extract_state_items(
                state_text,
                project_id=project_id,
                relative_name=relative.as_posix(),
                observed_at=observation_time,
            )
            for state_index, state_item in enumerate(extracted):
                validate_publish_text(
                    state_item["text"],
                    f"projects[{index}].state_files[{item_index}].items[{state_index}]",
                )
            state_items.extend(extracted[: MAX_STATE_ITEMS_PER_PROJECT - len(state_items)])
            state_files_read.append(relative.as_posix())
            if len(state_items) >= MAX_STATE_ITEMS_PER_PROJECT:
                break

        architecture_index: dict[str, Any] | None = None
        architecture_report: dict[str, Any] = {
            "status": "disabled",
            "mode": "disabled",
            "files_scanned": 0,
            "source_bodies_read": 0,
            "source_bodies_published": 0,
        }
        if architecture_visibility != "disabled":
            architecture_index, architecture_report = collect_architecture_index(
                root,
                project_id=project_id,
                mode=architecture_visibility,
            )

        git_signals, git_evidence, git_report = _git_facts(root, project_id)
        signals.extend(git_signals)
        evidence.extend(git_evidence)
        inventory_signals, inventory_evidence, inventory_report = collect_filename_inventory(root, project_id)
        signals.extend(inventory_signals)
        evidence.extend(inventory_evidence)
        approved_overview = next(
            (
                documents[name]
                for name in ("README.md", "PROJECT_CHARTER.md", "AGENTS.md", "CLAUDE.md")
                if documents.get(name)
            ),
            "",
        )
        configured_name = _string(project.get("name"), f"projects[{index}].name", optional=True)
        configured_summary = _string(project.get("summary"), f"projects[{index}].summary", optional=True)
        name = configured_name or _safe_derived_text(
            _markdown_title(approved_overview), project_id, f"projects[{index}].derived_name", metadata_warnings
        )
        summary = approved_summary or configured_summary or _safe_derived_text(
            _markdown_summary(approved_overview),
            "Repository metadata was collected from explicitly allowlisted sources; no approved summary is available.",
            f"projects[{index}].derived_summary",
            metadata_warnings,
        )
        open_questions = _strings(project.get("open_questions", []), f"projects[{index}].open_questions")
        constraints = _strings(project.get("constraints", []), f"projects[{index}].constraints")
        for relative_name in ("AGENTS.md", "CLAUDE.md", "PROJECT_CHARTER.md"):
            if relative_name in attach_files:
                continue  # The complete, line-numbered document is already in the briefing.
            document = documents.get(relative_name)
            if not document:
                continue
            for item, line_number in _markdown_constraints(document):
                safe_item = _safe_derived_text(
                    item,
                    "",
                    f"projects[{index}].metadata_constraint",
                    metadata_warnings,
                )
                if not safe_item or safe_item in constraints:
                    continue
                constraints.append(safe_item)
                evidence.append(f"{project_id}:file:{relative_name}:line-{line_number}")
                if len(constraints) >= MAX_METADATA_CONSTRAINTS:
                    break
            if len(constraints) >= MAX_METADATA_CONSTRAINTS:
                break
        open_items_added = 0
        for relative_name, document in sorted(documents.items()):
            for item, line_number in _markdown_open_items(document):
                safe_item = _safe_derived_text(
                    item,
                    "",
                    f"projects[{index}].metadata_open_item",
                    metadata_warnings,
                )
                if not safe_item:
                    continue
                derived_question = f"Approved metadata open item from `{relative_name}`: {safe_item}"
                if derived_question not in open_questions:
                    open_questions.append(derived_question)
                evidence.append(f"{project_id}:file:{relative_name}:line-{line_number}")
                open_items_added += 1
                if open_items_added >= MAX_METADATA_OPEN_ITEMS:
                    break
            if open_items_added >= MAX_METADATA_OPEN_ITEMS:
                break
        status = _string(project.get("status"), f"projects[{index}].status", optional=True) or (
            "unknown; repository activity is not treated as project status"
        )
        projects.append(
            {
                "id": project_id,
                "name": name,
                "summary": summary,
                "status": status,
                "sensitivity": sensitivity,
                "cloud_visibility": "allow",
                "redaction_profile": redaction_profile,
                "signals": signals,
                "constraints": constraints,
                "risks": _strings(project.get("risks", []), f"projects[{index}].risks"),
                "open_questions": open_questions,
                "state_items": state_items,
                "evidence": evidence,
                **({"attached_documents": attached_documents} if attach_files else {}),
                "configuration_fields": sorted(
                    field for field in CONFIGURATION_FIELDS
                    if project.get(field) or (field == "summary" and approved_summary)
                ),
                **({"architecture_index": architecture_index} if architecture_index is not None else {}),
            }
        )
        report_projects.append(
            {
                "id": project_id,
                "cloud_visibility": "allow",
                "sensitivity": sensitivity,
                "redaction_profile": redaction_profile,
                "metadata_files_read": sorted(documents),
                **({"attached_documents": [{"path": item["path"], "redacted_lines": item["redacted_lines"]} for item in attached_documents]} if attach_files else {}),
                "observed_paths": sorted(observed_present),
                "warnings": metadata_warnings,
                "git": git_report,
                "filename_inventory": inventory_report,
                "metadata_open_item_count": open_items_added,
                "state_files_read": sorted(state_files_read),
                "state_item_count": len(state_items),
                "dependency_metadata_files_read": sorted(dependency_files_read),
                "source_code_bodies_read": int(architecture_report.get("source_bodies_read", 0)),
                "architecture_index": architecture_report,
            }
        )
        relationship_inputs[project_id] = {
            "documents": documents,
            "identities": dependency_identities,
            "dependencies": dependencies,
            "dependency_sources": dependency_sources,
        }

    session_reports: list[dict[str, Any]] = []
    projects_by_id = {project["id"]: project for project in projects}
    review_state_files = _strings(config.get("review_state_files", []), "review_state_files")
    if len(review_state_files) > MAX_REVIEW_STATE_FILES:
        raise ManifestError(f"review_state_files exceeds the {MAX_REVIEW_STATE_FILES} file limit")
    review_reports: list[dict[str, Any]] = []
    reviewed_projects: set[str] = set()
    for index, raw_review_path in enumerate(review_state_files):
        candidate_path = Path(raw_review_path).expanduser()
        unresolved = path.parent / candidate_path if not candidate_path.is_absolute() else candidate_path
        approved_by_project, review_report = read_review_state(
            unresolved.resolve(),
            project_ids=configured_project_ids,
            observed_at=observation_time,
        )
        overlap = reviewed_projects & set(approved_by_project)
        if overlap:
            raise ManifestError(
                f"review state files contain duplicate approved projects: {', '.join(sorted(overlap))}"
            )
        reviewed_projects.update(approved_by_project)
        for project_id, approved_items in approved_by_project.items():
            if project_id not in detail_allowed_ids:
                review_report.setdefault("projects_withheld_by_visibility", []).append(project_id)
                continue
            project_record = projects_by_id[project_id]
            project_record["state_items"] = [*approved_items, *project_record.get("state_items", [])]
        review_reports.append({"input": index + 1, **review_report})

    session_summary_files = _strings(config.get("session_summary_files", []), "session_summary_files")
    if len(session_summary_files) > MAX_SESSION_SUMMARY_FILES:
        raise ManifestError(f"session_summary_files exceeds the {MAX_SESSION_SUMMARY_FILES} file limit")
    session_item_counts: dict[str, int] = {}
    for index, raw_summary_path in enumerate(session_summary_files):
        candidate_path = Path(raw_summary_path).expanduser()
        unresolved = path.parent / candidate_path if not candidate_path.is_absolute() else candidate_path
        summary_path = unresolved.resolve()
        project_id, session_items, session_questions = read_session_summary(
            summary_path,
            project_ids=configured_project_ids,
            observed_at=observation_time,
        )
        if project_id not in detail_allowed_ids:
            session_reports.append(
                {
                    "input": index + 1,
                    "project_id": project_id,
                    "state_items_added": 0,
                    "questions_added": 0,
                    "withheld_by_visibility": True,
                }
            )
            continue
        project_record = projects_by_id[project_id]
        existing = {(item["kind"], item["text"].casefold()) for item in project_record.get("state_items", [])}
        accepted = [item for item in session_items if (item["kind"], item["text"].casefold()) not in existing]
        new_count = session_item_counts.get(project_id, 0) + len(accepted)
        if new_count > MAX_SESSION_ITEMS_PER_PROJECT:
            raise ManifestError(
                f"session summaries for {project_id} exceed the {MAX_SESSION_ITEMS_PER_PROJECT} state item limit"
            )
        session_item_counts[project_id] = new_count
        project_record["state_items"].extend(accepted)
        for question in session_questions:
            if question not in project_record["open_questions"]:
                project_record["open_questions"].append(question)
        session_reports.append(
            {"input": index + 1, "project_id": project_id, "state_items_added": len(accepted), "questions_added": len(session_questions)}
        )

    for project_record in projects:
        upgraded_records = [
            upgrade_state_item(project_record["id"], item, observed_at=observation_time)
            for item in project_record.get("state_items", [])
        ]
        resolved_by_id = {
            record["record_id"]: record
            for record in resolve_state_records(upgraded_records, [], observed_at=observation_time)
        }
        project_record["state_items"] = [resolved_by_id[record["record_id"]] for record in upgraded_records]

    raw_configured_relationships = _list(config.get("relationships", []), "relationships")
    relationships: list[dict[str, str]] = []
    configured_relationships_withheld = 0
    for index, raw_relationship in enumerate(raw_configured_relationships):
        relationship = _mapping(raw_relationship, f"relationships[{index}]")
        _keys(relationship, RELATIONSHIP_KEYS, f"relationships[{index}]")
        normalized_relationship = {
            key: str(_string(relationship.get(key), f"relationships[{index}].{key}"))
            for key in RELATIONSHIP_KEYS
        }
        if (
            normalized_relationship["source"] not in projects_by_id
            or normalized_relationship["target"] not in projects_by_id
        ):
            configured_relationships_withheld += 1
            continue
        relationships.append(normalized_relationship)

    configured_relationship_count = len(raw_configured_relationships)
    relationship_candidate_files = _strings(
        config.get("relationship_candidate_files", []), "relationship_candidate_files"
    )
    if len(relationship_candidate_files) > MAX_RELATIONSHIP_CANDIDATE_FILES:
        raise ManifestError(
            f"relationship_candidate_files exceeds the {MAX_RELATIONSHIP_CANDIDATE_FILES} file limit"
        )
    relationship_candidates: list[dict[str, str]] = []
    candidate_ids: set[str] = set()
    for index, raw_candidate_path in enumerate(relationship_candidate_files):
        candidate_path = Path(raw_candidate_path).expanduser()
        unresolved = path.parent / candidate_path if not candidate_path.is_absolute() else candidate_path
        loaded = read_relationship_candidates(unresolved.resolve(), project_ids=set(projects_by_id))
        overlap = candidate_ids & {item["candidate_id"] for item in loaded}
        if overlap:
            raise ManifestError(f"relationship candidate files contain duplicate IDs: {', '.join(sorted(overlap))}")
        candidate_ids.update(item["candidate_id"] for item in loaded)
        relationship_candidates.extend(loaded)
    derived_dependencies = derive_dependency_relationships(relationship_inputs)
    derived_code_paths, code_path_reports = derive_code_path_relationships(
        project_roots, code_relationship_projects
    )
    for project_report in report_projects:
        code_report = code_path_reports.get(project_report["id"])
        if code_report:
            project_report["code_relationship_scan"] = code_report
            project_report["source_code_bodies_read"] += code_report["source_code_bodies_read"]
    project_ids = set(detail_allowed_ids)
    repeated_fragments = repeated_reference_fragments(
        {project_id: inputs["documents"] for project_id, inputs in relationship_inputs.items()},
        project_ids=project_ids,
    )
    derived_documents = [
        relationship
        for source_id, inputs in sorted(relationship_inputs.items())
        for relationship in derive_document_relationships(
            source_id,
            inputs["documents"],
            project_ids,
            ignored_fragments=repeated_fragments,
        )
    ]
    derived_state = [
        relationship
        for relationship in _derive_state_relationships(projects)
        if relationship["source"] in detail_allowed_ids and relationship["target"] in detail_allowed_ids
    ]
    seen_relationships = {(item["source"], item["target"], item["type"]) for item in relationships}
    for relationship in [*derived_dependencies, *derived_code_paths, *derived_documents, *derived_state]:
        key = (relationship["source"], relationship["target"], relationship["type"])
        if key not in seen_relationships:
            relationships.append(relationship)
            seen_relationships.add(key)

    if not projects:
        raise ManifestError(
            "no projects are eligible for publication; classify at least one project as allow or summary-only"
        )

    candidate: dict[str, Any] = {
        "schema_version": "0.2",
        "generated_at": timestamp,
        "workspace": normalized_workspace,
        "projects": projects,
        "relationships": relationships,
        **({"skills": skills} if "skill_roots" in config else {}),
    }
    candidate = validate_manifest(candidate)
    candidate["facts_sha256"] = facts_sha256(candidate)
    candidate = validate_manifest(candidate)
    report = {
        "schema_version": "0.2",
        "generated_at": timestamp,
        "facts_sha256": candidate["facts_sha256"],
        "project_count": len(projects),
        "requires_human_approval": True,
        "untrusted_metadata_requires_review": True,
        "source_code_bodies_read": sum(int(item.get("source_code_bodies_read", 0)) for item in report_projects),
        "relationships": {
            "configured": configured_relationship_count,
            "configured_withheld_by_visibility": configured_relationships_withheld,
            "runtime_dependency": sum(item["type"] == "runtime-dependency" for item in derived_dependencies),
            "build_dependency": sum(item["type"] == "build-dependency" for item in derived_dependencies),
            "scans_or_indexes": len(derived_code_paths),
            "document_reference": len(derived_documents),
            "state_blocker": len(derived_state),
            "repeated_reference_fragments_ignored": len(repeated_fragments),
        },
        "skills": {
            "roots_configured": len(skill_reports),
            "roots_scanned": sum(report["status"] == "scanned" for report in skill_reports),
            "skills_collected": len(skills),
            "instruction_bodies_read": 0,
            "raw_summaries_withheld": sum(
                int(root_report.get("raw_summaries_withheld", 0)) for root_report in skill_reports
            ),
            "approved_summaries_used": sum(
                int(root_report.get("approved_summaries_used", 0)) for root_report in skill_reports
            ),
            "instruction_injection_findings": sum(
                int(root_report.get("instruction_injection_findings", 0)) for root_report in skill_reports
            ),
            "roots": skill_reports,
        },
        "semantic_safety": {
            "projects_configured": len(configured_project_ids),
            "projects_allowed": len(detail_allowed_ids),
            "projects_summary_only": summary_only_project_count,
            "projects_denied": denied_project_count,
            "missing_policy_defaults_to_deny": True,
        },
        "session_summaries": {
            "files_read": len(session_reports),
            "raw_transcripts_read": 0,
            "inputs": session_reports,
        },
        "review_state": {
            "files_read": len(review_reports),
            "projects_approved": len(reviewed_projects),
            "inputs": review_reports,
        },
        "relationship_candidates": {
            "files_read": len(relationship_candidate_files),
            "candidates_awaiting_review": len(relationship_candidates),
            "promoted_automatically": 0,
        },
        "architecture_index": {
            "projects_enabled": sum(
                item.get("architecture_index", {}).get("status") == "scanned" for item in report_projects
            ),
            "source_bodies_published": 0,
            "default_mode": "disabled",
        },
        "_relationship_review_queue": candidate_queue(relationship_candidates),
        "projects": sorted(report_projects, key=lambda item: item["id"]),
    }
    return candidate, report


def _change_summary(candidate: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    if previous is None:
        return {
            "baseline_available": False,
            "changed": True,
            "added_projects": sorted(project["id"] for project in candidate["projects"]),
            "removed_projects": [],
            "changed_projects": [],
            "changed_project_fields": {},
            "workspace_changed": True,
            "relationships_changed": bool(candidate["relationships"]),
            "skills_changed": bool(candidate.get("skills", [])),
        }
    current_projects = {project["id"]: project for project in candidate["projects"]}
    previous_projects = {project["id"]: project for project in previous["projects"]}
    added = sorted(set(current_projects) - set(previous_projects))
    removed = sorted(set(previous_projects) - set(current_projects))
    changed_projects = sorted(
        project_id
        for project_id in set(current_projects) & set(previous_projects)
        if current_projects[project_id] != previous_projects[project_id]
    )
    changed_project_fields = {
        project_id: sorted(
            key
            for key in set(current_projects[project_id]) | set(previous_projects[project_id])
            if key != "id" and current_projects[project_id].get(key) != previous_projects[project_id].get(key)
        )
        for project_id in changed_projects
    }
    workspace_changed = candidate["workspace"] != previous["workspace"]
    relationships_changed = candidate["relationships"] != previous["relationships"]
    skills_changed = candidate.get("skills", []) != previous.get("skills", [])
    return {
        "baseline_available": True,
        "changed": bool(added or removed or changed_projects or workspace_changed or relationships_changed or skills_changed),
        "added_projects": added,
        "removed_projects": removed,
        "changed_projects": changed_projects,
        "changed_project_fields": changed_project_fields,
        "workspace_changed": workspace_changed,
        "relationships_changed": relationships_changed,
        "skills_changed": skills_changed,
    }


def _reject_denied_references(value: Any, patterns: list[re.Pattern[str]]) -> None:
    if isinstance(value, str):
        if any(pattern.search(value) for pattern in patterns):
            raise ManifestError(
                "publishable candidate or historical state contains a reference withheld by cloud visibility policy; "
                "review the private input before scanning"
            )
    elif isinstance(value, dict):
        for item in value.values():
            _reject_denied_references(item, patterns)
    elif isinstance(value, list):
        for item in value:
            _reject_denied_references(item, patterns)


def _previous_in_current_scope(
    previous: dict[str, Any] | None,
    candidate: dict[str, Any],
    report: dict[str, Any],
) -> dict[str, Any] | None:
    """Create a policy-limited comparison view without changing private history.

    The original digest still identifies the private approved predecessor; this
    view is not a replacement snapshot and must not be written as one.
    """
    denied_ids = {
        project["id"]
        for project in report["projects"]
        if project.get("cloud_visibility") == "deny"
    }
    denied_aliases = denied_ids | {
        project["name"]
        for project in (previous["projects"] if previous is not None else [])
        if project["id"] in denied_ids
    }
    denied_patterns = [
        re.compile(rf"(?<![a-z0-9_-]){re.escape(alias)}(?![a-z0-9_-])", re.IGNORECASE)
        for alias in sorted(denied_aliases)
    ]
    _reject_denied_references(candidate, denied_patterns)
    if previous is None:
        return None
    summary_only = {
        project["id"]: project
        for project in candidate["projects"]
        if project.get("cloud_visibility") == "summary-only"
    }
    scoped = dict(previous)
    scoped["projects"] = [
        dict(summary_only.get(project["id"], project))
        for project in previous["projects"]
        if project["id"] not in denied_ids
    ]
    current_ids = {project["id"] for project in candidate["projects"]}
    for project in scoped["projects"]:
        if project["id"] in current_ids:
            _reject_denied_references(project.get("state_items", []), denied_patterns)
    withheld_relationship_ids = denied_ids | set(summary_only)
    scoped["relationships"] = [
        relationship
        for relationship in previous["relationships"]
        if relationship["source"] not in withheld_relationship_ids
        and relationship["target"] not in withheld_relationship_ids
    ]
    return scoped


def scan_workspace(
    config_path: Path | str,
    review_dir: Path | str,
    *,
    previous_manifest: Path | str | None = None,
    previous_snapshot: Path | str | None = None,
    observed_at: str | None = None,
) -> ScanPaths:
    if previous_manifest is not None and previous_snapshot is not None:
        raise ManifestError("choose either previous_manifest or previous_snapshot, not both")
    candidate, report = collect_candidate(config_path, observed_at=observed_at)
    previous = (
        load_approved_snapshot(previous_snapshot)["manifest"]
        if previous_snapshot is not None
        else (load_manifest(previous_manifest) if previous_manifest is not None else None)
    )
    previous = _previous_in_current_scope(previous, candidate, report)
    lifecycle_time = datetime.fromisoformat(candidate["generated_at"])
    if previous is not None:
        previous_projects = {project["id"]: project for project in previous["projects"]}
        for project in candidate["projects"]:
            old_project = previous_projects.get(project["id"])
            old_records = [
                upgrade_state_item(project["id"], item, observed_at=lifecycle_time)
                for item in (old_project.get("state_items", []) if old_project else [])
            ]
            project["state_items"] = resolve_state_records(
                project.get("state_items", []), old_records, observed_at=lifecycle_time
            )
        candidate.pop("facts_sha256", None)
        candidate = validate_manifest(candidate)
        candidate["facts_sha256"] = facts_sha256(candidate)
        candidate = validate_manifest(candidate)
    report["changes"] = _change_summary(candidate, previous)
    report["previous_facts_sha256"] = previous.get("facts_sha256") if previous else None
    changes = report["changes"]
    snapshot_changes = {
        "baseline_available": changes["baseline_available"],
        "previous_facts_sha256": report["previous_facts_sha256"],
        "added_projects": changes["added_projects"],
        "removed_projects": changes["removed_projects"],
        "changed_projects": [
            {"id": project_id, "fields": changes["changed_project_fields"].get(project_id, [])}
            for project_id in changes["changed_projects"]
        ],
        "workspace_changed": changes["workspace_changed"],
        "relationships_changed": changes["relationships_changed"],
        "skills_changed": changes["skills_changed"],
    }
    snapshot_changes["changes_sha256"] = snapshot_changes_sha256(snapshot_changes)
    candidate["snapshot_changes"] = snapshot_changes
    candidate.pop("facts_sha256", None)
    candidate = validate_manifest(candidate)
    candidate["facts_sha256"] = facts_sha256(candidate)
    candidate = validate_manifest(candidate)
    report["facts_sha256"] = candidate["facts_sha256"]
    destination = Path(review_dir).resolve()
    if any(marker in part.lower() for part in destination.parts for marker in SYNC_DIRECTORY_MARKERS):
        raise ManifestError("review_dir appears to be cloud-synced; review artifacts must stay private until build")
    candidate_path = destination / "candidate-manifest.json"
    report_path = destination / "scan-report.json"
    changes_json_path = destination / "changes.json"
    changes_markdown_path = destination / "changes.md"
    relationship_review_queue_path = destination / "relationship-review-queue.json"
    relationship_review_queue = report.pop("_relationship_review_queue", candidate_queue([]))
    git_appendix = [
        {
            "project_id": project_report["id"],
            **(
                {"changed_path_count": project_report["git"]["changed_path_count"]}
                if "changed_path_count" in project_report.get("git", {})
                else {}
            ),
            **(
                {"commits_30d": project_report["git"]["commits_30d"]}
                if "commits_30d" in project_report.get("git", {})
                else {}
            ),
        }
        for project_report in report["projects"]
        if project_report.get("git", {}).get("repository")
    ]
    semantic = semantic_changes(candidate, previous, git_activity_appendix=git_appendix)
    _atomic_write_text(candidate_path, json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(changes_json_path, json.dumps(semantic, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(changes_markdown_path, render_changes_markdown(semantic))
    _atomic_write_text(
        relationship_review_queue_path,
        json.dumps(relationship_review_queue, ensure_ascii=False, indent=2) + "\n",
    )
    return ScanPaths(
        candidate_manifest=candidate_path,
        report=report_path,
        changes_json=changes_json_path,
        changes_markdown=changes_markdown_path,
        relationship_review_queue=relationship_review_queue_path,
    )
