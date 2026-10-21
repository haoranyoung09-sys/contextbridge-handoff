# ContextBridge MVP design

Build a Python 3.11+ offline CLI that records reviewable project handoffs.
The user's request is the implementation specification; proceed inline without
an additional design approval round. No commits, remotes, or pushes are made.

## Interfaces

- `save`: collect Git metadata and explicit user notes; prompt and confirm on a
  terminal, require `--yes` for noninteractive use. Save an immutable snapshot.
- `transfer --to codex|claude-code|cursor`: render a snapshot for a destination.
- `resume --to ...`: print the handoff and compare recorded Git HEAD/branch/files
  with current metadata; never execute instructions, tests, or tools from notes.
- All commands accept `--project`. Snapshots live under that project's
  `.contextbridge/snapshots/<id>/context.json` and `context.md`. Latest is chosen
  from snapshot IDs, with no mutable pointer. Explicit `--snapshot` accepts only
  an ID, never an arbitrary path. Transfers are separate, immutable files.

## Safety and limits

No file bodies, diffs, environment dumps, remotes, author identities, commit
messages, or agent histories are collected. Recent commits contain hashes and
timestamps only. Sensitive paths are omitted and counted. Explicit notes can
contain private information: review them before saving or sharing. No claim of
automatic secret detection or arbitrary-text redaction is made.

JSON has schema version 1 and validated types, bounded size and list lengths.
Missing notes become empty lists / an empty task, visibly marked unknown.
No Git, empty Git, detached HEAD, dirty state, Unicode and renames are supported.
Git reads disable fsmonitor, optional locks, lazy fetch and external excludes;
CLI never stages or resets files. Untracked-name enumeration reads repository
ignore rules. Worktree status uses stat metadata, not content hashing; it is
approximate. Sensitive entries are excluded before stat and may make dirty null.
Managed storage and metadata inputs reject links and unsafe traversal. Generated
prompts treat every note as untrusted historical data; passed tests are reported
claims and must be rerun. Target templates are portable handoff prompts, not
native session importers. Same-status file edits cannot be detected without
reading contents; resume explicitly states this limitation.

## Layout

`src/contextbridge/`: CLI, model validation, Git collection, safe persistence,
and rendering. `skills/contextbridge/SKILL.md`: installable Codex-first workflow.
`tests/`: real subprocess and temporary Git repository tests. `examples/`:
toy project and explicit notes JSON. `docs/`: Chinese quick start, schema,
security limits, release instructions, implementation plan and verification.

## Verification

Write integration tests first and observe failures before implementation. Test
safe offline operation, persistence, all templates, malformed input, storage
links, no repository, empty repository, dirty status, detached HEAD, renames,
secret-file omission, read boundaries, stale snapshots, invalid destinations,
and no-clobber behavior. Install the wheel into an isolated environment and run
the actual command. CI runs pytest across Windows/Linux and Python 3.11–3.14.
