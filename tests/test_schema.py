from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_public_schema_is_valid_and_accepts_examples() -> None:
    schema = json.loads((PROJECT_ROOT / "schema" / "context-manifest.schema.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    for name in ("synthetic-manifest.json", "real-project-template.json"):
        manifest = json.loads((PROJECT_ROOT / "examples" / name).read_text(encoding="utf-8"))
        validator.validate(manifest)
