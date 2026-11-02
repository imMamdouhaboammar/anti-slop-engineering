# Review the change surface

1. **Compare planned with observed paths.** Capture `git diff --name-status <base>` and untracked changes. Inspect the real hunks, not only filenames or a score.
2. **Classify each path.** Owner, dependent consumer, migration, test, integration. Demand a causal explanation for an unexpected category. Multiple files may be required by a correct schema or API change.
3. **Search for symptom fan-out.** Look for repeated filters, checks, transformations or null-handling across controllers, handlers and views. Ask whether a single owner can enforce the same contract. Avoid centralization where semantics actually differ.
4. **Challenge root-only shortcuts.** Check whether moving code upstream could break identity, transaction ordering, authorization or context-specific behavior. A root fix that silently violates consumers is not a root fix.
5. **Check test oracles.** Tests should fail under the original bug or a realistic mutation, protect the owner invariant, and exercise affected consumers. Don't weaken old assertions to make refactors pass.
6. **Check data/authority.** A nullable field, a data deletion, and a production migration are separate decisions. Inspect recovery and explicit approval for irreversible actions; the JSON audit cannot grant authority.
7. **Revise or complete.** If the owner remains wrong, reopen investigation. If the wider diff is justified, record why and finish. If evidence is missing, say `NOT VERIFIED` and pause risky execution.

## Optional deterministic guard

From a repository containing `scripts/root_fix_guard.py`:

```bash
python3 scripts/root_fix_guard.py audit path/to/record.json --json --base HEAD --repo .
```

The audit compares `planned_changes[].path` to changed tracked and untracked paths. `UNPLANNED_CHANGE` and `WIDE_CHANGE_SURFACE` are **review** findings, never proof of bad architecture. An unavailable Git ref is an input error, not a clean diff. Inspect the actual hunks and source evidence before assigning an engineering verdict.
