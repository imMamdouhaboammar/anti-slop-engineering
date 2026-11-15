---
name: supply-chain-and-sbom-sentinel
description: Review new dependencies, lockfiles, install hooks, build attestations, SBOMs, and container base images. Use when package identity, artifact integrity, registry trust, or a change in release ownership needs verification.
license: MIT
metadata:
  version: "0.1.0"
  parent: anti-slop-engineering
---

# Supply Chain and SBOM Sentinel

## Review order

1. Read the import or build requirement, package manifest, and lockfile diff. Record the intended package coordinate, exact version, effective registry or source commit, artifact integrity value, and the reason for the change. Show additions, changes in source or ownership, and new lifecycle hooks separately from lockfile reordering.
2. Start from a trusted upstream source, such as the project's verified documentation or repository, then match its documented coordinate with the registry record and lockfile. For a private package, inspect scoped registry configuration and resolver fallback rules. Remove credentials from evidence. A similar name, first-seen publisher, unsigned release, or low download count alone cannot establish malicious intent.
3. Inspect the exact package artifact as data, without executing install or build code. Do not extract untrusted tar paths into the workspace. Read manifests, lifecycle commands, and files those commands invoke. Trace network access, credential reads, writes outside the package, and subprocesses. Native build hooks can be legitimate. Record their need and the controls before permitting them.
4. Verify available integrity evidence with the ecosystem's existing tooling. A digest match binds bytes to an expected digest. Provenance verification also checks the signature or attestation and compares the source revision, builder or workflow identity, and subject digest to independent policy. Registry guidance and attestations are optional sources when offline.
5. If supplied, compare the SBOM's generated artifact identity, version, target platform, dependency relationships, and hashes with the reviewed lockfile and built image. Distinguish build-time, optional, and runtime dependencies. For OCI images, identify whether the pin is for an index or a platform manifest before comparing digests. A matching SBOM or digest does not establish absence of vulnerabilities.
6. Report each check with its evidence and a trust decision. Before adding an install step, request missing evidence or propose a safe replacement. Record remediation at the authoritative resolver, build, or release boundary.

| Decision | Evidence |
| --- | --- |
| Verified | Canonical identity and registry match, approved digest or independently verified signed provenance matches the artifact, and relevant scripts were reviewed. State precisely which checks ran. |
| Suspicious | A concrete mismatch or prohibited behavior, such as an approved digest mismatch, registry substitution, a package coordinate that differs from trusted documentation, or a lifecycle hook that reads unrelated secrets. Record evidence and hold installation. |
| Unknown | Available evidence cannot establish identity, bytes, or script behavior. For an offline uncached release, request the approved metadata or artifact. Never infer approval from a clean grep or missing alerts. |

Catalog: [CI-01, CI-04, CI-07](../anti-slop-engineering/references/anti-pattern-catalog.md).

## Evidence exercise

Run [offline review cases](examples/review_cases.py) with Python 3.9+. The fixtures represent already inspected evidence, not a package verifier. They assert the distinction among a package name mismatch, a prohibited hook, a matching approved artifact, unavailable offline evidence, and a mismatched container digest. No fixture downloads, extracts, builds, or runs third-party code.

Sources: [npm package provenance](https://docs.npmjs.com/viewing-package-provenance/), [npm audit signatures](https://docs.npmjs.com/cli/npm-audit/), [Docker image digest pinning](https://docs.docker.com/reference/cli/docker/image/pull/#pull-an-image-by-digest-immutable-identifier), [SLSA artifact verification](https://slsa.dev/spec/v1.1/verifying-artifacts), [CycloneDX specification](https://cyclonedx.org/specification/overview/).
