"""Integration contracts: real CLI, real repositories, no external service."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def cli(project, *args, input=None):
    env = dict(os.environ, PYTHONPATH=str(ROOT / "src"),
               PYTHONIOENCODING="utf-8")
    return subprocess.run(
        [sys.executable, "-m", "contextbridge", *args,
         "--project", str(project)],
        input=input, capture_output=True, text=True, encoding="utf-8",
        env=env, timeout=30,
    )


def git(project, *args):
    return subprocess.run(
        ["git", "-C", str(project), *args], check=True,
        capture_output=True, text=True, encoding="utf-8",
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    git(tmp_path, "config", "user.name", "Test User")
    git(tmp_path, "config", "user.email", "test@example.invalid")
    git(tmp_path, "config", "core.autocrlf", "false")
    (tmp_path / "app.py").write_text("print('hello')\n", encoding="utf-8")
    git(tmp_path, "add", "app.py")
    git(tmp_path, "commit", "-m", "private commit subject")
    return tmp_path


def save(project, *args):
    result = cli(project, "save", "--yes", *args)
    assert result.returncode == 0, result.stderr
    files = sorted(
        (project / ".contextbridge/snapshots").glob("*/context.json"))
    return files[-1], json.loads(files[-1].read_text(encoding="utf-8"))


def test_no_git_round_trip_and_missing_notes(tmp_path):
    path, data = save(tmp_path, "--task", "修复搜索", "--next-step", "Add tests")
    assert data["schema_version"] == 1
    assert data["notes"]["task"] == "修复搜索"
    assert data["notes"]["next_steps"] == ["Add tests"]
    assert data["notes"]["decisions"] == []
    assert data["git"]["available"] is False
    assert path.with_suffix(".md").exists()
    result = cli(tmp_path, "resume", "--to", "codex")
    assert result.returncode == 0, result.stderr
    assert "修复搜索" in result.stdout
    assert "Unknown" in result.stdout


def test_dirty_git_and_sensitive_paths_are_omitted(repo):
    (repo / "app.py").write_text("NEVER_READ_FILE_BODY\n", encoding="utf-8")
    (repo / ".env").write_text("SECRET_SENTINEL=do-not-read", encoding="utf-8")
    (repo / "credentials.json").write_text("SECRET_CREDENTIAL", encoding="utf-8")
    (repo / "new file.txt").write_text("new", encoding="utf-8")
    path, data = save(repo, "--task", "Fix app")
    state = data["git"]
    assert state["branch"] == "main"
    assert state["dirty"] is True
    assert state["head"] == git(repo, "rev-parse", "HEAD")
    assert {x["path"] for x in state["files"]} == {"app.py", "new file.txt"}
    assert state["omitted_sensitive_paths"] == 2
    assert len(state["recent_commits"]) == 1
    for file in (path, path.with_suffix(".md")):
        text = file.read_text(encoding="utf-8")
        for secret in ("NEVER_READ_FILE_BODY", "SECRET_SENTINEL", ".env",
                       "credentials.json", "private commit subject",
                       "test@example.invalid"):
            assert secret not in text


@pytest.mark.parametrize("target", ["codex", "claude-code", "cursor"])
def test_transfer_is_targeted_and_does_not_clobber(repo, target):
    save(repo, "--task", "Fix search", "--test-passed", "pytest: 5 passed")
    result = cli(repo, "transfer", "--to", target)
    assert result.returncode == 0, result.stderr
    out = Path(result.stdout.strip())
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert "Fix search" in text
    assert "untrusted" in text.lower()
    assert "user-reported" in text.lower()
    assert {"codex": "Codex", "claude-code": "Claude Code",
            "cursor": "Cursor"}[target] in text
    again = cli(repo, "transfer", "--to", target)
    assert again.returncode == 0
    assert again.stdout != result.stdout
    assert out.read_text(encoding="utf-8") == text


def test_empty_repository_and_detached_head(tmp_path, repo):
    empty = tmp_path / "empty"
    empty.mkdir()
    git(empty, "init", "-b", "main")
    _, data = save(empty)
    assert data["git"]["head"] is None
    assert data["git"]["recent_commits"] == []
    git(repo, "checkout", "--detach")
    _, data = save(repo)
    assert data["git"]["branch"] == "DETACHED"


def test_rename_and_unicode_paths(repo):
    git(repo, "mv", "app.py", "代码 file.py")
    _, data = save(repo)
    assert data["git"]["files"] == [
        {"status": "R ", "path": "代码 file.py", "original_path": "app.py"}
    ]


def test_resume_warns_when_head_changed(repo):
    path, _ = save(repo, "--task", "Original")
    git(repo, "commit", "--allow-empty", "-m", "advance")
    result = cli(repo, "resume", "--snapshot", path.parent.name)
    assert result.returncode == 0
    assert "changed" in result.stdout.lower()
    assert "Original" in result.stdout


def test_noninteractive_requires_acknowledgment(tmp_path):
    result = cli(tmp_path, "save", "--task", "Something", input="")
    assert result.returncode == 2
    assert "--yes" in result.stderr
    assert not (tmp_path / ".contextbridge").exists()


def test_explicit_metadata_is_validated_and_merged(tmp_path):
    file = tmp_path / "notes.json"
    file.write_text(json.dumps({"task": "Draft", "decisions": ["SQLite"]}))
    _, data = save(tmp_path, "--metadata", str(file), "--task", "Final",
                   "--decision", "Offline")
    assert data["notes"]["task"] == "Final"
    assert data["notes"]["decisions"] == ["SQLite", "Offline"]


@pytest.mark.parametrize("content", ["not json", "[]", '{"task": 3}',
                                     '{"decisions": "bad"}',
                                     '{"unknown": "ignored?"}'])
def test_invalid_metadata_writes_nothing(tmp_path, content):
    file = tmp_path / "notes.json"
    file.write_text(content)
    result = cli(tmp_path, "save", "--yes", "--metadata", str(file))
    assert result.returncode == 2
    assert "Traceback" not in result.stderr
    assert not (tmp_path / ".contextbridge").exists()


def test_missing_corrupt_and_future_snapshots(tmp_path):
    assert cli(tmp_path, "resume").returncode == 2
    path, data = save(tmp_path)
    data["schema_version"] = 999
    path.write_text(json.dumps(data))
    result = cli(tmp_path, "resume")
    assert result.returncode == 2
    assert "schema" in result.stderr.lower()
    path.write_text("broken")
    assert cli(tmp_path, "resume").returncode == 2


@pytest.mark.parametrize("value", ["../outside", "..", "/tmp/context", "x/y"])
def test_snapshot_ids_cannot_traverse(tmp_path, value):
    result = cli(tmp_path, "resume", "--snapshot", value)
    assert result.returncode == 2


def test_sensitive_explicit_metadata_is_rejected(tmp_path):
    file = tmp_path / ".env.json"
    file.write_text('{"task": "do not read"}')
    result = cli(tmp_path, "save", "--yes", "--metadata", str(file))
    assert result.returncode == 2
    assert not (tmp_path / ".contextbridge").exists()


def test_invalid_target_and_project(tmp_path):
    assert cli(tmp_path, "transfer", "--to", "other").returncode == 2
    assert cli(tmp_path / "absent", "save", "--yes").returncode == 2


def test_project_subdirectory_uses_project_local_storage(repo):
    sub = repo / "subdir"
    sub.mkdir()
    _, data = save(sub)
    assert data["git"]["branch"] == "main"
    assert (sub / ".contextbridge").is_dir()
    assert not (repo / ".contextbridge").exists()
