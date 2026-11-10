# Architectural Memory Anti-Patterns Catalog

> Forensic breakdown of common failure modes where repositories forget past engineering decisions and suffer from silent degradation.

## 1. Architectural Amnesia (النسيان المعماري)
- **Mechanism:** An agent in a fresh session starts modifying a service without checking historical decision records. It naively chooses a happy-path implementation (e.g. naive `UPDATE counter = counter + 1`), obliterating past concurrency or zero-trust hardening.
- **Diagnostic Signal:** PR introduces patterns previously cataloged as critical defects in `paranoid-record.json` or `decision-record.json`.
- **Hardened Remedy:** Mandatory Gate 0 reading of `.anti-slop/invariant-ledger.toon` and fail-closed CI drift gates (`steward drift`).

## 2. The Phantom Override (التجاوز الشبحي)
- **Mechanism:** A developer or agent deletes a critical guard (e.g. auth check, idempotency verification, or timeout) with a comment like `// TODO: re-enable later` or simply removes it to get a local test passing.
- **Diagnostic Signal:** Line deletions in PR diff matching required invariant patterns without an accompanying `reassessment-trigger.json`.
- **Hardened Remedy:** Automatic detection of pattern deletion (`INVARIANT_PATTERN_REMOVED`) exiting with code 2.

## 3. Split-Brain Ledgers (انفصام سجل الـ Invariants)
- **Mechanism:** Multiple teams or agents create uncoordinated decision files with conflicting rules (e.g. one mandates Redis idempotency, another mandates database unique keys, with neither superseding the other).
- **Diagnostic Signal:** Conflicting invariant assertions or duplicate invariant IDs detected during `steward sync`.
- **Hardened Remedy:** `steward audit` strictly enforces unique invariant IDs, and `steward sync` deduplicates and requires explicit `superseded_by` relationships.

## 4. Ungrounded Waivers (استثناءات بلا إثبات)
- **Mechanism:** Bypassing an invariant by declaring "it was waived" in a commit message or PR description without verifiable verification proof.
- **Diagnostic Signal:** Lack of structured `verification_proof` or `trade_off_delta` in reassessment records.
- **Hardened Remedy:** Schema validation of `reassessment-trigger.json` rejecting empty trade-offs or missing empirical proofs.
