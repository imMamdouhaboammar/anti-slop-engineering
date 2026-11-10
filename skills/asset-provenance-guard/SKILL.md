---
name: asset-provenance-guard
description: Enforce cryptographic SHA-256 asset integrity, explicit open-source license provenance (CC0, MIT, SIL OFL, Apache 2.0), and prevent unverified external CDN hotlinks in shipping builds.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Asset Sourcing & License Provenance Ledger Guard

> Guarantee cryptographic asset integrity, eliminate copyright liabilities, and prevent unverified external CDN hotlinks across all shipping media.

## Why This Skill Is Needed & Target State

AI-assisted generation frequently pulls third-party media or hallucinated assets without verification:
1. **Unverified CDN Hotlinks**: Hotlinking external CDNs (`images.unsplash.com`, `cdn.jsdelivr.net`) creates production failure risks if the remote link rots or changes.
2. **Copyright Contamination**: Sourcing 3D models, textures, sound effects, or typography without explicit open license records risks copyright infringement.
3. **Asset Tampering & Drift**: Binary media can be silently swapped or corrupted without Git noticing binary diff details.

The target state is cryptographic provenance: every asset has an immutable SHA-256 hash, an explicit open-source license (CC0, MIT, SIL OFL, Apache 2.0), and a structured entry in `.anti-slop/asset-ledger.jsonl`.

## Invariant Rules

1. **Physical Provenance Ledger:** Every local image, model, font, or audio file in project asset directories must possess an entry in `.anti-slop/asset-ledger.jsonl`.
2. **Cryptographic SHA-256 Integrity:** Computed file SHA-256 hashes must match the recorded ledger hash exactly.
3. **Approved Permissible License:** Licenses must originate from the approved permissible catalog (`CC0`, `MIT`, `OFL-1.1`, `Apache-2.0`, `Public Domain`, `Hand-Authored`).
4. **Zero Hotlink Dependencies:** Production code must bundle assets locally or reference canonical immutable CDNs; unverified third-party hotlinks are flagged.

## Asset Ledger Format (`.anti-slop/asset-ledger.jsonl`)

```json
{"path": "models/hero.gltf", "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", "source_url": "https://polyhaven.com/a/hero", "license": "CC0", "attribution": "Poly Haven"}
```

## CLI Usage

```bash
# Scan asset directories against local ledger
bunx anti-slop-engineering asset-provenance --scan assets/

# Auto-record newly authored assets as Hand-Authored
bunx anti-slop-engineering asset-provenance --scan public/ --record-missing

# Validate custom ledger file with JSON output
bunx anti-slop-engineering asset-provenance --ledger .anti-slop/asset-ledger.jsonl --json --strict
```
