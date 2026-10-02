"""Preflight invalid outputs and preserve prior content on interrupted writes."""
import json
from pathlib import Path

import pytest

from ai_context_linker import core
from ai_context_linker.demo import demo_manifest
from ai_context_linker.slicing import build_question_context


@pytest.fixture
def existing_bundle_and_slice(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(demo_manifest()), encoding="utf-8")
    output = tmp_path / "publish"
    bundle = core.build_bundle(manifest, output)
    question = build_question_context(manifest, "recipe-notebook", output)
    return manifest, output, bundle.markdown, question.markdown


def test_rebuild_invalidates_generated_slice_and_allows_explicit_regeneration(existing_bundle_and_slice):
    manifest, output, entry, question = existing_bundle_and_slice
    original = question.read_bytes()
    core.build_bundle(manifest, output)
    assert not question.exists()
    assert entry.is_file()
    build_question_context(manifest, "recipe-notebook", output)
    assert question.read_bytes() == original


@pytest.mark.parametrize("replacement", ["User-owned notes.\n", "# Example问题定向简报\n\nUser-owned notes.\n"])
def test_rebuild_preserves_unrecognized_question_before_any_write(existing_bundle_and_slice, replacement):
    manifest, output, entry, question = existing_bundle_and_slice
    question.write_text(replacement, encoding="utf-8")
    before = {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}
    with pytest.raises(core.ManifestError, match="non-generated question"):
        core.build_bundle(manifest, output)
    assert before == {p.relative_to(output): p.read_bytes() for p in output.rglob("*") if p.is_file()}


def test_question_cleanup_failure_does_not_publish_new_entry(existing_bundle_and_slice, monkeypatch):
    manifest, output, entry, question = existing_bundle_and_slice
    old_entry = entry.read_bytes()
    original_unlink = Path.unlink
    def fail_question(path, *args, **kwargs):
        if path == question:
            raise PermissionError("synthetic locked question")
        return original_unlink(path, *args, **kwargs)
    monkeypatch.setattr(Path, "unlink", fail_question)
    with pytest.raises(PermissionError, match="synthetic locked"):
        core.build_bundle(manifest, output)
    assert entry.read_bytes() == old_entry
    assert question.exists()


def test_question_link_guard_runs_before_bundle_writes(existing_bundle_and_slice, monkeypatch):
    manifest, output, entry, question = existing_bundle_and_slice
    before = entry.read_bytes()
    original_check = core._check_output_path
    def check(path):
        if path == question:
            raise core.ManifestError("synthetic reparse point")
        original_check(path)
    monkeypatch.setattr(core, "_check_output_path", check)
    with pytest.raises(core.ManifestError, match="reparse point"):
        core.build_bundle(manifest, output)
    assert entry.read_bytes() == before
    assert question.exists()


@pytest.mark.parametrize("failure", [OSError("disk failure"), KeyboardInterrupt()])
def test_atomic_write_preserves_previous_content_and_cleans_temp(tmp_path, monkeypatch, failure):
    target = tmp_path / "briefing.md"
    target.write_text("previous briefing", encoding="utf-8")
    def fail(*args):
        raise failure
    monkeypatch.setattr(core.os, "replace", fail)
    with pytest.raises(type(failure)):
        core._atomic_write_text(target, "new briefing")
    assert target.read_text(encoding="utf-8") == "previous briefing"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["briefing.md"]


def test_bundle_rejects_directory_card_before_changing_entry(tmp_path):
    from pathlib import Path
    manifest = Path(__file__).resolve().parents[1] / "examples/synthetic-manifest.json"
    data = json.loads(manifest.read_text(encoding="utf-8"))
    output = tmp_path / "publish"
    output.mkdir()
    entry = output / "ai_context.md"
    entry.write_text("previous complete briefing", encoding="utf-8")
    (output / "projects" / (data["projects"][0]["id"] + ".md")).mkdir(parents=True)
    with pytest.raises(core.ManifestError, match="regular file"):
        core.build_bundle(manifest, output)
    assert entry.read_text(encoding="utf-8") == "previous complete briefing"
    assert not (output / "ai_context_linker.graph.json").exists()
