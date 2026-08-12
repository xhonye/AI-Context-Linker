from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import ManifestError, build_bundle
from .scanner import scan_workspace


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-context-linker",
        description="Build a privacy-safe project briefing for ChatGPT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="validate a manifest and build the stable context bundle")
    build.add_argument("--manifest", required=True, type=Path, help="approved JSON manifest")
    build.add_argument("--output-dir", required=True, type=Path, help="local or Drive-synced publish directory")
    scan = subparsers.add_parser("scan", help="build a reviewable candidate manifest from an allowlisted workspace config")
    scan.add_argument("--config", required=True, type=Path, help="private workspace configuration")
    scan.add_argument("--review-dir", required=True, type=Path, help="private directory for review artifacts")
    scan.add_argument("--previous-manifest", type=Path, help="previous approved manifest used for change review")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "scan":
            paths = scan_workspace(args.config, args.review_dir, previous_manifest=args.previous_manifest)
            print(paths.candidate_manifest.resolve())
            print(paths.report.resolve())
            print("Review the candidate manifest, then run `ai-context-linker build` to approve and publish it.")
            return 0
        paths = build_bundle(args.manifest, args.output_dir)
    except (ManifestError, OSError) as exc:
        print(f"ai-context-linker: {exc}", file=sys.stderr)
        return 2
    print(paths.markdown.resolve())
    print(paths.graph.resolve())
    return 0
