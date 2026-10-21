# Verification record

Local validation on 2026-10-21 (Asia/Shanghai), Windows, Python 3.11.9.

## Automated tests

The initial integration baseline had **23 failing tests** before the CLI
existed. Implementation, edge-case tests, and independently reviewed fixes
produced **54 passed, 0 failed, 0 skipped** on the final suite.

```console
python -m pytest -q
```

The suite exercised real temporary repositories, no repository, unavailable Git,
unborn/detached HEAD, dirty worktrees, exact-object renames, Unicode, interactive
save/cancel, all destination templates, malformed/future snapshots, duplicate
JSON keys, invalid Unicode, missing notes, sensitive-name omission, unknown
cleanliness, inherited Git overrides, root-relative collection in subfolders,
staged deletion with untracked reappearance, type changes, bounded subprocess
output and deadlines, exclusive writes, and Windows junction rejection.

Two checks required normal Windows permissions because the execution sandbox
blocks junction creation and Git's shell process. Those tests ran successfully
with normal permissions. A configured clean-filter control demonstrated that
ordinary `git status` executes the filter while ContextBridge does not.

## Review and skill validation

Independent review found and prompted fixes for Git content/filter access,
malformed availability reasons, invalid Unicode surrogates, type-change states,
unbounded subprocess capture, nested-project paths, and staged deletion
reappearance. The final targeted review reported no remaining important issues.
Each reproducible issue received an appropriate regression test.

The bundled skill creator's validator reported `Skill is valid!`.
A separate agent applied the skill's documented workflow to a temporary toy
project: save, pinned-ID Codex transfer, and resume all succeeded without
prompts. No passed tests were invented, sensitive fixture names were omitted,
and the output stated the historical-data trust boundary. This is workflow
validation, not proof of resistance to adversarial prompt injection.

Import sorting and autopep8 checks completed with no remaining differences.

## Installation and examples

Successfully built `contextbridge_handoff-0.1.0.tar.gz` and
`contextbridge_handoff-0.1.0-py3-none-any.whl` using `python -m build
--no-isolation`. A sandbox temporary-directory permission problem was resolved
by directing build scratch files into this task's workspace; the build then
completed without network access.

Installed the wheel into a fresh virtual environment using `pip install
--no-index --no-deps <wheel>`. The installed console command reported `0.1.0`
and displayed help. The installed save, all three target transfers, and resume
completed successfully against a separate copy of the toy project with no Git.
The generated JSON/Markdown and prompts are included in `examples/generated/`.
The Git-enabled paths were exercised by the full pytest suite.

## Limits

Only Windows/Python 3.11 was executed locally. The GitHub Actions matrix for
Linux/Windows and Python 3.11–3.14 is configured but has not run remotely.
No hosted agent UI integration, native session import, real-secret scan,
network operation, commit, or publication was performed on this project.
Metadata-only status deliberately trades exact content detection for privacy.
