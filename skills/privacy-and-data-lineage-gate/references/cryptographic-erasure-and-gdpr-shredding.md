# Cryptographic Erasure & GDPR Crypto-Shredding

> Solving the distributed systems contradiction: Enforcing GDPR Article 17 Right-to-be-Forgotten across immutable Kafka event streams, Parquet lakehouses, and cold storage backups in $O(1)$ time.

## The Distributed Systems Contradiction

Modern cloud architectures depend on append-only, immutable storage:
- **Streaming Event Brokers:** Kafka, Redpanda, Apache Pulsar.
- **Analytics Lakehouses:** Apache Iceberg, Delta Lake, Apache Hudi, columnar Parquet files.
- **Database Durability:** Write-Ahead Logs (WAL), CDC streams (Debezium).
- **Disaster Recovery:** Daily point-in-time snapshots, S3 Glacier immutable vault backups.

Under GDPR Article 17 and CCPA, users have a non-negotiable legal right to have their personal data permanently erased upon request.

Attempting physical deletion by rewriting Kafka partitions, recompacting terabytes of immutable Parquet files, or mutating cold backup archives per user request causes catastrophic I/O amplification, compaction storms, and high risk of distributed state corruption.

---

## The Solution: Key-per-Subject Crypto-Shredding

Instead of mutating immutable storage blocks, the architecture enforces **Envelope Encryption with Key-per-Subject Cryptographic Erasure (Crypto-Shredding)**:

1. **Key Hierarchy:**
   - **Key Encryption Key (KEK):** Managed inside hardware security modules (HSM) / Cloud KMS (AWS KMS, GCP Cloud KMS, Apple Secure Enclave).
   - **Data Encryption Key (DEK):** Unique 256-bit symmetric key (`AES-256-GCM` or `XChaCha20-Poly1305`) generated for each distinct user/subject ID.
2. **Persistence Boundary:**
   - All PII fields (email, phone, address, IP, device identifiers) are encrypted using the subject's specific DEK before persisting to database rows, Kafka message payloads, or Iceberg tables.
   - Non-sensitive operational metadata (e.g. `order_amount_cents`, `timestamp_ms`, `currency_code`) remains unencrypted for efficient indexing, partitioning, and aggregation.
3. **Execution of Erasure ($O(1)$ Complexity):**
   - When a deletion event is triggered, the system invokes KMS key destruction on the subject's DEK.
   - All memory and local cache entries holding the DEK are overwritten with zeroes and purged.
   - All historical ciphertext stored in Kafka log segments, database WALs, Parquet files, and backup snapshots instantly becomes undecryptable cryptographic noise indistinguishable from random bytes.
   - Physical deletion across thousands of machines is accomplished with a single sub-second KMS key deletion.

---

## Architectural Workflow Diagram

```text
[User Deletion Request]
         │
         ▼
[GDPR Deletion Choreographer] ────► [1. KMS Subject DEK Shred] (DEK Deleted from HSM)
         │                                      │
         ├──────────────────────────────────────┼──► All Historical Kafka/Parquet Ciphertext
         │                                      │    is now permanently undecryptable ($O(1)$)
         ▼                                      ▼
[2. Cache Eviction]                [3. Audit Receipt Generator]
Purge active Redis/Memcached       Issues cryptographic proof of
plaintext keys and indices         key shredding (HMAC/ZK token)
```

---

## Technical Invariants

| Invariant | Requirement | Violation Severity |
| --- | --- | --- |
| **Key Granularity** | 1:1 binding between Subject UUID and DEK. Shared tenant keys for PII are banned. | **BLOCK** |
| **Cipher Suite** | Authenticated encryption only: `AES-256-GCM` (96-bit IV) or `XChaCha20-Poly1305`. ECB or unauthenticated CBC are strictly prohibited. | **BLOCK** |
| **IV/Nonce Uniqueness** | Cryptographically secure random nonce generated per encryption operation. Nonce reuse is an instant failure. | **BLOCK** |
| **Revocation Latency** | Key destruction must propagate globally within $\le 5,000\text{ ms}$ (target: $< 250\text{ ms}$). | **BLOCK** |
| **Soft-Delete Prohibition** | Setting `is_deleted = true` or `deleted_at = NOW()` without crypto-shredding or storage purging is illegal under GDPR. | **BLOCK** |
| **Verification Receipt** | Every deletion execution must emit an immutable deletion receipt record containing the shredded key ID, subject ID hash, timestamp, and signature. | **BLOCK** |
