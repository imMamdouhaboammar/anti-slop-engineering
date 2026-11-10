# Privacy Booby Traps: The Top 10 Silent Leaks

> Subtle architectural flaws and anti-patterns that silently compromise user privacy, violate GDPR/CCPA regulations, and leak sensitive identifiers.

---

## 1. The Soft-Delete Fallacy
- **The Anti-Pattern:** Marking rows with `is_deleted = true` or `deleted_at = NOW()` in database tables and reporting to regulators that user data has been "erased".
- **The Reality:** Data remains in plaintext, indexed in memory, replicated to read replicas, included in daily database snapshots, and ingested into analytics data lakes.
- **The Fix:** Physical cryptographic erasure via key-per-subject crypto-shredding, accompanied by active cache eviction and storage-level tombstone purging.

---

## 2. Catch-Block Logging: `logger.error(err, req.body)`
- **The Anti-Pattern:** Writing defensive try/catch blocks that dump the full request payload or error object into the logger:
  ```typescript
  catch (err) {
    logger.error("Signup failed", { err, payload: req.body });
  }
  ```
- **The Reality:** Transmits plaintext passwords, credit card CVVs, emails, and social security numbers directly into Datadog, CloudWatch, or Sentry log lakes.
- **The Fix:** Tainted PII types (`Redacted<T>`) whose `toString()` and `toJSON()` render `[REDACTED]`. Never log raw request bodies.

---

## 3. The SHA-256 Telemetry Hash Illusion
- **The Anti-Pattern:** Hashing customer email addresses with standard SHA-256 and passing them to third-party ad networks (Facebook Conversions API, Google Ads Enhanced Conversions) believing it is "anonymized".
- **The Reality:** The space of valid email addresses is easily brute-forced via precomputed rainbow tables in minutes. SHA-256 without per-user secret salt is pseudonymous linkable PII, not anonymous data.
- **The Fix:** Use ephemeral rotating tokens, Apple Private Click Measurement, or local differential privacy.

---

## 4. Indefinite Table Retention (The "Save Everything Just in Case" Mentality)
- **The Anti-Pattern:** Creating tables or logging collections that store IP addresses, geolocation coordinates, or user session events without a defined TTL or retention policy.
- **The Reality:** Breaches expose years of historical user habits, locations, and network endpoints, incurring severe GDPR Article 5(1)(e) storage limitation penalties.
- **The Fix:** Enforce mandatory schema-level `retention_ttl_days` and automated partition dropping pipelines.

---

## 5. URL Query Parameter Leakage
- **The Anti-Pattern:** Placing user identifiers or magic links in URL query strings:
  ```http
  GET /reset-password?email=customer@example.com&token=secret123
  ```
- **The Reality:** Query parameters are permanently stored in browser histories, proxy access logs, CDN access logs, and transmitted in `Referer` headers to external resources.
- **The Fix:** Pass all sensitive parameters via HTTP request body or encrypted headers.

---

## 6. The Global Regex Scrubber Anti-Pattern
- **The Anti-Pattern:** Assuming that a centralized regex scrubber in the log collector (e.g. FluentBit, Logstash) will catch all PII before writing to disk.
- **The Reality:** Regex filters miss obfuscated keys, nested JSON strings, typos (`emial`, `user_addr`), and catastrophic backtracking freezes log pipelines.
- **The Fix:** Enforce type-level redaction at the application boundary where domain semantic meaning is known.

---

## 7. Database Backup Persistence
- **The Anti-Pattern:** Deleting a user from the production database while daily disk snapshots or pg_dump archives retain the unencrypted user data for 365 days.
- **The Reality:** Restoring a database from backup during disaster recovery silently resurrects deleted users, violating GDPR Right-to-be-Forgotten.
- **The Fix:** Cryptographic erasure ensures restored backup ciphertext cannot be decrypted once the KMS DEK is destroyed.

---

## 8. Shared DEK Tenant Collision
- **The Anti-Pattern:** Encrypting an entire multi-tenant database or Kafka topic with a single shared tenant key.
- **The Reality:** Deleting a single user requires either re-encrypting the entire tenant dataset (causing massive I/O storms) or failing to execute cryptographic erasure.
- **The Fix:** Maintain a 1:1 binding between Subject UUID and Data Encryption Key (DEK).

---

## 9. Cross-Purpose Data Joining (Purpose Creep)
- **The Anti-Pattern:** Joining security fraud logs (collected without consent under legitimate interest) with marketing personalization pipelines to increase ad conversions.
- **The Reality:** Gross violation of GDPR Purpose Limitation and Apple Privacy policies resulting in regulatory sanctions.
- **The Fix:** Purpose-Based Access Control (PBAC) admission gates that reject cross-purpose joins at the query parser.

---

## 10. Unredacted Exception & DTO Serialization
- **The Anti-Pattern:** Returning full entity or user domain objects from API route handlers:
  ```typescript
  const user = await db.users.findUnique({ where: { id } });
  return res.json(user);
  ```
- **The Reality:** Exposes internal fields (password hashes, two-factor secret seeds, internal flags, IP histories) to clients.
- **The Fix:** Explicit DTO projection allowlists with all outgoing fields validated through runtime schemas.
