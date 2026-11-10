# Use Case: Audit Data Lineage

> Auditing system data flows from ingress endpoints to downstream event streams, ETL jobs, and telemetry sinks.

## Audit Steps

1. **Trace Data Sources:**
   Identify all entry points accepting user attributes (REST APIs, GraphQL mutations, Webhook receivers, Mobile SDK payloads).

2. **Verify Transformation Gates:**
   Ensure incoming attributes are sanitized, normalized, and wrapped into `Redacted<T>` types immediately at the ingress boundary.

3. **Inspect Persistence & Replication Paths:**
   Trace where data flows: primary DB, read replicas, search indexes (Elasticsearch), Redis caches, Kafka topics, and backup stores.
   Confirm that all stores either use crypto-shredded encryption or receive tombstone invalidation on user deletion.

4. **Fence Egress Sinks:**
   Verify that all third-party analytics (Mixpanel, Google Analytics, Amplitude) route through the first-party Telemetry Egress Gateway with strict schema allowlists and differential privacy noise injection.
