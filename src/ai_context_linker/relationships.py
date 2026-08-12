"""Deterministic, evidence-graded project relationship adapters."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path
from typing import Any


DEPENDENCY_METADATA_FILENAMES = ("pyproject.toml", "package.json", "Cargo.toml", "go.mod")
MAX_DEPENDENCY_METADATA_BYTES = 128 * 1024
GENERIC_REFERENCE_IDS = {"docs", "skills", "test", "tests"}


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
