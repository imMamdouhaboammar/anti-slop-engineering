# Data Lineage & Flow Policy Graphs

> The Meta Data Infrastructure Standard: Comprehensive provenance tracking, flow-policy enforcement, and telemetry egress fencing from ingestion to cold archive.

## The Data Swarm Lineage Architecture

In a distributed microservice and data lakehouse environment, data does not remain static; it replicates across queues, event buses, ETL pipelines, training feature stores, and third-party SaaS integrations.

Without an automated **Data Lineage Directed Acyclic Graph (DAG)**, organizations cannot:
1. Prove where customer data resides when responding to regulatory audits.
2. Ensure that deleting a record in the primary database cascades to all downstream caches, search indexes, and warehouses.
3. Prevent sensitive identifiers from flowing into unauthorized third-party telemetry sinks.

---

## Lineage DAG Structure

Every personal data flow must be mapped and enforced across five canonical lifecycle phases:

```text
[Ingestion Source] ──────► [In-Memory Entity] ──────► [Processing / Transformation]
 (HTTP / Webhook / App)      (Redacted<PII> Types)      (Deterministic Sanitization)
                                                                 │
                                                                 ▼
[Egress Sink: Forbidden] ◄── [Flow Policy Gate] ────► [Persistence Layer]
 (Logger, Analytics, LLM)    (Allowlist Validation)     (Crypto-Shredded Storage)
```

### Node Attributes in Lineage Registry

```json
{
  "node_id": "service.identity.user_registered",
  "data_classification": "restricted_pii",
  "fields": ["email", "phone_number", "ip_address"],
  "upstream_sources": ["api.gateway.signup_route"],
  "downstream_sinks": [
    "db.postgres.users_table",
    "kafka.topic.user_lifecycle_events",
    "telemetry.egress_gateway"
  ],
  "transformation_rules": [
    "email -> wrap_in_redacted_type",
    "ip_address -> truncate_to_slash_24"
  ]
}
```

---

## Flow Policy Matrix & Forbidden Sinks

The Flow Policy Gate intercepts data transfers and rejects unauthorized routes at compile time or via network proxies:

| Target Sink | Status | Permitted Payload | Prohibited Payload |
| --- | --- | --- | --- |
| **Console / Log Sinks** (CloudWatch, Datadog, Sentry) | **FENCED** | Correlation IDs, error codes, generic status messages | Any plaintext or reversibly hashed PII (`email`, `phone`, `full_name`, `ssn`) |
| **Third-Party Analytics** (Mixpanel, Amplitude, Segment) | **FENCED** | Ephemeral session IDs, coarse actions (`button_clicked`), DP-aggregated metrics | Direct identifiers (`user_email`, `phone`, `device_udid`, `untruncated_ip`) |
| **LLM Prompts & Vector Stores** | **FENCED** | Scrubbed context, synthetic tokens, zero-knowledge extracted facts | Raw personal conversations, customer identification documents, unredacted names |
| **HTTP Referrer & URL Query Params** | **FORBIDDEN** | Clean route paths (`/account/settings`) | PII in query strings (`?email=user@example.com&token=...`) |
| **Internal Event Streams** (Kafka, Redpanda) | **RESTRICTED** | Ciphertext encrypted with subject-specific DEK | Plaintext PII payloads in unencrypted topics |

---

## Telemetry Egress Gateway Invariant

All telemetry leaving the service mesh must traverse a **Telemetry Egress Gateway**:
1. Payloads are validated against a strict schema allowlist.
2. Any field marked as `restricted_pii` that is not masked or differential-privacy noised immediately aborts the egress call with an alert.
3. Client-side SDKs are prohibited from establishing direct outbound connections to third-party tracking domains; all analytics traffic must terminate at the first-party egress gateway.
