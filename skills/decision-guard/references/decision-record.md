# Decision record contract (version 1)

The JSON format is a portable checkpoint for consequential decisions. It is not a benchmark, source verifier, risk score or substitute for human authority. Save it near the active project's decision evidence, not automatically in every repository.

| Field | Required content |
| --- | --- |
| `kind` | `investigation` or `architecture` |
| `goal`, `proposal` | Desired result distinct from initially proposed method |
| `evidence[]` | `source`, `finding`, `level` (`observed`, `derived`, `inferred`) |
| `direct_check` | `status` (`found`, `not_found`, `unknown`, `not_applicable`), `source`, `finding` |
| `assumptions[]` | `claim`, `state` (`verified` or `unverified`), `basis` |
| `decision_axes[]` | Architecture only: `name`, 2+ distinct `considered` options, one selected value (or single candidate with `constraint_rationale`) |
| `alternatives[]` | Architecture only: at least 2 distinct credible options (or single candidate with `constraint_rationale`), each with `name`, `benefit`, `risk`, `reversal` |
| `horizons[]` | Architecture only: current and later `stage`, each with `scenario` and `consequence` |
| `decision` | `action` (`proceed`, `pause`, `stop`), `choice`, `reason`, `invalidated_by` |

When a direct answer is found and execution continues, add `decision.direct_path_handling` (`use` or `bypass`). A bypass also needs `decision.direct_override_reason`. Recording an unsupported reason does not make it true. When hard constraints eliminate alternatives, an axis or decision may specify a single candidate with `constraint_rationale`; eliminated candidates do not count as credible options. For an investigation that ends in `stop`, architectural alternatives and horizons are unnecessary.

The checker intentionally allows `pause` with `direct_check.status = unknown`. It blocks `proceed` with an unknown direct-path status and detects absent architectural comparisons. It checks for structurally present evidence, not whether source citations are authentic or projections make sense.

Exit codes: `0` structurally complete, `2` missing/contradictory record information, `1` malformed input or unreadable file. A `0` does not authorize implementation. The `decision_action` field distinguishes a complete `pause` record from a complete `proceed` record.

Example: [`examples/architecture-record.json`](../examples/architecture-record.json). The example is illustrative only, not observed performance or a real vendor recommendation.
