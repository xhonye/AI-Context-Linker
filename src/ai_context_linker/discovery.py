"""Safe, shallow discovery of project candidates for private configuration.

Discovery inspects directory names and marker existence only. It does not read
source-code or metadata bodies, and its output is private input for ``scan``.
"""

from __future__ import annotations

import json
import hashlib
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
from urllib.parse import urlsplit, urlunsplit

from .adapters import is_link_or_reparse
from .core import ManifestError, _atomic_write_text, _check_output_path
from .relationships import DEPENDENCY_METADATA_FILENAMES
from .scanner import DEFAULT_ALLOW_FILES, SYNC_DIRECTORY_MARKERS
from .skills import default_user_skill_roots, project_skill_roots
from .state import STATE_FILENAMES


PROJECT_MARKERS = {
    ".git",
    "AGENTS.md",
    "CLAUDE.md",
    "README.md",
    "Cargo.toml",
    "go.mod",
    "package.json",
    "pyproject.toml",
}
PROJECT_DOCUMENT_SUFFIXES = {".md"}
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".idea",
    ".pytest_cache",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "chatgpt_google_drive",
    "dist",
    "node_modules",
    "output",
    "vendor",
    "venv",
}


@dataclass(frozen=True)
class DiscoveryResult:
    config: Path
    project_count: int


def _is_cloud_synced(path: Path) -> bool:
    return any(marker in part.lower() for part in path.parts for marker in SYNC_DIRECTORY_MARKERS)


def _project_id(name: str) -> str:
    candidate = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not candidate:
        candidate = "project"
    if not candidate[0].isalnum():
        candidate = f"project-{candidate}"
    return candidate[:63].rstrip("-")


def _unique_id(name: str, used: set[str]) -> str:
    base = _project_id(name)
    candidate = base
    suffix = 2
    while candidate in used:
        ending = f"-{suffix}"
        candidate = f"{base[: 63 - len(ending)].rstrip('-')}{ending}"
        suffix += 1
    used.add(candidate)
    return candidate


def _git_origin(root: Path) -> str | None:
    """Return a credential-free canonical Git origin for private identity matching."""
    try:
        result = subprocess.run(
            ["git", "-c", "credential.helper=", "config", "--get", "remote.origin.url"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    remote = result.stdout.strip()
    if "://" in remote:
        parsed = urlsplit(remote)
        host = parsed.hostname or ""
        if parsed.port:
            host = f"{host}:{parsed.port}"
        remote = urlunsplit((parsed.scheme.casefold(), host.casefold(), parsed.path, "", ""))
    else:
        remote = re.sub(r"^[^@/\\]+@", "", remote)
    return remote.rstrip("/\\").removesuffix(".git").casefold()


def _registry_key(root: Path) -> str:
    """Build a private opaque identity; raw origins and paths are never persisted here."""
    origin = _git_origin(root)
    if origin:
        digest = hashlib.sha256(origin.encode("utf-8")).hexdigest()
        return f"git-origin-sha256:{digest}"
    normalized_path = str(root.resolve()).replace("\\", "/").casefold()
    digest = hashlib.sha256(normalized_path.encode("utf-8")).hexdigest()
    return f"path-sha256:{digest}"


def _load_previous_config(previous_config: Path | str | None) -> dict:
    if previous_config is None:
        return {}
    path = Path(previous_config).expanduser()
    _check_output_path(path)
    resolved = path.resolve()
    if _is_cloud_synced(resolved):
        raise ManifestError("previous_config appears to be cloud-synced; the private registry must stay local")
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("previous_config must be readable valid JSON") from exc
    projects = raw.get("projects") if isinstance(raw, dict) else None
    if not isinstance(projects, list):
        raise ManifestError("previous_config.projects must be an array")
    def private_path(value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ManifestError("previous_config private paths must be non-empty strings")
        # Keep the old config's path meaning, without resolving away link evidence.
        return str((resolved.parent / Path(value).expanduser()).absolute())

    raw["projects"] = [dict(item) for item in projects if isinstance(item, dict)]
    for project in raw["projects"]:
        if "path" in project:
            project["path"] = private_path(project["path"])
    for key in ("review_state_files", "session_summary_files", "relationship_candidate_files"):
        if key in raw:
            if not isinstance(raw[key], list):
                raise ManifestError(f"previous_config.{key} must be an array")
            raw[key] = [private_path(value) for value in raw[key]]
    if "skill_roots" in raw:
        if not isinstance(raw["skill_roots"], list) or any(
            not isinstance(item, dict) for item in raw["skill_roots"]
        ):
            raise ManifestError("previous_config.skill_roots must be an array of objects")
        raw["skill_roots"] = [
            {**item, "path": private_path(item.get("path"))} for item in raw["skill_roots"]
        ]
    return raw


def _is_project_candidate(path: Path) -> bool:
    if any((path / marker).exists() for marker in PROJECT_MARKERS):
        return True
    try:
        return any(child.is_file() and child.suffix.lower() in PROJECT_DOCUMENT_SUFFIXES for child in path.iterdir())
    except OSError:
        return False


def discover_projects(
    roots: Iterable[Path | str], *, previous_config: Path | str | None = None
) -> list[dict[str, object]]:
    """Discover direct child projects under explicit roots without reading bodies."""
    previous = _load_previous_config(previous_config)
    return _discover_projects(roots, previous.get("projects", []))


def _discover_projects(roots: Iterable[Path | str], previous_projects: list[dict]) -> list[dict[str, object]]:
    resolved_roots: list[Path] = []
    for index, raw_root in enumerate(roots):
        unresolved_root = Path(raw_root).expanduser()
        if is_link_or_reparse(unresolved_root):
            raise ManifestError(f"roots[{index}] must not be a symlink or reparse point")
        root = unresolved_root.resolve()
        if not root.is_dir():
            raise ManifestError(f"roots[{index}] is not an existing directory")
        if _is_cloud_synced(root):
            raise ManifestError(f"roots[{index}] appears to be cloud-synced and cannot be discovered")
        if root not in resolved_roots:
            resolved_roots.append(root)

    candidates: dict[str, Path] = {}
    for root in resolved_roots:
        try:
            children = sorted(root.iterdir(), key=lambda item: item.name.casefold())
        except OSError as exc:
            raise ManifestError(f"cannot enumerate discovery root: {root.name}") from exc
        for child in children:
            if child.name.casefold() in EXCLUDED_DIRECTORY_NAMES:
                continue
            if is_link_or_reparse(child) or not child.is_dir() or not _is_project_candidate(child):
                continue
            resolved = child.resolve()
            if not resolved.is_relative_to(root):
                continue
            if resolved in resolved_roots:
                continue
            candidates.setdefault(str(resolved).casefold(), resolved)

    previous_by_registry: dict[str, list[str]] = {}
    previous_by_path: dict[str, str] = {}
    previous_by_id: dict[str, dict[str, object]] = {}
    for project in previous_projects:
        project_id = project.get("id")
        if not isinstance(project_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,62}", project_id):
            continue
        previous_by_id[project_id] = project
        key = project.get("registry_key")
        if isinstance(key, str):
            previous_by_registry.setdefault(key, []).append(project_id)
        raw_path = project.get("path")
        if isinstance(raw_path, str):
            previous_by_path[str(Path(raw_path).expanduser().resolve()).casefold()] = project_id

    candidate_keys = {root: _registry_key(root) for root in candidates.values()}
    current_key_counts: dict[str, int] = {}
    for key in candidate_keys.values():
        current_key_counts[key] = current_key_counts.get(key, 0) + 1

    reserved_ids = set(previous_by_id)
    used_ids: set[str] = set()
    projects: list[dict[str, object]] = []
    for root in sorted(candidates.values(), key=lambda item: (item.name.casefold(), str(item).casefold())):
        registry_key = candidate_keys[root]
        prior_ids = previous_by_registry.get(registry_key, [])
        reusable_id = None
        if current_key_counts[registry_key] == 1 and len(prior_ids) == 1 and prior_ids[0] not in used_ids:
            reusable_id = prior_ids[0]
        if reusable_id is None:
            same_path_id = previous_by_path.get(str(root).casefold())
            if same_path_id and same_path_id not in used_ids:
                reusable_id = same_path_id
        project_id = reusable_id or _unique_id(root.name, used_ids | reserved_ids)
        used_ids.add(project_id)
        allow_files = [name for name in DEFAULT_ALLOW_FILES if (root / name).is_file() and not (root / name).is_symlink()]
        detected_dependencies = [
            name
            for name in DEPENDENCY_METADATA_FILENAMES
            if (root / name).is_file() and not is_link_or_reparse(root / name)
        ]
        detected_state_files = [
            name
            for name in sorted(STATE_FILENAMES)
            if (root / name).is_file() and not is_link_or_reparse(root / name)
        ]
        previous = previous_by_id.get(reusable_id, {})
        preserved_fields = {
            key: previous[key]
            for key in (
                "name",
                "summary",
                "status",
                "sensitivity",
                "cloud_visibility",
                "redaction_profile",
                "approved_summary",
                "constraints",
                "risks",
                "open_questions",
                "code_relationship_scan",
                "architecture_visibility",
                "attach_files",
                "observe_paths",
            )
            if key in previous
        }
        projects.append(
            {
                "id": project_id,
                "path": str(root),
                "registry_key": registry_key,
                "allow_files": previous.get("allow_files", allow_files),
                "dependency_files": previous.get("dependency_files", detected_dependencies),
                "state_files": previous.get("state_files", []),
                "state_file_candidates": detected_state_files,
                "observe_paths": [],
                "sensitivity": previous.get("sensitivity", "private"),
                "cloud_visibility": previous.get("cloud_visibility", "deny"),
                "redaction_profile": previous.get("redaction_profile", "standard"),
                **preserved_fields,
            }
        )
    return projects


def discover_workspace(
    roots: Iterable[Path | str],
    config_path: Path | str,
    *,
    workspace_name: str | None = None,
    include_skills: bool = False,
    previous_config: Path | str | None = None,
    overwrite: bool = False,
) -> DiscoveryResult:
    """Write a private, reviewable workspace configuration for ``scan``."""
    _check_output_path(Path(config_path).expanduser())
    destination = Path(config_path).expanduser().resolve()
    if _is_cloud_synced(destination):
        raise ManifestError("config output appears to be cloud-synced; discovery configuration must stay private")
    if destination.exists() and not overwrite:
        raise ManifestError("config output already exists; pass --force only after reviewing the target")
    previous = _load_previous_config(previous_config)
    projects = _discover_projects(roots, previous.get("projects", []))
    if not projects:
        raise ManifestError("no project candidates found directly under the supplied roots")
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": workspace_name or "Discovered workspace",
            "summary": "Project candidates were discovered locally from explicit roots and require human review.",
            "current_focus": "Review included projects and approved metadata before scanning.",
            "decisions": ["Discovery inspects directory and marker existence only; it does not read source bodies."],
            "unknowns": ["Project importance, usage, status, and relationships remain unknown until reviewed."],
        },
        "projects": projects,
        "relationships": [],
        **(
            {"skill_roots": [*default_user_skill_roots(), *project_skill_roots(projects)]}
            if include_skills
            else {}
        ),
    }
    for key in ("workspace", "relationships", "review_state_files", "session_summary_files",
                "relationship_candidate_files"):
        if key in previous:
            config[key] = previous[key]
    if workspace_name is not None:
        if not isinstance(config["workspace"], dict):
            raise ManifestError("previous_config.workspace must be an object")
        config["workspace"] = {**config["workspace"], "name": workspace_name}
    if "skill_roots" in previous:
        known = {item.get("id") for item in previous["skill_roots"]}
        config["skill_roots"] = [
            *previous["skill_roots"],
            *(item for item in config.get("skill_roots", []) if item["id"] not in known),
        ]
    _atomic_write_text(destination, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return DiscoveryResult(config=destination, project_count=len(projects))
