from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from ai_context_linker.architecture_index import collect_architecture_index
from ai_context_linker.core import validate_manifest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_schema_is_valid_and_accepts_examples() -> None:
    schema = json.loads((PROJECT_ROOT / "schema" / "context-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    for name in ("synthetic-manifest.json", "synthetic-manifest-v02.json", "real-project-template.json"):
        manifest = json.loads((PROJECT_ROOT / "examples" / name).read_text(encoding="utf-8"))
        validator.validate(manifest)
        validate_manifest(manifest)


def test_workspace_config_schema_is_valid_and_accepts_synthetic_example() -> None:
    manifest_schema = json.loads(
        (PROJECT_ROOT / "schema" / "context-manifest.schema.json").read_text(encoding="utf-8")
    )
    schema = json.loads((PROJECT_ROOT / "schema" / "workspace-config.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(
        schema,
        registry=Registry().with_resource(
            "context-manifest.schema.json",
            Resource.from_contents(manifest_schema),
        ),
    )
    config = json.loads((PROJECT_ROOT / "examples" / "synthetic-workspace-config.json").read_text(encoding="utf-8"))
    validator.validate(config)
    config["projects"][0]["architecture_visibility"] = "modules-symbols"
    validator.validate(config)


def test_public_schema_accepts_collected_architecture_index() -> None:
    schema = json.loads((PROJECT_ROOT / "schema" / "context-manifest.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    manifest = json.loads((PROJECT_ROOT / "examples" / "synthetic-manifest-v02.json").read_text(encoding="utf-8"))
    fixture = PROJECT_ROOT / "examples" / "evaluation" / "architecture-gold" / "project"
    architecture, _ = collect_architecture_index(
        fixture,
        project_id=manifest["projects"][0]["id"],
        mode="modules-symbols",
    )
    manifest["projects"][0]["architecture_index"] = architecture

    validator.validate(manifest)
    validate_manifest(manifest)

    legacy = json.loads((PROJECT_ROOT / "examples" / "synthetic-manifest.json").read_text(encoding="utf-8"))
    legacy["projects"][0]["architecture_index"] = architecture
    assert list(validator.iter_errors(legacy))


def test_evaluation_scorecard_schema_is_valid_and_accepts_synthetic_example() -> None:
    schema = json.loads(
        (PROJECT_ROOT / "schema" / "evaluation-scorecard.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    scorecard = json.loads(
        (PROJECT_ROOT / "examples" / "evaluation" / "scorecard.json").read_text(encoding="utf-8")
    )
    validator.validate(scorecard)


def test_review_state_schema_accepts_v01_and_v02_synthetic_examples() -> None:
    schema = json.loads((PROJECT_ROOT / "schema" / "review-state.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    for name in ("synthetic-review-state-v01.json", "synthetic-review-state-v02.json"):
        review_state = json.loads((PROJECT_ROOT / "examples" / name).read_text(encoding="utf-8"))
        validator.validate(review_state)


def test_approved_snapshot_schema_is_valid() -> None:
    schema = json.loads((PROJECT_ROOT / "schema" / "approved-snapshot.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)


def _validator_with_manifest_schema(schema_name: str) -> Draft202012Validator:
    manifest_schema = json.loads(
        (PROJECT_ROOT / "schema" / "context-manifest.schema.json").read_text(encoding="utf-8")
    )
    schema = json.loads((PROJECT_ROOT / "schema" / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(
        schema,
        registry=Registry().with_resource(
            "context-manifest.schema.json",
            Resource.from_contents(manifest_schema),
        ),
    )


def test_relationship_candidate_schema_accepts_synthetic_example() -> None:
    validator = _validator_with_manifest_schema("relationship-candidates.schema.json")
    candidates = json.loads(
        (PROJECT_ROOT / "examples" / "synthetic-relationship-candidates.json").read_text(encoding="utf-8")
    )
    validator.validate(candidates)


def test_gold_suite_schema_accepts_synthetic_fixture() -> None:
    validator = _validator_with_manifest_schema("evaluation-gold-suite.schema.json")
    suite = json.loads(
        (PROJECT_ROOT / "examples" / "evaluation" / "gold-v02" / "gold-suite.json").read_text(encoding="utf-8")
    )
    validator.validate(suite)
