"""Bounded ancestor dependency declarations, never child ownership edges."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .adapters import is_link_or_reparse
from .core import ManifestError, validate_publish_text
from .relationships import DEPENDENCY_METADATA_FILENAMES, parse_dependency_metadata

MAX_ANCESTOR_DEPTH = 32
MAX_SHARED_NAMES = 100
SAFE_NAME = re.compile(r"[a-z0-9@][a-z0-9@._/+\-]{0,199}\Z")


def repository_boundary(root: Path) -> Path | None:
    """Find the nearest physical Git marker without following links."""
    for depth, directory in enumerate((root, *root.parents)):
        if depth > MAX_ANCESTOR_DEPTH or is_link_or_reparse(directory):
            return None
        marker = directory / ".git"
        if is_link_or_reparse(marker):
            return None
        if marker.exists():
            return directory
    return None


def collect_shared_dependencies(
    root: Path, repository: Path, *, project_id: str, excluded_roots: list[Path],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    """Read nearest ancestor per supported filename, capped at four files.

    No package identities or dependencies are returned to relationship adapters.
    All provenance paths are repository-relative, never parent traversals.
    """
    signals: list[str] = []
    evidence: list[str] = []
    report: list[dict[str, Any]] = []
    if root == repository or not root.is_relative_to(repository):
        return signals, evidence, report
    remaining = set(DEPENDENCY_METADATA_FILENAMES)
    for directory in root.parents:
        if not directory.is_relative_to(repository):
            break
        if is_link_or_reparse(directory) or any(directory.is_relative_to(p) for p in excluded_roots):
            report.append({"status": "withheld-by-policy"})
            break
        for name in sorted(remaining):
            target = directory / name
            if not target.exists() and not target.is_symlink():
                continue
            remaining.remove(name)  # Do not fall through a broken nearer declaration.
            relative = target.relative_to(repository).as_posix()
            entry: dict[str, Any] = {"path": relative, "scope": "repository-shared"}
            report.append(entry)
            try:
                validate_publish_text(relative, "shared dependency path")
                if any(part.startswith(".") for part in target.relative_to(repository).parts):
                    raise ValueError("hidden path")
                if is_link_or_reparse(target) or not target.is_file():
                    raise ValueError("link or non-file")
                _, declared = parse_dependency_metadata(target)
                groups: list[str] = []
                omitted = 0
                remaining_chars = 2800
                remaining_names = MAX_SHARED_NAMES
                for kind, names in sorted(declared.items()):
                    safe_names: list[str] = []
                    for value in sorted(names):
                        if not SAFE_NAME.fullmatch(value):
                            omitted += 1
                            continue
                        try:
                            validate_publish_text(value, "shared dependency name")
                        except ManifestError:
                            omitted += 1
                            continue
                        safe_names.append(value)
                    # Keep each signal within the existing 4,000-character contract.
                    selected: list[str] = []
                    for value in safe_names:
                        if remaining_names == 0 or len(value) + 2 > remaining_chars:
                            omitted += 1
                        else:
                            selected.append(value)
                            remaining_names -= 1
                            remaining_chars -= len(value) + 2
                    groups.append(f"{kind}: {', '.join(selected) or 'none extracted'}")
                body = '; '.join(groups)
                signals.append(
                    f"Repository-shared dependency declarations from `{relative}` "
                    f"(repository-relative): {body}. Child usage is unknown; "
                    "these are not confirmed child dependencies or a complete environment inventory."
                    + (" Some names were omitted by safety or size limits." if omitted else "")
                )
                entry.update(status="read", omitted_names=omitted)
                evidence.append(f"{project_id}:repository-dependency-metadata:{relative}")
            except (OSError, UnicodeError, ValueError, ManifestError):
                # Never retain parser messages, absolute paths, URLs or source text.
                entry["status"] = "unavailable"
                try:
                    validate_publish_text(relative, "shared dependency path")
                except ManifestError:
                    entry.pop("path", None)
                    relative = "withheld path"
                signals.append(f"Repository-shared dependency metadata `{relative}` was unavailable; shared dependencies remain unknown.")
        if directory == repository or not remaining:
            break
    return signals, evidence, report
