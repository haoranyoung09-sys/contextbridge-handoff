"""CLI with explicit user notes and safe, offline defaults."""

import argparse
import sys
from pathlib import Path

from . import (
    __version__,
    git,
    storage
)
from .model import (
    NOTE_LISTS,
    make_snapshot,
    notes,
    parse_json
)
from .render import (
    LABELS,
    TARGETS,
    render
)
from .safety import (
    BridgeError,
    checked_path,
    read_text,
    sensitive
)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(
        description="Save and hand off local AI coding context; no network.")
    root.add_argument("--version", action="version", version=__version__)
    sub = root.add_subparsers(dest="command", required=True)
    for name in ("save", "transfer", "resume"):
        command = sub.add_parser(name)
        command.add_argument("--project", type=Path, default=Path.cwd(),
                             help="Existing project directory (default: cwd)")
        if name == "save":
            command.add_argument(
                "--task", help="Current task (overrides JSON)")
            command.add_argument("--metadata", type=Path,
                                 help="Explicit notes JSON; no auto-discovery")
            command.add_argument("--yes", action="store_true",
                                 help="Acknowledge notes are reviewed; skip prompts")
            for flag, key in (
                ("decision", "decisions"), ("failed-attempt", "failed_attempts"),
                ("test-passed", "tests_passed"), ("known-issue", "known_issues"),
                ("next-step", "next_steps"),
            ):
                command.add_argument(f"--{flag}", dest=key, action="append",
                                     default=[], help="Repeat to add notes")
        else:
            command.add_argument(
                "--snapshot", help="Snapshot ID; default latest")
            command.add_argument("--to", choices=TARGETS,
                                 required=name == "transfer", default="codex")
            if name == "transfer":
                command.add_argument("--stdout", action="store_true",
                                     help="Print instead of writing a transfer")
    return root


def _user_notes(args) -> dict:
    value = notes({})
    if args.metadata is not None:
        path = checked_path(args.metadata)
        if sensitive(path.as_posix()):
            raise BridgeError("Sensitive metadata paths are not allowed.")
        value = notes(parse_json(read_text(path)))
    if args.task is not None:
        value["task"] = args.task
    for key in NOTE_LISTS:
        value[key].extend(getattr(args, key))
    return notes(value)


def _prompt(value: dict) -> dict:
    print("Enter reviewed notes. Blank keeps a value; '-' clears it.")
    print("For lists, enter one item per prompt; blank finishes the list.")
    print("Do not include credentials or confidential details.")
    for key, label in LABELS.items():
        if key == "task":
            print(f"Current task: {value[key]!r}")
            item = input(f"{label}: ")
            if item:
                value[key] = "" if item == "-" else item
        else:
            print(f"{label}: {value[key]!r}")
            while True:
                item = input(f"{label} item (blank to finish): ")
                if not item:
                    break
                if item == "-":
                    value[key] = []
                else:
                    value[key].append(item)
    return notes(value)


def _resume(data, current) -> str:
    if not current["available"] or not data["git"]["available"]:
        return ("WARNING: Git metadata is unavailable for the current project "
                "or the snapshot. Verify the working tree manually.")
    if data["git"] != current:
        return ("WARNING: Git metadata changed or is unavailable since this "
                "snapshot. Reconcile the current working tree before editing.")
    return ("Git metadata matches the snapshot. File contents were not checked; "
            "same-status edits cannot be detected. Verify before continuing.")


def main(argv=None) -> int:
    root = parser()
    args = root.parse_args(argv)
    try:
        project = checked_path(args.project)
        if not project.is_dir():
            raise BridgeError("Project must be an existing directory.")
        if args.command == "save":
            if not args.yes and not sys.stdin.isatty():
                raise BridgeError("Noninteractive save requires --yes after "
                                  "reviewing the supplied notes.")
            user_notes = _user_notes(args)
            if not args.yes:
                user_notes = _prompt(user_notes)
            data = make_snapshot(
                user_notes, git.collect(project), project.name)
            if not args.yes:
                print(render(data))
                if input("Save this snapshot locally? [y/N] ").lower() != "y":
                    print("Canceled; no snapshot written.")
                    return 0
            path = storage.save(project, data)
            if not data["git"]["available"]:
                print("Git metadata unavailable: " + data["git"]["reason"],
                      file=sys.stderr)
            print(path)
        else:
            data = storage.load(project, args.snapshot)
            if args.command == "resume":
                print(_resume(data, git.collect(project)))
                print()
                print(render(data, args.to))
            elif args.stdout:
                print(render(data, args.to))
            else:
                print(storage.transfer(project, data, args.to))
        return 0
    except (BridgeError, OSError, EOFError) as exc:
        # Raw OS errors can contain private paths, so don't echo their details.
        message = str(exc) if isinstance(exc, BridgeError) else (
            "File operation failed or input ended; check paths and permissions.")
        print(f"contextbridge: {message}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("contextbridge: Canceled.", file=sys.stderr)
        return 130
