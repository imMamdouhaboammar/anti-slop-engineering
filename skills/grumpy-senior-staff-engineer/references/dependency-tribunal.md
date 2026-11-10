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
