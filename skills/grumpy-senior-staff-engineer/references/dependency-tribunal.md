# Dependency Tribunal: Native-First Evaluation Protocol

> Every external dependency is a supply-chain attack vector, a maintenance burden, and a future upgrade migration. Prove it's worth it.

## The 5-Question Tribunal

Before adding any `npm install`, `pip install`, `cargo add`, or `go get`, the dependency must survive this tribunal. If it fails any question, the dependency is rejected.

### Question 1: Can the standard library do this?

| Language | Check First |
| --- | --- |
| TypeScript/Node | `URL`, `URLSearchParams`, `fetch`, `AbortController`, `crypto`, `Intl`, `structuredClone`, `Object.groupBy`, Web Streams, `readline` |
| Python | `pathlib`, `dataclasses`, `json`, `re`, `asyncio`, `httpx`-equivalent via `urllib`, `hashlib`, `secrets`, `typing` |
| Go | `net/http`, `encoding/json`, `crypto`, `sync`, `context`, `time`, `strings`, `regexp` |
| Rust | `std::collections`, `std::sync`, `std::io`, `std::time`, `std::fs` |
| SQL | Window functions, CTEs, `tsvector`, `JSONB`, composite indexes |

If the standard library solves it in ≤ 15 lines, write the 15 lines. No dependency added.

### Question 2: How many transitive dependencies does this bring?

```bash
# npm — count the total dependency tree
npm ls --all 2>/dev/null | wc -l

# python — inspect the wheel
pip show <package> | grep Requires

# rust — check Cargo.lock additions
cargo add <package> --dry-run
```

A package that solves a 15-line problem but drags in 400 transitive packages is a supply-chain bet worth evaluating very carefully.

### Question 3: What is the maintenance health?

Minimum bar for accepting a dependency:
- Last release within 12 months
- Open critical CVEs: zero (check https://osv.dev or `npm audit`)
- Maintained by: a named organization or multiple active contributors (not one person)
- License: MIT, Apache 2.0, BSD, or ISC

### Question 4: What is the removal cost?

If this dependency disappears (maintainer abandons, CVE forces immediate removal, license changes), how long does removal take? If the answer is "weeks of refactoring," the coupling is too deep. Use an adapter pattern or abstraction boundary.

### Question 5: Is there a lighter alternative?

| Heavy Choice | Lighter Alternative | Savings |
| --- | --- | --- |
| `moment.js` (67KB) | `Intl.DateTimeFormat` + `Temporal` | Zero packages |
| `lodash` | `Object.groupBy`, `Array.prototype.at`, `structuredClone` | Zero packages |
| `axios` | Native `fetch` + `AbortSignal.timeout` | Zero packages |
| `uuid` package | `crypto.randomUUID()` | Zero packages |
| `validator.js` | Zod or Valibot (strict schema parsing) | Smaller, type-safe |
| `winston` | `pino` (5× faster, structured JSON by default) | Performance |
| Full ORM (Prisma, TypeORM) | `postgres.js` or `pg` with typed queries | Smaller, predictable |

---

## Dependency Addition Output Format

When a dependency *does* survive the tribunal, document the decision:

```json
{
  "package": "zod",
  "version": "^3.23.0",
  "tribunal_result": "APPROVED",
  "question_1": "Standard library has no schema parsing with stripping and refinements",
  "question_2": "0 production dependencies",
  "question_3": "colinhacks/zod — 30k stars, weekly releases, MIT license, zero open CVEs",
  "question_4": "Adapter interface at boundary; removal requires 1 day of find-replace",
  "question_5": "Valibot is lighter but has smaller ecosystem; Zod is the safer long-term choice",
  "added_by": "Boundary validation at all API routes"
}
```

A dependency added without this record is a dependency that will be forgotten until it fails.

## Lockfile-first evidence for Bun

For an existing dependency, capture the declared range from `package.json` and the exact release from `bun.lock` before proposing changes. Then inspect the matching installed package manifest and its exported definitions if the task depends on an API. An absent installation or mismatched version leaves local API availability unverified.

The [offline Bun example](../examples/bun-lock-evidence.mjs) reads text lockfile version 2. It identifies a direct root dependency declared with an exact version, caret range, or tilde range and distinguishes stable from prerelease selections. It reports mismatched declarations, missing records, and unsupported lockfile formats, tagged or local resolutions, aliases, direct overrides, and ambiguous dependency groups. For a workspace or non-registry resolution, inspect the corresponding manifest and lockfile entry before making a recommendation.

```bash
bun <skill-directory>/examples/bun-lock-evidence.mjs <project-root> <package-name>
```

A `locked` result reflects the selected lockfile record. The receipt also carries an `installed` block read from `node_modules/<package>/package.json`: `{status: "installed", name, version}` when the installed manifest matches the requested package, or an explicit `missing`, `unreadable`, `identity_mismatch`, or `unsupported` status when it does not. Declared range, locked version, and installed identity/version are reported separately and can disagree; a mismatch leaves local API availability unverified, and the `installed` block never changes the lockfile verdict or exit code. Confirm installation from this block rather than a Bun package listing's installed count. Use the project-supported Bun version when inspecting the lockfile with package-manager commands. Keep an existing pin unless the requested change needs a release outside it. If a release decision needs registry data, record the package, registry, release channel, compatibility constraints, and lookup date. A missing or offline registry leaves availability, deprecation, and current release status unknown.

With `--public-npm --cache <path> [--cache-max-age <seconds>]` (default 3600), the example applies a freshness contract to that registry lookup. The cache file records one observation bound to the package, its registry source, and the locked version it was observed against; a record bound to anything else is ignored. A record no older than the maximum age is served without consulting the registry. An older record triggers a live lookup: a successful observation replaces the cache and is reported with `provenance: "registry"` and `age_seconds: 0`; an unavailable registry serves the expired record marked `provenance: "cache"`, `freshness: "stale"`, with its real `age_seconds` and the live attempt's status in `live_status`. Every cached result reports `provenance` and `age_seconds` alongside the original `observed_at`. Only a fresh result (registry or cache) exits 0; stale evidence is reported, never passed as current. The cache file is the only write — installation, lockfile, and manifest stay read-only, and the offline lock verdict is unchanged.

Bun documentation for [text lockfiles](https://bun.com/docs/pm/lockfile) and [JSONC parsing](https://bun.com/reference/globals/bun/JSONC/parse)

Add `--public-npm` only for a known public package when current registry evidence is relevant. This sends the package name to `https://registry.npmjs.org` and uses no repository registry configuration or credentials. The request rejects non-200 responses other than an explicit unlisted-package result, has a four-second deadline and a 2 MB body limit. It follows no redirects.

The registry block separately reports the exact lockfile version's listing, whether npm lists it as deprecated, the verified `latest` tag, and whether a stable tagged version satisfies the manifest range. `latest` is a maintainer-managed tag, so it does not establish the newest release or a recommended upgrade. An unavailable lookup preserves the lockfile facts and exits 2. The example stores no cache and makes no manifest changes. [npm package metadata format](https://github.com/npm/registry/blob/main/docs/responses/package-metadata.md)
