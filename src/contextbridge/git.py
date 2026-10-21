"""Index/tree/stat-only Git collection: no worktree hashing or filters."""

import os
import re
import shutil
import stat
import subprocess
import threading
from pathlib import Path

from .safety import (
    BridgeError,
    checked_path,
    internal,
    sensitive
)


def run_bounded(argv, env, timeout=10, limit=4_194_304):
    """Bound stdout while reading, discard stderr, and enforce a deadline."""
    process = subprocess.Popen(argv, stdout=subprocess.PIPE,
                               stderr=subprocess.DEVNULL, env=env)
    output = bytearray()
    done = threading.Event()
    overflow = []

    def consume():
        try:
            while chunk := process.stdout.read(65536):
                if len(output) + len(chunk) > limit:
                    overflow.append(True)
                    break
                output.extend(chunk)
        finally:
            done.set()

    reader = threading.Thread(target=consume, daemon=True)
    reader.start()
    try:
        if not done.wait(timeout):
            raise BridgeError("Git metadata collection timed out.")
        if overflow:
            raise BridgeError("Git metadata exceeds the 4 MiB output limit.")
        try:
            code = process.wait(timeout=1)
        except subprocess.TimeoutExpired as exc:
            raise BridgeError("Git metadata collection timed out.") from exc
        return subprocess.CompletedProcess(argv, code, bytes(output))
    finally:
        if process.poll() is None:
            process.kill()
        process.wait()
        reader.join(timeout=1)
        if not reader.is_alive():
            process.stdout.close()


def _index(raw):
    """Parse Git's index debug metadata without decoding path separators."""
    entries = {}
    offset = 0
    while offset < len(raw):
        end = raw.index(b"\0", offset)
        header = raw[offset:end]
        offset = end + 1
        lines = []
        for _ in range(5):
            end = raw.index(b"\n", offset)
            lines.append(raw[offset:end])
            offset = end + 1
        info, path = header.split(b"\t", 1)
        mode, oid, stage = info.decode("ascii").split()
        mtime = re.search(rb"mtime: (-?\d+):(\d+)", lines[1])
        size = re.search(rb"size: (\d+)", lines[4])
        if mtime is None or size is None:
            raise BridgeError("Unsupported Git index metadata format.")
        path = path.decode("utf-8", "strict")
        entries[path] = {
            "mode": mode, "oid": oid, "stage": stage,
            "mtime_ns": int(mtime[1]) * 1_000_000_000 + int(mtime[2]),
            "size": int(size[1]),
        }
    return entries


def _worktree_code(root, path, entry):
    if entry["mode"] == "160000":
        return " "  # Submodule contents are intentionally not inspected.
    file = root / path
    for parent in file.parents:
        if parent == root:
            break
        if parent.is_symlink():
            return "M"
        if os.name == "nt" and parent.exists():
            if parent.lstat().st_file_attributes & 0x400:
                return "M"
    try:
        info = file.lstat()
    except FileNotFoundError:
        return "D"
    is_link = stat.S_ISLNK(info.st_mode)
    if is_link != (entry["mode"] == "120000"):
        return "T"
    if not is_link and not stat.S_ISREG(info.st_mode):
        return "T"
    if info.st_size != entry["size"] or info.st_mtime_ns != entry["mtime_ns"]:
        return "M"
    if os.name != "nt" and entry["mode"] in {"100644", "100755"}:
        if bool(info.st_mode & stat.S_IXUSR) != (entry["mode"] == "100755"):
            return "M"
    return " "


def collect(project: Path) -> dict:
    state = dict(available=False, reason="git_unavailable", branch=None,
                 head=None, dirty=None, files=[], recent_commits=[],
                 omitted_sensitive_paths=0, status_accuracy="metadata-only")
    executable = shutil.which("git")
    if not executable:
        return state
    env = {"PATH": str(Path(executable).parent), "LC_ALL": "C",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
           "GIT_NO_LAZY_FETCH": "1", "GIT_NO_REPLACE_OBJECTS": "1"}

    collection_dir = project

    def run(*args):
        return run_bounded(
            [executable, "--no-optional-locks", "-c", "core.fsmonitor=false",
             "-c", "core.untrackedCache=false", "-c",
             "core.excludesFile=" + os.devnull, "-C", str(collection_dir), *args], env)

    try:
        root_result = run("rev-parse", "--show-toplevel")
        if root_result.returncode:
            state["reason"] = "not_repository"
            return state
        root = checked_path(
            Path(root_result.stdout.decode("utf-8").removesuffix("\n")))
        collection_dir = root
        index_result = run("ls-files", "--stage", "--debug", "-z")
        untracked = run("ls-files", "--others", "--exclude-standard", "-z")
        if index_result.returncode or untracked.returncode:
            raise BridgeError("Git index metadata could not be collected.")
        index = _index(index_result.stdout)
        others = {p.decode("utf-8")
                  for p in untracked.stdout.split(b"\0") if p}
        branch = run("symbolic-ref", "--quiet", "--short", "HEAD")
        head = run("rev-parse", "--verify", "HEAD")
        state.update(available=True, reason=None,
                     branch=(branch.stdout.decode("utf-8").strip()
                             if not branch.returncode else "DETACHED"),
                     head=(head.stdout.decode("ascii").strip()
                           if not head.returncode else None), dirty=False)
        tree = {}
        if state["head"]:
            result = run("ls-tree", "-r", "-z", "HEAD")
            if result.returncode:
                raise BridgeError("Git tree metadata could not be collected.")
            for record in result.stdout.split(b"\0"):
                if record:
                    info, path = record.split(b"\t", 1)
                    mode, _, oid = info.decode("ascii").split()
                    tree[path.decode("utf-8")] = (mode, oid)
        paths = set(index) | set(tree) | others
        hidden = {p for p in paths if sensitive(p) and not internal(p)}
        state["omitted_sensitive_paths"] = len(hidden)
        hidden_objects = {(index[p]["mode"], index[p]["oid"])
                          for p in hidden if p in index and p not in tree}
        # Suppress the old side of exact renames into a sensitive path too.
        hidden.update(p for p, identity in tree.items()
                      if p not in index and identity in hidden_objects)
        if hidden:
            state["dirty"] = None
        files = {}
        reappeared = []
        for path in sorted(paths):
            if internal(path):
                continue
            entry = index.get(path)
            before = tree.get(path)
            after = (entry["mode"], entry["oid"]) if entry else None
            staged = ("U" if entry and entry["stage"] != "0" else
                      "A" if before is None and after else
                      "D" if before and after is None else
                      "T" if before and after and before[0][:3] != after[0][:3] else
                      "M" if before != after else " ")
            if path in hidden:
                if staged != " " or path in others:
                    state["dirty"] = True
                continue
            if path in others:
                if staged == "D":
                    code = "D "
                    reappeared.append({"status": "??", "path": path})
                else:
                    code = "??"
            else:
                worktree = _worktree_code(root, path, entry) if entry else " "
                code = staged + worktree
            if code != "  ":
                files[path] = {"status": code, "path": path}
                state["dirty"] = True
        # Pair exact-object staged renames without reading either file's blob.
        for new in list(files):
            if not files[new]["status"].startswith("A"):
                continue
            for old in list(files):
                if files[old]["status"] != "D ":
                    continue
                if tree.get(old) == (index[new]["mode"], index[new]["oid"]):
                    files[new]["status"] = "R" + files[new]["status"][1]
                    files[new]["original_path"] = old
                    del files[old]
                    break
        state["files"] = list(files.values()) + reappeared
        if state["head"]:
            log = run("log", "-10", "--format=%H%x09%cI", "HEAD", "--")
            if log.returncode:
                raise BridgeError("Git history could not be collected.")
            for row in log.stdout.decode("ascii").splitlines():
                commit_hash, date = row.split("\t", 1)
                state["recent_commits"].append(
                    {"hash": commit_hash, "committed_at": date})
        return state
    except (OSError, UnicodeError, ValueError) as exc:
        if isinstance(exc, BridgeError):
            raise
        raise BridgeError(
            "Git metadata collection failed or is unsupported.") from exc
