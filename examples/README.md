# Example: hand off an unfinished Unicode search task

See [generated/codex.md](generated/codex.md),
[generated/claude-code.md](generated/claude-code.md), and
[generated/cursor.md](generated/cursor.md) for outputs produced by the installed
wheel. [generated/context.json](generated/context.json) is the corresponding
schema-v1 snapshot. These benign samples use a separate copy of the toy project
outside Git, illustrating the unavailable-Git path.

`toy-project/search.py` intentionally has exact, case-sensitive matching.
`notes.json` describes the intended fix and does not claim tests have passed.

From the repository root after installing ContextBridge:

```console
python examples/toy-project/search.py
contextbridge save --project examples/toy-project --metadata examples/notes.json --yes
contextbridge transfer --project examples/toy-project --to codex
contextbridge resume --project examples/toy-project --to codex
```

The first command prints `[]`. The other commands save local JSON/Markdown,
write a destination prompt, and show current-state checks. Open the transfer
path printed by the CLI. In a new Codex session, paste its content and ask to
continue the task. No actual agent session is imported or launched.

For other tools, repeat `transfer --to claude-code` or `transfer --to cursor`.
The toy folder's storage is ignored by this repository. The Git information
comes from the enclosing repository; copy the toy folder outside it to try a
project without Git.
