# Root-Fix record contract (version 1)

Use for consequential, cross-layer, disputed, or repeatedly patched problems; omit for narrow changes with an established owner. A record is a checkpoint for reasoning, not a proof of causality.

| JSON field | Contract |
| --- | --- |
| `problem`, `symptom` | Desired observable correction and observed failure, not a patch command |
| `root_cause` | `cause` hypothesis, responsible `owner`, `evidence[]` with `source`, `finding`, `level` (`observed`, `derived`, `inferred`) |
| `options[]` | Competing fixes with `approach`, `tradeoff`, boolean `selected`; compare at least two for `proceed`, or one with `sole_option_reason` |
| `planned_changes[]` | Repo-relative `path`, `role` (`owner`, `consumer`, `test`, `migration`, `integration`), `reason` |
| `invariants[]` | Preserved `rule` plus independent `proof` (test/probe to execute, not a success assertion) |
| `data_impact` | `mode` (`none`, `additive`, `destructive`). A destructive `proceed` also needs `approval_ref` and `recovery` |
| `decision` | `action` (`proceed`, `pause`, `stop`), `reason`, `invalidated_by` |

`proceed` requires observed/derived evidence supporting ownership, a selected fix, a planned owner change, invariants and an impact classification. `pause` or `stop` may record an unresolved owner, empty alternatives and no planned changes. Source names and approval references are strings, not authenticated evidence; independently verify them.

```bash
python3 scripts/root_fix_guard.py audit record.json --json
python3 scripts/root_fix_guard.py audit record.json --json --base HEAD --repo /path/to/repo
```

The checker returns `0` if structurally complete, `2` for missing required fields, `1` for invalid input or Git inspection failure. JSON includes `record_status`, `decision_action`, `machine_check_only`, `diff_status`, `changed_files` and severity-tagged `findings`.

`UNPLANNED_CHANGE` identifies paths missing from `planned_changes`, including untracked files; `WIDE_CHANGE_SURFACE` prompts review above eight files. Both are `review` signals, not automatic blockers, because migration and consumer compatibility can legitimately expand a coherent fix. When `data_impact.mode` is destructive, an approval/recovery reference is structurally required and `MANUAL_AUTHORITY_CHECK` remains until the reviewer verifies it. No checker validates evidence truth, access permissions, or whether a production migration is safe.

Illustrative case: [`examples/email-checkout-record.json`](../examples/email-checkout-record.json). Its synthetic paths and sources are not observed facts about a real project.
