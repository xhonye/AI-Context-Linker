from __future__ import annotations

from pathlib import Path

from ai_context_linker.relationships import (
    derive_dependency_relationships,
    derive_document_relationships,
    parse_dependency_metadata,
    repeated_reference_fragments,
)


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
