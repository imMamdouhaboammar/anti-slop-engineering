# Rust change check

`anti-slop-rust change-check` applies file-level intent and scope policies to the [Git change evidence v1](git-changeset.md) record. It reads JSON from standard input or `--changeset <file>` and accepts the existing `--format text|json` report format.

```bash
python3 scripts/git_changeset.py --repo . --base HEAD --snapshot index |
  anti-slop-rust change-check --read-only --allowed src/,tests/ --format json
```

- `--read-only` emits one `STS-I01` blocker per recorded file operation, including binary and metadata-only changes. `--allowed` applies `STS-S01` scope to Git path components. A trailing slash matches descendants only. A bare path matches the path and its descendants. Both sides of a rename or copy are checked. A non-UTF-8 path retains the `unknown` label and blocks scoped changes whose path cannot be verified.
- Worktree records can also list untracked paths. Use `--include-untracked` to include that evidence in file-level checks. The default checks the tracked `files` records.
- Version, snapshot and target combinations, paths, and hunk coordinates are validated before any report is emitted. Malformed input and records above 64 MiB exit nonzero. A valid report exits 1 when blockers exist and 0 otherwise.
- A v1 change set contains coordinates and metadata. The consumer opens no repository files and treats the record as producer-supplied evidence without independently proving its provenance. Findings use line 1 as a file-level anchor. Source-dependent rules still run through the existing `triage` and `shit-check` commands.
