# Snapshot schema v1

`context.json` is authoritative for loading. `context.md` is a human-readable
view; editing it does not change future transfers. To revise notes, save a new
snapshot using explicit metadata and flags. Do not mutate old snapshot IDs.

The top-level fields are:

| Field | Meaning |
| --- | --- |
| `schema_version` | Integer `1`; booleans and future versions are rejected |
| `id` | UTC `YYYYMMDDTHHMMSSffffffZ-` followed by 12 random lowercase hex digits |
| `created_at` | Timezone-aware ISO 8601 timestamp |
| `project_name` | Directory basename, not an absolute machine path |
| `notes_source` | Literal `user-reported` |
| `notes` | Task string and five string lists |
| `git` | Collected metadata, or explicit unavailable state |

Notes keys: `task`, `decisions`, `failed_attempts`, `tests_passed`,
`known_issues`, `next_steps`. Metadata input accepts this notes object directly,
not the whole snapshot. Fields are optional in input; all are written in output.
Each text value is limited to 10,000 characters, each list to 100 items, and JSON
files to 1 MiB. Duplicate keys, unknown fields, invalid UTF-8, and control
characters other than tab/newline/carriage return are rejected.

Git keys: `available`, `reason`, `branch`, `head`, `dirty`, `files`,
`recent_commits`, `omitted_sensitive_paths`, `status_accuracy`. The latter is
always `metadata-only`: staged status compares tree/index object IDs; worktree
status compares stat metadata and is approximate. Omitted paths count all
sensitive entries in tree/index/untracked metadata, not just changed entries.
Sensitive entries are not inspected for worktree changes, so `dirty: null`
means cleanliness cannot be determined. Missing HEAD in an empty repository
is `null`; a detached branch is `DETACHED`. An unavailable repository uses
`available: false` and reason `not_repository`, `git_unavailable`, or `git_error`.
`dirty` is a boolean or `null` when unknown. File entries have porcelain-style `status`
and root-relative `path`, with optional `original_path` for a rename/copy. Up to
5,000 file entries and ten recent commits are allowed. Commit entries contain
only `hash` and `committed_at`.

`M` in the worktree column means a stat-derived possible change, not a content
comparison. A staged deletion whose file remains untracked is represented by
two entries for that path (`D ` and `??`), so consumers must not deduplicate
files by pathname alone. Only exact-object staged renames receive `R`.

Snapshots are loaded only by valid IDs from the selected project's managed
directory. IDs inside JSON must match the directory name. Links/junctions are
rejected. Newer schema versions require an updated reader; no implicit migration
or fallback is attempted. Data is quoted in prompts; quoting is a presentation
aid, not a security boundary against a model obeying malicious text.
