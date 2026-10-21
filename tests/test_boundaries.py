"""Security and operational edge cases beyond the happy-path CLI."""

import builtins
import json
import subprocess
import sys
from pathlib import Path

import pytest
from test_cli import (
    cli,
    git,
    repo,
    save
)

from contextbridge import cli as command
from contextbridge import git as collector
from contextbridge import storage
from contextbridge.model import (
    make_snapshot,
    notes
)
from contextbridge.safety import BridgeError


def test_missing_git_is_explicit(tmp_path, monkeypatch):
    monkeypatch.setattr(collector.shutil, "which", lambda name: None)
    state = collector.collect(tmp_path)
    assert state["available"] is False
    assert state["reason"] == "git_unavailable"


def test_inherited_git_directory_cannot_redirect_collection(repo, monkeypatch):
    other = repo / "other"
    other.mkdir()
    git(other, "init", "-b", "wrong-repository")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))
    assert collector.collect(repo)["branch"] == "main"


def test_sensitive_rename_never_exposes_either_name(repo):
    git(repo, "mv", "app.py", "secret-access.py")
    path, data = save(repo)
    assert data["git"]["files"] == []
    assert data["git"]["dirty"] is True
    assert data["git"]["omitted_sensitive_paths"] == 1
    assert "secret-access" not in path.read_text()


def test_save_does_not_read_working_file_contents(repo, monkeypatch):
    def deny_open(*args, **kwargs):
        raise AssertionError("Git collection must never open working files")

    monkeypatch.setattr(Path, "open", deny_open)
    state = collector.collect(repo)
    assert state["available"] is True
    assert state["head"]


def test_output_storage_is_not_itself_dirty(repo):
    _, first = save(repo)
    _, second = save(repo)
    assert first["git"] == second["git"]
    assert second["git"]["dirty"] is False


def test_declining_confirmation_writes_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    answers = iter(["Fix app", "", "", "", "", "", "n"])
    monkeypatch.setattr(builtins, "input", lambda _: next(answers))
    assert command.main(["save", "--project", str(tmp_path)]) == 0
    assert "Canceled" in capsys.readouterr().out
    assert not (tmp_path / ".contextbridge").exists()


def test_confirmed_interactive_notes_are_saved(tmp_path, monkeypatch):
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    answers = iter(["Fix app", "Offline", "", "", "", "", "Test it", "", "y"])
    monkeypatch.setattr(builtins, "input", lambda _: next(answers))
    assert command.main(["save", "--project", str(tmp_path)]) == 0
    data = storage.load(tmp_path)
    assert data["notes"]["task"] == "Fix app"
    assert data["notes"]["decisions"] == ["Offline"]
    assert data["notes"]["next_steps"] == ["Test it"]


def test_metadata_is_bounded_before_parse(tmp_path):
    file = tmp_path / "notes.json"
    file.write_text(" " * 1_048_577)
    result = cli(tmp_path, "save", "--yes", "--metadata", str(file))
    assert result.returncode == 2
    assert not (tmp_path / ".contextbridge").exists()


@pytest.mark.parametrize("bad", [
    {"schema_version": True}, {"notes": {"task": []}},
    {"git": []}, {"created_at": "bad"}, {"id": "../escape"},
    {"notes_source": "verified"},
])
def test_malformed_snapshot_types_fail_cleanly(tmp_path, bad):
    path, data = save(tmp_path)
    data.update(bad)
    path.write_text(json.dumps(data))
    result = cli(tmp_path, "resume")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_duplicate_metadata_keys_are_rejected(tmp_path):
    file = tmp_path / "notes.json"
    file.write_text('{"task": "one", "task": "two"}')
    assert cli(tmp_path, "save", "--yes",
               "--metadata", str(file)).returncode == 2


def test_stdout_transfer_does_not_create_transfer_directory(tmp_path):
    save(tmp_path)
    result = cli(tmp_path, "transfer", "--to", "cursor", "--stdout")
    assert result.returncode == 0
    assert "Cursor" in result.stdout
    assert not (tmp_path / ".contextbridge/transfers").exists()


def test_snapshot_collision_never_overwrites(tmp_path):
    state = collector.collect(tmp_path)
    data = make_snapshot(notes({"task": "one"}), state, "demo")
    path = storage.save(tmp_path, data)
    original = path.read_bytes()
    data["notes"]["task"] = "two"
    with pytest.raises(BridgeError):
        storage.save(tmp_path, data)
    assert path.read_bytes() == original


@pytest.fixture
def linked_storage(tmp_path):
    target = tmp_path / "outside"
    target.mkdir()
    project = tmp_path / "project"
    project.mkdir()
    link = project / ".contextbridge"
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)
    return project, target


def test_linked_storage_cannot_write_outside_project(linked_storage):
    project, outside = linked_storage
    result = cli(project, "save", "--yes")
    assert result.returncode == 2
    assert list(outside.iterdir()) == []


def test_latest_linked_snapshot_is_rejected(tmp_path):
    path, data = save(tmp_path)
    destination = path.parent.parent / ("99991231T235959999999Z-" + "a" * 12)
    if sys.platform == "win32":
        import _winapi
        _winapi.CreateJunction(str(path.parent), str(destination))
    else:
        destination.symlink_to(path.parent, target_is_directory=True)
    assert cli(tmp_path, "resume").returncode == 2


def test_resume_no_git_never_claims_git_matches(tmp_path):
    save(tmp_path)
    result = cli(tmp_path, "resume")
    assert "unavailable" in result.stdout.lower()
    assert "Git metadata matches" not in result.stdout


@pytest.mark.parametrize("bad", [[], {}])
def test_invalid_git_reason_never_crashes(tmp_path, bad):
    path, data = save(tmp_path)
    data["git"]["reason"] = bad
    path.write_text(json.dumps(data))
    result = cli(tmp_path, "resume")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_surrogate_metadata_is_rejected_before_writing(tmp_path):
    file = tmp_path / "notes.json"
    file.write_text('{"task": "\\ud800"}')
    result = cli(tmp_path, "save", "--metadata", str(file), "--yes")
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert not (tmp_path / ".contextbridge").exists()


def test_collection_never_runs_worktree_clean_filters(repo):
    # A normal git status hashes a changed file through this configured filter.
    marker = repo / "FILTER_WAS_RUN"
    script = repo / "filter.py"
    script.write_text(
        "from pathlib import Path\nimport sys\n"
        f"Path({str(marker)!r}).write_text('unsafe')\n"
        "sys.stdout.buffer.write(sys.stdin.buffer.read())\n"
    )
    git(repo, "config", "filter.tripwire.clean",
        f'"{sys.executable}" "{script}"')
    (repo / ".gitattributes").write_text("app.py filter=tripwire\n")
    (repo / "app.py").write_text("print('HELLO')\n")
    state = collector.collect(repo)
    assert state["available"]
    assert not marker.exists(), "Collector invoked a content-reading Git filter"
    assert state["status_accuracy"] == "metadata-only"
    git(repo, "status", "--porcelain")
    assert marker.exists(), "Control must demonstrate the configured filter runs"


def test_tracked_sensitive_worktree_is_not_inspected(repo, monkeypatch):
    file = repo / ".env"
    file.write_text("EXPLICIT_TEST_FIXTURE_NOT_A_REAL_SECRET\n")
    git(repo, "add", ".env")
    git(repo, "commit", "-m", "fixture")
    original = Path.lstat

    def guard(path, *args, **kwargs):
        assert path.name != ".env", "Sensitive files must be excluded before stat"
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", guard)
    state = collector.collect(repo)
    assert state["dirty"] is None
    assert state["omitted_sensitive_paths"] == 1


def test_git_stdout_is_bounded_during_read():
    with pytest.raises(BridgeError, match="limit"):
        collector.run_bounded(
            [sys.executable, "-c", "import sys; sys.stdout.write('x'*200000)"],
            env=None, limit=1024,
        )


def test_git_stderr_is_discarded_and_deadline_enforced():
    result = collector.run_bounded(
        [sys.executable, "-c",
         "import sys; sys.stderr.write('x'*200000); print('ok')"], env=None)
    assert result.stdout.strip() == b"ok"
    with pytest.raises(BridgeError, match="timed out"):
        collector.run_bounded(
            [sys.executable, "-c", "import time; time.sleep(10)"],
            env=None, timeout=0.1,
        )


@pytest.mark.parametrize("staged", [False, True])
def test_file_type_changes_are_supported_without_opening_file(repo, staged):
    file = repo / "app.py"
    file.unlink()
    # A directory is an unstaged type change with no file body to inspect.
    if not staged:
        file.mkdir()
    else:
        file.write_text("#!/usr/bin/env python\n")
        oid = git(repo, "rev-parse", "HEAD:app.py")
        git(repo, "update-index", "--cacheinfo", f"120000,{oid},app.py")
    _, data = save(repo)
    assert data["git"]["dirty"] is True
    entry = next(x for x in data["git"]["files"] if x["path"] == "app.py")
    assert "T" in entry["status"]


def test_nested_project_uses_repository_root_for_all_metadata(repo):
    sub = repo / "sub"
    sub.mkdir()
    (sub / "app.py").write_text("nested file with different size\n")
    git(repo, "add", "sub/app.py")
    git(repo, "commit", "-m", "nested fixture")
    (sub / "app.py").write_text("modified nested file\n")
    _, data = save(sub)
    assert data["git"]["files"] == [
        {"status": " M", "path": "sub/app.py"}
    ]


def test_staged_deletion_and_untracked_reappearance_are_both_preserved(repo):
    git(repo, "rm", "--cached", "app.py")
    _, data = save(repo)
    assert data["git"]["files"] == [
        {"status": "D ", "path": "app.py"},
        {"status": "??", "path": "app.py"},
    ]
