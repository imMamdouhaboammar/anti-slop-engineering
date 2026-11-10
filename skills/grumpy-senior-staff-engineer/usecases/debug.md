# Root-Cause Interrogation: Debugging & Incident Investigation

Use this workflow when investigating bugs, production failures, flaky tests, or performance regressions.

## Debugging Procedure

### Phase 0: Reproduce Without a Fix in Mind

Before forming a hypothesis, reproduce the failure signal:
1. Can you reproduce it from logs, without reading source code?
2. Can you trigger it in a local or staging environment?
3. Can you describe the failure in one sentence that does not include the word "maybe"?

If you cannot reproduce it, you are not debugging — you are guessing. Stop guessing.

### Phase 1: Trace Backward to the Violated Invariant

A bug is a symptom. Find the invariant. Ask five times:

1. **Why did this fail?** → "The balance went negative."
2. **Why could the balance go negative?** → "The balance check and update are not atomic."
3. **Why are they not atomic?** → "We read the balance and update it in two separate queries."
4. **Why are two separate queries acceptable?** → "They were written that way and no one questioned it."
5. **What is the invariant?** → "Balance must never go below zero; balance mutations must be atomic."

Stop at the invariant, not the symptom.

### Phase 2: Check the Siblings

After identifying the violated invariant, enumerate every other code path that:
- Performs the same read-modify-write pattern
- Skips the same validation
- Swallows the same exception type
- Has the same missing timeout

These are the next incidents already scheduled. Fix all of them, not just the one that fired.

### Phase 3: Write the Failing Test First

Before writing the fix:
1. Write a test that reproduces the exact failure.
2. Run it. It must fail (red).
3. Write the minimal fix.
4. Run the test. It must pass (green).
5. Prove the fix is permanent: remove it, run the test, verify it fails again.

A fix without a red-green-refactor cycle is a guess with extra steps.

### Phase 4: Systemic Fix

Fix the invariant at the source:
1. Apply the fix to all sibling paths identified in Phase 2.
2. Add or improve the log line that makes this failure class visible at 3AM.
3. File the [3AM Post-Mortem](../playbooks/3am-postmortem-playbook.md) with the root cause record.

## Debug Output Format

```markdown
### Debug Report: <Bug Title>

**Reproduction:**
<One sentence: how to trigger the failure without reading source code.>

**Root Cause (Violated Invariant):**
<The invariant that was assumed but not enforced. Not the last change.>

**Sibling Paths (Scheduled Future Incidents):**
- `src/billing.ts:88` — same TOCTOU pattern on credit deduction
- `src/subscriptions.ts:45` — same missing timeout on Stripe call

**Fix Applied:**
<PR link or inline patch.>

**Failing Test Added:**
<Test name and file path. Confirmed red before fix, green after fix.>

**Log Line Added:**
<The exact structured log line that makes this failure class visible at 3AM.>

**Verdict:**
`RESOLVED` | `MITIGATED_PENDING_SYSTEMIC_FIX`
```
