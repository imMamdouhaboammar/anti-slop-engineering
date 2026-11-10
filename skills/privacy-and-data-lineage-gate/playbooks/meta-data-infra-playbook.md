# Meta Data Infrastructure Playbook

> Scaled data infrastructure practices: automated taint analysis, cryptographic erasure across petabyte event streams, purpose-based query admission, and partition lifecycle management.

## 1. Automated Taint Tracking Across Microservices

In large-scale microservice architectures, data is continuously passed over gRPC, thrift, and event streams.

1. **Ingress Taint Tagging:**
   When an incoming HTTP or RPC payload enters the edge gateway, fields categorized as personal data (email, phone, ip, address) are tagged with a taint attribute (`Tainted[RestrictedPII]`).
2. **Propagation Invariant:**
   Any function, variable, or derived string that combines or transforms a tainted input automatically inherits the taint attribute.
3. **Sink Interception:**
   Logging libraries, RPC clients calling external services, and analytics emitters query the taint status of their arguments. If an argument carries `Tainted[RestrictedPII]`, the sink drops the field or throws a compile/runtime exception.

---

## 2. Key-per-Subject Crypto-Shredding KMS Lifecycle

Operating cryptographic erasure at scale across immutable Kafka topics, Scribe logs, RocksDB state stores, and Apache Iceberg tables:

```text
[User Account Creation]
         │
         ▼
[1. KMS Generate DEK] ──► Encrypt with KEK ──► Store Wrapped DEK in KMS Key Vault
                                                   │
                                                   ▼
                                       Cache DEK in Key-Cache (TTL: 1h)
                                                   │
                                                   ▼
                                       Encrypt all incoming user PII payloads
```

```text
[User Account Deletion Request]
         │
         ▼
[1. Purge Key-Cache] ──► Zero local memory in all worker nodes (< 250ms)
         │
         ▼
[2. KMS Destroy DEK] ──► Irrevocably delete wrapped key material from KMS Vault
         │
         ▼
[3. Emit Deletion Receipt] ──► Immutable cryptographic receipt (GDPR Article 17 Proof)
         │
         ▼
All historical ciphertext in Kafka logs, WAL files, Parquet lakehouse, and S3 cold storage is permanently undecryptable.
```

---

## 3. Purpose-Based Access Control (PBAC) Admission Gates

All internal SQL queries, Presto/Trino jobs, and Spark ETL pipelines must present a declared `QueryPurpose` token:

```sql
-- Valid Query: Authorized purpose matches table purpose binding
SET session query_purpose = 'BILLING_SETTLEMENT';
SELECT user_id, amount_cents FROM invoices WHERE invoice_date >= CURRENT_DATE - INTERVAL 30 DAY;

-- Rejected Query: Analytics job attempting to read restricted authentication credentials
SET session query_purpose = 'PRODUCT_ANALYTICS';
SELECT user_id, password_hash, email FROM user_credentials;
-- Fails with: PBAC_POLICY_VIOLATION: Purpose 'PRODUCT_ANALYTICS' is not authorized to read 'user_credentials'
```

---

## 4. Lakehouse Partition Retention & Automated Garbage Collection

For high-throughput analytical databases (ClickHouse, Snowflake, BigQuery, Apache Iceberg):

1. **Time-Based Partitioning:** Partition tables by day or month (`PARTITION BY toYYYYMM(recorded_at)`).
2. **Automated Partition Dropping:** Scheduled cron tasks execute atomic drop commands on expired partitions:
   ```sql
   ALTER TABLE telemetry_events DROP PARTITION '202511';
   ```
   This eliminates row-by-row `DELETE` scans and avoids vacuum compaction overhead.
3. **Cold Storage Lifecycle Policies:** S3/GCS bucket lifecycle rules automatically transition logs older than 30 days to non-recoverable purge.
