# Offline rotation review

Run `node --test rotation.test.mjs` or `bun test rotation.test.mjs` in this directory.

| Test | Evidence |
| --- | --- |
| AES-GCM known answer | The built-in library returns the exact ciphertext and authentication tag in NIST's public GCM-AES128 Example 2. The same bytes decrypt with the correct tag and fail authentication with a changed tag. |
| Duplicate nonce | The evidence check rejects a repeated nonce under one data-key identity and permits the same synthetic nonce label under a different data-key identity. |
| Version retirement | The offline model accepts a legacy read after enabling the new writer, rejects writes under the inactive version, then rejects reads under the revoked version. |
| Unavailable key service | The model denies the affected operation and emits allowlisted operation, version and reason fields. The synthetic sensitive marker never appears in output. |

Apply a published vector for the production algorithm through the actual crypto library and verify the on-disk envelope independently. In an isolated environment, write with the old version, switch writes to the new version, and verify both remain readable by the deployed reader. Simulate timeouts and permission denial, review captured logs for test markers, rehearse rollback and backup restore, then revoke the old version and verify the failure path. This fixture checks review scenarios in memory. Deployment and provider integration require their own evidence.

[Public AES-GCM example values](https://csrc.nist.gov/csrc/media/projects/cryptographic-standards-and-guidelines/documents/examples/aes_gcm.pdf) · [NIST CAVP testing and validation limits](https://csrc.nist.gov/Projects/cryptographic-algorithm-validation-program/cavp-testing-block-cipher-modes)
