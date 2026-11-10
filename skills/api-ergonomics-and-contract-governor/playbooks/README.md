# API Ergonomics & Contract Governance Playbooks

> Orchestration suite for designing public SDKs, CLIs, and internal boundaries with Microsoft TypeScript compiler rigor and Stripe developer experience.

## Playbook Index

| Playbook | Core Domain | Key Disciplines |
| --- | --- | --- |
| [Microsoft TypeScript Playbook](microsoft-typescript-playbook.md) | TypeScript Compiler-Team Rigor | Nominal branded types, zero `any`, discriminated unions, hover readability, `.d.ts` emit cleanliness |
| [Stripe DX Playbook](stripe-dx-playbook.md) | World-Class API & SDK DX | Idempotency keys, cursor pagination, progressive disclosure, predictable naming, backwards compatibility |
| [API Booby-Trap Catalog](references/api-booby-traps.md) | Forensic Failure Modes | Boolean traps, option soup, stringly-typed IDs, unhandled error leaks, breaking change landmines |

---

## The Four Governance Pillars

1. **Pit of Success Defaults:** Safe timeouts (10s default), automated retries with full-jitter exponential backoff, TLS enforcement, and bounded pagination.
2. **Illegal States Unrepresentable:** Discriminated unions with tag discriminators, branded types (`Brand<T, B>`), and compile-time exhaustiveness checks.
3. **Progressive Disclosure:** 3-tier layering: 1-line facade $\to$ configured options bag $\to$ raw transport/streaming power engine.
4. **RFC 9457 Problem Details:** Machine-readable error contracts with deterministic codes, invalid parameter paths, actionable remediation hints, and retryability flags.
