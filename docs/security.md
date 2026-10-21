# Security and privacy

## Data boundaries

The runtime uses Python's standard library and local Git subprocesses. It has
no HTTP client, API token handling, telemetry, clipboard access, or automatic
agent launch. It never runs test commands or shell snippets supplied in notes.
It never stages, resets, checks out, commits, pushes, or fetches a repository.

It collects branch/HEAD, file names/status, and commit hashes/timestamps. It does
not request file bodies, diffs, commit messages/authors, remote URLs, environment
contents, or agent session logs. The only ordinary input file it explicitly
reads is the user-named metadata JSON; it also reads its own snapshots. It
does not search for notes. Git reads repository/index metadata and local
`.gitignore`/`.git/info/exclude` rules to enumerate untracked names. External
`core.excludesFile` settings are disabled. Lazy object fetching is disabled.

The collector uses `ls-files --stage --debug`, `ls-tree`, and file `lstat`
metadata. It never calls `git status`, hashes worktree bodies, or runs clean
filters. Sensitive entries are excluded before `lstat`. Worktree status is
approximate: touching an unchanged file can report M; editing a file while
preserving size and timestamp can be missed. Submodule contents are not checked.
Omitted paths count potentially sensitive entries whether changed or clean;
`dirty: null` means those hidden entries prevent a clean verdict. Staged renames
are detected only when old/new object IDs and modes match exactly.

Names are excluded case-insensitively if a component starts with `.env`, `.ssh`,
`.aws`, `.azure`, or `.gnupg`; equals `.git`, `.npmrc`, `.pypirc`, `.netrc`,
`id_rsa`, `id_ed25519`, `kubeconfig`, or `.kube`; contains `secret`, `credential`,
`password`, `token`, or `private-key`/`private_key`/`privatekey`; or ends with
`.pem`, `.key`, `.p12`, `.pfx`, or `.keystore`. This conservative policy also
hides harmless names such as a tokenizer module. `.contextbridge` entries are
excluded so generated output does not cause self-generated dirty state.

## What this cannot guarantee

This is not secret detection or automatic text redaction. Arbitrary filenames,
branch names, the project basename, and explicitly supplied notes may reveal
private information. Review the generated JSON/Markdown before sharing. The
tool cannot know whether a user-written test claim is true.

Snapshots are unencrypted local files. Private Unix creation modes are used;
Windows access follows the parent directory's ACL. OS backups, syncing folders,
and other processes can access these files according to their own permissions.
Add `.contextbridge/` to your project's ignore rules before staging files.

Path components are checked for symlinks and Windows reparse points. The tool
rejects linked storage and metadata inputs, bounds JSON reads, validates schema
and types, and creates fresh output names. It does not defend against an
attacker concurrently replacing directories between checks, malicious Git
binaries, compromised OS accounts, or arbitrary filesystem races. Run it only
in a checkout and local environment you trust. It is not a sandbox for hostile
repositories or a cryptographically authenticated handoff protocol.

Global/system Git config and inherited Git environment overrides are excluded
from collection. Repository-local Git configuration still applies except for
disabled fsmonitor and optional writes. Git's view may differ from your normal
shell's globally configured behavior (for example, line-ending preferences).
Nested projects report paths relative to their enclosing repository root.

Generated prompts label historical data as untrusted and require current user
instructions to govern work. Prompt injection remains possible if a destination
agent disregards that distinction. Transferring a document does not authorize
any command embedded in it.

`resume` compares metadata only. It cannot discover same-status content edits,
ensure the current tests pass, or prove the checkout is the same project. Bring
the correct source changes and inspect the destination before continuing.
