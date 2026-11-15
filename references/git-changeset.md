# Git change evidence v1

The Python standard-library producer in `scripts/git_changeset.py` supplies file changes to the Python SRE Git scan. Existing CLI flags, report fields, exit status, and native input paths remain compatible. Native adapters can consume this record once their separate migrations are verified.

## Snapshot inputs

| Snapshot | Comparison | Target field | Untracked paths |
| --- | --- | --- | --- |
| `worktree` | Resolved base commit to current working tree | null | Non-ignored paths listed separately |
| `index` | Resolved base commit to staged index | null | Empty |
| `commit` | Resolved base commit to resolved target commit | Target commit OID | Empty |

The envelope is a JSON-compatible object with `version: 1`, `snapshot`, `base`, `target`, `files`, and `untracked`. Working-tree and index evidence is a local observation. An editor may change those files after collection. Untracked path evidence alone contains no content or findings.

## File records

| Field | Meaning |
| --- | --- |
| `status`, `score` | Git operation status, with an optional Git similarity or dissimilarity score |
| `old_path`, `new_path` | Repository-relative path records. Added files lack an old path. Deleted files lack a new path. |
| `old_mode`, `new_mode` | Octal mode strings, or null when Git does not supply a side |
| `added`, `deleted`, `binary` | Git numstat counts. Binary counts are null. |
| `hunks` | Array of old/new start and count values. A count of zero describes a boundary and contains no lines on that side. Type changes can have separate old and new ranges. |

A path record contains `text` and `raw_hex`. A valid UTF-8 path has text and null raw hex. Undecodable paths carry the original bytes in raw hex and null text. Readers must make unsupported paths explicit. Treat paths as untrusted identifiers before opening files. Git metadata comes from a single NUL-delimited raw/numstat and zero-context patch invocation. Patch filenames determine hunk attribution, so a type change can emit two patch sections for one raw record.

## Finding identity and compatibility

Adapters carry the engine's emitted rule ID and native severity through migration. Canonical IDs and optional catalog IDs describe cross-engine relationships. Findings use repository-relative locations with side and range where available. Evidence excerpts are bounded and come from the same snapshot. Existing public findings may continue using their current names and severity values while adapter coverage is introduced.

[Existing Rust/Go/Python capability and parity matrix](../tests/fixtures/engine-parity/CAPABILITY_MATRIX.md)
[Git diff format](https://git-scm.com/docs/diff-format)
