# Evidence-driven decision method

## 1. Source hierarchy and semantic validation

| Evidence type | Representative source | What it warrants |
| --- | --- | --- |
| Observed | Executed query, repository config, API response, contract, measured workload | The inspected artifact said or did X at that time |
| Derived | Reproducible arithmetic from observed inputs | The result follows if the input definitions and computation are correct |
| Inferred | Domain reasoning, projected workload, untested architecture assumption | A hypothesis to test, not a measured fact |
| Unavailable | No permission, missing API, network failure, missing dataset | Uncertainty; never infer nonexistence |

For a supposedly direct field, check event semantics, filters, units, population, attribution, clock, refund/reversal behavior, freshness, tenant boundaries and provenance. A field name is not enough. If the user asks for a total and the API exposes a gross total, it may still require adjustment. Record the smallest proof that disambiguates them.

Try to disprove the proposed method with one credible direct source before investing in a new calculation. Search official/internal source definitions first, then the relevant runtime code, and then secondary explanations. If access is blocked, make the limitation explicit and ask only for a fact the current environment cannot recover. Do not invent a schema or API.

## 2. Premise and alternatives

Write the goal as a desired observation/outcome, independent of implementation. Example: "Find the exact number of completed, non-refunded purchases" is the goal; "compose seven conversion ratios" is a proposal. For architecture, "operate a secure authenticated app within team and budget constraints" is the goal; "Next.js on Vercel" is a proposal.

Search candidate approaches based on constraints, not token familiarity. Include a zero-build/direct-use option if it might satisfy the goal, and a lower-complexity option whenever it is credible. Reject strawmen: every compared option must be viable under the same known hard constraints. If only one candidate is compliant, state why and do not fabricate a second viable alternative.

## 3. Architectural independence

| Axis | Ask | Common trap |
| --- | --- | --- |
| Rendering | Which routes need SSR, metadata, static generation or only client rendering? | Treating a login wall as proof that every SSR need vanishes |
| Runtime | Are workloads requests, streams, queues, cron or long jobs? | Picking request-limited compute for long jobs without checking limits |
| Hosting | Who handles deploys, patching, observability, incidents, downtime? | Comparing only list price, ignoring personnel and failure cost |
| Persistence | Required transactions, locality, recovery point, restore time, isolation? | Treating a colocated DB as an automatic long-term saving |
| Auth | Managed auth vs self-owned identity, audit and migration boundary? | Underestimating coupling or inventing compliance guarantees |

Framework, host and database can have different providers. Inspect each real dependency and its documented deployment contracts before asserting a lock-in. A well-known stack can be the right choice when its hosting, maintenance and failure characteristics match the actual organization. A self-managed design is not preferable merely because bills appear predictable.

## 4. Cost of ownership and reversal

Evaluate at least: build effort, on-call/operations, backups and restores, security updates, downtime risk, expected usage charges, observability, migration, developer availability and provider dependency. Do not use unsupported exact forecasts. Compare ranges or qualitative exposure when volume and prices are unknown.

Separate reversible decisions from sticky ones. Changing web hosting may be modest if the app is portable; replacing auth identities, storage conventions, persistent data models or provider-specific functions may be expensive. Design bounded seams only where an actual migration threat warrants them. Avoid speculative multi-cloud abstractions for imaginary future portability.

Consider at least one realistic future change and one failure scenario; use explicit premises such as "if write volume grows tenfold" rather than "the app will reach 10x". Name what observable signal would reopen the decision. If a choice can be cheap to revise later, prefer making a bounded decision now over endless analysis.

## 5. Decision interruption policy

Interrupt on evidence that would invalidate the reason for the work, not merely on an alternative idea. State: (1) new source and observed fact; (2) effect on current plan; (3) cheapest next verification; (4) what to keep or stop; (5) any authority needed. Prior effort is a historical fact, not a forward-looking benefit. If a source conflicts with a contract or user direction, obtain permission rather than silently overriding a decision.

The point is calibrated skepticism: too little yields eager compliance; too much yields investigation theater and delayed delivery. Once a bounded choice survives the source checks and has explicit revisit conditions, execute and collect actual operating evidence.
