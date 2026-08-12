from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import ManifestError, build_bundle


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ai-context-linker",
        description="Build a privacy-safe project briefing for ChatGPT.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="validate a manifest and build the stable context bundle")
    build.add_argument("--manifest", required=True, type=Path, help="approved JSON manifest")
    build.add_argument("--output-dir", required=True, type=Path, help="local or Drive-synced publish directory")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        paths = build_bundle(args.manifest, args.output_dir)
    except (ManifestError, OSError) as exc:
        print(f"ai-context-linker: {exc}", file=sys.stderr)
        return 2
    print(paths.markdown.resolve())
    print(paths.graph.resolve())
    return 0
