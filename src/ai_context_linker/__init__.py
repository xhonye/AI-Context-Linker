"""Privacy-safe project briefing builder."""

from .core import ManifestError, build_bundle, load_manifest
from .discovery import discover_projects, discover_workspace
from .scanner import collect_candidate, scan_workspace

__all__ = [
    "ManifestError",
    "build_bundle",
    "collect_candidate",
    "discover_projects",
    "discover_workspace",
    "load_manifest",
    "scan_workspace",
]
__version__ = "0.2.0"
