"""Preflight invalid outputs and preserve prior content on interrupted writes."""
import json

import pytest

from ai_context_linker import core


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
