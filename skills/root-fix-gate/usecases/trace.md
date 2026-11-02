# Trace the owning boundary

1. **Freeze the observable contract.** Record what happens, what must happen, and a minimal reproduction. Treat the user's fix suggestion as a hypothesis, not the goal.
2. **Inventory the active architecture.** Inspect repository instructions, data models, schema, entry points, validation, services, serializers, auth and tests relevant to the symptom. Use actual source search and call sites; don't infer architecture from directory names alone.
3. **Follow the full data path.** Trace input/write, storage, transformation, read and output. Mark where the invalid value or rule first appears. Investigate one shared predecessor before changing multiple descendants.
4. **Assign the owner.** Ask which component should make the invariant true for all relevant operations. Name the enforcement point, its consumers, and why the owner is authoritative. Check whether different contexts intentionally have different requirements.
5. **Construct competing hypotheses.** At least contrast a consumer-level patch against a source/boundary correction when both are plausible. Give each a failure mode and verification probe. If one approach is the sole compliant option, state the binding constraint; do not fabricate a viable alternative.
6. **Falsify before coding.** Probe dependencies capable of disproving the chosen owner: auth, password reset, unique constraints, migration/data history, transactions, external APIs, batch jobs, permissions and other readers. Do only the probes material to this task.
7. **Set change surface.** Classify expected paths as owner, consumer, test, migration or integration. A small root fix may still require many legitimate compatibility tests and a migration. State any unknowns and authority needed.
8. **Choose action.** `proceed` only with grounded ownership evidence and a testable boundary; `pause` when destructive, identity or contract assumptions remain unverified; `stop` when direct existing behavior already satisfies the requirement.

## Focused search strategy

- Search field/rule names in models, DB schema, writes, API contracts and consumers (`rg -n 'email|contact_email' <relevant-paths>` is an example, not a universal command).
- Find real call sites before extracting a shared helper; count consumers that need **identical** semantics, not just the same field name.
- Read failing tests and prior migrations before touching nullability or canonical serialization.
- Prefer a temporary reproduction or a read-only probe over speculative global changes. If the host lacks filesystem or runtime access, mark ownership `inferred` and withhold risky mutation.

## Worked case: email collected only at checkout

**Symptom:** The task is to avoid asking for email on the profile and ask for it on the order form. An initial agent hides it in each controller and view.

**Hypotheses:** (A) display policy is wrongly repeated; (B) identity incorrectly requires a contact field that belongs to checkout; (C) the auth provider truly requires email as an identifier, so moving the field to the order alone breaks sign-in.

**Probe:** Read `User` and `Order` schemas, registration and login code, reset flows, order receipts, and existing records. Confirm whether order email is distinct from account identity. Do not assume email can safely be set to `null` because the UI does not display it.

**Conditional design:** If identity does not require email and checkout owns customer contact, make account email optional and validate order contact at checkout, with necessary DB migration and consumer updates. If auth depends on account email, preserve that invariant and find a non-destructive display/collection policy. Never erase stored user email as a side effect of changing a form.
