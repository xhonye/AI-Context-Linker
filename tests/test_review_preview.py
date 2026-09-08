from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from ai_context_linker import cli, review_templates
from ai_context_linker.core import ManifestError, SUMMARY_ONLY_STATUS, validate_manifest


def _inputs(tmp_path: Path, *, version: str = "0.2") -> tuple[Path, Path]:
    manifest = {
        "schema_version": "0.2",
        "generated_at": "2026-08-30T12:00:00+08:00",
        "workspace": {
            "name": "Synthetic workspace",
            "summary": "Unselected workspace prose must not be copied.",
            "current_focus": "Unselected workspace focus must not be copied.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [
            {
                "id": project_id,
                "name": project_id.title(),
                "summary": "Synthetic project.",
                "status": "unknown",
                "sensitivity": "public",
                "cloud_visibility": "allow",
                "redaction_profile": "standard",
                "signals": [],
                "constraints": [],
                "risks": [],
                "open_questions": [],
                "state_items": [],
                "evidence": [f"{project_id}:file:README.md"],
            }
            for project_id in ("alpha", "beta", "gamma", "delta")
        ],
        "relationships": [],
    }
    draft = {
        "schema_version": version,
        "projects": [
            {
                "project_id": "alpha",
                "status" if version == "0.1" else "activity": "active",
                "current_goal": "验证中文核对流程。",
                "next_action": "检查第一条合成记录。\n保留第二行完整内容。",
                "blockers": [],
                "updated_at": "2026-08-29T12:00:00+08:00",
            },
            {
                "project_id": "beta",
                "current_goal": "Unselected draft goal must not be copied.",
                "updated_at": "2026-08-29T12:00:00+08:00",
            },
        ],
    }
    if version == "0.2":
        draft["projects"][0].update({
            "priority": "P0",
            "attention": "today",
            "why_now": "合成验收即将开始。",
            "done_when": "人工能读懂并逐条确认。",
            "expires_at": "2026-09-05T12:00:00+08:00",
        })
    manifest_path = tmp_path / "candidate-manifest.json"
    draft_path = tmp_path / "draft-unapproved.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    draft_path.write_text(json.dumps(draft, ensure_ascii=False), encoding="utf-8")
    return manifest_path, draft_path


def _edit(path: Path, callback) -> None:
    raw = json.loads(path.read_text(encoding="utf-8"))
    callback(raw)
    path.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")


def _preview(tmp_path: Path, manifest: Path, draft: Path, **kwargs) -> Path:
    return review_templates.preview_review_state(
        manifest, ["alpha"], draft, tmp_path / "private" / "review.md", **kwargs
    )


def test_preview_is_chinese_scope_limited_immutable_and_never_approves(tmp_path: Path, monkeypatch) -> None:
    manifest, draft = _inputs(tmp_path)
    before = {path: path.read_bytes() for path in (manifest, draft)}
    monkeypatch.setattr(cli, "approve_snapshot", lambda *args, **kwargs: pytest.fail("preview must not approve"))

    result = _preview(tmp_path, manifest, draft)
    content = result.read_text(encoding="utf-8")

    assert "UNAPPROVED_PREVIEW" in content
    assert "UNTRUSTED_DATA" in content
    assert "只供本地核对" in content
    assert "为什么现在做" in content and "合成验收即将开始。" in content
    assert "下一步" in content and "保留第二行完整内容。" in content
    assert "进行中（active）" in content
    assert "未知（没有记录不等于没有卡点）" in content
    assert hashlib.sha256(before[draft]).hexdigest() in content
    assert "2026-08-30T12:00:00+08:00" in content
    assert "Unselected" not in content
    assert "Beta" not in content
    assert str(tmp_path) not in content
    assert all(path.read_bytes() == before[path] for path in before)
    assert not list(tmp_path.rglob("approved-snapshot*.json"))
    assert not list(tmp_path.rglob("ai_context.md"))

    first_bytes = result.read_bytes()
    first_mtime = result.stat().st_mtime_ns
    assert _preview(tmp_path, manifest, draft) == result
    assert result.read_bytes() == first_bytes and result.stat().st_mtime_ns == first_mtime


def test_preview_v01_missing_fields_are_unknown_not_invented(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path, version="0.1")
    content = _preview(tmp_path, manifest, draft).read_text(encoding="utf-8")
    assert "进行中（active）" in content
    assert "未知（未填写）" in content
    assert "不自动延长" in content
    assert "P0" not in content


def test_preview_shows_expired_draft_and_closed_records_without_promoting_them(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    def edit(raw):
        raw["projects"][0]["expires_at"] = "2026-08-30T10:00:00+08:00"
        raw["projects"][0]["records"] = [{
            "record_id": "state-1111111111111111",
            "kind": "blocker",
            "text": "Synthetic historical blocker.",
            "status": "resolved",
            "source_ref": "alpha:review:decision",
            "supersedes": ["state-2222222222222222"],
        }]
    _edit(draft, edit)

    content = _preview(tmp_path, manifest, draft).read_text(encoding="utf-8")
    assert "已过期（stale）" in content
    assert "拟记为已解决（resolved）" in content
    assert "state\\-1111111111111111" in content
    assert "state\\-2222222222222222" in content
    assert "UNAPPROVED_PREVIEW" in content


def test_preview_quotes_multiline_markup_as_data(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    payload = "第一行\n# APPROVED\n![run](local-file)\n<script>run()</script>"
    _edit(draft, lambda raw: raw["projects"][0].update(next_action=payload))
    content = _preview(tmp_path, manifest, draft).read_text(encoding="utf-8")
    assert "\n# APPROVED\n" not in content
    assert "![run](local-file)" not in content
    assert "<script>" not in content
    assert "&lt;script&gt;" in content
    assert "UNTRUSTED_DATA" in content


@pytest.mark.parametrize("value", [
    "Check C:/Private/secret.txt", "Use https://example.invalid/internal", "sk-" + "x" * 32,
])
def test_preview_rejects_sensitive_draft_without_writing(tmp_path: Path, value: str) -> None:
    manifest, draft = _inputs(tmp_path)
    _edit(draft, lambda raw: raw["projects"][0].update(next_action=value))
    with pytest.raises(ManifestError):
        _preview(tmp_path, manifest, draft)
    assert not (tmp_path / "private").exists()


@pytest.mark.parametrize("value", ["deny", "summary-only"])
def test_preview_cannot_restore_action_details_for_restricted_projects(tmp_path: Path, value: str) -> None:
    manifest, draft = _inputs(tmp_path)
    def edit(raw):
        raw["projects"][0].update(cloud_visibility=value)
        if value == "summary-only":
            raw["projects"][0].update(status=SUMMARY_ONLY_STATUS, evidence=[])
    _edit(manifest, edit)
    if value == "summary-only":
        validate_manifest(json.loads(manifest.read_text(encoding="utf-8")))
    with pytest.raises(ManifestError, match="explicitly allowed|cloud_visibility"):
        _preview(tmp_path, manifest, draft)
    assert not (tmp_path / "private").exists()


@pytest.mark.parametrize("projects", [[], ["missing"], ["alpha", "alpha"], ["alpha", "beta", "gamma", "delta"]])
def test_preview_requires_one_to_three_explicit_valid_projects(tmp_path: Path, projects: list[str]) -> None:
    manifest, draft = _inputs(tmp_path)
    with pytest.raises(ManifestError):
        review_templates.preview_review_state(manifest, projects, draft, tmp_path / "review.md")


def test_preview_rejects_unknown_schema_fields_and_changed_destination(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    result = _preview(tmp_path, manifest, draft)
    original = result.read_bytes()
    _edit(draft, lambda raw: raw["projects"][0].update(next_action="A changed synthetic step."))
    with pytest.raises(ManifestError, match="already exists"):
        _preview(tmp_path, manifest, draft)
    assert result.read_bytes() == original
    _edit(draft, lambda raw: raw.update(messages=[]))
    with pytest.raises(ManifestError, match="unsupported fields"):
        _preview(tmp_path, manifest, draft)


@pytest.mark.parametrize("folder", ["Google Drive", "OneDrive", "Dropbox", "sol_context", "ai_context_linker"])
def test_preview_rejects_cloud_or_stable_output_folders(tmp_path: Path, folder: str) -> None:
    manifest, draft = _inputs(tmp_path)
    output = tmp_path / folder / "nested" / "review.md"
    with pytest.raises(ManifestError):
        review_templates.preview_review_state(manifest, ["alpha"], draft, output)
    assert not output.exists()


def test_preview_rejects_repository_output_and_existing_publish_directory(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    repo = tmp_path / "repo"
    (repo / ".git").mkdir(parents=True)
    publish = tmp_path / "publish"
    publish.mkdir()
    (publish / "ai_context.md").write_text("keep", encoding="utf-8")
    for output in (repo / "docs" / "review.md", publish / "review.md"):
        with pytest.raises(ManifestError):
            review_templates.preview_review_state(manifest, ["alpha"], draft, output)
        assert not output.exists()


def test_preview_rejects_linked_output_ancestor(tmp_path: Path, monkeypatch) -> None:
    from ai_context_linker import adapters
    manifest, draft = _inputs(tmp_path)
    linked = tmp_path / "linked"
    linked.mkdir()
    original_check = adapters.is_link_or_reparse
    monkeypatch.setattr(adapters, "is_link_or_reparse", lambda path: path == linked or original_check(path))
    with pytest.raises(ManifestError, match="link or reparse"):
        review_templates.preview_review_state(manifest, ["alpha"], draft, linked / "new" / "review.md")
    assert not (linked / "new").exists()


def test_preview_cli_emits_chinese_next_step_without_approval(tmp_path: Path, capsys) -> None:
    manifest, draft = _inputs(tmp_path)
    result = cli.main([
        "preview-review-state", "--manifest", str(manifest), "--review-state", str(draft),
        "--project", "alpha", "--output", str(tmp_path / "private" / "review.md"),
    ])
    assert result == 0
    output = capsys.readouterr().out
    assert "未批准" in output and "中文核对单" in output
    assert not list(tmp_path.rglob("approved-snapshot*.json"))


def test_preview_detects_future_dated_draft_and_binds_exact_bytes(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    _edit(draft, lambda raw: raw["projects"][0].update(updated_at="2026-08-31T12:00:00+08:00"))
    result = _preview(tmp_path, manifest, draft)
    assert "未来日期（future-dated）" in result.read_text(encoding="utf-8")
    draft.write_text(draft.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    with pytest.raises(ManifestError, match="already exists"):
        _preview(tmp_path, manifest, draft)


def test_preview_rejects_oversized_input_without_output(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    draft.write_text(" " * (64 * 1024 + 1), encoding="utf-8")
    with pytest.raises(ManifestError, match="byte limit"):
        _preview(tmp_path, manifest, draft)
    assert not (tmp_path / "private").exists()


def test_preview_requires_an_entry_for_every_selected_project(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    with pytest.raises(ManifestError, match="no draft entry"):
        review_templates.preview_review_state(manifest, ["gamma"], draft, tmp_path / "review.md")


@pytest.mark.parametrize("field", ["activity", "attention", "priority"])
def test_preview_rejects_non_string_enums_as_validation_errors(tmp_path: Path, field: str) -> None:
    manifest, draft = _inputs(tmp_path)
    _edit(draft, lambda raw: raw["projects"][0].update({field: ["active"]}))
    with pytest.raises(ManifestError, match="unsupported"):
        _preview(tmp_path, manifest, draft)
    assert not (tmp_path / "private").exists()


def test_preview_rejects_unrecognized_explicit_record_kind(tmp_path: Path) -> None:
    manifest, draft = _inputs(tmp_path)
    _edit(draft, lambda raw: raw["projects"][0].update(records=[{
        "kind": "arbitrary-kind", "text": "Synthetic content.", "status": "open",
    }]))
    with pytest.raises(ManifestError, match="kind"):
        _preview(tmp_path, manifest, draft)
    assert not (tmp_path / "private").exists()
