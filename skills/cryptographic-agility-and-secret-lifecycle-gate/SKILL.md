---
name: cryptographic-agility-and-secret-lifecycle-gate
description: Review authenticated encryption, key-version migrations, encryption key retirement, and service-secret rotation. Use when a change affects cryptographic libraries, key storage, KMS permissions, or credential handling.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Cryptographic Agility and Secret Lifecycle

## Collect review evidence

- Identify the data and secret classes, where plaintext appears, trust boundaries, the party authorized to decrypt, and the effect of compromise or missing keys. Tie each claim to concrete code, deployed policy, or a sanitized trace.
- Record the library and algorithm versions, provider and regulatory constraints, whether ciphertext uses authenticated encryption with associated data (AEAD), and the key or credential owner. Review primitive choices for their exact use and deployment policy. Use a maintained library or provider API for cryptography.
- For nonce-sensitive AEAD such as AES-GCM, check how distinct encryptions avoid a repeated nonce under the same actual data key. Include concurrent writers, restarts, retries and restore from backup. A key alias can change without changing key material. Test with a forced duplicate on the application or library path responsible for detecting or preventing it. Check that plaintext is released only after authentication succeeds.
- For envelope encryption, review data-key generation, wrapping under a KMS-managed key, and separate permissions for data access and unwrap. Persist ciphertext, authentication metadata, the wrapped data key and the key reference needed for recovery. Bind record context such as tenant and purpose as authenticated data when relevant. Keep plaintext keys out of durable storage.

## Change encryption versions

| Stage | Required evidence |
| --- | --- |
| Prepare | Inventory stored ciphertext and backups by envelope and key version. Deploy readers that recognize both formats before emitting the new format. Accept only supported format and algorithm combinations. Check the old and new read paths on isolated copies. |
| Change writers | Use one active write version. Preserve authorized reads of older ciphertext using its recorded version. Verify old and new readers during the rollout, including KMS timeouts and access denial. An unavailable key stops the dependent operation with a bounded, observable failure. |
| Migrate existing data | Rewrap data keys when only the KEK changes and provider support permits it. Re-encrypt data when replacing its data key or algorithm. Backfill idempotently, check concurrency, and compare object inventories and read success before retiring compatibility. |
| Roll back or retire | A rollback before retirement must retain a reader for ciphertext already written with the new version. Keep key access according to the approved recovery and retention policy. Test backup recovery, then revoke retired access and verify rejection. Escalate suspected compromise immediately and follow the approved incident plan. |

## Rotate application secrets

- Inventory each consumer of the credential, its issuance scope, expiration, and rollback owner. Prefer short-lived credentials when supported. Issue and deliver the successor through the approved secret store, validate it with a canary consumer, roll it out, and verify that the prior credential is revoked at its issuer.
- Keep values out of source, process arguments, logs, traces, test artifacts, and failure responses. Review what the exception handler receives and what the logger emits. Test with a synthetic marker and inspect output from failed operations. Use safe event codes and version labels for correlation.
- Return a review decision with source evidence, known-answer results, rollout and restore results, and gaps. An exception must name the affected objects and callers, owner, reason, containment, expiry date, and removal test. Record a missing live KMS rehearsal as an evidence gap.

## Verify

Run `node --test rotation.test.mjs` from the installed skill's [examples directory](examples/rotation.test.mjs), or `bun test rotation.test.mjs`. The test exercises Node's built-in AES-GCM against a public known answer and checks an offline lifecycle model. Run the same cases against your production library and an isolated test KMS to verify actual rotation, revocation, and recovery behavior. [Scenario and expected results](examples/rotation-scenario.md)

- [NIST SP 800-57 Part 1 key management](https://csrc.nist.gov/pubs/sp/800/57/pt1/r5/final)
- [RFC 5116 authenticated encryption](https://www.rfc-editor.org/rfc/rfc5116.html)
- [Google Cloud KMS envelope encryption](https://docs.cloud.google.com/kms/docs/envelope-encryption)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
