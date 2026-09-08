"""Synthetic failure paths for the repository-only verification entrypoint."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture
def workflow():
    spec = importlib.util.spec_from_file_location(
        "linker_dev_verify", Path(__file__).parents[1] / "scripts" / "verify.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repository(tmp_path: Path, monkeypatch, workflow):
    repo = tmp_path / "repository"
    (repo / "src" / "ai_context_linker").mkdir(parents=True)
    (repo / "tests").mkdir()
    (repo / "pyproject.toml").write_text(
        '[project]\nname = "ai-context-linker"\nversion = "0.2.0"\n', encoding="utf-8"
    )
    (repo / "src/ai_context_linker/__init__.py").write_text("", encoding="utf-8")
    (repo / "tests/test_synthetic.py").write_text("def test_example():\n    assert True\n", encoding="utf-8")

    def fake_git(root, *args):
        if args == ("rev-parse", "--show-toplevel"):
            return str(repo)
        if args == ("rev-parse", "HEAD"):
            return "a" * 40
        if args == ("ls-files", "-z", "--cached", "--others", "--exclude-standard"):
            return "\0".join(path.relative_to(repo).as_posix() for path in sorted(repo.rglob("*")) if path.is_file()) + "\0"
        if args == ("diff", "--check", "HEAD"):
            return ""
        raise AssertionError(args)

    monkeypatch.setattr(workflow, "git_output", fake_git)
    return repo


def test_repository_identity_fails_closed(workflow, repository, monkeypatch, tmp_path):
    monkeypatch.setattr(workflow, "git_output", lambda *args: str(tmp_path / "other"))
    with pytest.raises(workflow.VerificationError, match="repository"):
        workflow.source_snapshot(repository)


def test_source_hash_is_stable_and_changes_with_new_test(workflow, repository):
    first = workflow.source_snapshot(repository)
    assert first == workflow.source_snapshot(repository)
    (repository / "tests/test_added.py").write_text("def test_new():\n    pass\n", encoding="utf-8")
    assert workflow.source_snapshot(repository)["source_sha256"] != first["source_sha256"]


def test_uncommitted_tracked_deletion_is_a_valid_snapshot(workflow, repository, monkeypatch):
    original_git = workflow.git_output
    def git(root, *args):
        result = original_git(root, *args)
        return result + "src/removed.py\0" if args[0] == "ls-files" else result
    monkeypatch.setattr(workflow, "git_output", git)
    snapshot = workflow.source_snapshot(repository)
    assert "src/removed.py" not in snapshot["files"]


def test_snapshot_does_not_collect_private_untracked_files(workflow, repository):
    (repository / "review-state.json").write_text('{"private": "SYNTHETIC_PRIVATE"}', encoding="utf-8")
    snapshot = workflow.source_snapshot(repository)
    assert "review-state.json" not in snapshot["files"]
    assert "SYNTHETIC_PRIVATE" not in json.dumps(snapshot)


@pytest.mark.parametrize("filename", [
    "pytest.ini", "tox.ini", "setup.cfg", "conftest.py", "pytest.py", "setup.py", "MANIFEST.in",
])
def test_root_execution_inputs_are_bound_to_source_hash(workflow, repository, filename):
    first = workflow.source_snapshot(repository)
    target = repository / filename
    target.write_text("# synthetic execution input\n", encoding="utf-8")
    second = workflow.source_snapshot(repository)
    assert filename in second["files"]
    assert second["source_sha256"] != first["source_sha256"]
    target.write_text("# changed synthetic execution input\n", encoding="utf-8")
    assert workflow.source_snapshot(repository)["source_sha256"] != second["source_sha256"]


@pytest.mark.parametrize("unsafe", ["existing", "repository", "cloud", "stable"])
def test_output_requires_new_private_external_directory(workflow, repository, tmp_path, unsafe):
    paths = {
        "existing": tmp_path / "existing",
        "repository": repository / "output",
        "cloud": tmp_path / "Google Drive" / "run",
        "stable": tmp_path / "sol_context" / "run",
    }
    paths["existing"].mkdir()
    with pytest.raises(workflow.VerificationError, match="output"):
        workflow.prepare_output(paths[unsafe], repository)


def test_output_rejects_linked_ancestor(workflow, repository, tmp_path, monkeypatch):
    linked = tmp_path / "linked"
    linked.mkdir()
    original = workflow.path_is_link
    monkeypatch.setattr(workflow, "path_is_link", lambda path: path == linked or original(path))
    with pytest.raises(workflow.VerificationError, match="output"):
        workflow.prepare_output(linked / "run", repository)


def test_child_environment_is_isolated_and_pip_is_offline(workflow, repository, tmp_path, monkeypatch):
    monkeypatch.setenv("PYTHONPATH", "SYNTHETIC_FOREIGN_IMPORT")
    monkeypatch.setenv("PYTHONHOME", "SYNTHETIC_FOREIGN_HOME")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--collect-only")
    monkeypatch.setenv("PIP_FIND_LINKS", "https://synthetic.invalid/packages")
    monkeypatch.setenv("PIP_INDEX_URL", "https://synthetic.invalid/index")
    monkeypatch.setenv("LINKER_TEST_SECRET", "SYNTHETIC_SECRET_NOT_FOR_SUBCOMMANDS")
    env = workflow.child_environment(repository, tmp_path, source=True)
    assert env["PYTHONPATH"] == str(repository / "src")
    assert env["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] == "1"
    assert env["PIP_NO_INDEX"] == "1"
    assert env["PIP_CONFIG_FILE"] == os.devnull
    assert "PYTEST_ADDOPTS" not in env and "PYTHONHOME" not in env
    assert "PIP_FIND_LINKS" not in env and "PIP_INDEX_URL" not in env
    assert "LINKER_TEST_SECRET" not in env
    assert "PYTHONPATH" not in workflow.child_environment(repository, tmp_path, source=False)


@pytest.mark.parametrize("attributes", [
    'tests="0" errors="0" failures="0" skipped="0"',
    'tests="2" errors="1" failures="0" skipped="0"',
    'tests="2" errors="0" failures="1" skipped="0"',
    'tests="2" errors="0" failures="0" skipped="2"',
])
def test_junit_cannot_fake_success(workflow, tmp_path, attributes):
    path = tmp_path / "tests.xml"
    path.write_text(f"<testsuites><testsuite {attributes}/></testsuites>", encoding="utf-8")
    with pytest.raises(workflow.VerificationError, match="pytest"):
        workflow.read_test_result(path)


def test_junit_reports_skips_without_claiming_full_coverage(workflow, tmp_path):
    path = tmp_path / "tests.xml"
    path.write_text(
        '<testsuites><testsuite tests="3" errors="0" failures="0" skipped="1">'
        '<testcase name="one"/><testcase name="two"/>'
        '<testcase name="three"><skipped/></testcase></testsuite></testsuites>',
        encoding="utf-8",
    )
    assert workflow.read_test_result(path) == {"tests": 3, "passed": 2, "failures": 0, "errors": 0, "skipped": 1}


@pytest.mark.parametrize("xml", [
    '<testsuites><testsuite tests="99" errors="0" failures="0" skipped="0"/></testsuites>',
    '<testsuite tests="2" errors="0" failures="0" skipped="0"><testcase name="one"/></testsuite>',
    '<testsuite tests="1" errors="0" failures="0" skipped="0"><testcase name="one"><failure/></testcase></testsuite>',
    '<testsuite tests="1" errors="0" failures="0" skipped="0"><testsuite tests="1" errors="0" failures="0" skipped="0"><testcase name="one"/></testsuite></testsuite>',
    '<testsuite tests="2" errors="0" failures="0" skipped="2"><testcase name="one"><skipped/></testcase><testcase name="two"><skipped/></testcase></testsuite>',
    '<testsuite tests="2" errors="0" failures="1" skipped="0"><testcase name="one"/><testcase name="two"><failure/></testcase></testsuite>',
])
def test_junit_declared_counts_cannot_override_actual_cases(workflow, tmp_path, xml):
    path = tmp_path / "tests.xml"
    path.write_text(xml, encoding="utf-8")
    with pytest.raises(workflow.VerificationError, match="pytest"):
        workflow.read_test_result(path)


def test_subcommand_failure_keeps_raw_output_private(workflow, tmp_path, monkeypatch):
    monkeypatch.setattr(workflow.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 7, "SYNTHETIC_SECRET_NOTE"))
    runner = workflow.CommandRunner(tmp_path, {}, [])
    with pytest.raises(workflow.VerificationError) as error:
        runner.run("synthetic-stage", [sys.executable, "-V"], tmp_path)
    assert "SYNTHETIC_SECRET_NOTE" not in str(error.value)
    assert "SYNTHETIC_SECRET_NOTE" in (tmp_path / "synthetic-stage.log").read_text(encoding="utf-8")
    assert runner.stages[-1]["status"] == "fail"


def test_command_arguments_are_recorded_only_in_private_audit(workflow, tmp_path, monkeypatch):
    monkeypatch.setattr(workflow.subprocess, "run", lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 0, "ok"))
    runner = workflow.CommandRunner(tmp_path, {}, [])
    argv = ["synthetic", "SYNTHETIC_PRIVATE_ARGUMENT"]
    assert runner.run("synthetic-stage", argv, tmp_path) == "ok"
    audit = json.loads((tmp_path / "commands-private.jsonl").read_text(encoding="utf-8"))
    assert audit["argv"] == argv and audit["cwd"] == str(tmp_path)
    assert "SYNTHETIC_PRIVATE_ARGUMENT" not in json.dumps(runner.stages)


@pytest.mark.parametrize("failure", [FileNotFoundError(), subprocess.TimeoutExpired(["synthetic"], 1)])
def test_missing_executable_and_timeout_are_failures(workflow, tmp_path, monkeypatch, failure):
    def fail(*args, **kwargs):
        raise failure
    monkeypatch.setattr(workflow.subprocess, "run", fail)
    with pytest.raises(workflow.VerificationError):
        workflow.CommandRunner(tmp_path, {}, []).run("synthetic-stage", ["synthetic"], tmp_path)


def test_false_gold_report_is_rejected(workflow, tmp_path):
    path = tmp_path / "gold.json"
    path.write_text('{"all_gates_pass": false}', encoding="utf-8")
    with pytest.raises(workflow.VerificationError, match="gold"):
        workflow.check_gold_report(path, "gold-action")


def test_installed_origin_cannot_be_the_source_tree(workflow, repository, tmp_path):
    env_dir = tmp_path / "environment"
    with pytest.raises(workflow.VerificationError, match="installed"):
        workflow.check_installed_origin(
            {"prefix": str(env_dir), "module": str(repository / "src/ai_context_linker/__init__.py")}, env_dir
        )


def test_candidate_requires_matching_reviewed_source(workflow, repository, tmp_path):
    with pytest.raises(workflow.VerificationError, match="review"):
        workflow.verify(repository, tmp_path / "candidate", "candidate", reviewed_source="0" * 64)
    assert not (tmp_path / "candidate").exists()


def test_unsupported_interpreter_fails_before_writing(workflow, repository, tmp_path, monkeypatch):
    monkeypatch.setattr(workflow.sys, "version_info", (3, 10))
    with pytest.raises(workflow.VerificationError, match="python_311_or_newer_required"):
        workflow.verify(repository, tmp_path / "run", "check")
    assert not (tmp_path / "run").exists()


def test_missing_dependency_never_triggers_an_install(workflow, repository, tmp_path, monkeypatch):
    calls = []
    def fail(self, stage, argv, cwd, *, env=None):
        calls.append((stage, argv))
        raise workflow.VerificationError(stage, "dependency_check_failed")
    monkeypatch.setattr(workflow.CommandRunner, "run", fail)
    with pytest.raises(workflow.VerificationError):
        workflow.verify(repository, tmp_path / "run", "check")
    assert len(calls) == 1 and calls[0][0] == "environment"
    assert all("install" not in argv for _, argv in calls)
    summary = json.loads((tmp_path / "run/summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "fail" and not summary["replacement_ready"]
    assert "SYNTHETIC" not in json.dumps(summary)


@pytest.fixture
def passing_commands(workflow, monkeypatch):
    calls = []

    def run(self, stage, argv, cwd, *, env=None):
        calls.append((stage, [str(arg) for arg in argv], cwd, None))
        if stage == "pytest":
            (self.output / "tests.xml").write_text(
                '<testsuite tests="1" errors="0" failures="0" skipped="0"><testcase name="synthetic"/></testsuite>',
                encoding="utf-8",
            )
        return ""

    monkeypatch.setattr(workflow.CommandRunner, "run", run)
    monkeypatch.setattr(workflow, "synthetic_checks", lambda *args: None)
    return calls


def test_check_is_isolated_and_never_builds_or_installs(workflow, repository, tmp_path, passing_commands):
    output = tmp_path / "run"
    summary = workflow.verify(repository, output, "check")
    assert summary["status"] == "pass" and summary["tests"]["passed"] == 1
    assert not summary["package_built"] and not summary["install_verified"]
    assert [stage for stage, *_ in passing_commands] == ["environment", "pytest"]
    _, command, cwd, _ = passing_commands[-1]
    staged = output / "verification-source"
    assert "-I" in command and "--import-mode=importlib" in command
    assert command[command.index("-c") + 1] == str(staged / "pyproject.toml")
    assert f"--confcutdir={staged}" in command and str(staged / "tests") in command
    assert cwd == output


def test_staged_checks_exclude_inputs_not_in_the_fingerprint(workflow, repository, tmp_path):
    snapshot = workflow.source_snapshot(repository)
    (repository / "conftest.py").write_text("# synthetic unreviewed hook\n", encoding="utf-8")
    staged = workflow.stage_source(repository, tmp_path / "staged", snapshot)
    assert (staged / "tests/test_synthetic.py").is_file()
    assert not (staged / "conftest.py").exists()
    assert not (staged / ".git").exists()


@pytest.mark.parametrize("phase", ["pytest", "gold", "extra-file"])
def test_mutated_verification_copy_cannot_report_success(workflow, repository, tmp_path, monkeypatch, passing_commands, phase):
    original_run = workflow.CommandRunner.run

    def mutate(staged):
        path = staged / ("conftest.py" if phase == "extra-file" else "src/ai_context_linker/__init__.py")
        path.write_text("# synthetic mutation inside frozen copy\n", encoding="utf-8")

    def run(self, stage, argv, cwd, *, env=None):
        result = original_run(self, stage, argv, cwd, env=env)
        if stage == "pytest" and phase != "gold":
            mutate(self.output / "verification-source")
        return result

    monkeypatch.setattr(workflow.CommandRunner, "run", run)
    if phase == "gold":
        monkeypatch.setattr(workflow, "synthetic_checks", lambda runner, staged, *args: mutate(staged))
    with pytest.raises(workflow.VerificationError, match="frozen_copy_changed"):
        workflow.verify(repository, tmp_path / "run", "check")
    summary = json.loads((tmp_path / "run/summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "fail"


def test_source_mutation_invalidates_success(workflow, repository, tmp_path, monkeypatch, passing_commands):
    def mutate(*args):
        (repository / "tests/test_added.py").write_text("# synthetic change during verification\n", encoding="utf-8")
    monkeypatch.setattr(workflow, "synthetic_checks", mutate)
    with pytest.raises(workflow.VerificationError, match="source_changed_during_run"):
        workflow.verify(repository, tmp_path / "run", "check")
    summary = json.loads((tmp_path / "run/summary.json").read_text(encoding="utf-8"))
    assert summary["status"] == "fail"


def test_synthetic_cli_does_not_import_from_repository_cwd(workflow, repository, tmp_path, monkeypatch):
    calls = []
    def run(self, stage, argv, cwd, *, env=None):
        calls.append((stage, cwd))
        return ""
    monkeypatch.setattr(workflow.CommandRunner, "run", run)
    monkeypatch.setattr(workflow, "check_gold_report", lambda *args: None)
    workflow.synthetic_checks(workflow.CommandRunner(tmp_path, {}, []), repository, tmp_path, [sys.executable, "-B"])
    assert len(calls) == 5 and all(cwd == tmp_path for _, cwd in calls)


def test_clean_build_cannot_inherit_real_source_imports(workflow, repository, tmp_path, monkeypatch):
    output = tmp_path / "run"
    output.mkdir()
    calls = []
    def stop_at_build(self, stage, argv, cwd, *, env=None):
        calls.append((stage, argv, env if env is not None else self.env))
        raise workflow.VerificationError(stage, "synthetic_stop_before_build")
    monkeypatch.setattr(workflow.CommandRunner, "run", stop_at_build)
    runner = workflow.CommandRunner(output, workflow.child_environment(repository, output, source=True), [])
    with pytest.raises(workflow.VerificationError, match="synthetic_stop_before_build"):
        workflow.build_and_install(runner, repository, output, workflow.source_snapshot(repository))
    stage, argv, env = calls[0]
    assert stage == "wheel" and "-I" in argv
    assert "PYTHONPATH" not in env and env["PIP_NO_INDEX"] == "1"


def test_build_cannot_modify_frozen_inputs(workflow, repository, tmp_path, monkeypatch):
    output = tmp_path / "run"
    output.mkdir()
    calls = []
    def mutate(self, stage, *args, **kwargs):
        calls.append(stage)
        (output / "build-source/src/ai_context_linker/__init__.py").write_text("# synthetic build mutation\n", encoding="utf-8")
        return ""
    monkeypatch.setattr(workflow.CommandRunner, "run", mutate)
    with pytest.raises(workflow.VerificationError, match="frozen_copy_changed"):
        workflow.build_and_install(workflow.CommandRunner(output, {}, []), repository, output, workflow.source_snapshot(repository))
    assert calls == ["wheel"]


def test_build_generated_files_do_not_allow_frozen_input_changes(workflow, repository, tmp_path):
    snapshot = workflow.source_snapshot(repository)
    staged = workflow.stage_source(repository, tmp_path / "staged", snapshot)
    (staged / "build").mkdir()
    (staged / "build/generated.txt").write_text("synthetic generated metadata", encoding="utf-8")
    workflow.check_staged_source(staged, snapshot, allow_generated=True)
    with pytest.raises(workflow.VerificationError, match="frozen_copy_changed"):
        workflow.check_staged_source(staged, snapshot)
    (staged / "src/ai_context_linker/__init__.py").write_text("# synthetic mutation\n", encoding="utf-8")
    with pytest.raises(workflow.VerificationError, match="frozen_copy_changed"):
        workflow.check_staged_source(staged, snapshot, allow_generated=True)
