---
name: privacy-and-data-lineage-gate
description: Enforces Apple Privacy and Meta Data Infrastructure engineering discipline to protect user data from the system itself. Use when designing user data pipelines, processing PII/sensitive customer data, defining database schemas storing personal information, implementing GDPR/CCPA deletion lifecycles, or instrumenting analytics and telemetry sinks — even if they don't explicitly say "privacy gate". Do NOT use for external network DDoS mitigation, routine UI cosmetic styling, or non-user operational infrastructure.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Skill: The Privacy & Data Lineage Gate (Apple Privacy & Meta Data Infra)

> While external security shields the system from outside adversaries, this gate protects user data from the system itself: zero internal leaks, cryptographic erasure across immutable ledgers, mandatory retention TTLs, and provenance flow control.

## Why This Skill Is Needed & Target State

Modern security teams focus on external attackers: firewalls, rate limiters, token-bucket WAFs, and injection guards. Yet over 90% of privacy violations and regulatory fines stem from **internal systemic design defects**:
1. Accidental PII logging when developers pass full `user` objects or unhandled `req.body` to logging transports (Datadog, CloudWatch, Sentry).
2. Telemetry leakage where third-party analytics SDKs (Mixpanel, Google Analytics, Facebook Pixel) receive raw emails, phone numbers, or hardware IDs.
3. The "Soft-Delete Fallacy" where systems set `is_deleted = true`, leaving user personal data permanently exposed across immutable Kafka partitions, database WALs, Parquet lakehouses, and disaster recovery backups.
4. Indefinite data retention where tables accumulate high-precision GPS coordinates, raw IPs, and browsing activity for years without an automated retention TTL or business purpose justification.

The target state is **Apple Privacy & Meta Data Infrastructure Rigor**: all personal identifiers are encapsulated in compiler-enforced tainted types (`Redacted<T>`), account deletion guarantees instantaneous $O(1)$ cryptographic erasure (crypto-shredding via KMS key-per-subject), every schema mandates an automated retention TTL with explicit purpose binding, and all data flows are mapped within an audited lineage DAG with strictly fenced telemetry egress.

---

## Activation and Boundaries

| Situation | Behavior |
| --- | --- |
| Designing user data storage, database schemas, or caching layers | Enforce purpose binding, data minimization, and mandatory `retention_ttl_days` with automated GC |
| Building event-driven architectures, Kafka pipelines, or lakehouse tables | Enforce Key-per-Subject Cryptographic Erasure (Crypto-Shredding) for $O(1)$ GDPR Article 17 erasure |
| Authoring or refactoring code handling PII (emails, phones, IPs, addresses) | Wrap sensitive fields in `Redacted<T>` branded types; ban unredacted `toString()`, `toJSON()`, and log calls |
| Instrumenting analytics, telemetry, crash reporting, or external third-party SDKs | Route all telemetry through a first-party Egress Gateway with differential privacy and strict allowlists |
| Reviewing PRs that add user data fields or modify deletion lifecycles | Audit data lineage DAG and reject naive soft-delete patterns or unbounded retention tables |
| External network DDoS mitigation, token buckets, or firewall configurations | Do not activate; delegate to `paranoid-principal-architect` and `security-review` |
| Routine styling tweaks, documentation formatting, or local non-user scripts | Do not activate; use Anti-Slop Engineering BUILD/FIX gates |

---

## The Four Absolute Laws

1. **The Internal Threat Axiom (System as Adversary):** Code is treated as an active threat to user data. Never rely on developer vigilance, code review vigilance, or central regex log scrubbers. Personal data must be physically impossible to print, serialize, or transmit without an audited unwrap operation.
2. **The Crypto-Shredding Invariant ($O(1)$ Erasure over Immutable Stores):** In distributed append-only architectures (Kafka, Redpanda, Iceberg, WALs, S3 snapshots), physical row deletion is an architectural anti-pattern. Every user must have an isolated Data Encryption Key (DEK). User erasure is executed by destroying the DEK from the KMS, instantly rendering all distributed ciphertext unrecoverable in $O(1)$ time.
3. **The Data Minimization & Retention Mandate:** If an operation does not require personal data, it must not be collected. If an operation requires age verification, collect boolean `is_over_21`, never date of birth. Any table, cache, or message queue storing user data without an explicit purpose binding and automated retention TTL is rejected at the CI gate.
4. **The Provenance & Fenced Egress Law:** Every byte of personal data must be traceable across a Directed Acyclic Graph (DAG) from ingestion to cold storage. Direct outbound connections from clients or microservices to third-party analytics are strictly prohibited; all telemetry traverses an egress gateway that strips PII and applies local differential privacy ($\epsilon \le 1.0$).

---

## Invariant Rules

1. **Tainted PII Types everywhere.** Wrap emails, phone numbers, IP addresses, physical locations, and national IDs in nominal branded types and `Redacted<T>` containers.
2. **Ban unredacted serialization.** Override `toString()`, `toJSON()`, and runtime inspection hooks (`[util.inspect.custom]`) to output `[REDACTED]` by default.
3. **Audited unwrapping only.** The underlying sensitive value can only be accessed via an explicit `.reveal(auditContext)` method requiring an actor ID, correlation ID, and authorized business reason.
4. **Crypto-shredding for immutable ledgers.** Store user data in event streams and lakehouses encrypted with a user-specific DEK (`AES-256-GCM` or `XChaCha20-Poly1305`). User deletion shreds the key in KMS within $\le 5,000\text{ ms}$.
5. **No naive soft-deletes.** Setting `is_deleted = true` without cryptographic shredding or physical storage purging is a blocker defect under GDPR Article 17.
6. **Mandatory retention TTL.** Every database table, collection, and cache key storing user data must declare `retention_ttl_days` ($\le 90$ days default, $\le 730$ days maximum) backed by an automated partition drop cron or TTL index.
7. **Explicit purpose binding.** Every schema and pipeline must declare its business purpose (`AUTHENTICATION`, `BILLING`, `LEGAL_AUDIT`, `SECURITY_FRAUD_PREVENTION`, `ANALYTICS_OPT_IN`). Cross-purpose joins are rejected at the query admission gate.
8. **Differential privacy on telemetry.** Numeric metrics derived from user behavior must inject Laplace/Gaussian perturbation noise with privacy budget $\epsilon \le 1.0$.
9. **Coarse attribute truncation.** Truncate IPv4 to `/24`, IPv6 to `/48`, and GPS coordinates to coarse geohash ($\ge 20\text{ km}$ precision) before persistence or analytics logging.
10. **Zero PII in URL query strings.** Never place user emails, names, or tokens in query parameters where they leak into access logs, browser history, and `Referer` headers.

---

## Execution Router

| Task Shape | Primary Workflow | Reference Contract |
| --- | --- | --- |
| Designing a new user data pipeline, database schema, or lakehouse | [Architect Privacy System](usecases/architect-privacy-system.md) | [Data Minimization & TTL](references/data-minimization-and-retention-ttl.md) |
| Implementing domain entities, DTOs, or models handling sensitive PII | [Implement Tainted Types](usecases/implement-tainted-types.md) | [Tainted PII Types](references/tainted-pii-types-and-compiler-enforcement.md) |
| Implementing GDPR Right-to-be-Forgotten or account deletion lifecycles | [Verify Cryptographic Erasure](usecases/verify-cryptographic-erasure.md) | [Cryptographic Erasure](references/cryptographic-erasure-and-gdpr-shredding.md) |
| Auditing data flows, event topics, or third-party telemetry integrations | [Audit Data Lineage](usecases/audit-data-lineage.md) | [Lineage & Flow Graphs](references/data-lineage-and-flow-policy-graphs.md) |
| Auditing an architectural compliance record | [Record Contract](references/privacy-record-contract.md) | `scripts/privacy_guard.py` |

---

## Mandatory Pre-Execution Privacy Matrix

Before creating or approving code handling customer data, subject the design to this matrix:

- **Distrust of System Logging:** If an unhandled exception fires on this route, will `logger.error` or APM agents dump raw request payloads or personal attributes into Datadog, Sentry, or CloudWatch?
- **Distrust of Immutable Storage:** If this user requests account deletion tomorrow, how do we erase this record from Kafka topic partitions, database WAL logs, Parquet files, and S3 glacier backups without rewriting petabytes of storage?
- **Distrust of Retention:** Why does this table need to keep this data indefinitely? What automated cron or TTL mechanism purges records once their business purpose expires?
- **Distrust of Third-Party Sinks:** Are third-party analytics libraries (Mixpanel, Google, AppsFlyer) receiving raw emails, device UDIDs, or unmasked IPs? Is telemetry routed through an authorized egress gateway?
- **Distrust of Granularity:** Did we collect an exact birthdate when a boolean `is_over_21` suffices? Did we store 6-decimal GPS coordinates when a city or coarse geohash is enough?

---

## Prohibited Anti-Patterns (Instant Rejection List)

1. **The Soft-Delete Fallacy:** Marking database rows with `is_deleted = true` or `deleted_at = NOW()` and claiming GDPR erasure compliance while PII remains plaintext in backups and data lakes.
2. **Logging `req.body` or Unredacted Error Objects:** Passing full request payloads or entities containing personal information directly into `console.log` or logging libraries.
3. **The SHA-256 Telemetry Hash Illusion:** Passing SHA-256 hashed emails to third-party ad or tracking networks without per-user secret salting (easily inverted via rainbow tables).
4. **Indefinite Table Retention:** Creating database schemas or cache stores holding user identifiers without an explicit `retention_ttl_days` and automated GC pipeline.
5. **URL Query Parameter PII:** Transmitting user emails, telephone numbers, or authentication tokens inside URL query strings (`?email=...`).
6. **Centralized Regex Scrubber Reliance:** Depending solely on centralized regex scrubbing at the log forwarder (Fluentd/Logstash) rather than enforcing type-level redaction at the domain boundary.

---

## Required Output & Review Workflow

Structure all architectural designs, code reviews, and implementations through this 3-phase discipline:

1. **Privacy & Lineage Pre-Mortem:** Bullet out the top 3 internal leak vectors, unencrypted immutable stores, and unneeded data attributes.
2. **Hardened Privacy Implementation:** Emit production-grade code with tainted types, `Redacted<T>` wrappers, purpose bindings, automated TTLs, and crypto-shredding interfaces.
3. **Adversarial Erasure & Leak Verification:** Provide tests verifying that logging prints `[REDACTED]`, telemetry egress strips PII, and KMS key destruction renders historical ciphertext permanently undecryptable.

When a durable architectural record is warranted, save a JSON assessment following the [Privacy Record Contract](references/privacy-record-contract.md) and audit it with:

```bash
npx anti-slop-engineering privacy audit <record.json> --json
# Or scan source code directly for privacy hazards:
npx anti-slop-engineering privacy audit <record.json> --source <source_file> --json
```
