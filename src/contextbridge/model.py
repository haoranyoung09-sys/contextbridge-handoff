"""Version 1 snapshot and explicit user-note validation."""

import json
import re
from datetime import (
    datetime,
    timezone
)
from uuid import uuid4

from .safety import (
    BridgeError,
    valid_git_path
)


NOTE_LISTS = ("decisions", "failed_attempts", "tests_passed", "known_issues",
              "next_steps")
ID_PATTERN = re.compile(r"\d{8}T\d{12}Z-[a-f0-9]{12}\Z")


def new_id() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ-") + uuid4().hex[:12]


def parse_json(text: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise BridgeError("Duplicate JSON keys are not allowed.")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=unique)
    except (ValueError, RecursionError) as exc:
        raise BridgeError(
            "Invalid JSON input (including duplicate keys).") from exc


def _object(value, keys, label):
    if not isinstance(value, dict) or set(value) - set(keys):
        raise BridgeError(f"Invalid {label} fields.")


def _text(value, label, limit=10_000):
    if not isinstance(value, str) or len(value) > limit:
        raise BridgeError(
            f"{label} must be text of at most {limit} characters.")
    if any(ord(c) < 32 and c not in "\n\t\r" for c in value):
        raise BridgeError(f"{label} contains unsupported control characters.")
    if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        raise BridgeError(
            f"{label} contains invalid Unicode surrogate characters.")
    return value


def notes(value) -> dict:
    _object(value, ("task", *NOTE_LISTS), "metadata")
    result = {"task": _text(value.get("task", ""), "task")}
    for key in NOTE_LISTS:
        items = value.get(key, [])
        if not isinstance(items, list) or len(items) > 100:
            raise BridgeError(f"{key} must be a list of at most 100 strings.")
        result[key] = [_text(item, key) for item in items]
    return result


def make_snapshot(user_notes: dict, git_state: dict, project_name: str) -> dict:
    data = {
        "schema_version": 1,
        "id": new_id(),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_name": project_name,
        "notes_source": "user-reported",
        "notes": notes(user_notes),
        "git": git_state,
    }
    return validate(data)


def validate(data) -> dict:
    keys = {"schema_version", "id", "created_at", "project_name",
            "notes_source", "notes", "git"}
    _object(data, keys, "snapshot")
    if set(data) != keys:
        raise BridgeError("Snapshot is missing required metadata.")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise BridgeError("Unsupported snapshot schema_version; expected 1.")
    if not isinstance(data["id"], str) or not ID_PATTERN.fullmatch(data["id"]):
        raise BridgeError("Invalid snapshot ID.")
    try:
        if datetime.fromisoformat(data["created_at"]).utcoffset() is None:
            raise ValueError
    except (ValueError, TypeError) as exc:
        raise BridgeError("Invalid snapshot timestamp.") from exc
    _text(data["project_name"], "project_name", 255)
    if data["notes_source"] != "user-reported":
        raise BridgeError("Invalid notes_source.")
    data["notes"] = notes(data["notes"])
    state = data["git"]
    git_keys = {"available", "reason", "branch", "head", "dirty", "files",
                "recent_commits", "omitted_sensitive_paths", "status_accuracy"}
    _object(state, git_keys, "Git metadata")
    if set(state) != git_keys:
        raise BridgeError("Git metadata is incomplete.")
    if type(state["available"]) is not bool:
        raise BridgeError("Git available must be boolean.")
    if state["reason"] is not None and (
            not isinstance(state["reason"], str) or state["reason"] not in {
                "not_repository", "git_unavailable", "git_error"}):
        raise BridgeError("Invalid Git availability reason.")
    if state["status_accuracy"] != "metadata-only":
        raise BridgeError("Unsupported Git status accuracy.")
    if state["branch"] is not None:
        _text(state["branch"], "branch", 1024)
    if state["head"] is not None and (
            not isinstance(state["head"], str) or not re.fullmatch(
                r"[a-f0-9]{40}|[a-f0-9]{64}", state["head"])):
        raise BridgeError("Invalid Git HEAD.")
    if state["dirty"] is not None and type(state["dirty"]) is not bool:
        raise BridgeError("Git dirty must be boolean or null.")
    count = state["omitted_sensitive_paths"]
    if type(count) is not int or count < 0:
        raise BridgeError("Invalid omitted path count.")
    if not isinstance(state["files"], list) or len(state["files"]) > 5000:
        raise BridgeError("Git file list exceeds the 5000-entry limit.")
    for file in state["files"]:
        _object(file, {"status", "path", "original_path"}, "changed file")
        if not {"status", "path"} <= file.keys():
            raise BridgeError("Changed file is missing status or path.")
        status = file["status"]
        if not isinstance(status, str) or not re.fullmatch(r"[ MADRCTU?!]{2}", status):
            raise BridgeError("Invalid Git file status.")
        for key in ("path", "original_path"):
            if key in file:
                path = _text(file[key], "Git file path", 4096)
                if not valid_git_path(path):
                    raise BridgeError(
                        "Unsafe or sensitive Git path in snapshot.")
    commits = state["recent_commits"]
    if not isinstance(commits, list) or len(commits) > 10:
        raise BridgeError("Invalid recent commit list.")
    for commit in commits:
        _object(commit, {"hash", "committed_at"}, "commit")
        if set(commit) != {"hash", "committed_at"} or not isinstance(
                commit["hash"], str) or not re.fullmatch(
                    r"[a-f0-9]{40}|[a-f0-9]{64}", commit["hash"]):
            raise BridgeError("Invalid commit hash.")
        _text(commit["committed_at"], "commit timestamp", 100)
    return data
