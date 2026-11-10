# Repo Memory & Invariant Steward Playbook Suite

> Operational procedures for preserving architectural memory, syncing the living Invariant Ledger, and enforcing zero-drift pull request defense.

## Playbook Index

- **[The Invariant Steward Playbook](steward-playbook.md)**: End-to-end operational guide for compiling decision records, synchronizing the living ledger, maintaining TOON representations, and Gate 0 agent integration.
- **[Drift Triage & Remediation Playbook](drift-triage-playbook.md)**: Step-by-step investigation guide when `steward drift` flags an architectural violation, differentiating legitimate evolution from accidental regressions.
- **[Memory Anti-Patterns Catalog](references/memory-anti-patterns.md)**: Forensic reference guide detailing architectural amnesia, phantom overrides, split-brain ledgers, and ungrounded waivers.

## Core Operational Workflow

```
[Historical Decisions] ──► (steward sync) ──► [.anti-slop/invariant-ledger.json & .toon]
                                                              │
                                                              ▼
                                                   [Gate 0: Agent Reads Memory]
                                                              │
                                                              ▼
                                                    [Gate 1-3: Code Changes]
                                                              │
                                                              ▼
[Incoming PR / Diff]    ──► (steward drift) ──► [Zero Drift Check (Pass/Block)]
                                                              │
                                                      [If Evolving Invariant]
                                                              │
                                                              ▼
                                                   (steward reassess trigger.json)
```
