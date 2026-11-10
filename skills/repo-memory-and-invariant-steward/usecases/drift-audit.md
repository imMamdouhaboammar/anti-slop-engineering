# Use Case: Drift Audit

> How to evaluate a Pull Request, branch, or working tree diff against active invariants.

## When to Run
- In GitHub Actions CI on every `pull_request` event.
- Before opening a PR or committing staged changes.
- During code review to ensure zero architectural degradation.

## Workflow

1. Run the drift command against base:
   ```bash
   npx anti-slop-engineering steward drift --base HEAD
   ```
2. Interpret the exit code:
   - `0`: Clean. No active invariants broken or dropped.
   - `2`: Architectural drift detected! Merge blocked.
3. If drift is reported:
   - Refer to [Drift Triage Playbook](../playbooks/drift-triage-playbook.md).
   - If an error: revert violating code or restore required safety tokens.
   - If intentional evolution: supply `--reassessment reassessment-trigger.json`.
