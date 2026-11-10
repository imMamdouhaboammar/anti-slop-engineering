# Use Case: Verify Cryptographic Erasure

> Verification protocol proving $O(1)$ cryptographic erasure and GDPR compliance across immutable logs and distributed caches.

## Verification Protocol

1. **Provision Subject & Key:**
   Generate test user subject ID and assign an isolated DEK in KMS.

2. **Produce Encrypted Events:**
   Write encrypted test payloads into Kafka topics, database tables, and mock Parquet files.

3. **Verify Pre-Erasure Decryption:**
   Confirm that querying the payload with the active DEK yields the valid original plaintext.

4. **Execute Cryptographic Erasure:**
   Invoke KMS key shredding on the subject's DEK and zero local key caches.

5. **Attempt Post-Erasure Decryption (Falsification Gate):**
   Attempt to decrypt the historical Kafka message or Parquet row using the KMS.
   The operation **MUST FAIL** with a cryptographic key missing or invalid authentication tag error.

6. **Verify Deletion Receipt:**
   Confirm emission of a signed deletion receipt containing the destroyed key ID, subject hash, and timestamp.
