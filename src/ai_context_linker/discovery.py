"""Safe, shallow discovery of project candidates for private configuration.

Discovery inspects directory names and marker existence only. It does not read
source-code or metadata bodies, and its output is private input for ``scan``.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from .adapters import is_link_or_reparse
from .core import ManifestError, _atomic_write_text
from .scanner import DEFAULT_ALLOW_FILES, SYNC_DIRECTORY_MARKERS


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


def _is_project_candidate(path: Path) -> bool:
    if any((path / marker).exists() for marker in PROJECT_MARKERS):
        return True
    try:
        return any(child.is_file() and child.suffix.lower() in PROJECT_DOCUMENT_SUFFIXES for child in path.iterdir())
    except OSError:
        return False


def discover_projects(roots: Iterable[Path | str]) -> list[dict[str, object]]:
    """Discover direct child projects under explicit roots without reading bodies."""
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

    used_ids: set[str] = set()
    projects: list[dict[str, object]] = []
    for root in sorted(candidates.values(), key=lambda item: (item.name.casefold(), str(item).casefold())):
        allow_files = [name for name in DEFAULT_ALLOW_FILES if (root / name).is_file() and not (root / name).is_symlink()]
        projects.append(
            {
                "id": _unique_id(root.name, used_ids),
                "path": str(root),
                "allow_files": allow_files,
                "observe_paths": [],
            }
        )
    return projects


def discover_workspace(
    roots: Iterable[Path | str],
    config_path: Path | str,
    *,
    workspace_name: str = "Discovered workspace",
    overwrite: bool = False,
) -> DiscoveryResult:
    """Write a private, reviewable workspace configuration for ``scan``."""
    destination = Path(config_path).expanduser().resolve()
    if _is_cloud_synced(destination):
        raise ManifestError("config output appears to be cloud-synced; discovery configuration must stay private")
    if destination.exists() and not overwrite:
        raise ManifestError("config output already exists; pass --force only after reviewing the target")
    projects = discover_projects(roots)
    if not projects:
        raise ManifestError("no project candidates found directly under the supplied roots")
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": workspace_name,
            "summary": "Project candidates were discovered locally from explicit roots and require human review.",
            "current_focus": "Review included projects and approved metadata before scanning.",
            "decisions": ["Discovery inspects directory and marker existence only; it does not read source bodies."],
            "unknowns": ["Project importance, usage, status, and relationships remain unknown until reviewed."],
        },
        "projects": projects,
        "relationships": [],
    }
    _atomic_write_text(destination, json.dumps(config, ensure_ascii=False, indent=2) + "\n")
    return DiscoveryResult(config=destination, project_count=len(projects))
