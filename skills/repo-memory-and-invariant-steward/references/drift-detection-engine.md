# Drift Detection Engine Specification

> Explains the AST, Git diff parsing heuristics, and pattern matching rules used to detect architectural drift.

## Diff Invariant Scanning Mechanics

The Drift Detection Engine (`scripts/invariant_steward_guard.py drift`) evaluates incoming changes across three stages:

### Stage 1: Path Scope Resolution
For every file modified in the diff (via `git diff --name-only <base>` or parsed diff headers):
- Evaluates path glob matches against each invariant's `enforcement_scope.paths`.
- If no governed files are modified, the diff is marked clean for that invariant.

### Stage 2: Forbidden Pattern Matching
For all lines added in the diff (`+` lines, ignoring `+++` header):
- Evaluates case-insensitive regular expressions for each pattern in `enforcement_scope.forbidden_patterns`.
- If a match is found: emits `INVARIANT_FORBIDDEN_PATTERN` (Severity: `block`).

### Stage 3: Required Pattern Deletion
For governed files:
- Evaluates lines deleted (`-` lines) vs lines added (`+` lines) for each required token in `enforcement_scope.patterns`.
- If a required token is completely removed from a governed file without replacement: emits `INVARIANT_PATTERN_REMOVED` (Severity: `block`).

### Stage 4: Reassessment Waiver Override
If an official `reassessment-trigger.json` is provided and structurally complete:
- Verifies that `target_invariant_id` matches the flagged invariant.
- If verified, the violation is waived, and drift status reports `clean` with `waived_invariants` noted.
