"""Bounded, filename-only project fact adapters.

These adapters inspect names and filesystem metadata, never file bodies. Their
signals describe observable structure without claiming quality, usage, or value.
"""

from __future__ import annotations

from collections import deque
from pathlib import Path


EXCLUDED_WALK_DIRECTORIES = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    ".venv",
    ".vscode",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "output",
    "site-packages",
    "target",
    "vendor",
    "venv",
}
ENTRY_POINT_NAMES = {
    "app.py",
    "cli.py",
    "index.js",
    "index.ts",
    "main.go",
    "main.js",
    "main.py",
    "main.rs",
    "main.ts",
    "manage.py",
    "server.js",
    "server.py",
    "server.ts",
}
TEST_DIRECTORY_NAMES = {"spec", "specs", "test", "tests"}
WINDOWS_REPARSE_POINT = 0x400


def is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & WINDOWS_REPARSE_POINT)
    except OSError:
        return True


def _looks_like_test_file(path: Path) -> bool:
    name = path.name.casefold()
    suffixes = "".join(path.suffixes).casefold()
    return (
        name.startswith("test_")
        or name.endswith("_test.py")
        or ".test." in name
        or ".spec." in name
        or suffixes in {".feature"}
    )


def collect_filename_inventory(
    root: Path,
    project_id: str,
    *,
    max_depth: int = 5,
    max_entries: int = 20_000,
) -> tuple[list[str], list[str], dict[str, object]]:
    """Collect bounded entry-point and test facts from names only."""
    queue: deque[tuple[Path, int]] = deque([(root, 0)])
    inspected = 0
    entry_points: set[str] = set()
    test_files = 0
    truncated = False

    while queue:
        directory, depth = queue.popleft()
        try:
            children = sorted(directory.iterdir(), key=lambda item: item.name.casefold())
        except OSError:
            continue
        for child in children:
            inspected += 1
            if inspected > max_entries:
                truncated = True
                queue.clear()
                break
            if is_link_or_reparse(child):
                continue
            if child.is_dir():
                if depth < max_depth and child.name.casefold() not in EXCLUDED_WALK_DIRECTORIES:
                    resolved = child.resolve()
                    if resolved.is_relative_to(root):
                        queue.append((resolved, depth + 1))
                continue
            if not child.is_file():
                continue
            if child.name.casefold() in ENTRY_POINT_NAMES:
                entry_points.add(child.name.casefold())
            if _looks_like_test_file(child.relative_to(root)):
                test_files += 1

    signals: list[str] = []
    evidence: list[str] = []
    if entry_points:
        rendered = ", ".join(f"`{name}`" for name in sorted(entry_points))
        signals.append(f"Conventional entry-point filename(s) detected: {rendered}; file contents were not read.")
        evidence.append(f"{project_id}:inventory:entry-points")
    if test_files:
        signals.append(
            f"Filename-only inventory detected {test_files} test file(s); test contents and outcomes were not inspected."
        )
        evidence.append(f"{project_id}:inventory:test-files")
    if truncated:
        signals.append(
            f"Filename inventory stopped at the {max_entries} entry safety limit; structural coverage is incomplete."
        )
        evidence.append(f"{project_id}:inventory:truncated")
    report = {
        "entries_inspected": min(inspected, max_entries),
        "entry_point_names": sorted(entry_points),
        "test_file_count": test_files,
        "truncated": truncated,
        "source_code_bodies_read": 0,
    }
    return signals, evidence, report


def classify_changed_path(raw_path: str) -> str:
    """Classify a Git-relative path without exposing it in published output."""
    path = raw_path.replace("\\", "/").casefold()
    name = path.rsplit("/", 1)[-1]
    suffix = Path(name).suffix
    parts = set(path.split("/"))
    if parts & TEST_DIRECTORY_NAMES or name.startswith("test_") or ".test." in name or ".spec." in name:
        return "tests"
    if suffix in {".md", ".mdx", ".rst", ".txt"} or "docs" in parts:
        return "docs"
    if suffix in {".json", ".toml", ".yaml", ".yml"} or name in {"dockerfile", "makefile"}:
        return "config"
    if suffix in {
        ".c",
        ".cc",
        ".cpp",
        ".cs",
        ".go",
        ".java",
        ".js",
        ".jsx",
        ".kt",
        ".php",
        ".py",
        ".rb",
        ".rs",
        ".sh",
        ".swift",
        ".ts",
        ".tsx",
    }:
        return "source"
    return "other"
