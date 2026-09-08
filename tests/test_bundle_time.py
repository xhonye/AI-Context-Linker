"""A full briefing and a question must agree about action validity."""
import copy
import json
from datetime import datetime

import pytest

from ai_context_linker import cli
from ai_context_linker.core import ManifestError, build_bundle, facts_sha256, validate_manifest
from ai_context_linker.slicing import render_question_context
from ai_context_linker.state_records import make_state_record, resolve_state_records


def timed_manifest():
    records = [make_state_record(
        project_id="alpha", kind=kind, text=text, source_kind="approved-review",
        source_ref=f"alpha:approved-review:{kind}", observed_at="2026-09-01T09:00:00+08:00",
        status="open", expires_at="2026-09-02T12:00:00+08:00",
    ) for kind, text in [("attention", "today"), ("next-action", "Run the acceptance fixture.")]]
    result = validate_manifest({
        "schema_version": "0.2", "generated_at": "2026-09-01T12:00:00+08:00",
        "workspace": {"name": "Time fixture", "summary": "Synthetic workspace.",
                      "current_focus": "Check expiry.", "decisions": [], "unknowns": []},
        "projects": [{"id": "alpha", "name": "Alpha", "summary": "Synthetic project.",
                      "status": "unknown", "signals": [], "constraints": [], "risks": [],
                      "open_questions": [], "state_items": records, "evidence": []}],
        "relationships": [],
    })
    result["facts_sha256"] = facts_sha256(result)
    return result


def test_bundle_expiry_agrees_with_slice_and_preserves_source(tmp_path):
    data = timed_manifest()
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    before = manifest.read_bytes()
    replay = build_bundle(manifest, tmp_path / "replay")
    expired = build_bundle(manifest, tmp_path / "expired", as_of="2026-09-02T12:00:00+08:00")
    assert "Run the acceptance fixture." in replay.markdown.read_text(encoding="utf-8")
    entry = expired.markdown.read_text(encoding="utf-8")
    assert "Run the acceptance fixture." not in entry
    assert "Run the acceptance fixture." not in render_question_context(
        data, "今天推进什么？", as_of="2026-09-02T12:00:00+08:00")
    card = expired.project_cards[0].read_text(encoding="utf-8")
    assert "stale" in next(line for line in card.splitlines() if "Run the acceptance fixture." in line)
    for text in (entry, card):
        assert "2026-09-01T12:00:00+08:00" in text
        assert "2026-09-02T12:00:00+08:00" in text
        assert data["facts_sha256"] in text
    assert manifest.read_bytes() == before
    assert expired.graph.read_bytes() == replay.graph.read_bytes()


@pytest.mark.parametrize("as_of", ["bad", "2026-09-02T12:00:00", "2026-08-01T00:00:00Z"])
def test_invalid_bundle_time_does_not_touch_existing_output(tmp_path, as_of):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(timed_manifest()), encoding="utf-8")
    result = build_bundle(manifest, tmp_path / "publish")
    before = {p: p.read_bytes() for p in (tmp_path / "publish").rglob("*") if p.is_file()}
    with pytest.raises(ManifestError):
        build_bundle(manifest, result.markdown.parent, as_of=as_of)
    assert {p: p.read_bytes() for p in before} == before


def test_build_cli_supports_explicit_time(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(timed_manifest()), encoding="utf-8")
    assert cli.main(["build", "--manifest", str(manifest), "--output-dir", str(tmp_path / "result"),
                     "--as-of", "2026-09-02T12:00:00+08:00"]) == 0
    assert "Run the acceptance fixture." not in (tmp_path / "result/ai_context.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("status", ["open", "resolved", "superseded", "needs_review"])
def test_future_record_becomes_dated_without_reopening_status(status):
    record = timed_manifest()["projects"][0]["state_items"][0]
    record["status"] = status
    original = copy.deepcopy(record)
    future = resolve_state_records([record], [], observed_at=datetime.fromisoformat("2026-09-01T08:00:00+08:00"))
    assert future[0]["freshness"] == "future-dated"
    current = resolve_state_records(future, [], observed_at=datetime.fromisoformat(record["observed_at"]))
    assert current[0]["freshness"] == "current"
    assert current[0]["status"] == status
    assert record == original


def test_legacy_bundle_cannot_claim_time_recheck(tmp_path):
    data = timed_manifest()
    data["schema_version"] = "0.1"
    data["projects"][0].pop("state_items")
    data.pop("facts_sha256")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ManifestError, match="v0.2"):
        build_bundle(manifest, tmp_path / "result", as_of="2026-09-02T12:00:00+08:00")
    assert not (tmp_path / "result").exists()
