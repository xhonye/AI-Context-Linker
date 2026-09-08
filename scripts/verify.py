"""Repository-only, offline verification orchestration; not a product compiler.

Runs reviewed test/build code, not an OS sandbox. Logs stay in a new external
directory. No model calls, real state approval, network installs or publication.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import time
import tomllib
import traceback
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import unquote


INPUT_DIRS = {"src", "tests", "scripts", "schema", "examples", "docs", ".github"}
INPUT_FILES = {
    "pyproject.toml", "README.md", "README.zh-CN.md", "AGENTS.md", "PROJECT_CHARTER.md", "CHANGELOG.md",
    "SECURITY.md", "CONTRIBUTING.md", "LICENSE", ".gitignore", ".gitattributes", "MANIFEST.in",
}
SYNC_MARKERS = ("google drive", "googledrive", "onedrive", "dropbox", "icloud", "drivefs")


class VerificationError(RuntimeError):
    def __init__(self, stage: str, reason: str):
        self.stage = stage
        self.reason = reason
        super().__init__(f"{stage}: {reason}")


def path_is_link(path: Path) -> bool:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return False
    return stat.S_ISLNK(info.st_mode) or bool(getattr(info, "st_file_attributes", 0) & 0x400)


def check_path(path: Path, stage: str) -> None:
    try:
        if ".." in path.parts or any(path_is_link(part) for part in (path, *path.parents)):
            raise VerificationError(stage, "unsafe_link_or_path")
    except OSError as exc:
        raise VerificationError(stage, "cannot_inspect_path") from exc


def git_output(repo: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-c", "core.safecrlf=false", "-c", "core.fsmonitor=false", *args], cwd=repo, capture_output=True,
            text=True, encoding="utf-8", errors="replace", timeout=30, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise VerificationError("repository", "git_unavailable") from exc
    if result.returncode:
        raise VerificationError("repository", "git_check_failed")
    return result.stdout.strip() if "-z" not in args else result.stdout


def source_snapshot(repo: Path) -> dict:
    check_path(repo.absolute(), "repository")
    repo = repo.resolve()
    if Path(git_output(repo, "rev-parse", "--show-toplevel")).resolve() != repo:
        raise VerificationError("repository", "wrong_repository_root")
    try:
        project = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))["project"]
        if project["name"] != "ai-context-linker":
            raise VerificationError("repository", "wrong_project")
    except (OSError, ValueError, KeyError) as exc:
        raise VerificationError("repository", "invalid_project_metadata") from exc
    raw_paths = git_output(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    files = {}
    for relative in sorted(set(raw_paths.split("\0")) - {""}):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise VerificationError("repository", "unsafe_input_path")
        root_config = len(path.parts) == 1 and path.suffix in {".py", ".toml", ".ini", ".cfg"}
        if path.parts[0] not in INPUT_DIRS and relative not in INPUT_FILES and not root_config:
            continue
        absolute = repo / path
        check_path(absolute, "repository")
        if not absolute.exists():
            # ls-files includes tracked deletions until they are staged/committed.
            continue
        if not absolute.is_file():
            raise VerificationError("repository", "missing_verification_input")
        files[path.as_posix()] = hashlib.sha256(absolute.read_bytes()).hexdigest()
    if "pyproject.toml" not in files or "src/ai_context_linker/__init__.py" not in files:
        raise VerificationError("repository", "missing_verification_inputs")
    return {
        "head": git_output(repo, "rev-parse", "HEAD"),
        "source_sha256": hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest(),
        "files": files,
    }


def prepare_output(output: Path, repo: Path) -> Path:
    if not output.is_absolute():
        raise VerificationError("output", "absolute_directory_required")
    check_path(output, "output")
    destination = output.resolve()
    forbidden = any(
        marker in part.casefold() for part in destination.parts for marker in SYNC_MARKERS
    ) or any(part.casefold() in {"sol_context", "ai_context_linker"} for part in destination.parts)
    if destination.is_relative_to(repo.resolve()) or destination.exists() or forbidden:
        raise VerificationError("output", "new_external_private_directory_required")
    destination.mkdir(parents=True, exist_ok=False)
    return destination


def child_environment(repo: Path, output: Path, *, source: bool) -> dict[str, str]:
    # Do not hand unrelated application credentials to test/build subprocesses.
    platform_keys = {
        "PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "SYSTEMDRIVE",
        "TEMP", "TMP", "TMPDIR", "HOME", "USERPROFILE", "HOMEDRIVE", "HOMEPATH",
        "APPDATA", "LOCALAPPDATA", "LANG", "LC_ALL", "TZ",
    }
    env = {
        key: value for key, value in os.environ.items()
        if key.upper() in platform_keys
    }
    env.update({
        "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1", "PIP_NO_INDEX": "1",
        "PIP_CONFIG_FILE": os.devnull, "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    })
    if source:
        env["PYTHONPATH"] = str(repo / "src")
    return env


class CommandRunner:
    def __init__(self, output: Path, env: dict, stages: list):
        self.output = output
        self.env = env
        self.stages = stages

    def run(self, stage: str, argv: list[str], cwd: Path, *, env: dict | None = None) -> str:
        started = time.monotonic()
        entry = {"stage": stage, "status": "fail"}
        self.stages.append(entry)
        try:
            command = [str(arg) for arg in argv]
            environment = env if env is not None else self.env
            with (self.output / "commands-private.jsonl").open("a", encoding="utf-8") as audit:
                audit.write(json.dumps({
                    "stage": stage, "argv": command, "cwd": str(cwd),
                    "pythonpath": environment.get("PYTHONPATH"),
                }) + "\n")
            result = subprocess.run(
                command, cwd=cwd, env=environment,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, input="", text=True,
                encoding="utf-8", errors="replace", timeout=120, check=False,
            )
            (self.output / f"{stage}.log").write_text(result.stdout, encoding="utf-8")
            entry["returncode"] = result.returncode
            if result.returncode:
                raise VerificationError(stage, "subcommand_failed_see_private_log")
            entry["status"] = "pass"
            return result.stdout
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise VerificationError(stage, "subcommand_unavailable_or_timed_out") from exc
        finally:
            entry["seconds"] = round(time.monotonic() - started, 3)


def read_test_result(path: Path) -> dict:
    try:
        root = ET.parse(path).getroot()
        suites = [root] if root.tag == "testsuite" else list(root.findall("testsuite"))
        if root.tag not in {"testsuites", "testsuite"} or len(suites) != len(list(root.iter("testsuite"))):
            raise ValueError("unexpected or nested test suites")
        totals = dict.fromkeys(("tests", "failures", "errors", "skipped"), 0)
        for suite in suites:
            declared = {key: int(suite.attrib[key]) for key in totals}
            cases = list(suite.findall("testcase"))
            actual = {"tests": len(cases), "failures": 0, "errors": 0, "skipped": 0}
            if len(cases) != len(list(suite.iter("testcase"))):
                raise ValueError("nested test cases")
            for case in cases:
                outcomes = {key: len(case.findall(tag)) for key, tag in (
                    ("failures", "failure"), ("errors", "error"), ("skipped", "skipped"),
                )}
                if sum(outcomes.values()) > 1:
                    raise ValueError("ambiguous case outcome")
                for key, value in outcomes.items():
                    actual[key] += value
            if declared != actual:
                raise ValueError("declared counts do not match cases")
            for key, value in actual.items():
                totals[key] += value
    except (OSError, ET.ParseError, KeyError, ValueError) as exc:
        raise VerificationError("pytest", "invalid_test_report") from exc
    passed = totals["tests"] - totals["failures"] - totals["errors"] - totals["skipped"]
    if passed <= 0 or totals["failures"] or totals["errors"] or any(value < 0 for value in totals.values()):
        raise VerificationError("pytest", "no_passing_tests_or_failures")
    return {**totals, "passed": passed}


def check_gold_report(path: Path, stage: str) -> None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        if report.get("all_gates_pass") is not True:
            raise VerificationError(stage, "gold_gates_failed")
    except (OSError, ValueError, AttributeError) as exc:
        raise VerificationError(stage, "invalid_gold_report") from exc


def check_installed_origin(identity: dict, environment: Path) -> None:
    try:
        prefix = Path(identity["prefix"]).resolve()
        module = Path(identity["module"]).resolve()
        if prefix != environment.resolve() or not module.is_relative_to(prefix) or "site-packages" not in module.parts:
            raise VerificationError("installed-origin", "source_tree_or_wrong_environment")
    except (KeyError, TypeError, OSError) as exc:
        raise VerificationError("installed-origin", "invalid_identity") from exc


def static_checks(repo: Path, snapshot: dict) -> dict:
    links = 0
    for relative in snapshot["files"]:
        path = repo / relative
        if path.suffix == ".py" and path.parts[len(repo.parts)] in {"src", "scripts", "tests"}:
            ast.parse(path.read_text(encoding="utf-8"), filename=relative)
        elif relative.startswith("schema/") and path.suffix == ".json":
            json.loads(path.read_text(encoding="utf-8"))
        if path.suffix != ".md" or not (relative.startswith("docs/") or "/" not in relative):
            continue
        prose = re.sub(r"```.*?```", "", path.read_text(encoding="utf-8"), flags=re.DOTALL)
        for match in re.finditer(r"\[[^\]\n]*\]\(([^\s)]+)(?:\s+\"[^\"]*\")?\)", prose):
            target = unquote(match.group(1).strip("<>"))
            if target.startswith(("https:", "http:", "mailto:", "#")):
                continue
            local = target.split("#", 1)[0]
            if local and not (path.parent / local).exists():
                raise VerificationError("static", "broken_local_document_link")
            links += 1
    git_output(repo, "diff", "--check", "HEAD")
    return {"local_links_checked": links}


def synthetic_checks(runner: CommandRunner, repo: Path, output: Path, python: list[str], prefix: str = "") -> None:
    examples = repo / "examples"
    gold = output / f"{prefix}gold-action"
    architecture = output / f"{prefix}gold-architecture"
    for stage, args, report in [
        ("gold-action", ["evaluate-gold", "--suite", examples / "evaluation/gold-v02/gold-suite.json", "--output-dir", gold], gold / "gold-evaluation.json"),
        ("gold-architecture", ["evaluate-architecture", "--fixture-dir", examples / "evaluation/architecture-gold/project", "--expected", examples / "evaluation/architecture-gold/expected.json", "--output-dir", architecture], architecture / "architecture-evaluation.json"),
    ]:
        runner.run(prefix + stage, [*python, "-m", "ai_context_linker", *args], output)
        check_gold_report(report, prefix + stage)
    review = output / f"{prefix}synthetic-review"
    bundle = output / f"{prefix}synthetic-bundle"
    for stage, args in [
        ("scan", ["scan", "--config", examples / "synthetic-workspace-config.json", "--review-dir", review]),
        ("build", ["build", "--manifest", review / "candidate-manifest.json", "--output-dir", bundle]),
        ("slice", ["slice", "--manifest", review / "candidate-manifest.json", "--question", "What should I prioritize next?", "--output-dir", bundle]),
    ]:
        runner.run(prefix + "synthetic-" + stage, [*python, "-m", "ai_context_linker", *args], output)


def stage_source(repo: Path, staging: Path, snapshot: dict) -> Path:
    # Only frozen inputs: no ignored hooks, stale build/ or private runtime files.
    staging.mkdir(exist_ok=False)
    for relative, expected_hash in snapshot["files"].items():
        check_path(repo / relative, "source-freeze")
        payload = (repo / relative).read_bytes()
        if hashlib.sha256(payload).hexdigest() != expected_hash:
            raise VerificationError("source-freeze", "source_changed_during_run")
        destination = staging / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    return staging


def check_staged_source(staging: Path, snapshot: dict, *, allow_generated: bool = False) -> None:
    expected = snapshot["files"]
    if not allow_generated:
        observed = set()
        for path in staging.rglob("*"):
            check_path(path, "source-freeze")
            if path.is_file():
                observed.add(path.relative_to(staging).as_posix())
        if observed != set(expected):
            raise VerificationError("source-freeze", "frozen_copy_changed")
    for relative, expected_hash in expected.items():
        path = staging / relative
        check_path(path, "source-freeze")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected_hash:
            raise VerificationError("source-freeze", "frozen_copy_changed")


def build_and_install(runner: CommandRunner, repo: Path, output: Path, snapshot: dict) -> dict:
    staging = stage_source(repo, output / "build-source", snapshot)
    wheels = output / "wheel"
    isolated_env = child_environment(repo, output, source=False)
    runner.run("wheel", [sys.executable, "-I", "-B", "-m", "build", "--wheel", "--no-isolation", "--outdir", wheels, staging], output, env=isolated_env)
    check_staged_source(staging, snapshot, allow_generated=True)
    built = list(wheels.glob("ai_context_linker-*.whl"))
    if len(built) != 1:
        raise VerificationError("wheel", "expected_one_wheel")
    environment = output / "install-env"
    runner.run("venv", [sys.executable, "-I", "-B", "-m", "venv", environment], output, env=isolated_env)
    executable = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    python = [str(executable), "-I", "-B"]
    installed = CommandRunner(output, isolated_env, runner.stages)
    installed.run("install", [*python, "-m", "pip", "install", "--no-index", "--no-deps", "--disable-pip-version-check", built[0]], output)
    installed.run("pip-check", [*python, "-m", "pip", "check"], output)
    raw = installed.run("installed-origin", [*python, "-c", "import ai_context_linker,json,sys; print(json.dumps({'prefix':sys.prefix,'module':ai_context_linker.__file__}))"], output)
    check_installed_origin(json.loads(raw), environment)
    synthetic_checks(installed, staging, output, python, "installed-")
    check_staged_source(staging, snapshot, allow_generated=True)
    return {"package_built": True, "install_verified": True, "wheel_sha256": hashlib.sha256(built[0].read_bytes()).hexdigest()}


def verify(repo: Path, output: Path, profile: str, *, reviewed_source: str | None = None) -> dict:
    if sys.version_info < (3, 11):
        raise VerificationError("environment", "python_311_or_newer_required")
    repo = repo.absolute()
    snapshot = source_snapshot(repo)
    if profile not in {"check", "candidate"}:
        raise VerificationError("arguments", "unknown_profile")
    if profile == "candidate" and reviewed_source != snapshot["source_sha256"]:
        raise VerificationError("review", "matching_reviewed_source_hash_required")
    destination = prepare_output(output, repo)
    summary = {
        "schema_version": "0.1", "profile": profile, "status": "fail", "stages": [],
        "head": snapshot["head"], "source_sha256": snapshot["source_sha256"],
        "package_built": False, "install_verified": False, "replacement_ready": False,
        "project_state_approved": False, "release_verified": False,
        "review_identity_verified": False,
    }
    runner = CommandRunner(destination, child_environment(repo, destination, source=True), summary["stages"])
    try:
        (destination / "inputs-private.json").write_text(json.dumps({
            **snapshot, "repo": str(repo), "python": sys.executable,
            "python_version": sys.version, "reviewed_source_sha256": reviewed_source,
        }, indent=2), encoding="utf-8")
        requirements = ["pytest", "jsonschema"] + (["build", "setuptools"] if profile == "candidate" else [])
        runner.run("environment", [sys.executable, "-I", "-B", "-c", f"import importlib.metadata,json; print(json.dumps({{name: importlib.metadata.version(name) for name in {requirements!r}}}))"], destination)
        staged = stage_source(repo, destination / "verification-source", snapshot)
        runner.env = child_environment(staged, destination, source=True)
        junit = destination / "tests.xml"
        runner.run("pytest", [
            sys.executable, "-I", "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
            "-c", staged / "pyproject.toml", f"--confcutdir={staged}", "--import-mode=importlib",
            f"--junitxml={junit}", f"--basetemp={destination / 'pytest-tmp'}", staged / "tests",
        ], destination)
        check_staged_source(staged, snapshot)
        summary["tests"] = read_test_result(junit)
        summary["static"] = static_checks(repo, snapshot)
        synthetic_checks(runner, staged, destination, [sys.executable, "-B"])
        check_staged_source(staged, snapshot)
        if profile == "candidate":
            summary.update(build_and_install(runner, repo, destination, snapshot))
        if source_snapshot(repo) != snapshot:
            raise VerificationError("source-freeze", "source_changed_during_run")
        summary["status"] = "pass"
        return summary
    except Exception as exc:
        (destination / "failure-private.log").write_text(traceback.format_exc(), encoding="utf-8")
        error = exc if isinstance(exc, VerificationError) else VerificationError("verification", "unexpected_failure_see_private_log")
        summary["failure"] = {"stage": error.stage, "reason": error.reason}
        raise error
    finally:
        (destination / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("check", "candidate"), default="check")
    parser.add_argument("--output-dir", type=Path, help="new absolute directory outside the repository and known sync folders")
    parser.add_argument("--reviewed-source", help="review acknowledgement bound to --print-fingerprint; not project-state approval")
    parser.add_argument("--print-fingerprint", action="store_true", help="print the source fingerprint without writing or running tests")
    args = parser.parse_args(argv)
    repo = Path(__file__).absolute().parents[1]
    try:
        if args.print_fingerprint:
            print(source_snapshot(repo)["source_sha256"])
            return 0
        if args.output_dir is None:
            raise VerificationError("arguments", "output_directory_required")
        summary = verify(repo, args.output_dir, args.profile, reviewed_source=args.reviewed_source)
        print(json.dumps(summary))
        return 0
    except (VerificationError, OSError, ValueError) as exc:
        failure = {"stage": exc.stage, "reason": exc.reason} if isinstance(exc, VerificationError) else {"stage": "preflight", "reason": "invalid_input_or_io_failure"}
        print(json.dumps({"status": "fail", "failure": failure, "replacement_ready": False}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
