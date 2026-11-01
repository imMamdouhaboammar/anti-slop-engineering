# Defend an architecture choice

1. **Freeze requirements, not brands.** Capture public/private routes, execution shape, jobs, data growth, team skill, reliability/recovery target, compliance, budget and ownership. Mark absent inputs unknown, not guessed.
2. **List hard constraints and current assets.** Include signed requirements, already-operating infrastructure, existing integrations and migration costs. Exclude options that violate a binding constraint.
3. **Decompose independently.** Consider rendering mode, frontend framework, API and background runtime, hosting, database, storage, auth and operations only to the extent each affects this product. A full-stack framework, host and DB are not inseparable.
4. **Search for the smaller third option.** If a logged-in dashboard already has an API and no server-rendering need, test whether a client-side application is sufficient before comparing two full-stack frameworks.
5. **Compare serious candidates.** For each: what it makes easy now, what it burdens the team with, failure mode, operational owner, irreversibility, exit path and evidence. Use current official docs/benchmarks where claims are time-sensitive; otherwise mark unverified.
6. **Stress the decision.** Evaluate today plus at least one plausible future state: growth, 3am incident, loss of provider feature, backup restore, compliance change, deployment topology or price sensitivity. Future states are conditional scenarios, not predictions.
7. **Recommend conditionally.** Distinguish verified facts from assumptions and articulate a concrete revisit trigger. If critical owner/requirement/price is unresolved, choose a reversible experiment or pause hard commitments. Do not block harmless discovery.
8. **Handoff execution.** Obtain user approval for material platform, spending, migration or data-placement decisions. Once authorized, resume the parent implementation workflow and test actual deployment characteristics.

## Worked case: authenticated SaaS

**Evidence:** Public content comprises landing and legal pages. The private app has heavy background jobs. No confirmed ops owner or restore target.

**Consider:** Separate the rendering layer from background compute. Compare a Vite SPA, TanStack Start and Next.js against actual server-rendering needs. Compare VPS and managed runtime on deploy effort, incident response, queue support and fixed/usage cost. Compare colocated and managed PostgreSQL on restore testing, backups, isolation and team capability.

**Do not conclude:** "Next.js always requires Vercel", "Supabase is required for PostgreSQL", or "VPS is inherently superior over two years". All three are unsupported shortcuts.

**Conditional output:** A VPS with local PostgreSQL can be a strong initial option if an owner can patch it, monitor it and prove an offsite restore. Managed hosting may be preferable when no one can operate that stack. Framework choice remains independent of hosting, and no option is selected purely by popularity.
