# Ownership and causal boundaries

## The responsibility test

The right fix is located where the relevant invariant becomes authoritative, not necessarily where a wrong value is visible. An invariant may concern identity, order contact, billing, transport representation, permission, or presentation. A shared string name such as `email` does not prove two contexts have the same responsibility.

| Symptom | First likely owner to inspect | Counterexample that defeats the shortcut |
| --- | --- | --- |
| Same validation repeated in controllers | Domain validation/schema or shared application policy | Each endpoint applies a genuinely different rule |
| Email shown on multiple profile screens | Identity data contract and response serialization | Email is valid identity data but visibility is a presentation policy |
| Email required only when ordering | Checkout order contact boundary and identity constraints | Login, reset, or provider identity requires email |
| Same retry copied through clients | Network/client abstraction or central retry policy | Operations have different idempotency/rate-limit constraints |
| Permission filtering duplicated across routes | Authorization policy close to protected operations | Tenant-specific resources require distinct policy rules |
| UI displays inconsistent totals | Canonical aggregation/data definition | Currency/timezone semantics differ by consumer |
| Legacy adapter emits wrong shape | Adapter/serialization boundary | Core domain contract itself is invalid |

Trace **origin → writes → persistence → transformations → reads → consumers**. Find the earliest location whose invariant is actually wrong. Replacing only the output may conceal the cause; changing an earlier component without checking later contracts may also break the system.

## Choosing the owner

Use five questions in order:

1. What behavior would be false if all UI/controllers disappeared? That rule likely belongs deeper than presentation.
2. Can any authorized entry point bypass the proposed enforcement? If yes, a controller-only check may be insufficient.
3. Would all callers agree on the same rule? If not, a global helper or model hook may be incorrect.
4. Is the data rule a persistence invariant, a domain rule, a workflow policy, or a representation concern? Keep each at its proper boundary.
5. What system contract would disprove the chosen fix? Run that probe before implementing destructive or broad changes.

## What the smallest coherent change means

Count logical responsibilities, not files. Updating a canonical schema, its migration, API contract, three consumer adaptations, and tests can be a better design than one dangerous middleware interception. Conversely, repeated response hacks across many endpoints often point to a missed common rule.

A new abstraction is justified only when it owns a meaningful shared contract. Do not extract merely because two functions mention email. Distinguish intentional duplication in tests from duplicated production invariants. Avoid relocating a rule into an ORM entity when doing so creates side effects on reads, unexpected network calls, or cross-context coupling.

## Evidence levels and escalation

**Observed** means inspected repository source, executed query, official contract, or reproduced behavior. **Derived** means a conclusion reproducibly follows from observed inputs. **Inferred** means a hypothesis, not a verified owner. **Unavailable** means access or environment prevented the check; it never means the path is absent.

For account identity, payment, privacy, authorization, schema migration and retention, missing evidence may require a pause even if implementation looks easy. Delete/migrate production data only with the user's specific authority, a tested recovery path, and the contract impact understood. For a routine reversible local edit with a known owner, do not manufacture a record or elaborate architecture debate.

## Architectural counterexamples

- **Global model masking:** A model getter strips email everywhere. It also strips it from order receipts and identity recovery. The correct fix may be an output serializer for a single public surface, not the model.
- **Per-view suppression:** Twenty screens each hide email because registration improperly requires it. If verified, a corrected identity/checkout contract can remove the need for duplicated patches, while migrations and auth tests remain necessary.
- **Distributed policy by design:** Different tenants have distinct verified retention requirements. A single global normalizer breaks those rules; scoped domain policies are correct even when multiple files change.
- **False root-cause certainty:** A failing API response might come from a stale cache, wrong serialization, or storage invariant. Treat each as a hypothesis until a read/write trace identifies the first incorrect boundary.
