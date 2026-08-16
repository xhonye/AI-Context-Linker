from __future__ import annotations

import json
from pathlib import Path

from ai_context_linker.relationships import (
    derive_code_path_relationships,
    derive_dependency_relationships,
    derive_document_relationships,
    parse_dependency_metadata,
    repeated_reference_fragments,
)


def test_code_path_relationships_are_opt_in_bounded_and_do_not_publish_source(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "config.py").write_text(
        f'TARGET = r"{target}"\napi_key = "sk-example0123456789012345"\n',
        encoding="utf-8",
    )

    relationships, reports = derive_code_path_relationships(
        {"source": source, "target": target}, {"source"}
    )
    rendered = json.dumps(relationships)

    assert relationships == [
        {
            "source": "source",
            "target": "target",
            "type": "code-path-dependency",
            "summary": "Allowlisted local code/config references the approved root of `target`.",
            "evidence": "source:code-path:config.py:line-1",
        }
    ]
    assert str(target) not in rendered
    assert "sk-example" not in rendered
    assert reports["source"]["source_code_bodies_read"] == 1


def test_code_path_relationship_scan_reports_file_limit(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "a.py").write_text("VALUE = 1\n", encoding="utf-8")

    _, reports = derive_code_path_relationships(
        {"source": source, "target": target}, {"source"}, max_files=1
    )

    assert reports["source"]["source_code_bodies_read"] == 1
    assert reports["source"]["truncated"] is True


def test_code_path_relationship_scan_skips_sensitive_filenames(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "credentials.py").write_text(f'TARGET = r"{target}"\n', encoding="utf-8")

    relationships, reports = derive_code_path_relationships(
        {"source": source, "target": target}, {"source"}
    )

    assert relationships == []
    assert reports["source"]["source_code_bodies_read"] == 0


def test_code_path_relationship_scan_skips_hidden_directories(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    hidden = source / ".agent-state"
    source.mkdir()
    target.mkdir()
    hidden.mkdir()
    (hidden / "config.py").write_text(f'TARGET = r"{target}"\n', encoding="utf-8")

    relationships, reports = derive_code_path_relationships(
        {"source": source, "target": target}, {"source"}
    )

    assert relationships == []
    assert reports["source"]["source_code_bodies_read"] == 0


def test_code_path_relationship_scan_requires_start_boundary(tmp_path: Path) -> None:
    source = tmp_path / "source"
    target = tmp_path / "target"
    source.mkdir()
    target.mkdir()
    (source / "config.py").write_text(
        f'TARGET = r"prefix{target}"\n', encoding="utf-8"
    )

    relationships, reports = derive_code_path_relationships(
        {"source": source, "target": target}, {"source"}
    )

    assert relationships == []
    assert reports["source"]["source_code_bodies_read"] == 1


def test_pyproject_relationship_requires_unique_declared_identity(tmp_path: Path) -> None:
    source_file = tmp_path / "source.toml"
    source_file.write_text(
        '[project]\nname = "source-package"\ndependencies = ["target_package>=1", "external"]\n',
        encoding="utf-8",
    )
    target_file = tmp_path / "target.toml"
    target_file.write_text('[project]\nname = "target-package"\n', encoding="utf-8")
    source_file = source_file.rename(tmp_path / "pyproject.toml")
    identities, dependencies = parse_dependency_metadata(source_file)
    target_dir = tmp_path / "target"
    target_dir.mkdir()
    target_manifest = target_dir / "pyproject.toml"
    target_file.replace(target_manifest)
    target_identities, _ = parse_dependency_metadata(target_manifest)

    relationships = derive_dependency_relationships(
        {
            "source": {
                "identities": identities,
                "dependencies": dependencies,
                "dependency_sources": {name: {"pyproject.toml"} for name in dependencies},
            },
            "target": {"identities": target_identities, "dependencies": set(), "dependency_sources": {}},
        }
    )

    assert relationships == [
        {
            "source": "source",
            "target": "target",
            "type": "declared-dependency",
            "summary": "Structured dependency metadata declares a dependency on `target`.",
            "evidence": "source:dependency-metadata:pyproject.toml:target",
        }
    ]


def test_document_reference_requires_code_or_link_markup() -> None:
    documents = {
        "README.md": (
            "ordinary target-project prose is ignored\n"
            "Use `target-project` for the reviewed integration.\n"
            "See [another](../other-project/README.md).\n"
        )
    }

    relationships = derive_document_relationships(
        "source-project", documents, {"source-project", "target-project", "other-project"}
    )

    assert [(item["target"], item["type"]) for item in relationships] == [
        ("target-project", "document-reference"),
        ("other-project", "document-reference"),
    ]
    assert relationships[0]["evidence"] == "source-project:file:README.md:line-2"


def test_ambiguous_dependency_identity_does_not_create_edge() -> None:
    metadata = {
        "source": {
            "identities": {"source"},
            "dependencies": {"shared"},
            "dependency_sources": {"shared": {"package.json"}},
        },
        "first": {"identities": {"shared"}, "dependencies": set(), "dependency_sources": {}},
        "second": {"identities": {"shared"}, "dependencies": set(), "dependency_sources": {}},
    }

    assert derive_dependency_relationships(metadata) == []


def test_repeated_reference_fragment_is_identified_as_template_noise() -> None:
    documents = {
        "first": {"AGENTS.md": "Use `shared-governance` for routing."},
        "second": {"AGENTS.md": "Use `shared-governance` for routing."},
        "third": {"CLAUDE.md": "Use `shared-governance` for routing."},
        "unique": {"README.md": "Use `product-core` for data."},
    }

    ignored = repeated_reference_fragments(documents)

    assert ignored == {"shared-governance"}
    assert derive_document_relationships(
        "first",
        documents["first"],
        {"first", "shared-governance"},
        ignored_fragments=ignored,
    ) == []
