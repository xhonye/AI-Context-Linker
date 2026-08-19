from __future__ import annotations

from pathlib import Path

import pytest

from ai_context_linker.core import ManifestError
from ai_context_linker.skills import (
    MAX_SKILL_FRONTMATTER_BYTES,
    collect_skill_root,
    parse_skill_frontmatter,
)


def write_skill(root: Path, folder: str, frontmatter: str, body: bytes = b"instructions") -> Path:
    skill_dir = root / folder
    skill_dir.mkdir(parents=True)
    skill_file = skill_dir / "SKILL.md"
    skill_file.write_bytes(f"---\n{frontmatter}\n---\n".encode() + body)
    return skill_file


def test_frontmatter_parser_stops_before_instruction_body(tmp_path: Path) -> None:
    skill_file = write_skill(
        tmp_path,
        "safe",
        "name: safe-skill\ndescription: Safe public summary.",
        b"\xff\xfe api_key=sk-private-body-must-not-be-read",
    )

    assert parse_skill_frontmatter(skill_file) == ("safe-skill", "Safe public summary.")


def test_frontmatter_parser_supports_folded_description(tmp_path: Path) -> None:
    skill_file = write_skill(
        tmp_path,
        "folded",
        "name: folded\ndescription: >\n  First capability.\n  Second capability.",
    )

    assert parse_skill_frontmatter(skill_file) == (
        "folded",
        "First capability. Second capability.",
    )


def test_frontmatter_reader_enforces_byte_limit(tmp_path: Path) -> None:
    skill_file = write_skill(
        tmp_path,
        "oversized",
        "description: " + ("x" * MAX_SKILL_FRONTMATTER_BYTES),
    )

    with pytest.raises(ManifestError, match="exceeds the safety limit"):
        parse_skill_frontmatter(skill_file)


def test_skill_collection_publishes_only_name_summary_and_safe_evidence(tmp_path: Path) -> None:
    write_skill(tmp_path, "review", "name: review\ndescription: Review approved facts.")

    skills, report = collect_skill_root(
        tmp_path,
        root_id="codex-user",
        provider="codex",
        scope="user",
    )

    assert skills == [
        {
            "source": "codex-user",
            "provider": "codex",
            "scope": "user",
            "name": "review",
            "summary": "Review approved facts.",
            "evidence": "skill-frontmatter:codex:user",
        }
    ]
    assert report["instruction_bodies_read"] == 0
    assert str(tmp_path) not in str(skills)


def test_skill_summary_with_address_is_replaced(tmp_path: Path) -> None:
    write_skill(tmp_path, "internal", "name: internal\ndescription: Connect to https://internal.example/run")

    skills, report = collect_skill_root(
        tmp_path,
        root_id="claude-user",
        provider="claude-code",
        scope="user",
    )

    assert skills[0]["summary"] == "Summary omitted because it failed publish-safety checks."
    assert "internal.example" not in str(skills)
    assert report["skipped"] == [{"entry": "internal", "reason": "unsafe summary omitted"}]


def test_skill_summary_with_secret_fails_closed(tmp_path: Path) -> None:
    write_skill(
        tmp_path,
        "unsafe",
        "name: unsafe\ndescription: api_key=sk-example0123456789012345",
    )

    with pytest.raises(ManifestError, match="likely secret"):
        collect_skill_root(
            tmp_path,
            root_id="gemini-user",
            provider="gemini-cli",
            scope="user",
        )


def test_missing_skill_root_is_reported_without_fabricating_skills(tmp_path: Path) -> None:
    skills, report = collect_skill_root(
        tmp_path / "missing",
        root_id="missing-root",
        provider="agent-skills",
        scope="custom",
    )

    assert skills == []
    assert report["status"] == "missing"
