from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError, build_graph, facts_sha256, render_markdown, validate_manifest
from ai_context_linker.scanner import collect_candidate, scan_workspace
from ai_context_linker.slicing import render_question_context


def _project(project_id: str) -> dict[str, object]:
    return {
        "id": project_id,
        "name": project_id.title(),
        "summary": f"Synthetic {project_id} project.",
        "status": "unknown",
        "signals": [],
        "constraints": [],
        "risks": [],
        "open_questions": [],
        "state_items": [],
        "evidence": [f"{project_id}:file:README.md"],
    }


def _manifest(relationships: list[dict[str, str]]) -> dict:
    raw = {
        "schema_version": "0.2",
        "generated_at": "2026-08-28T12:00:00+08:00",
        "workspace": {
            "name": "Relationship fixture",
            "summary": "Synthetic relationship graph.",
            "current_focus": "Review relationship layers.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [_project("source"), _project("target")],
        "relationships": relationships,
    }
    normalized = validate_manifest(raw)
    normalized["facts_sha256"] = facts_sha256(normalized)
    return validate_manifest(normalized)


def test_v02_relationship_requires_known_type_and_layer() -> None:
    relationship = {
        "source": "source",
        "target": "target",
        "type": "runtime-dependency",
        "layer": "observed",
        "summary": "Structured metadata declares a runtime dependency.",
        "evidence": "source:dependency-metadata:pyproject.toml:target",
    }

    assert _manifest([relationship])["relationships"][0]["layer"] == "observed"

    invalid = dict(relationship)
    invalid.pop("layer")
    with pytest.raises(ManifestError, match="layer"):
        _manifest([invalid])


def test_default_graph_excludes_ai_candidate_edges() -> None:
    manifest = _manifest(
        [
            {
                "source": "source",
                "target": "target",
                "type": "runtime-dependency",
                "layer": "observed",
                "summary": "Observed dependency.",
                "evidence": "source:dependency-metadata:pyproject.toml:target",
            },
            {
                "source": "source",
                "target": "target",
                "type": "candidate-merge",
                "layer": "ai-candidate",
                "summary": "AI suggests a possible merge for human review.",
                "evidence": "ai-candidate:merge-1",
            },
        ]
    )

    graph = build_graph(manifest)
    markdown = render_markdown(manifest)
    slice_markdown = render_question_context(manifest, "Which projects have relationships?")

    assert any(edge["type"] == "runtime-dependency" for edge in graph["edges"])
    assert not any(edge.get("layer") == "ai-candidate" for edge in graph["edges"])
    assert "candidate-merge" not in markdown
    assert "candidate-merge" not in slice_markdown


def test_ai_relationship_candidates_stay_out_of_formal_manifest(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "README.md").write_text("# Source\n\nSynthetic source.\n", encoding="utf-8")
    (target / "README.md").write_text("# Target\n\nSynthetic target.\n", encoding="utf-8")
    candidates = tmp_path / "relationship-candidates.json"
    candidates.write_text(
        json.dumps(
            {
                "schema_version": "0.2",
                "candidates": [
                    {
                        "candidate_id": "merge-1",
                        "source": "source",
                        "target": "target",
                        "type": "candidate-merge",
                        "summary": "AI suggests reviewing a possible merge.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Candidate queue",
            "summary": "Synthetic candidate queue.",
            "current_focus": "Keep AI candidates out of facts.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [
            {"id": "source", "path": str(source), "sensitivity": "public", "cloud_visibility": "allow", "redaction_profile": "standard", "allow_files": ["README.md"]},
            {"id": "target", "path": str(target), "sensitivity": "public", "cloud_visibility": "allow", "redaction_profile": "standard", "allow_files": ["README.md"]},
        ],
        "relationship_candidate_files": [str(candidates)],
        "relationships": [],
    }
    config_path = tmp_path / "workspace.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    paths = scan_workspace(config_path, tmp_path / "review", observed_at="2026-08-28T12:00:00+08:00")
    manifest = json.loads(paths.candidate_manifest.read_text(encoding="utf-8"))
    queue = json.loads(paths.relationship_review_queue.read_text(encoding="utf-8"))

    assert manifest["relationships"] == []
    assert queue["candidates"][0]["layer"] == "ai-candidate"
    assert queue["candidates"][0]["candidate_id"] == "merge-1"


def test_approved_semantic_separate_by_design_enters_formal_graph(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "README.md").write_text("# Source\n\nSynthetic source.\n", encoding="utf-8")
    (target / "README.md").write_text("# Target\n\nSynthetic target.\n", encoding="utf-8")
    config = {
        "schema_version": "0.2",
        "workspace": {
            "name": "Separate fixture",
            "summary": "Synthetic separation decision.",
            "current_focus": "Preserve approved boundaries.",
            "decisions": [],
            "unknowns": [],
        },
        "projects": [
            {"id": "source", "path": str(source), "sensitivity": "public", "cloud_visibility": "allow", "redaction_profile": "standard", "allow_files": ["README.md"]},
            {"id": "target", "path": str(target), "sensitivity": "public", "cloud_visibility": "allow", "redaction_profile": "standard", "allow_files": ["README.md"]},
        ],
        "relationships": [
            {
                "source": "source",
                "target": "target",
                "type": "separate-by-design",
                "layer": "approved-semantic",
                "summary": "The projects intentionally keep different trust boundaries.",
                "evidence": "approved-review:relationship:separate-1",
            }
        ],
    }
    config_path = tmp_path / "workspace.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")

    candidate, _ = collect_candidate(config_path, observed_at="2026-08-28T12:00:00+08:00")

    assert candidate["relationships"][0]["type"] == "separate-by-design"
    assert candidate["relationships"][0]["layer"] == "approved-semantic"
