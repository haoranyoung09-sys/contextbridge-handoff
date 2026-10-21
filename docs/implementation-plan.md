# ContextBridge Implementation Plan

**Goal:** Implement the user's complete offline handoff MVP inline.
**Architecture:** Standard library CLI, strict JSON model, read-only Git
collector, immutable local snapshots, and three destination prompt renderers.
**Tech stack:** Python 3.11+, setuptools, pytest.
**Spec:** [design.md](design.md).

## Global constraints

No paid APIs, telemetry, network, secret-file bodies, environment collection,
automatic commits, or pushes. Never overwrite existing user files.

## Review focus

Input validation, path traversal/symlinks, unborn/detached HEAD, renamed sensitive
files, and truthful handling of stale/user-reported context.

## Tasks

- [x] 1. Write failing CLI integration tests in `tests/test_cli.py`, covering
  save/transfer/resume and safety boundaries. Run pytest to establish baseline.
- [x] 2. Implement `cli.main(argv)`, `model.validate(data)`,
  `git.collect(project)`, `storage.save/load`, and `render.render` under
  `src/contextbridge`. Run the full test suite and correct failures.
- [x] 3. Add schema/security/reference docs, examples, English README, Chinese
  quick start, MIT license, CI, and the installable skill. Execute documented
  workflow and skill validation.
- [x] 4. Request independent code review; fix findings with regression tests.
  Build and install wheel, rerun full suite, and record verification evidence.

Git repository is newly initialized at `outputs/ContextBridge`; no isolation
worktree is needed because there is no existing repository or work to disturb.
No commit step: the user explicitly forbids unapproved publishing and did not
request commits. Preserve the plan and verification as the reviewable record.
