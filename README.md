# ContextBridge — Universal AI Agent Handoff

**Switch AI coding tools with a reviewable record of where work stopped.**

ContextBridge is an offline Python CLI for handing project context between
Codex, Claude Code, and Cursor. It saves explicit task notes alongside Git
metadata, then creates a prompt tailored to the next tool. It requires Python
3.11+ and has **no runtime dependencies, paid API, network calls, or telemetry**.

**MVP / alpha:** this creates portable documents, not native session imports.
It does not migrate chat history, hidden reasoning, tool permissions, source
files, or uncommitted changes. You choose what the next agent receives.

[中文快速开始](docs/quickstart.zh-CN.md) · [Security](docs/security.md) ·
[Schema](docs/schema.md) · [Publishing](docs/publishing.md)

## Install from this checkout

```console
python -m venv .venv
```

Activate it with `source .venv/bin/activate` on macOS/Linux or
`.venv\Scripts\Activate.ps1` in PowerShell, then:

```console
python -m pip install .
contextbridge --help
```

The build step may download setuptools if it is not available. The installed
CLI runs offline. For an offline checkout with no installation, run
`PYTHONPATH=src python -m contextbridge --help` on macOS/Linux; in PowerShell,
set `$env:PYTHONPATH = 'src'` and run `python -m contextbridge --help`.
The distribution name `contextbridge-handoff` is provisional; no package has
been published or name availability verified.

## A complete handoff

Inside the project being handed off:

```console
contextbridge save
contextbridge transfer --to codex
contextbridge resume --to codex
```

`save` prompts for the current task, key decisions, failed attempts, passed
tests, known issues, and next steps. It shows the complete snapshot and asks
before saving. Blank keeps a value; `-` clears it. List prompts accept one
item at a time. Canceling writes nothing.

For automation, supply reviewed notes and explicitly skip prompts:

```console
contextbridge save --project /path/to/project --task "Fix Unicode search" --decision "Keep matching offline" --test-passed "pytest: 12 passed before latest edit" --known-issue "Windows case folding unverified" --next-step "Add regression tests" --yes
contextbridge transfer --project /path/to/project --to claude-code
contextbridge transfer --project /path/to/project --to cursor --stdout
```

`transfer` prints the path of a new Markdown file. Open it and paste its
contents into the destination agent with your current request. `--stdout`
prints the prompt without creating a transfer file. `resume` prints a prompt
and compares current Git metadata with the saved state. It does not execute
notes, run tests, change files, or launch an agent.

Use the same checkout when switching tools. On another machine, separately
bring the correct repository and changes, and copy the reviewed
`.contextbridge/snapshots/<id>/` directory into the target project's storage.
There is no automatic upload or repository clone.

## Explicit metadata JSON

```console
contextbridge save --metadata /path/to/reviewed-notes.json --yes
```

Only the named UTF-8 JSON file is read; notes files are never auto-discovered.
Use [examples/notes.json](examples/notes.json) as a starting point. A CLI task
overrides the JSON task; repeated CLI list flags append to the JSON lists.
Unknown keys or wrong types are rejected. Missing values are displayed as
unknown rather than invented. `--yes` acknowledges review; it does not verify
that the claims are true. Explicit notes are not automatically redacted.

## What is saved

```text
your-project/
└── .contextbridge/
    ├── snapshots/
    │   └── <UTC timestamp>-<random ID>/
    │       ├── context.json
    │       └── context.md
    └── transfers/
        └── <snapshot ID>-<target>-<unique ID>.md
```

Each snapshot has `schema_version: 1`, an ID and UTC timestamp, notes, and Git
branch, HEAD, working-tree status, changed file paths/statuses, and up to ten
recent commit hashes/timestamps. It omits commit messages, authors, remotes,
diffs, and file bodies. Storage files are created exclusively; subsequent saves
and transfers do not overwrite earlier ones. Snapshots are local JSON/Markdown,
not an encrypted archive or a tamper-proof audit log.

For privacy, worktree status is **metadata-only and approximate**. Staged
changes compare index/tree object IDs; unstaged changes compare size, mtime,
and mode without hashing files or invoking content filters. A touched but
unchanged file may appear modified; same-size edits with preserved timestamps
may be missed. Exact-object staged renames are paired; edited renames may
appear as deletion/addition. Submodule working contents are not inspected.
Sensitive entries are excluded before stat checks and counted whether changed
or clean. A `null` dirty value means hidden entries prevent a clean verdict.
Git may read repository `.gitignore` rules while enumerating untracked names.

Use `--snapshot <id>` on `transfer` or `resume` to choose a specific snapshot;
otherwise the latest timestamp/ID is used. Unsupported versions and corrupted
snapshots fail with an explanation rather than silently loading older data.
Storage stays under the exact `--project` directory, even in a Git subfolder;
Git filenames are relative to the repository root. Add `.contextbridge/` to
your project's `.gitignore` yourself before committing anything.

No Git repository or no Git executable is supported: notes still save and the
missing metadata is reported. Empty repositories, detached HEAD and dirty
worktrees are supported. Resume compares metadata, **not file contents**; edits
that preserve a file's status can go undetected. Always inspect and test again.

## Install the Codex skill

Copy the included `skills/contextbridge` folder into your chosen project's
`.agents/skills/` folder. For example, from this checkout in PowerShell:

```powershell
New-Item -ItemType Directory -Force /path/to/project/.agents/skills
Copy-Item -Recurse skills/contextbridge /path/to/project/.agents/skills/contextbridge
```

Use an unused destination folder; inspect or merge any existing installation
before copying. On macOS/Linux use `mkdir -p` and `cp -R` for the same paths.
Open a new Codex session so the installed skill can be discovered, then ask
`$contextbridge` to prepare or consume a handoff. The CLI must be installed in
the environment where Codex runs commands. The skill does not install the CLI
or grant additional permissions. See [SKILL.md](skills/contextbridge/SKILL.md).

Claude Code and Cursor are supported through destination prompts; this MVP
does not install native plugins or modify their instruction files.

## Try the example

```console
contextbridge save --project examples/toy-project --metadata examples/notes.json --yes
contextbridge transfer --project examples/toy-project --to codex
contextbridge resume --project examples/toy-project --to codex
```

The example folder is part of this repository, so Git metadata describes this
repository. To try the no-Git path, copy the toy folder outside any repository.
See [examples/README.md](examples/README.md) for the actual demonstration.

## Develop and test

```console
python -m pip install -e ".[dev]"
python -m pytest
python -m isort --check-only src tests
python -m autopep8 --diff --recursive src tests
python -m build
```

Tests use temporary projects and real local Git repositories; nothing is
uploaded. Link/junction tests skip only if the operating system disallows
creating them. Git must be installed for the repository integration tests.
The CI matrix covers Linux/Windows and Python 3.11–3.14; local verification
results are recorded in [docs/verification.md](docs/verification.md).

To format, run `python -m isort src tests` followed by
`python -m autopep8 --in-place --recursive src tests`.

## Contribute

Keep runtime behavior local and dependency-free. Add a regression test for
behavior changes. Never commit real snapshots, secrets, or personal notes.
For security concerns, avoid posting private snapshot contents in public
issues. No hosted reporting service is configured for this new project.

Licensed under [MIT](LICENSE). See [release steps](docs/publishing.md) before
creating a GitHub repository or publishing a distribution.
