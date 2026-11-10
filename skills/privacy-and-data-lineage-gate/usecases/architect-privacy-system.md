# Use Case: Architect Privacy System

> End-to-end workflow for designing new services, databases, or event-driven pipelines compliant with Apple Privacy standards and Meta Data Infrastructure discipline.

## Workflow

1. **Classify Data Ingress:**
   - Catalog all incoming attributes into sensitivity tiers: `restricted_pii`, `confidential_telemetry`, `sensitive_financial`, `protected_health`, or `public_operational`.
   - Apply Data Minimization: can any raw identifier be eliminated or replaced with a boolean gate or coarse bucket?

2. **Define Purpose Bindings:**
   - Map every attribute to an authorized legal purpose: `AUTHENTICATION`, `BILLING`, `LEGAL_AUDIT`, `SECURITY_FRAUD_PREVENTION`, or `ANALYTICS_OPT_IN`.
   - Prohibit unmapped fields from persisting.

3. **Design Cryptographic Erasure Architecture:**
   - Assign Key-per-Subject envelope encryption for all immutable and distributed storage (Kafka, WAL, Lakehouse, S3).
   - Specify KMS provider (AWS KMS, GCP Cloud KMS, HashiCorp Vault, Apple Secure Enclave) and symmetric cipher (`AES-256-GCM` or `XChaCha20-Poly1305`).
   - Define sub-second key shredding flow and tombstone cache eviction.

4. **Establish Retention TTL Lifecycle:**
   - Define schema-level `retention_ttl_days` ($\le 90$ days default).
   - Specify automated background GC mechanism (partition dropping cron, DynamoDB TTL, or Redis EXPIRE).

5. **Generate Architectural Assessment Record:**
   - Capture design into a JSON assessment following [Privacy Record Contract](../references/privacy-record-contract.md).
   - Verify compliance with `npx anti-slop-engineering privacy audit <record.json> --json`.
