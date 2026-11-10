---
name: repo-memory-and-invariant-steward
description: Maintains the repository's architectural memory and enforces invariant preservation across sessions. Use when syncing historical decision records into a living compact Invariant Ledger, checking PRs/branches for architectural drift, verifying Gate 0 invariant constraints, or validating formal Reassessment Triggers — even if they don't explicitly say "invariant steward". Do NOT use for routine cosmetic edits or non-consequential scripts.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: Repo Memory & Invariant Steward (الذاكرة المعمارية للمنظومة)

> Invariants outlive sessions. Never allow architectural decisions to evaporate into git history.

## Why This Skill Is Needed & Target State

Autonomous AI agents generate exceptional decision records (`decision-record.json`, `paranoid-record.json`, `rollout-record.json`, etc.) in individual sessions. However, across sessions and multi-developer pull requests, repositories suffer from **Architectural Amnesia**:
1. Agents start new sessions with a blank slate, ignoring hard-won architectural invariants and re-introducing banned anti-patterns.
2. In-flight pull requests unknowingly violate past concurrency models, bypass zero-trust boundaries, break wire compatibility, or delete idempotency keys without opening an official **Reassessment Trigger**.
3. Historical decisions remain scattered across dozens of individual JSON files rather than being indexed as an actionable, living constraint set for Gate 0 ingestion.

The target state is **Persistent Architectural Memory**: all approved architectural invariants are compiled into a compact, living Invariant Ledger (`.anti-slop/invariant-ledger.json` and `.anti-slop/invariant-ledger.toon`) read automatically during Gate 0, and every incoming PR or diff is evaluated for architectural drift before code reaches production.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Starting a new feature, refactor, or bugfix in Gate 0 | Ingest active invariants from `.anti-slop/invariant-ledger.toon`; map blast radius against governed paths |
| Concluding an architectural decision or adding a new record | Run Invariant Ledger Sync to index new invariants, assertions, and revisit triggers |
| Reviewing or opening a Pull Request / branch diff | Run Drift Detection (`steward drift --base HEAD`); verify zero active invariants are violated or silently dropped |
| Legitimate evolution or retirement of a recorded invariant | File and validate a formal Reassessment Trigger (`reassessment-trigger.json`) before modifying protected contracts |
| Routine styling tweaks, local test fixtures, or docs typos | Do not activate; use standard Anti-Slop Engineering BUILD/FIX gates |

---

## The Five Absolute Laws

1. **The Invariant Permanence Axiom (Memory Survives Sessions):** An architectural invariant recorded in an approved decision record remains legally binding on the repository until explicitly superseded, waived, or deprecated through a verified Reassessment Trigger. Time, session boundary, or agent model change does not decay an invariant.
2. **Zero Silent Overrides (Reassessment Before Mutation):** Code modifications that conflict with an active recorded invariant are fatal defects. An agent cannot "silently clean up" or bypass an established architectural constraint because it seems inconvenient for the current task.
3. **Compact Ledger Ingestion at Gate 0:** Before writing or approving code, agents must consult the living Invariant Ledger to understand the non-negotiable boundaries of the touched subsystems.
4. **Bidirectional Cryptographic Provenance:** Every ledger entry must trace its lineage back to an authoritative record path and SHA-256 hash. Orphaning or forging invariants without backing evidence is strictly prohibited.
5. **Fail-Closed Drift Defense:** If an incoming change touches an invariant-governed path and alters required patterns, introduces forbidden patterns, or removes contracts, the drift gate must block (`exit code 2`) until a valid Reassessment Trigger is supplied.

---

## Invariant Rules

1. **Deterministic Ledger Sync:** Historical records (`*record*.json`) must be parsed, deduplicated, and indexed by unique Invariant IDs (e.g. `INV-PARANOID-001`, `INV-ROLLOUT-002`).
2. **Token-Thrifty TOON Generation:** Every ledger sync must emit both a canonical JSON artifact (`.anti-slop/invariant-ledger.json`) and an ultra-compact TOON representation (`.anti-slop/invariant-ledger.toon`) to minimize context consumption in Gate 0.
3. **Explicit Enforcement Scopes:** Every invariant must declare governed file paths (globs), required patterns (tokens that must not be deleted), and forbidden patterns (anti-patterns that must not be introduced).
4. **Mandatory Reassessment Delta:** A Reassessment Trigger cannot be a bare override; it must provide a structured `trade_off_delta` detailing what is gained, what operational risk is assumed, and what verification proof was gathered.
5. **No Ghost Waivers:** A temporary waiver must declare an explicit expiry date or issue milestone. Permanent waivers are invalid; they must be structured as formal superseding records.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Compile or update living invariant index | [Sync Ledger](usecases/sync.md) | [Ledger Contract](references/invariant-ledger-contract.md) |
| Scan PR or Git diff for architectural drift | [Drift Audit](usecases/drift-audit.md) | [Drift Engine](references/drift-detection-engine.md) |
| Evolve, waive, or retire an existing invariant | [Reassess Invariant](usecases/reassess.md) | [Reassessment Protocol](references/reassessment-protocol.md) |
| Gate 0 Agent context loading & blast radius check | [Gate 0 Integration](references/gate0-memory-integration.md) | `scripts/invariant_steward_guard.py` |

---

## Gate 0 Ingestion Protocol

When an AI agent initializes Gate 0 for any task:

1. **Read Compact Memory:** Ingest `.anti-slop/invariant-ledger.toon` (or run `npx anti-slop-engineering steward sync` if missing).
2. **Path Intersection Audit:** Check whether any file in the planned change intersects with `enforcement_scope.paths` of any active invariant.
3. **Constraint Binding:** Note all required patterns and forbidden patterns for the governed files into the task change contract (Gate 1).
4. **Reassessment Preflight:** If the user request directly demands changing a behavior protected by an active invariant, halt immediately and prompt for or draft an official Reassessment Trigger before touching code.

---

## PR Drift Detection & Violation Taxonomy

The Drift Detection engine classifies violations into three severity tiers:

```
                  Incoming PR / Git Diff
                            │
               ┌────────────┴────────────┐
               ▼                         ▼
     Touches Governed Path      Outside Governed Path
               │                         │
      ┌────────┴────────┐                ▼
      ▼                 ▼            Clean (Pass)
Forbidden Pattern   Required Pattern
  Introduced            Removed
      │                 │
      ▼                 ▼
  [BLOCKER]         [BLOCKER]
INV_FORBIDDEN_PAT  INV_PATTERN_REMOVED
      │                 │
      └────────┬────────┘
               ▼
   Is Reassessment Trigger Present & Valid?
         ├── YES ──► Waived / Superseded (Pass)
         └── NO  ──► Hard Gate Block (Exit Code 2)
```

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **Silent Invariant Dropping:** Removing a database index, timeout, or auth guard because "it simplified the test."
2. **Ghost Overrides:** Modifying a contract without citing or creating a `reassessment-trigger.json`.
3. **Split-Brain Ledgers:** Committing multiple conflicting ledger files instead of a unified single source of truth.
4. **Vague Invariants:** Registering broad slogans ("make it fast") without actionable assertions, paths, or patterns.
5. **Unverified Waivers:** Claiming an invariant is waived without providing empirical verification proof in the trigger record.

---

## Mandatory Pre-Execution Interrogation Matrix

Before approving a PR or concluding an architectural session:

- **Memory Check:** Did this session create new architectural rules? If yes, was `steward sync` executed to capture them?
- **Drift Check:** Did any modified line in this PR touch an invariant-governed file? Did `steward drift --base HEAD` return 0?
- **Pattern Check:** Were any required safety tokens (e.g. `Idempotency-Key`, `AbortSignal.timeout`, `timingSafeEqual`) deleted from governed modules?
- **Authority Check:** Does every active invariant trace back to a valid, committed decision record with a matching SHA-256?

---

## Required CLI Commands

```bash
# Sync all historical records into living Invariant Ledger & TOON
npx anti-slop-engineering steward sync
# or: python3 scripts/invariant_steward_guard.py sync --records skills docs .anti-slop

# Check working tree or branch diff for architectural drift
npx anti-slop-engineering steward drift --base HEAD
# or: python3 scripts/invariant_steward_guard.py drift --base HEAD

# Validate an Invariant Ledger structural integrity
npx anti-slop-engineering steward audit .anti-slop/invariant-ledger.json
# or: python3 scripts/invariant_steward_guard.py audit .anti-slop/invariant-ledger.json

# Validate an official Reassessment Trigger record
npx anti-slop-engineering steward reassess reassessment-trigger.json
# or: python3 scripts/invariant_steward_guard.py reassess reassessment-trigger.json
```

---

## Domain References

- **[Playbook Suite Overview](playbooks/README.md)**: Central operational index for architectural memory stewardship.
- **[The Invariant Steward Playbook](playbooks/steward-playbook.md)**: Syncing, Gate 0 memory indexing, and ledger lifecycle.
- **[Drift Triage & Remediation Playbook](playbooks/drift-triage-playbook.md)**: Handling drift alerts, investigating root causes, and resolving conflicts.
- **[Memory Anti-Patterns Catalog](playbooks/references/memory-anti-patterns.md)**: Forensic failure modes: architectural amnesia, phantom overrides, and split-brain states.
- **[Invariant Ledger Contract](references/invariant-ledger-contract.md)**: Schema specification for the living Invariant Ledger.
- **[Drift Detection Engine](references/drift-detection-engine.md)**: Diff parsing heuristics, AST matching, and fail-closed gates.
- **[Reassessment Protocol](references/reassessment-protocol.md)**: Legitimate evolution, superseding, and deprecation mechanics.
- **[Gate 0 Memory Integration](references/gate0-memory-integration.md)**: Agent instructions for zero-drift execution.

---

## Failure Taxonomy

| Failure Mode | Observable Signal | Remediation |
| --- | --- | --- |
| Architectural Amnesia | New PR re-implements banned pattern or drops auth boundary | Ingest ledger at Gate 0; reject PR via `steward drift` |
| Phantom Override | Invariant assertion deleted without reassessment record | File formal `reassessment-trigger.json` or revert deletion |
| Stale Ledger | Decision records committed without syncing to ledger | Execute `steward sync` in pre-commit hook or CI pipeline |
| Unanchored Invariant | Invariant record missing `authority.record_sha256` | Re-sync from authoritative source record |
| Context Explosion | Ledger exceeds token budget in agent prompt | Enforce compact `.anti-slop/invariant-ledger.toon` representation |

---

## Delegated Skills

- `anti-slop-engineering`: Follow Gate 0 discovery and baseline locking across all coding changes.
- `decision-guard`: Produce initial decision records with explicit trade-offs and revisit triggers.
- `paranoid-principal-architect`: Supply zero-trust and 10M scale invariants into the memory ledger.
- `safe-evolution-and-rollout-choreographer`: Supply wire-compatibility and dark launch invariants.
- `observability-and-slo-architect`: Supply telemetry cardinality and SLO budget invariants.

---

## Completion and Limits

The stewardship task is complete when all active decision records are synced into `.anti-slop/invariant-ledger.json` and `.anti-slop/invariant-ledger.toon`, the ledger passes structural audit with 0 findings, and `steward drift --base HEAD` confirms that no active invariants were broken or dropped without an approved Reassessment Trigger.
