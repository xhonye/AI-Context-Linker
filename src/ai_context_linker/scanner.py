"""Deterministic, allowlist-only local workspace scanner.

The scanner produces a candidate manifest for human review. It never publishes
the bundle and never reads source-code bodies. Local paths remain confined to
the private scanner configuration.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .core import (
    ManifestError,
    _atomic_write_text,
    facts_sha256,
    load_manifest,
    validate_manifest,
    validate_publish_text,
)


CONFIG_KEYS = {"schema_version", "workspace", "projects", "relationships"}
CONFIG_PROJECT_KEYS = {
    "id",
    "path",
    "name",
    "summary",
    "status",
    "allow_files",
    "observe_paths",
    "risks",
    "open_questions",
}
WORKSPACE_KEYS = {"name", "summary", "current_focus", "decisions", "unknowns"}
RELATIONSHIP_KEYS = {"source", "target", "type", "summary", "evidence"}
DEFAULT_ALLOW_FILES = ("README.md", "AGENTS.md")
ALLOWED_METADATA_NAMES = {
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    "PROJECT_CHARTER.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
}
MAX_METADATA_BYTES = 64 * 1024
FORBIDDEN_OBSERVED_PARTS = {".git", ".ssh"}
FORBIDDEN_OBSERVED_MARKERS = {"credential", "secret", "token"}
FORBIDDEN_OBSERVED_SUFFIXES = {".db", ".key", ".p12", ".pem", ".sqlite", ".sqlite3"}
SYNC_DIRECTORY_MARKERS = {"dropbox", "google drive", "googledrive", "icloud", "onedrive"}


@dataclass(frozen=True)
class ScanPaths:
    candidate_manifest: Path
    report: Path


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
        if line.startswith(("#", "!", "<", ">", "- ", "* ", "+ ")) or re.match(r"^\d+\.\s", line):
            continue
        if line.startswith("[") and "](" in line:
            continue
        line = re.sub(r"!\[[^]]*\]\([^)]*\)", "", line)
        line = re.sub(r"\[([^]]+)\]\([^)]*\)", r"\1", line)
        line = re.sub(r"[`*_]", "", line).strip()
        if line:
            paragraph.append(line)
    return " ".join(paragraph)[:1000] or None


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


def _git_facts(root: Path, project_id: str) -> tuple[list[str], list[str]]:
    if not (root / ".git").exists():
        return [], []
    signals = ["A Git repository is present."]
    evidence = [f"{project_id}:git:repository"]
    branch = _run_git(root, "branch", "--show-current")
    if branch:
        signals.append(f"The current Git branch is `{branch}`.")
        evidence.append(f"{project_id}:git:branch")
    status = _run_git(root, "status", "--porcelain=v1", "-z")
    if status is not None:
        entries = [item for item in status.split("\0") if item]
        changed = 0
        index = 0
        while index < len(entries):
            entry = entries[index]
            changed += 1
            status_code = entry[:2]
            index += 2 if "R" in status_code or "C" in status_code else 1
        signals.append(f"The working tree reports {changed} changed path(s); this is activity evidence, not value evidence.")
        evidence.append(f"{project_id}:git:status")
    head_date = _run_git(root, "log", "-1", "--format=%cI")
    if head_date:
        signals.append(f"The latest recorded commit date is {head_date}; recency does not establish project importance.")
        evidence.append(f"{project_id}:git:head-date")
    return signals, evidence


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

    projects: list[dict[str, Any]] = []
    report_projects: list[dict[str, Any]] = []
    for index, raw_project in enumerate(_list(config.get("projects"), "projects")):
        project = _mapping(raw_project, f"projects[{index}]")
        _keys(project, CONFIG_PROJECT_KEYS, f"projects[{index}]")
        project_id = str(_string(project.get("id"), f"projects[{index}].id"))
        raw_root = str(_string(project.get("path"), f"projects[{index}].path"))
        root_candidate = Path(raw_root).expanduser()
        root = (path.parent / root_candidate).resolve() if not root_candidate.is_absolute() else root_candidate.resolve()
        if not root.is_dir():
            raise ManifestError(f"projects[{index}].path is not an existing directory")

        allow_files = _strings(project.get("allow_files", list(DEFAULT_ALLOW_FILES)), f"projects[{index}].allow_files")
        observed_paths = _strings(project.get("observe_paths", []), f"projects[{index}].observe_paths")
        documents: dict[str, str] = {}
        evidence: list[str] = []
        signals: list[str] = []
        metadata_warnings: list[str] = []
        observed_present: list[str] = []
        for item_index, raw_relative in enumerate(allow_files):
            relative = _metadata_path(raw_relative, f"projects[{index}].allow_files[{item_index}]")
            unresolved = root / relative
            if unresolved.is_symlink():
                raise ManifestError(f"projects[{index}].allow_files[{item_index}] must not be a symlink")
            target = _resolve_inside(root, relative, f"projects[{index}].allow_files[{item_index}]")
            if target.is_file():
                documents[relative.as_posix()] = _read_metadata(target, f"projects[{index}].allow_files[{item_index}]")
                signals.append(f"The allowlisted metadata file `{relative.as_posix()}` is present.")
                evidence.append(f"{project_id}:file:{relative.as_posix()}")

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

        git_signals, git_evidence = _git_facts(root, project_id)
        signals.extend(git_signals)
        evidence.extend(git_evidence)
        readme = documents.get("README.md", "")
        configured_name = _string(project.get("name"), f"projects[{index}].name", optional=True)
        configured_summary = _string(project.get("summary"), f"projects[{index}].summary", optional=True)
        name = configured_name or _safe_derived_text(
            _markdown_title(readme), project_id, f"projects[{index}].derived_name", metadata_warnings
        )
        summary = configured_summary or _safe_derived_text(
            _markdown_summary(readme),
            "Repository metadata was collected from explicitly allowlisted sources; no approved summary is available.",
            f"projects[{index}].derived_summary",
            metadata_warnings,
        )
        status = _string(project.get("status"), f"projects[{index}].status", optional=True) or (
            "unknown; repository activity is not treated as project status"
        )
        projects.append(
            {
                "id": project_id,
                "name": name,
                "summary": summary,
                "status": status,
                "signals": signals,
                "risks": _strings(project.get("risks", []), f"projects[{index}].risks"),
                "open_questions": _strings(
                    project.get("open_questions", []), f"projects[{index}].open_questions"
                ),
                "evidence": evidence,
            }
        )
        report_projects.append(
            {
                "id": project_id,
                "metadata_files_read": sorted(documents),
                "observed_paths": sorted(observed_present),
                "warnings": metadata_warnings,
                "source_code_bodies_read": 0,
            }
        )

    relationships: list[dict[str, str]] = []
    for index, raw_relationship in enumerate(_list(config.get("relationships", []), "relationships")):
        relationship = _mapping(raw_relationship, f"relationships[{index}]")
        _keys(relationship, RELATIONSHIP_KEYS, f"relationships[{index}]")
        relationships.append({key: str(_string(relationship.get(key), f"relationships[{index}].{key}")) for key in RELATIONSHIP_KEYS})

    timestamp = observed_at or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    candidate: dict[str, Any] = {
        "schema_version": "0.1",
        "generated_at": timestamp,
        "workspace": normalized_workspace,
        "projects": projects,
        "relationships": relationships,
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
        "source_code_bodies_read": 0,
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
            "workspace_changed": True,
            "relationships_changed": bool(candidate["relationships"]),
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
    workspace_changed = candidate["workspace"] != previous["workspace"]
    relationships_changed = candidate["relationships"] != previous["relationships"]
    return {
        "baseline_available": True,
        "changed": bool(added or removed or changed_projects or workspace_changed or relationships_changed),
        "added_projects": added,
        "removed_projects": removed,
        "changed_projects": changed_projects,
        "workspace_changed": workspace_changed,
        "relationships_changed": relationships_changed,
    }


def scan_workspace(
    config_path: Path | str,
    review_dir: Path | str,
    *,
    previous_manifest: Path | str | None = None,
    observed_at: str | None = None,
) -> ScanPaths:
    candidate, report = collect_candidate(config_path, observed_at=observed_at)
    previous = load_manifest(previous_manifest) if previous_manifest is not None else None
    report["changes"] = _change_summary(candidate, previous)
    report["previous_facts_sha256"] = previous.get("facts_sha256") if previous else None
    destination = Path(review_dir).resolve()
    if any(marker in part.lower() for part in destination.parts for marker in SYNC_DIRECTORY_MARKERS):
        raise ManifestError("review_dir appears to be cloud-synced; review artifacts must stay private until build")
    candidate_path = destination / "candidate-manifest.json"
    report_path = destination / "scan-report.json"
    _atomic_write_text(candidate_path, json.dumps(candidate, ensure_ascii=False, indent=2) + "\n")
    _atomic_write_text(report_path, json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return ScanPaths(candidate_manifest=candidate_path, report=report_path)
