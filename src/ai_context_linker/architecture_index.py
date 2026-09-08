"""Deterministic, path-free architecture indexing for explicitly opted-in projects.

The adapter reads bounded Python and JavaScript/TypeScript syntax locally, but
publishes only relative module identifiers and structural names. Source text,
comments, docstrings, string values, absolute roots, and generic call noise are
never part of the returned index.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from .adapters import is_link_or_reparse
from .core import ManifestError


ARCHITECTURE_MODES = {"disabled", "modules-only", "modules-symbols"}
SOURCE_LANGUAGES = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}
EXCLUDED_DIRECTORY_NAMES = {
    ".git",
    ".hg",
    ".svn",
    ".tox",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "dist",
    "build",
    "out",
    "output",
    "outputs",
    "artifact",
    "artifacts",
    "coverage",
    "htmlcov",
    "__pycache__",
    "generated",
    "vendor",
    "vendors",
    "site-packages",
    "example",
    "examples",
    "sample",
    "samples",
    "demo",
    "demos",
    "fixture",
    "fixtures",
    "backup",
    "backups",
    "review",
    "reviews",
    "_pruned",
}
GENERIC_CALL_NAMES = {
    "add",
    "append",
    "close",
    "copy",
    "extend",
    "format",
    "get",
    "items",
    "join",
    "keys",
    "len",
    "list",
    "log",
    "map",
    "open",
    "pop",
    "print",
    "read",
    "remove",
    "replace",
    "set",
    "sort",
    "split",
    "str",
    "strip",
    "trim",
    "update",
    "values",
    "write",
}
JS_CONTROL_CALL_NAMES = {
    "catch",
    "class",
    "do",
    "for",
    "function",
    "if",
    "new",
    "return",
    "switch",
    "typeof",
    "while",
}
MAX_ARCHITECTURE_FILES = 500
MAX_ARCHITECTURE_FILE_BYTES = 256 * 1024
MAX_ARCHITECTURE_TOTAL_BYTES = 8 * 1024 * 1024


@dataclass
class _ParsedModule:
    module_id: str
    language: str
    test_module: bool
    symbols: set[str] = field(default_factory=set)
    raw_imports: list[tuple[str, int, list[tuple[str, str]]]] = field(default_factory=list)
    raw_calls: set[str] = field(default_factory=set)
    call_scopes: dict[str, set[tuple[str, ...]]] = field(default_factory=dict)
    internal_imports: set[str] = field(default_factory=set)
    external_packages: set[str] = field(default_factory=set)
    import_bindings: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    internal_calls: set[str] = field(default_factory=set)


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self) -> None:
        self.symbols: set[str] = set()
        self.imports: list[tuple[str, int, list[tuple[str, str]]]] = []
        self.calls: set[str] = set()
        self._scope: list[str] = []
        self._function_scopes: list[str] = []
        self.call_scopes: dict[str, set[tuple[str, ...]]] = {}

    def _qualified(self, name: str) -> str:
        return ".".join([*self._scope, name])

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.add(self._qualified(node.name))
        for expression in [*node.bases, *node.keywords, *node.decorator_list]:
            self.visit(expression)
        self._scope.append(node.name)
        for statement in node.body:
            self.visit(statement)
        self._scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        qualified = self._qualified(node.name)
        self.symbols.add(qualified)
        # Defaults, annotations and decorators are evaluated outside the body.
        self.visit(node.args)
        for decorator in node.decorator_list:
            self.visit(decorator)
        if node.returns:
            self.visit(node.returns)
        self._scope.append(node.name)
        self._function_scopes.append(qualified)
        for statement in node.body:
            self.visit(statement)
        self._function_scopes.pop()
        self._scope.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.visit_FunctionDef(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            bound = alias.asname or alias.name.split(".")[0]
            self.imports.append((alias.name, 0, [("*", bound)]))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        bindings = [(alias.name, alias.asname or alias.name) for alias in node.names if alias.name != "*"]
        self.imports.append((node.module or "", node.level, bindings))

    def visit_Call(self, node: ast.Call) -> None:
        name = _python_call_name(node.func)
        if name:
            self.calls.add(name)
            scopes = list(reversed(self._function_scopes))
            current_scope = ".".join(self._scope)
            if current_scope and current_scope not in self._function_scopes:
                scopes.insert(0, current_scope)
            self.call_scopes.setdefault(name, set()).add((*scopes, ""))
        self.generic_visit(node)


def _python_call_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return f"{node.value.id}.{node.attr}"
    return None


def _is_test_module(module_id: str) -> bool:
    path = PurePosixPath(module_id)
    lowered_parts = {part.casefold() for part in path.parts[:-1]}
    name = path.name.casefold()
    return bool(
        lowered_parts & {"test", "tests", "__tests__"}
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def _module_aliases(module_id: str) -> set[str]:
    path = PurePosixPath(module_id)
    without_suffix = path.with_suffix("")
    parts = list(without_suffix.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    aliases = {".".join(parts)} if parts else set()
    if len(parts) > 1 and parts[0] in {"src", "lib", "app"}:
        aliases.add(".".join(parts[1:]))
    return {alias for alias in aliases if alias}


def _python_import_name(module: _ParsedModule, raw_name: str, level: int) -> str:
    if level == 0:
        return raw_name
    package = list(PurePosixPath(module.module_id).with_suffix("").parts[:-1])
    keep = max(0, len(package) - (level - 1))
    base = package[:keep]
    if raw_name:
        base.extend(raw_name.split("."))
    return ".".join(base)


def _external_package(specifier: str) -> str:
    if specifier.startswith("@"):
        return "/".join(specifier.split("/")[:2])
    return specifier.split("/", 1)[0].split(".", 1)[0]


def _resolve_js_import(module_id: str, specifier: str, module_ids: set[str]) -> str | None:
    if not specifier.startswith("."):
        return None
    base = PurePosixPath(module_id).parent.joinpath(specifier)
    normalized_parts: list[str] = []
    for part in base.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if normalized_parts:
                normalized_parts.pop()
            continue
        normalized_parts.append(part)
    normalized = PurePosixPath(*normalized_parts).as_posix()
    candidates = [normalized]
    if PurePosixPath(normalized).suffix not in SOURCE_LANGUAGES:
        candidates.extend(f"{normalized}{suffix}" for suffix in (".ts", ".tsx", ".js", ".jsx"))
        candidates.extend(f"{normalized}/index{suffix}" for suffix in (".ts", ".tsx", ".js", ".jsx"))
    return next((candidate for candidate in candidates if candidate in module_ids), None)


def _mask_js_comments_and_strings(text: str) -> str:
    result = list(text)
    index = 0
    state = "code"
    quote = ""
    while index < len(result):
        char = result[index]
        nxt = result[index + 1] if index + 1 < len(result) else ""
        if state == "code" and char == "/" and nxt == "/":
            result[index] = result[index + 1] = " "
            index += 2
            state = "line-comment"
            continue
        if state == "code" and char == "/" and nxt == "*":
            result[index] = result[index + 1] = " "
            index += 2
            state = "block-comment"
            continue
        if state == "code" and char in {'"', "'", "`"}:
            quote = char
            result[index] = " "
            index += 1
            state = "string"
            continue
        if state == "line-comment":
            if char == "\n":
                state = "code"
            else:
                result[index] = " "
            index += 1
            continue
        if state == "block-comment":
            if char == "*" and nxt == "/":
                result[index] = result[index + 1] = " "
                index += 2
                state = "code"
            else:
                if char != "\n":
                    result[index] = " "
                index += 1
            continue
        if state == "string":
            if char == "\\":
                result[index] = " "
                if index + 1 < len(result):
                    if result[index + 1] != "\n":
                        result[index + 1] = " "
                    index += 2
                else:
                    index += 1
                continue
            if char == quote:
                result[index] = " "
                index += 1
                state = "code"
                continue
            if char != "\n":
                result[index] = " "
            index += 1
            continue
        index += 1
    return "".join(result)


def _js_imports(text: str, masked: str) -> list[tuple[str, int, list[tuple[str, str]]]]:
    imports: list[tuple[str, int, list[tuple[str, str]]]] = []
    pattern = re.compile(
        r"\bimport\s+(?P<clause>[^;\n]+?)\s+from\s+['\"](?P<spec>[^'\"]+)['\"]",
        re.MULTILINE,
    )
    for match in pattern.finditer(text):
        if masked[match.start()] == " ":
            continue
        clause = match.group("clause").strip()
        bindings: list[tuple[str, str]] = []
        brace = re.search(r"\{([^}]*)\}", clause)
        if brace:
            for raw in brace.group(1).split(","):
                parts = [part.strip() for part in re.split(r"\s+as\s+", raw.strip()) if part.strip()]
                if parts:
                    bindings.append((parts[0], parts[-1]))
        namespace = re.search(r"\*\s+as\s+([A-Za-z_$][\w$]*)", clause)
        if namespace:
            bindings.append(("*", namespace.group(1)))
        default = clause.split(",", 1)[0].strip()
        if re.fullmatch(r"[A-Za-z_$][\w$]*", default):
            bindings.append(("default", default))
        imports.append((match.group("spec"), 0, bindings))
    for match in re.finditer(
        r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*require\(\s*['\"]([^'\"]+)['\"]\s*\)",
        text,
    ):
        if masked[match.start()] != " ":
            imports.append((match.group(2), 0, [("*", match.group(1))]))
    return imports


def _parse_python(module_id: str, text: str) -> _ParsedModule:
    tree = ast.parse(text, filename=module_id)
    visitor = _PythonVisitor()
    visitor.visit(tree)
    return _ParsedModule(
        module_id=module_id,
        language="python",
        test_module=_is_test_module(module_id),
        symbols=visitor.symbols,
        raw_imports=visitor.imports,
        raw_calls=visitor.calls,
        call_scopes=visitor.call_scopes,
    )


def _parse_javascript(module_id: str, text: str, language: str) -> _ParsedModule:
    masked = _mask_js_comments_and_strings(text)
    symbols = {
        match.group(1)
        for pattern in (
            r"\bclass\s+([A-Za-z_$][\w$]*)",
            r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(",
            r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z_$][\w$]*)\s*=>",
        )
        for match in re.finditer(pattern, masked)
    }
    calls: set[str] = set()
    for match in re.finditer(r"(?<![\w$])([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)?)\s*\(", masked):
        name = match.group(1)
        prefix = masked[max(0, match.start() - 16) : match.start()]
        if re.search(r"\b(?:class|function)\s*$", prefix):
            continue
        if name.split(".")[-1] in JS_CONTROL_CALL_NAMES:
            continue
        calls.add(name)
    return _ParsedModule(
        module_id=module_id,
        language=language,
        test_module=_is_test_module(module_id),
        symbols=symbols,
        raw_imports=_js_imports(text, masked),
        raw_calls=calls,
    )


def _enumerate_source_files(root: Path) -> tuple[list[Path], int, bool]:
    files: list[Path] = []
    skipped_directories = 0
    truncated = False
    for current, raw_directories, raw_files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        directories: list[str] = []
        for name in sorted(raw_directories, key=str.casefold):
            candidate = current_path / name
            if (
                name.startswith(".")
                or name.casefold() in EXCLUDED_DIRECTORY_NAMES
                or is_link_or_reparse(candidate)
            ):
                skipped_directories += 1
                continue
            directories.append(name)
        raw_directories[:] = directories
        for name in sorted(raw_files, key=str.casefold):
            candidate = current_path / name
            if candidate.suffix.casefold() not in SOURCE_LANGUAGES or is_link_or_reparse(candidate):
                continue
            files.append(candidate)
            if len(files) >= MAX_ARCHITECTURE_FILES:
                truncated = True
                return files, skipped_directories, truncated
    return files, skipped_directories, truncated


def _resolve_structure(modules: list[_ParsedModule]) -> None:
    module_ids = {module.module_id for module in modules}
    python_aliases = {
        alias: module.module_id
        for module in modules
        if module.language == "python"
        for alias in _module_aliases(module.module_id)
    }
    symbols_by_module = {module.module_id: module.symbols for module in modules}
    for module in modules:
        for raw_name, level, bindings in module.raw_imports:
            if module.language == "python":
                resolved_name = _python_import_name(module, raw_name, level)
                base_target = python_aliases.get(resolved_name)
                found_internal = False
                for imported_name, bound_name in bindings:
                    submodule_name = (
                        f"{resolved_name}.{imported_name}" if resolved_name and imported_name != "*" else ""
                    )
                    target = python_aliases.get(submodule_name) or base_target
                    if target is None:
                        continue
                    found_internal = True
                    module.internal_imports.add(target)
                    module.import_bindings[bound_name] = (
                        target,
                        None
                        if python_aliases.get(submodule_name) or imported_name in {"*", "default"}
                        else imported_name,
                    )
                if not found_internal and level == 0:
                    package = _external_package(raw_name)
                    if package and package not in getattr(sys, "stdlib_module_names", set()):
                        module.external_packages.add(package)
                continue
            target = _resolve_js_import(module.module_id, raw_name, module_ids)
            if target is None:
                if not raw_name.startswith("."):
                    module.external_packages.add(_external_package(raw_name))
                continue
            module.internal_imports.add(target)
            for imported_name, bound_name in bindings:
                module.import_bindings[bound_name] = (
                    target,
                    None if imported_name in {"*", "default"} else imported_name,
                )

        for raw_call in module.raw_calls:
            called_name = raw_call.split(".")[-1]
            if called_name.casefold() in GENERIC_CALL_NAMES:
                continue
            target: tuple[str, str | None] | None = None
            if "." in raw_call:
                prefix, attribute = raw_call.split(".", 1)
                binding = module.import_bindings.get(prefix)
                if binding:
                    symbol = f"{binding[1]}.{attribute}" if binding[1] else attribute
                    target = (binding[0], symbol)
            else:
                binding = module.import_bindings.get(raw_call)
                if binding and binding[1]:
                    target = binding
                else:
                    for scopes in module.call_scopes.get(raw_call, {("",)}):
                        for scope in scopes:
                            symbol = f"{scope}.{raw_call}" if scope else raw_call
                            if symbol in module.symbols:
                                module.internal_calls.add(f"{module.module_id}::{symbol}")
                                break
            if target and target[1] and target[1] in symbols_by_module.get(target[0], set()):
                module.internal_calls.add(f"{target[0]}::{target[1]}")


def collect_architecture_index(
    root: Path,
    *,
    project_id: str,
    mode: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Collect a bounded structural index for one explicitly opted-in project."""
    if mode not in ARCHITECTURE_MODES - {"disabled"}:
        raise ManifestError("architecture visibility must be modules-only or modules-symbols")
    resolved_root = root.resolve()
    files, skipped_directories, truncated = _enumerate_source_files(resolved_root)
    parsed: list[_ParsedModule] = []
    parse_failures = 0
    oversized_files = 0
    total_bytes = 0
    source_bodies_read = 0
    for path in files:
        size = path.stat().st_size
        if size > MAX_ARCHITECTURE_FILE_BYTES or total_bytes + size > MAX_ARCHITECTURE_TOTAL_BYTES:
            oversized_files += 1
            truncated = True
            continue
        total_bytes += size
        module_id = path.relative_to(resolved_root).as_posix()
        try:
            source_bodies_read += 1
            text = path.read_text(encoding="utf-8")
            language = SOURCE_LANGUAGES[path.suffix.casefold()]
            module = (
                _parse_python(module_id, text)
                if language == "python"
                else _parse_javascript(module_id, text, language)
            )
        except (OSError, UnicodeError, SyntaxError):
            parse_failures += 1
            continue
        parsed.append(module)
    _resolve_structure(parsed)

    modules: list[dict[str, Any]] = []
    for module in sorted(parsed, key=lambda item: item.module_id):
        record: dict[str, Any] = {
            "id": module.module_id,
            "language": module.language,
            "test_module": module.test_module,
            "internal_imports": sorted(module.internal_imports),
            "external_packages": sorted(module.external_packages),
            "evidence": f"{project_id}:file:{module.module_id}",
        }
        if mode == "modules-symbols":
            record["symbols"] = sorted(module.symbols)
            record["internal_calls"] = sorted(module.internal_calls)
        modules.append(record)
    payload = {
        "mode": mode,
        "truncated": truncated,
        "parse_failures": parse_failures,
        "modules": modules,
    }
    digest = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    index = {"mode": mode, "map_sha256": digest, **payload}
    report = {
        "status": "scanned",
        "mode": mode,
        "files_scanned": len(parsed),
        "source_bodies_read": source_bodies_read,
        "source_bodies_published": 0,
        "bytes_read": total_bytes,
        "parse_failures": parse_failures,
        "oversized_files": oversized_files,
        "files_skipped_by_directory": skipped_directories,
        "truncated": truncated,
    }
    return index, report
