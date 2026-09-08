from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import pytest

from ai_context_linker.core import (
    ManifestError,
    build_bundle,
    facts_sha256,
    snapshot_changes_sha256,
    validate_manifest,
)


def valid_manifest() -> dict:
    return {
        "schema_version": "0.1",
        "generated_at": "2026-08-11T12:00:00+08:00",
        "workspace": {
            "name": "示例工作区",
            "summary": "用于测试的合成项目组合。",
            "current_focus": "验证安全上下文。",
            "decisions": ["只发布批准字段。"],
            "unknowns": ["外部理解效果未知。"],
        },
        "projects": [
            {
                "id": "alpha",
                "name": "Alpha",
                "summary": "第一个合成项目。",
                "status": "active",
                "signals": ["测试存在。"],
                "risks": [],
                "open_questions": ["是否需要第二个数据源？"],
                "evidence": ["project-card:alpha-v1"],
            },
            {
                "id": "beta",
                "name": "Beta",
                "summary": "第二个合成项目。",
                "status": "planned",
                "signals": [],
                "risks": ["尚未运行。"],
                "open_questions": [],
                "evidence": ["project-card:beta-v1"],
            },
        ],
        "relationships": [
            {
                "source": "alpha",
                "target": "beta",
                "type": "feeds",
                "summary": "Alpha 向 Beta 提供经过批准的事实。",
                "evidence": "decision:1",
            }
        ],
    }


def test_build_bundle_writes_stable_markdown_and_graph(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(valid_manifest(), ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")

    markdown = paths.markdown.read_text(encoding="utf-8")
    graph = json.loads(paths.graph.read_text(encoding="utf-8"))
    assert paths.markdown.name == "ai_context.md"
    assert "# 示例工作区项目上下文入口" in markdown
    assert "[Alpha](projects/alpha.md)" in markdown
    assert "已确认项目关系：1 条" in markdown
    assert "生成器不自动证明该 manifest 已获人工批准" in markdown
    assert "所有内容均来自批准 manifest" not in markdown
    assert graph["derived"] is True
    assert {node["id"] for node in graph["nodes"]} == {"workspace", "alpha", "beta"}
    assert {path.name for path in paths.project_cards} == {"alpha.md", "beta.md"}
    assert paths.bundle_index is not None and paths.bundle_index.exists()
    alpha_card = (tmp_path / "publish" / "projects" / "alpha.md").read_text(encoding="utf-8")
    assert "第一个合成项目" in alpha_card


def test_rebuild_removes_only_stale_generated_project_cards(tmp_path: Path) -> None:
    publish = tmp_path / "publish"
    first_manifest_path = tmp_path / "first.json"
    first_manifest_path.write_text(json.dumps(valid_manifest(), ensure_ascii=False), encoding="utf-8")
    build_bundle(first_manifest_path, publish)
    assert (publish / "projects" / "beta.md").exists()

    second = valid_manifest()
    second["projects"] = [second["projects"][0]]
    second["relationships"] = []
    second_manifest_path = tmp_path / "second.json"
    second_manifest_path.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")
    paths = build_bundle(second_manifest_path, publish)

    assert not (publish / "projects" / "beta.md").exists()
    bundle_index = json.loads(paths.bundle_index.read_text(encoding="utf-8"))
    assert bundle_index["project_cards"] == ["projects/alpha.md"]


def test_rebuild_refuses_to_remove_user_replaced_stale_card_before_writing(tmp_path: Path) -> None:
    publish = tmp_path / "publish"
    first_manifest_path = tmp_path / "first.json"
    first_manifest_path.write_text(json.dumps(valid_manifest(), ensure_ascii=False), encoding="utf-8")
    build_bundle(first_manifest_path, publish)
    entry_before = (publish / "ai_context.md").read_text(encoding="utf-8")
    (publish / "projects" / "beta.md").write_text("User-owned replacement.\n", encoding="utf-8")

    second = valid_manifest()
    second["workspace"]["summary"] = "This write must not happen."
    second["projects"] = [second["projects"][0]]
    second["relationships"] = []
    second_manifest_path = tmp_path / "second.json"
    second_manifest_path.write_text(json.dumps(second, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ManifestError, match="non-generated stale project card"):
        build_bundle(second_manifest_path, publish)

    assert (publish / "ai_context.md").read_text(encoding="utf-8") == entry_before
    assert (publish / "projects" / "beta.md").read_text(encoding="utf-8") == "User-owned replacement.\n"


def test_project_card_renders_architecture_without_source_body(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["schema_version"] = "0.2"
    manifest["relationships"][0]["type"] = "runtime-dependency"
    manifest["relationships"][0]["layer"] = "observed"
    architecture = {
        "mode": "modules-symbols",
        "truncated": False,
        "parse_failures": 0,
        "modules": [
            {
                "id": "src/app.py",
                "language": "python",
                "test_module": False,
                "symbols": ["run"],
                "internal_imports": [],
                "external_packages": ["requests"],
                "internal_calls": [],
                "evidence": "alpha:file:src/app.py",
            }
        ],
    }
    architecture["map_sha256"] = hashlib.sha256(
        json.dumps(architecture, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    manifest["projects"][0]["architecture_index"] = architecture
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")

    card_path = next(path for path in paths.project_cards if path.name == "alpha.md")
    card = card_path.read_text(encoding="utf-8")
    assert "## Architecture Index" in card
    assert "`src/app.py`" in card
    assert "`run`" in card
    assert "requests" in card
    graph = json.loads(paths.graph.read_text(encoding="utf-8"))
    assert any(node["id"] == "module:alpha:src/app.py" for node in graph["nodes"])
    assert any(edge["type"] == "contains" and edge["target"] == "module:alpha:src/app.py" for edge in graph["edges"])


def test_build_bundle_rejects_sol_context_publish_directory(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(valid_manifest(), ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ManifestError, match="reserved for SOL Context"):
        build_bundle(manifest_path, tmp_path / "sol_context")


def test_build_bundle_rejects_directory_containing_sol_context_entry(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(valid_manifest(), ensure_ascii=False), encoding="utf-8")
    publish = tmp_path / "shared"
    publish.mkdir()
    (publish / "sol_context.md").write_text("SOL", encoding="utf-8")

    with pytest.raises(ManifestError, match="reserved for SOL Context"):
        build_bundle(manifest_path, publish)


def test_unknown_field_is_rejected_instead_of_uploaded() -> None:
    manifest = valid_manifest()
    manifest["projects"][0]["source_code"] = "print('should never upload')"

    with pytest.raises(ManifestError, match="unsupported fields"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    "unsafe_text, message",
    [
        ("api_key=sk-example0123456789012345", "likely secret"),
        ("See C:/Users/example/private/project.md", "absolute path"),
        ("Do not write to D:/", "absolute path"),
        ("Read /home/example/private/project.md", "absolute path"),
        ("Contact person@example.invalid", "sensitive address"),
        ("Open https://internal.example/run", "sensitive address"),
        ("Connect to 127.0.0.1:606", "sensitive address"),
    ],
)
def test_unsafe_strings_fail_closed(unsafe_text: str, message: str) -> None:
    manifest = valid_manifest()
    manifest["workspace"]["summary"] = unsafe_text

    with pytest.raises(ManifestError, match=message):
        validate_manifest(manifest)


def test_relationship_must_reference_known_projects() -> None:
    manifest = copy.deepcopy(valid_manifest())
    manifest["relationships"][0]["target"] = "missing"

    with pytest.raises(ManifestError, match="unknown project"):
        validate_manifest(manifest)


def test_optional_constraints_are_validated_and_rendered(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["projects"][0]["constraints"] = ["Only approved facts may be published."]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")

    alpha_card = next(path for path in paths.project_cards if path.name == "alpha.md")
    assert "### 已确认约束" in alpha_card.read_text(encoding="utf-8")
    assert "Only approved facts may be published." in alpha_card.read_text(encoding="utf-8")


def test_optional_skills_are_validated_and_rendered(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["skills"] = [
        {
            "source": "codex-user",
            "provider": "codex",
            "scope": "user",
            "name": "project-review",
            "summary": "Review approved project facts.",
            "evidence": "skill-frontmatter:codex:user",
        }
    ]
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")
    rendered = paths.markdown.read_text(encoding="utf-8")

    assert "## 可用 Skills" in rendered
    assert "project-review" in rendered
    assert "Review approved project facts." in rendered


def test_skill_summary_address_is_rejected_by_final_compiler() -> None:
    manifest = valid_manifest()
    manifest["skills"] = [
        {
            "source": "codex-user",
            "provider": "codex",
            "scope": "user",
            "name": "internal",
            "summary": "Connect to user@example.com for access.",
            "evidence": "skill-frontmatter:codex:user",
        }
    ]

    with pytest.raises(ManifestError, match="sensitive address"):
        validate_manifest(manifest)


def test_relationship_type_cannot_inject_markup() -> None:
    manifest = valid_manifest()
    manifest["relationships"][0]["type"] = "feeds--> `unknown`"

    with pytest.raises(ManifestError, match="lowercase letters"):
        validate_manifest(manifest)


def test_fact_hash_must_match_manifest_content() -> None:
    manifest = valid_manifest()
    manifest["facts_sha256"] = "0" * 64

    with pytest.raises(ManifestError, match="does not match"):
        validate_manifest(manifest)


def test_snapshot_changes_are_validated_hashed_and_rendered(tmp_path: Path) -> None:
    manifest = valid_manifest()
    manifest["snapshot_changes"] = {
        "baseline_available": True,
        "previous_facts_sha256": "1" * 64,
        "added_projects": [],
        "removed_projects": ["legacy"],
        "changed_projects": [{"id": "alpha", "fields": ["signals", "status"]}],
        "workspace_changed": False,
        "relationships_changed": True,
    }
    manifest["snapshot_changes"]["changes_sha256"] = snapshot_changes_sha256(manifest["snapshot_changes"])
    manifest["facts_sha256"] = facts_sha256(manifest)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

    paths = build_bundle(manifest_path, tmp_path / "publish")
    markdown = paths.markdown.read_text(encoding="utf-8")

    assert "## 与上次批准快照相比" in markdown
    assert "移除项目：legacy" in markdown
    assert "`alpha` 变化字段：signals, status" in markdown


def test_snapshot_changes_reject_unknown_project_field() -> None:
    manifest = valid_manifest()
    manifest["snapshot_changes"] = {
        "baseline_available": True,
        "previous_facts_sha256": None,
        "added_projects": [],
        "removed_projects": [],
        "changed_projects": [{"id": "alpha", "fields": ["source_code"]}],
        "workspace_changed": False,
        "relationships_changed": False,
    }
    manifest["snapshot_changes"]["changes_sha256"] = snapshot_changes_sha256(manifest["snapshot_changes"])

    with pytest.raises(ManifestError, match="unsupported fields"):
        validate_manifest(manifest)


def test_fact_hash_excludes_independently_hashed_change_view() -> None:
    manifest = valid_manifest()
    before = facts_sha256(manifest)
    changes = {
        "baseline_available": False,
        "previous_facts_sha256": None,
        "added_projects": ["alpha", "beta"],
        "removed_projects": [],
        "changed_projects": [],
        "workspace_changed": True,
        "relationships_changed": True,
    }
    changes["changes_sha256"] = snapshot_changes_sha256(changes)
    manifest["snapshot_changes"] = changes

    assert facts_sha256(manifest) == before


def test_tampered_snapshot_change_view_is_rejected() -> None:
    manifest = valid_manifest()
    changes = {
        "baseline_available": True,
        "previous_facts_sha256": "1" * 64,
        "added_projects": [],
        "removed_projects": [],
        "changed_projects": [],
        "workspace_changed": False,
        "relationships_changed": False,
    }
    changes["changes_sha256"] = snapshot_changes_sha256(changes)
    changes["relationships_changed"] = True
    manifest["snapshot_changes"] = changes

    with pytest.raises(ManifestError, match="does not match"):
        validate_manifest(manifest)
