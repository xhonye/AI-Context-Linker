from __future__ import annotations

import json
import subprocess
import sys

import pytest
from pathlib import Path

from ai_context_linker.architecture_index import collect_architecture_index


def _synthetic_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "src").mkdir(parents=True)
    (project / "tests").mkdir()
    (project / "web").mkdir()
    (project / "generated").mkdir()
    (project / ".tool-state").mkdir()
    (project / "output").mkdir()
    (project / "examples").mkdir()
    (project / "src" / "app.py").write_text(
        """\
from . import helpers
import requests

# C:/Users/example/private should never be published.
SECRET = "sk-example0123456789012345"

class Coordinator:
    def coordinate(self):
        return helpers.helper()

def run(items):
    def normalize(value):
        return value
    items.append(helpers.helper())
    return str(normalize(items))
""",
        encoding="utf-8",
    )
    (project / "src" / "helpers.py").write_text("def helper():\n    return 1\n", encoding="utf-8")
    (project / "tests" / "test_app.py").write_text(
        "from src.app import run\n\ndef test_run():\n    assert run([])\n",
        encoding="utf-8",
    )
    (project / "web" / "view.ts").write_text(
        """\
import { formatValue } from './format';
export function renderValue() {
  return formatValue().trim();
}
""",
        encoding="utf-8",
    )
    (project / "web" / "format.ts").write_text(
        "export const formatValue = () => 'safe';\n",
        encoding="utf-8",
    )
    (project / "generated" / "leak.py").write_text(
        "def generated_secret():\n    return 'do-not-index'\n",
        encoding="utf-8",
    )
    (project / ".tool-state" / "hidden.py").write_text(
        "def hidden_tool_state():\n    return None\n",
        encoding="utf-8",
    )
    (project / "output" / "installed_copy.py").write_text(
        "def stale_installed_copy():\n    return None\n",
        encoding="utf-8",
    )
    (project / "examples" / "sample.py").write_text(
        "def sample_only():\n    return None\n",
        encoding="utf-8",
    )
    return project


def test_architecture_index_is_path_free_deterministic_and_filters_call_noise(tmp_path: Path) -> None:
    project = _synthetic_project(tmp_path)

    first, report = collect_architecture_index(project, project_id="sample", mode="modules-symbols")
    second, _ = collect_architecture_index(project, project_id="sample", mode="modules-symbols")

    assert first == second
    assert first["map_sha256"] == second["map_sha256"]
    assert first["mode"] == "modules-symbols"
    modules = {module["id"]: module for module in first["modules"]}
    assert set(modules) == {
        "src/app.py",
        "src/helpers.py",
        "tests/test_app.py",
        "web/format.ts",
        "web/view.ts",
    }
    assert modules["src/app.py"]["language"] == "python"
    assert modules["src/app.py"]["symbols"] == [
        "Coordinator",
        "Coordinator.coordinate",
        "run",
        "run.normalize",
    ]
    assert modules["src/app.py"]["internal_imports"] == ["src/helpers.py"]
    assert modules["src/app.py"]["external_packages"] == ["requests"]
    assert modules["src/app.py"]["internal_calls"] == [
        "src/app.py::run.normalize",
        "src/helpers.py::helper",
    ]
    assert modules["tests/test_app.py"]["test_module"] is True
    assert modules["web/view.ts"]["internal_imports"] == ["web/format.ts"]
    assert modules["web/view.ts"]["internal_calls"] == ["web/format.ts::formatValue"]
    rendered = json.dumps(first, ensure_ascii=False)
    assert "append" not in rendered
    assert "str" not in rendered
    assert "trim" not in rendered
    assert "C:/Users" not in rendered
    assert "sk-example" not in rendered
    assert "do-not-index" not in rendered
    assert report["source_bodies_published"] == 0
    assert report["files_scanned"] == 5
    assert report["files_skipped_by_directory"] == 4


def test_link_or_reparse_tree_is_pruned(monkeypatch, tmp_path: Path) -> None:
    project = tmp_path / "project"
    linked = project / "linked-tree"
    linked.mkdir(parents=True)
    (linked / "private.py").write_text("def should_not_appear():\n    return None\n", encoding="utf-8")
    monkeypatch.setattr(
        "ai_context_linker.architecture_index.is_link_or_reparse",
        lambda path: path.name == "linked-tree",
    )

    index, report = collect_architecture_index(project, project_id="sample", mode="modules-symbols")

    assert index["modules"] == []
    assert report["files_skipped_by_directory"] == 1


def test_modules_only_mode_omits_symbols_and_calls(tmp_path: Path) -> None:
    project = _synthetic_project(tmp_path)

    index, _ = collect_architecture_index(project, project_id="sample", mode="modules-only")

    assert index["mode"] == "modules-only"
    assert all("symbols" not in module for module in index["modules"])
    assert all("internal_calls" not in module for module in index["modules"])
    assert all(module["evidence"].startswith("sample:file:") for module in index["modules"])


def test_parse_failures_are_counted_without_publishing_source(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "broken.py").write_text("def broken(:\n    secret = 'hidden'\n", encoding="utf-8")

    index, report = collect_architecture_index(project, project_id="sample", mode="modules-symbols")

    assert index["modules"] == []
    assert index["parse_failures"] == 1
    assert report["parse_failures"] == 1
    assert "hidden" not in json.dumps(index)


def test_external_call_does_not_resolve_to_unimported_internal_namesake(tmp_path: Path) -> None:
    (tmp_path / "app.py").write_text("from external import generate\ngenerate()\n", encoding="utf-8")
    (tmp_path / "unrelated.py").write_text("def generate():\n    pass\n", encoding="utf-8")
    index, _ = collect_architecture_index(tmp_path, project_id="sample", mode="modules-symbols")
    app = next(module for module in index["modules"] if module["id"] == "app.py")
    assert app["external_packages"] == ["external"]
    assert app["internal_calls"] == []


def test_javascript_imports_ignore_comments_and_strings(tmp_path: Path) -> None:
    (tmp_path / "app.js").write_text(
        "// import { generate } from './unrelated';\n"
        "/* const helper = require('./unrelated'); */\n"
        "const note = \"import { generate } from './unrelated';\";\n"
        "const other = `const helper = require('./unrelated');`;\n"
        "import { render } from './actual';\nrender();\n", encoding="utf-8",
    )
    (tmp_path / "unrelated.js").write_text("export function generate() {}\n", encoding="utf-8")
    (tmp_path / "actual.js").write_text("export function render() {}\n", encoding="utf-8")
    index, _ = collect_architecture_index(tmp_path, project_id="sample", mode="modules-symbols")
    app = next(module for module in index["modules"] if module["id"] == "app.js")
    assert app["internal_imports"] == ["actual.js"]
    assert app["internal_calls"] == ["actual.js::render"]


@pytest.mark.parametrize("unrelated", [
    "class Helper:\n    def generate(self):\n        return 99\n",
    "def other():\n    def generate():\n        return 99\n    return generate\n",
])
def test_python_calls_ignore_symbols_outside_lexical_scope(tmp_path: Path, unrelated: str) -> None:
    source = "from math import prod as generate\n" + unrelated + "assert generate([2, 3]) == 6\n"
    (tmp_path / "app.py").write_text(source, encoding="utf-8")
    subprocess.run([sys.executable, "app.py"], cwd=tmp_path, check=True, capture_output=True)
    index, _ = collect_architecture_index(tmp_path, project_id="sample", mode="modules-symbols")
    assert index["modules"][0]["internal_calls"] == []


def test_imported_class_method_uses_qualified_symbol(tmp_path: Path) -> None:
    (tmp_path / "builders.py").write_text(
        "class Builder:\n    @staticmethod\n    def create():\n        return 'created'\n", encoding="utf-8",
    )
    (tmp_path / "app.py").write_text(
        "from builders import Builder as Factory\nimport builders as module\n"
        "assert Factory.create() == 'created'\nassert isinstance(module.Builder(), Factory)\n", encoding="utf-8",
    )
    subprocess.run([sys.executable, "app.py"], cwd=tmp_path, check=True, capture_output=True)
    index, _ = collect_architecture_index(tmp_path, project_id="sample", mode="modules-symbols")
    app = next(module for module in index["modules"] if module["id"] == "app.py")
    assert app["internal_calls"] == ["builders.py::Builder", "builders.py::Builder.create"]
