"""Path-free semantic comparison between approved context snapshots."""

from __future__ import annotations

import json
from typing import Any

from .core import validate_publish_text


SEMANTIC_KINDS = {"priority", "attention", "current-goal", "next-action", "blocker", "deadline"}


def _records(project: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(record["record_id"]): record
        for record in project.get("state_items", [])
        if record.get("record_id") and record.get("kind") in SEMANTIC_KINDS
    }


def _relationship_key(item: dict[str, Any]) -> str:
    return f"{item['source']}|{item['type']}|{item['target']}"


def semantic_changes(
    current: dict[str, Any],
    previous: dict[str, Any] | None,
    *,
    git_activity_appendix: list[dict[str, Any]],
) -> dict[str, Any]:
    if previous is None:
        return {
            "schema_version": "0.2",
            "baseline_available": False,
            "previous_facts_sha256": None,
            "current_facts_sha256": current.get("facts_sha256"),
            "projects": {"added": [], "removed": [], "changed": []},
            "architecture_changes": [],
            "semantic_state_changes": [],
            "relationships": {"added": [], "removed": []},
            "git_activity_appendix": git_activity_appendix,
        }

    current_projects = {project["id"]: project for project in current["projects"]}
    previous_projects = {project["id"]: project for project in previous["projects"]}
    added_projects = sorted(set(current_projects) - set(previous_projects))
    removed_projects = sorted(set(previous_projects) - set(current_projects))
    changed_projects = sorted(
        project_id
        for project_id in set(current_projects) & set(previous_projects)
        if any(
            current_projects[project_id].get(field) != previous_projects[project_id].get(field)
            for field in (
                "name",
                "summary",
                "status",
                "constraints",
                "risks",
                "open_questions",
                "architecture_index",
                "attached_documents",
                "configuration_fields",
            )
        )
    )
    state_changes: list[dict[str, Any]] = []
    architecture_changes: list[dict[str, Any]] = []
    for project_id in sorted(set(current_projects) & set(previous_projects)):
        current_map = current_projects[project_id].get("architecture_index", {}).get("map_sha256")
        previous_map = previous_projects[project_id].get("architecture_index", {}).get("map_sha256")
        if current_map != previous_map:
            architecture_changes.append(
                {
                    "project_id": project_id,
                    "from": previous_map,
                    "to": current_map,
                }
            )
        current_records = _records(current_projects[project_id])
        previous_records = _records(previous_projects[project_id])
        for record_id in sorted(set(current_records) | set(previous_records)):
            current_record = current_records.get(record_id)
            previous_record = previous_records.get(record_id)
            if current_record is None:
                state_changes.append(
                    {"project_id": project_id, "record_id": record_id, "kind": previous_record["kind"], "change": "missing-needs-review"}
                )
            elif previous_record is None:
                state_changes.append(
                    {"project_id": project_id, "record_id": record_id, "kind": current_record["kind"], "change": "added"}
                )
            elif current_record["status"] != previous_record["status"]:
                state_changes.append(
                    {
                        "project_id": project_id,
                        "record_id": record_id,
                        "kind": current_record["kind"],
                        "change": "status",
                        "from": previous_record["status"],
                        "to": current_record["status"],
                    }
                )

            if current_record is not None and previous_record is not None:
                fields = [
                    field for field in ("kind", "text", "expires_at", "supersedes", "freshness")
                    if current_record.get(field) != previous_record.get(field)
                ]
                if fields:
                    state_changes.append(
                        {"project_id": project_id, "record_id": record_id, "kind": current_record["kind"],
                         "change": "updated", "fields": fields}
                    )

    current_relationships = {
        _relationship_key(item) for item in current["relationships"] if item.get("layer") != "ai-candidate"
    }
    previous_relationships = {
        _relationship_key(item) for item in previous["relationships"] if item.get("layer") != "ai-candidate"
    }
    result = {
        "schema_version": "0.2",
        "baseline_available": True,
        "previous_facts_sha256": previous.get("facts_sha256"),
        "current_facts_sha256": current.get("facts_sha256"),
        "projects": {
            "added": added_projects,
            "removed": removed_projects,
            "changed": changed_projects,
        },
        "architecture_changes": architecture_changes,
        "semantic_state_changes": state_changes,
        "relationships": {
            "added": sorted(current_relationships - previous_relationships),
            "removed": sorted(previous_relationships - current_relationships),
        },
        "git_activity_appendix": git_activity_appendix,
    }
    validate_publish_text(json.dumps(result, ensure_ascii=False), "semantic changes")
    return result


def render_changes_markdown(changes: dict[str, Any]) -> str:
    lines = ["# Approved snapshot semantic changes", ""]
    if not changes["baseline_available"]:
        lines.extend(
            [
                "- No previous approved snapshot is available.",
                "- This scan establishes a baseline and does not claim that anything changed.",
                "",
            ]
        )
    else:
        projects = changes["projects"]
        lines.extend(
            [
                "## Projects",
                "",
                f"- Added: {', '.join(projects['added']) if projects['added'] else 'none'}",
                f"- Removed: {', '.join(projects['removed']) if projects['removed'] else 'none'}",
                f"- Changed: {', '.join(projects['changed']) if projects['changed'] else 'none'}",
                "",
                "## Goals, next actions, blockers, and deadlines",
                "",
            ]
        )
        if changes["semantic_state_changes"]:
            for item in changes["semantic_state_changes"]:
                detail = item["change"]
                if detail == "status":
                    detail = f"status {item['from']} -> {item['to']}"
                elif detail == "updated":
                    detail = "updated " + ", ".join(item["fields"])
                lines.append(
                    f"- `{item['project_id']}` · `{item['kind']}` · `{item['record_id']}`: {detail}"
                )
        else:
            lines.append("- No semantic state changes.")
        lines.extend(["", "## Architecture maps", ""])
        if changes["architecture_changes"]:
            for item in changes["architecture_changes"]:
                lines.append(
                    f"- `{item['project_id']}`: `{item['from'] or 'none'}` -> `{item['to'] or 'none'}`"
                )
        else:
            lines.append("- No architecture map changes.")
        lines.extend(
            [
                "",
                "## Relationships",
                "",
                f"- Added: {', '.join(changes['relationships']['added']) if changes['relationships']['added'] else 'none'}",
                f"- Removed: {', '.join(changes['relationships']['removed']) if changes['relationships']['removed'] else 'none'}",
                "",
            ]
        )
    lines.extend(["## Git activity appendix", "", "> Git counts are observational appendix data and never establish project value, state, or priority.", ""])
    if changes["git_activity_appendix"]:
        for item in changes["git_activity_appendix"]:
            lines.append(
                f"- `{item['project_id']}`: changed paths={item.get('changed_path_count', 'unknown')}; commits in 30 days={item.get('commits_30d', 'unknown')}"
            )
    else:
        lines.append("- No Git count data was available.")
    lines.append("")
    rendered = "\n".join(lines)
    validate_publish_text(rendered, "semantic changes Markdown")
    return rendered
