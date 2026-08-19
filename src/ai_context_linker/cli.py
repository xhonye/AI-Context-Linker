from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import ManifestError, build_bundle
from .discovery import discover_workspace
from .scanner import scan_workspace
from .slicing import build_question_context


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-context-linker",
        description="Build a privacy-safe project briefing for ChatGPT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    discover = subparsers.add_parser(
        "discover", help="create a private candidate workspace config from explicit directory roots"
    )
    discover.add_argument("--root", required=True, action="append", type=Path, help="root whose direct children may be projects; repeat for multiple roots")
    discover.add_argument("--config-out", required=True, type=Path, help="private JSON configuration to create")
    discover.add_argument("--workspace-name", default="Discovered workspace", help="human-readable workspace name")
    discover.add_argument(
        "--include-skills",
        action="store_true",
        help="add detected Codex, Claude Code, Gemini CLI, and shared Agent Skills roots to the private config",
    )
    discover.add_argument("--force", action="store_true", help="replace an existing config after reviewing the target")
    build = subparsers.add_parser("build", help="validate a manifest and build the stable context bundle")
    build.add_argument("--manifest", required=True, type=Path, help="approved JSON manifest")
    build.add_argument("--output-dir", required=True, type=Path, help="local or Drive-synced publish directory")
    scan = subparsers.add_parser("scan", help="build a reviewable candidate manifest from an allowlisted workspace config")
    scan.add_argument("--config", required=True, type=Path, help="private workspace configuration")
    scan.add_argument("--review-dir", required=True, type=Path, help="private directory for review artifacts")
    scan.add_argument("--previous-manifest", type=Path, help="previous approved manifest used for change review")
    question_slice = subparsers.add_parser(
        "slice", help="build a compact question-directed briefing from an approved manifest"
    )
    question_slice.add_argument("--manifest", required=True, type=Path, help="approved JSON manifest")
    question_slice.add_argument("--question", required=True, help="current project discussion question")
    question_slice.add_argument("--output-dir", required=True, type=Path, help="directory for the compact briefing")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "discover":
            result = discover_workspace(
                args.root,
                args.config_out,
                workspace_name=args.workspace_name,
                include_skills=args.include_skills,
                overwrite=args.force,
            )
            print(result.config.resolve())
            print(f"Discovered {result.project_count} project candidate(s). Review the private config before scanning.")
            return 0
        if args.command == "scan":
            paths = scan_workspace(args.config, args.review_dir, previous_manifest=args.previous_manifest)
            print(paths.candidate_manifest.resolve())
            print(paths.report.resolve())
            print("Review the candidate manifest, then run `ai-context-linker build` to approve and publish it.")
            return 0
        if args.command == "slice":
            paths = build_question_context(args.manifest, args.question, args.output_dir)
            print(paths.markdown.resolve())
            return 0
        paths = build_bundle(args.manifest, args.output_dir)
    except (ManifestError, OSError) as exc:
        print(f"ai-context-linker: {exc}", file=sys.stderr)
        return 2
    print(paths.markdown.resolve())
    print(paths.graph.resolve())
    return 0
