from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_schema_is_valid_and_accepts_examples() -> None:
    schema = json.loads((PROJECT_ROOT / "schema" / "context-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    for name in ("synthetic-manifest.json", "real-project-template.json"):
        manifest = json.loads((PROJECT_ROOT / "examples" / name).read_text(encoding="utf-8"))
        validator.validate(manifest)


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
