from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .architecture_evaluation import build_architecture_evaluation_report
from .core import ManifestError, build_bundle
from .discovery import discover_workspace
from .evaluation import build_evaluation_report
from .gold_evaluation import build_gold_evaluation_report
from .review_templates import init_review_state, preview_review_state
from .scanner import scan_workspace
from .slicing import build_question_context
from .snapshots import approve_snapshot


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
    discover.add_argument("--workspace-name", help="workspace name; preserves the previous name on rediscovery")
    discover.add_argument(
        "--previous-config",
        type=Path,
        help="previous private config used as the stable project identity registry",
    )
    discover.add_argument(
        "--include-skills",
        action="store_true",
        help="add detected Codex, Claude Code, Gemini CLI, and shared Agent Skills roots to the private config",
    )
    discover.add_argument("--force", action="store_true", help="replace an existing config after reviewing the target")
    build = subparsers.add_parser("build", help="validate a manifest and build the stable context bundle")
    build.add_argument("--manifest", required=True, type=Path, help="approved JSON manifest")
    build.add_argument("--output-dir", required=True, type=Path, help="local or Drive-synced publish directory")
    build.add_argument("--as-of", help="复核完整简报行动有效性的带时区 ISO 时间；省略则按快照时间回放")
    scan = subparsers.add_parser("scan", help="build a reviewable candidate manifest from an allowlisted workspace config")
    scan.add_argument("--config", required=True, type=Path, help="private workspace configuration")
    scan.add_argument("--review-dir", required=True, type=Path, help="private directory for review artifacts")
    scan.add_argument("--previous-manifest", type=Path, help="previous approved manifest used for change review")
    scan.add_argument("--previous-snapshot", type=Path, help="previous explicitly approved snapshot wrapper")
    approve = subparsers.add_parser(
        "approve-snapshot", help="write an explicit immutable private approval record for a reviewed manifest"
    )
    approve.add_argument("--manifest", required=True, type=Path, help="reviewed candidate manifest to approve")
    approve.add_argument("--history-dir", required=True, type=Path, help="private non-synced approval history directory")
    init_review = subparsers.add_parser(
        "init-review-state", help="create a safe unapproved v0.2 review-state skeleton"
    )
    init_review.add_argument("--manifest", required=True, type=Path, help="candidate or approved manifest")
    init_review.add_argument(
        "--project", required=True, action="append", help="explicit project ID; repeat for at most three projects"
    )
    init_review.add_argument("--output", required=True, type=Path, help="private JSON file to create")
    init_review.add_argument("--force", action="store_true", help="replace an existing reviewed target")
    preview_review = subparsers.add_parser(
        "preview-review-state", help="生成只读中文核对单；不批准、不上传、不修改状态"
    )
    preview_review.add_argument("--manifest", required=True, type=Path, help="用于核对项目范围和时间的候选或批准 manifest")
    preview_review.add_argument("--review-state", required=True, type=Path, help="显式指定的私有状态草稿 JSON")
    preview_review.add_argument("--project", required=True, action="append", help="只核对这个项目 ID；最多指定三个")
    preview_review.add_argument("--output", required=True, type=Path, help="仓库及同步目录之外的私有 Markdown 文件")
    question_slice = subparsers.add_parser(
        "slice", help="build a compact question-directed briefing from an approved manifest"
    )
    question_slice.add_argument("--manifest", required=True, type=Path, help="approved JSON manifest")
    question_slice.add_argument("--question", required=True, help="current project discussion question")
    question_slice.add_argument("--output-dir", required=True, type=Path, help="directory for the compact briefing")
    question_slice.add_argument("--as-of", help="复核行动有效性的带时区 ISO 时间；省略则按快照时间回放，不刷新项目事实")
    question_slice.add_argument(
        "--include-document", action="append", default=[], metavar="PROJECT:PATH",
        help="include one existing manifest attachment in full; repeat for selected documents (no local file reads)",
    )
    evaluate = subparsers.add_parser(
        "evaluate", help="audit a paired-answer diagnostic with a private scorecard (not replacement acceptance)"
    )
    evaluate.add_argument("--scorecard", required=True, type=Path, help="private paired-answer scorecard")
    evaluate.add_argument("--output-dir", required=True, type=Path, help="directory for path-free aggregate results")
    evaluate_gold = subparsers.add_parser(
        "evaluate-gold", help="run the deterministic synthetic v0.2 release-gate suite"
    )
    evaluate_gold.add_argument("--suite", required=True, type=Path, help="synthetic gold suite JSON")
    evaluate_gold.add_argument("--output-dir", required=True, type=Path, help="directory for deterministic reports")
    evaluate_architecture = subparsers.add_parser(
        "evaluate-architecture", help="run the deterministic Architecture Index synthetic gold gates"
    )
    evaluate_architecture.add_argument("--fixture-dir", required=True, type=Path, help="synthetic source fixture")
    evaluate_architecture.add_argument("--expected", required=True, type=Path, help="synthetic expected facts JSON")
    evaluate_architecture.add_argument("--output-dir", required=True, type=Path, help="directory for deterministic reports")
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
                previous_config=args.previous_config,
                overwrite=args.force,
            )
            print(result.config.resolve())
            print(f"Discovered {result.project_count} project candidate(s). Review the private config before scanning.")
            return 0
        if args.command == "scan":
            paths = scan_workspace(
                args.config,
                args.review_dir,
                previous_manifest=args.previous_manifest,
                previous_snapshot=args.previous_snapshot,
            )
            print(paths.candidate_manifest.resolve())
            print(paths.report.resolve())
            print(paths.changes_json.resolve())
            print(paths.changes_markdown.resolve())
            print(paths.relationship_review_queue.resolve())
            print(
                "Review the candidate manifest, record approval with `approve-snapshot`, then build the reviewed manifest."
            )
            return 0
        if args.command == "approve-snapshot":
            paths = approve_snapshot(args.manifest, args.history_dir)
            print(paths.history.resolve())
            print(paths.latest.resolve())
            return 0
        if args.command == "init-review-state":
            path = init_review_state(
                args.manifest,
                args.project,
                args.output,
                overwrite=args.force,
            )
            print(path.resolve())
            print("Skeleton created without action facts or approval. Edit it privately before adding it to review_state_files.")
            return 0
        if args.command == "preview-review-state":
            path = preview_review_state(args.manifest, args.project, args.review_state, args.output)
            print(path.resolve())
            print("中文核对单已生成，状态仍未批准。请先核对内容和版本；不要把核对单放入同步目录。")
            return 0
        if args.command == "slice":
            paths = build_question_context(
                args.manifest, args.question, args.output_dir, as_of=args.as_of,
                include_documents=args.include_document,
            )
            print(paths.markdown.resolve())
            return 0
        if args.command == "evaluate":
            paths = build_evaluation_report(args.scorecard, args.output_dir)
            print(paths.markdown.resolve())
            print(paths.json.resolve())
            return 0
        if args.command == "evaluate-gold":
            paths = build_gold_evaluation_report(args.suite, args.output_dir)
            print(paths.markdown.resolve())
            print(paths.json.resolve())
            return 0
        if args.command == "evaluate-architecture":
            paths = build_architecture_evaluation_report(
                args.fixture_dir,
                args.expected,
                args.output_dir,
            )
            print(paths.markdown.resolve())
            print(paths.json.resolve())
            return 0
        paths = build_bundle(args.manifest, args.output_dir, as_of=args.as_of)
    except (ManifestError, OSError) as exc:
        print(f"ai-context-linker: {exc}", file=sys.stderr)
        return 2
    print(paths.markdown.resolve())
    print(paths.graph.resolve())
    if paths.bundle_index is not None:
        print(paths.bundle_index.resolve())
    if paths.project_cards:
        print(f"{paths.project_cards[0].parent.resolve()} ({len(paths.project_cards)} project shard(s))")
    return 0
