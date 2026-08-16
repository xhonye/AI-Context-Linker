"""Deterministic, evidence-graded project relationship adapters."""

from __future__ import annotations

import json
import re
import tomllib
from collections import deque
from pathlib import Path
from typing import Any

from .adapters import EXCLUDED_WALK_DIRECTORIES, is_link_or_reparse


DEPENDENCY_METADATA_FILENAMES = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod")
MAX_DEPENDENCY_METADATA_BYTES = 128 * 1024
GENERIC_REFERENCE_IDS = {"docs", "skills", "test", "tests"}
CODE_RELATIONSHIP_EXTENSIONS = {".py", ".js", ".ts", ".ps1", ".json", ".yaml", ".yml", ".toml"}
MAX_CODE_RELATIONSHIP_BYTES = 256 * 1024
SENSITIVE_CODE_PATH_MARKERS = {"credential", "secret", "token", "password", "private-key", "private_key"}


def _package_key(value: str) -> str:
    return re.sub(r"[-_.]+", "-", value.strip().casefold())


def _python_dependency_name(value: str) -> str | None:
    match = re.match(r"\s*([A-Za-z0-9][A-Za-z0-9_.-]*)", value)
    return _package_key(match.group(1)) if match else None


def _parse_pyproject(raw: bytes) -> tuple[set[str], set[str]]:
    data = tomllib.loads(raw.decode("utf-8"))
    project = data.get("project", {}) if isinstance(data, dict) else {}
    identities = {_package_key(project["name"])} if isinstance(project.get("name"), str) else set()
    dependencies: set[str] = set()
    for value in project.get("dependencies", []) if isinstance(project, dict) else []:
        if isinstance(value, str) and (name := _python_dependency_name(value)):
            dependencies.add(name)
    optional = project.get("optional-dependencies", {}) if isinstance(project, dict) else {}
    if isinstance(optional, dict):
        for values in optional.values():
            if isinstance(values, list):
                for value in values:
                    if isinstance(value, str) and (name := _python_dependency_name(value)):
                        dependencies.add(name)
    return identities, dependencies


def _parse_package_json(raw: bytes) -> tuple[set[str], set[str]]:
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("package.json root must be an object")
    identities = {_package_key(data["name"])} if isinstance(data.get("name"), str) else set()
    dependencies: set[str] = set()
    for section in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        values = data.get(section, {})
        if isinstance(values, dict):
            dependencies.update(_package_key(name) for name in values if isinstance(name, str))
    return identities, dependencies


def _parse_cargo(raw: bytes) -> tuple[set[str], set[str]]:
    data = tomllib.loads(raw.decode("utf-8"))
    package = data.get("package", {}) if isinstance(data, dict) else {}
    identities = {_package_key(package["name"])} if isinstance(package.get("name"), str) else set()
    dependencies: set[str] = set()
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        values = data.get(section, {}) if isinstance(data, dict) else {}
        if isinstance(values, dict):
            dependencies.update(_package_key(name) for name in values if isinstance(name, str))
    return identities, dependencies


def _parse_go_mod(raw: bytes) -> tuple[set[str], set[str]]:
    text = raw.decode("utf-8")
    identities: set[str] = set()
    dependencies: set[str] = set()
    in_require = False
    for raw_line in text.splitlines():
        line = raw_line.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("module "):
            identities.add(_package_key(line.removeprefix("module ").strip()))
        elif line == "require (":
            in_require = True
        elif in_require and line == ")":
            in_require = False
        elif line.startswith("require "):
            dependencies.add(_package_key(line.removeprefix("require ").split()[0]))
        elif in_require:
            dependencies.add(_package_key(line.split()[0]))
    return identities, dependencies


def parse_dependency_metadata(path: Path) -> tuple[set[str], set[str]]:
    if path.stat().st_size > MAX_DEPENDENCY_METADATA_BYTES:
        raise ValueError(f"{path.name} exceeds dependency metadata size limit")
    raw = path.read_bytes()
    if path.name == "pyproject.toml":
        return _parse_pyproject(raw)
    if path.name == "package.json":
        return _parse_package_json(raw)
    if path.name == "Cargo.toml":
        return _parse_cargo(raw)
    if path.name == "go.mod":
        return _parse_go_mod(raw)
    raise ValueError("unsupported dependency metadata filename")


def derive_dependency_relationships(
    project_metadata: dict[str, dict[str, Any]],
) -> list[dict[str, str]]:
    identity_owners: dict[str, set[str]] = {}
    for project_id, metadata in project_metadata.items():
        for identity in metadata.get("identities", set()):
            identity_owners.setdefault(identity, set()).add(project_id)

    relationships: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for source, metadata in sorted(project_metadata.items()):
        for dependency in sorted(metadata.get("dependencies", set())):
            owners = identity_owners.get(dependency, set())
            if len(owners) != 1:
                continue
            target = next(iter(owners))
            if target == source or (source, target) in seen:
                continue
            seen.add((source, target))
            source_files = sorted(metadata.get("dependency_sources", {}).get(dependency, []))
            source_file = source_files[0] if source_files else "dependency-metadata"
            relationships.append(
                {
                    "source": source,
                    "target": target,
                    "type": "declared-dependency",
                    "summary": f"Structured dependency metadata declares a dependency on `{target}`.",
                    "evidence": f"{source}:dependency-metadata:{source_file}:{target}",
                }
            )
    return relationships


def derive_document_relationships(
    source_id: str,
    documents: dict[str, str],
    project_ids: set[str],
    *,
    ignored_fragments: set[str] | None = None,
) -> list[dict[str, str]]:
    relationships: list[dict[str, str]] = []
    seen: set[str] = set()
    eligible_targets = sorted(project_ids - {source_id} - GENERIC_REFERENCE_IDS)
    if not eligible_targets:
        return relationships
    patterns = {
        target: re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(target)}(?![A-Za-z0-9_-])", re.I)
        for target in eligible_targets
        if len(target) >= 4
    }
    ignored = ignored_fragments or set()
    for filename, line_number, searchable in iter_explicit_reference_fragments(documents):
        if searchable.casefold() in ignored:
            continue
        for target, pattern in patterns.items():
            if target in seen or not pattern.search(searchable):
                continue
            seen.add(target)
            relationships.append(
                {
                    "source": source_id,
                    "target": target,
                    "type": "document-reference",
                    "summary": f"Approved metadata explicitly references `{target}`; this is not dependency proof.",
                    "evidence": f"{source_id}:file:{filename}:line-{line_number}",
                }
            )
    return relationships


def iter_explicit_reference_fragments(documents: dict[str, str]) -> list[tuple[str, int, str]]:
    fragments: list[tuple[str, int, str]] = []
    for filename, text in sorted(documents.items()):
        in_fence = False
        for line_number, raw_line in enumerate(text.splitlines(), start=1):
            line = raw_line.strip()
            if line.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            explicit_fragments = re.findall(r"`([^`]+)`|\]\(([^)]+)\)", line)
            searchable = " ".join(first or second for first, second in explicit_fragments)
            if not searchable:
                continue
            fragments.append((filename, line_number, searchable))
    return fragments


def repeated_reference_fragments(
    documents_by_project: dict[str, dict[str, str]],
    *,
    project_ids: set[str] | None = None,
    min_projects: int = 3,
) -> set[str]:
    owners: dict[str, set[str]] = {}
    reference_patterns = []
    if project_ids is not None:
        reference_patterns = [
            re.compile(rf"(?<![A-Za-z0-9_-]){re.escape(project_id)}(?![A-Za-z0-9_-])", re.I)
            for project_id in project_ids - GENERIC_REFERENCE_IDS
            if len(project_id) >= 4
        ]
    for project_id, documents in documents_by_project.items():
        for _, _, fragment in iter_explicit_reference_fragments(documents):
            if reference_patterns and not any(pattern.search(fragment) for pattern in reference_patterns):
                continue
            owners.setdefault(fragment.casefold(), set()).add(project_id)
    return {fragment for fragment, project_ids in owners.items() if len(project_ids) >= min_projects}


def derive_code_path_relationships(
    project_roots: dict[str, Path],
    enabled_projects: set[str],
    *,
    max_depth: int = 5,
    max_entries: int = 20_000,
    max_files: int = 1_000,
) -> tuple[list[dict[str, str]], dict[str, dict[str, int | bool]]]:
    """Find exact cross-project roots without publishing source text or absolute paths."""
    roots = {project_id: root.resolve() for project_id, root in project_roots.items()}
    relationships: list[dict[str, str]] = []
    reports: dict[str, dict[str, int | bool]] = {}
    for source_id in sorted(enabled_projects):
        source_root = roots[source_id]
        needles = {
            target_id: target_root.as_posix().casefold()
            for target_id, target_root in roots.items()
            if target_id != source_id
        }
        queue: deque[tuple[Path, int]] = deque([(source_root, 0)])
        entries_inspected = 0
        bodies_read = 0
        truncated = False
        seen_targets: set[str] = set()
        while queue and bodies_read < max_files:
            directory, depth = queue.popleft()
            try:
                children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
            except OSError:
                continue
            for child in children:
                entries_inspected += 1
                if entries_inspected > max_entries:
                    truncated = True
                    queue.clear()
                    break
                if is_link_or_reparse(child):
                    continue
                if child.is_dir():
                    if (
                        depth < max_depth
                        and not child.name.startswith(".")
                        and child.name.casefold() not in EXCLUDED_WALK_DIRECTORIES
                    ):
                        resolved = child.resolve()
                        if resolved.is_relative_to(source_root):
                            queue.append((resolved, depth + 1))
                    continue
                if (
                    not child.is_file()
                    or child.suffix.casefold() not in CODE_RELATIONSHIP_EXTENSIONS
                    or child.stat().st_size > MAX_CODE_RELATIONSHIP_BYTES
                ):
                    continue
                relative = child.relative_to(source_root)
                if {part.casefold() for part in relative.parts} & {"test", "tests", "fixture", "fixtures"}:
                    continue
                relative_lower = relative.as_posix().casefold()
                if any(marker in relative_lower for marker in SENSITIVE_CODE_PATH_MARKERS):
                    continue
                try:
                    lines = child.read_text(encoding="utf-8", errors="replace").splitlines()
                except OSError:
                    continue
                bodies_read += 1
                for line_number, line in enumerate(lines, start=1):
                    if line.lstrip().startswith(("#", "//", "<!--")):
                        continue
                    normalized = line.replace("\\", "/").casefold()
                    for target_id, needle in needles.items():
                        if target_id in seen_targets:
                            continue
                        start = normalized.find(needle)
                        if start < 0:
                            continue
                        if start > 0 and (
                            normalized[start - 1].isalnum()
                            or normalized[start - 1] in "._-"
                        ):
                            continue
                        end = start + len(needle)
                        if end < len(normalized) and normalized[end] not in "/\\\"'` )]}:,":
                            continue
                        seen_targets.add(target_id)
                        relationships.append(
                            {
                                "source": source_id,
                                "target": target_id,
                                "type": "code-path-dependency",
                                "summary": f"Allowlisted local code/config references the approved root of `{target_id}`.",
                                "evidence": f"{source_id}:code-path:{relative.as_posix()}:line-{line_number}",
                            }
                        )
                if bodies_read >= max_files:
                    truncated = True
                    break
        reports[source_id] = {
            "entries_inspected": min(entries_inspected, max_entries),
            "source_code_bodies_read": bodies_read,
            "truncated": truncated,
        }
    return sorted(relationships, key=lambda item: (item["source"], item["target"])), reports
