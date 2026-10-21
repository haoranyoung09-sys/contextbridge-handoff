"""Bounded JSON reads and immutable, local snapshot publication."""

import json
import tempfile
from pathlib import Path

from .model import (
    ID_PATTERN,
    new_id,
    parse_json,
    validate
)
from .render import render
from .safety import (
    BridgeError,
    checked_path,
    read_text
)


def _directory(path: Path, create=False) -> Path:
    path = checked_path(path)
    if create:
        path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not path.is_dir():
        raise BridgeError("ContextBridge storage directory does not exist.")
    return path


def save(project: Path, data: dict) -> Path:
    validate(data)
    serialized = json.dumps(data, ensure_ascii=True, indent=2) + "\n"
    if len(serialized.encode("utf-8")) > 1_048_576:
        raise BridgeError("Snapshot exceeds the 1 MiB size limit.")
    parent = _directory(project / ".contextbridge" / "snapshots", create=True)
    destination = checked_path(parent / data["id"])
    if destination.exists():
        raise BridgeError("Snapshot already exists; refusing to overwrite it.")
    # Publish the pair together. A crash before rename leaves only a hidden
    # temporary folder; readers only consider validated snapshot IDs.
    with tempfile.TemporaryDirectory(prefix=".pending-", dir=parent) as name:
        pending = Path(name)
        for filename, content in (("context.json", serialized),
                                  ("context.md", render(data))):
            file = pending / filename
            with file.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(content)
            file.chmod(0o600)
        pending.rename(destination)
    return destination / "context.json"


def load(project: Path, snapshot: str | None = None) -> dict:
    if snapshot is not None and not ID_PATTERN.fullmatch(snapshot):
        raise BridgeError("Invalid snapshot ID; paths are not accepted.")
    parent = _directory(project / ".contextbridge" / "snapshots")
    if snapshot is None:
        ids = sorted(p.name for p in parent.iterdir()
                     if ID_PATTERN.fullmatch(p.name))
        if not ids:
            raise BridgeError(
                "No snapshots found. Run contextbridge save first.")
        snapshot = ids[-1]
    file = checked_path(parent / snapshot / "context.json")
    data = validate(parse_json(read_text(file)))
    if data["id"] != snapshot:
        raise BridgeError("Snapshot ID does not match its storage directory.")
    return data


def transfer(project: Path, data: dict, target: str) -> Path:
    parent = _directory(project / ".contextbridge" / "transfers", create=True)
    file = checked_path(parent / f"{data['id']}-{target}-{new_id()}.md")
    # x mode refuses overwrites, including the improbable random ID collision.
    with file.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(render(data, target))
    file.chmod(0o600)
    return file
