---
name: anti-slop-engineering
description: Prevent, detect, and repair AI coding slop and dirty engineering in repositories. Use for planning features, writing code, changing tests, reviewing pull requests, refactoring, hardening CI, debugging regressions, or auditing agent-generated changes. Enforces behavioral contracts, focused diffs, test integrity, repo conventions, security boundaries, and evidence-based completion.
author: Mamdouh Aboammar <mamdouhfces1997@gmail.com>
license: MIT
metadata:
  version: "1.6.0"
  focus: "engineering-discipline"
  repository: "https://github.com/imMamdouhaboammar/anti-slop-engineering"
---

# Anti-Slop Engineering

**Mission:** Deliver the smallest *coherent, correct, maintainable* change supported by independent evidence. Never trade contract integrity, security, or reviewability for a green CI badge. Enforce Google Site Reliability Engineering (SRE) principles: Simplicity (KISS), Single Source of Truth (DRY), Anti-Speculation (YAGNI), and Fixing Issues at Scale (Eliminating Toil). Incorporate clean-room Stop-That-Shit boundary interception, Senior Dev ladders, and high-performance Rust/Go microservices. This skill applies to human and AI-authored changes equally.

## Operating priorities

1. Explicit user requirements, repository architecture, security policy, and existing public contracts outrank aesthetic preferences.
2. Preservation of authorized existing behavior outranks making a new implementation pass its own tests.
3. Prove behavior before polishing style; fix correctness and security blockers before cosmetic issues.
4. Minimize **unnecessary** complexity, not required tests, safety checks, or clarity. A short but incorrect solution fails.
5. Do not declare a finding without file/line evidence and an impact story. Never invent tool results or test runs.
6. Never change or approve unrelated code, tests, policies, dependencies, CI, or infra merely to make the current request pass.
7. **Official boilerplate & installers over manual scaffolding:** For any greenfield project, service, framework, library, or SDK integration, agents MUST rely on the official CLI installer, starter boilerplate, or generator (e.g., `uv init`, `cargo init`, `bun create`, official SDK quickstarts). Never manually hand-roll ad-hoc scaffolding, arbitrary directory layouts, or loose config files by hand.
8. **Strict latest stable versioning:** When installing, initializing, or introducing any new dependency, library, or SDK, strictly query the registry and pin the **latest stable version**. Never guess outdated versions from training memory or rely on obsolete templates.
9. **Taste, Visual Restraint & Clean UI Microcopy:** Never clutter user interfaces with walls of text, repetitive explanations, or overcrowded navigation bars. Respect visual hierarchy, purposeful white space, and minimal, polished microcopy. Eliminate gratuitous widgets, stat pills, or icon clutter.
10. **Zero Dev-Notes Leakage in User-Facing UI:** Never render internal developer instructions, agent reminders, mock disclaimers, or architecture apologies (`"Note: In production..."`, `"Mock data displayed"`, `"TODO: Add auth"`) into user-visible DOM/JSX. Keep internal technical context strictly in code comments or project design documents.
11. **Documentation Restraint & Zero Speculative Docs:** Never generate unprompted documentation files, submission dossiers, reviewer packets, or platform guides (e.g. "Publish to OpenAI ChatGPT Plugins", fake marketplace submission dossiers, speculative deployment recipes). Never cite dead, deprecated, or hallucinated third-party submission portals (e.g. `platform.openai.com/plugins`). Keep documentation strictly factual, lean, and grounded in real, requested repository capabilities. Reject documentation file sprawl and ceremonial note callouts.
12. **The Zero-Obviousness & Direct Payload Doctrine:** Strictly eliminate trivial syntax narration, tautological docstrings, patronizing UI microcopy, ceremonial documentation truisms, and affordance narration. All documentation, code, and interfaces must adhere to the **Direct Payload Invariant**: transition directly from domain headers into technical payloads (code, tables, media, schemas) with ZERO conversational preambles ("The following table outlines..."), ZERO affordance narration ("click to play/expand/copy/scroll", "watch here without leaving the page"), ZERO mechanical hand-holding ("open your terminal", "save the file"), and ZERO bilingual title-stacking or promotional buzzword inflation. Standard UI affordances and technical payloads speak for themselves; silence and clarity outrank noise.
13. **Google Site Reliability Engineering (SRE) Discipline:** Enforce the four foundational Google SRE principles across all changes:
    - **KISS (Simplicity as a prerequisite to reliability):** Keep cyclomatic nesting <=4 levels. Functions exceeding 80 lines must be decomposed into single-responsibility units. Reject pass-through wrapper chains that add no value.
    - **DRY (Single source of truth):** Replicated invariants, duplicated validation patterns, or parallel error structures are reliability hazards. Consolidate into canonical modules.
    - **YAGNI (Anti-speculative engineering):** Zero speculative parameters (`_unused_param`, `future_kwargs`), dead branches (`if False:`), or placeholder stubs. Build for active requirements only.
    - **Fix Issues at Scale (Eliminating toil & distributed resilience):** Automate repetitive manual toil. Enforce exponential backoff with full jitter on all network retries to avoid retry storms. Never use `sleep()` as an async race band-aid. Bound concurrency and enforce idempotency on state-changing endpoints.
14. **Clean-Room Senior Dev Ladder & SHIT Interception (Ponytail, STS, Boring Engineering):**
    - Intercept the four SHIT hazards: Scope creep (`S`), Hypothetical hardening/unread companion hashes (`H`), Intent violation (`I`), and Task thrashing (`T`).
    - Climb the Senior Dev Ladder before authoring code: (1) Does this need to exist? (2) Does it already exist in the codebase? (3) Does the stdlib/platform do it? (4) Does native runtime cover it? (5) Does an existing dependency solve it? (6) Can it be a direct expression? (7) Write only minimal, necessary, tested code.
    - **Name the Built-in:** Before writing custom parsing, validation, or UUID/cloning utilities, name the platform built-in (`crypto.randomUUID()`, `URLSearchParams`, `structuredClone()`). Hand-rolling standard primitives is a defect.
    - **Practical DRY 3-Point Barrier:** Shared utilities or abstractions are permitted only when appearing in >=2 real existing call-sites, when all call-sites require identical modifications upon change, and when the abstraction can be named without coordinating conjunctions (`and`, `or`).
15. **Decision Guard before consequential commitments:** When the task proposes derived metrics, an architectural stack, infrastructure, persistence, or a difficult-to-reverse engineering decision, read [Decision Guard](skills/decision-guard/SKILL.md). Check direct evidence and independent alternatives before treating the proposed method as necessary. Never substitute the decision record's structural check for source verification.
16. **Root-Fix Gate for scattered symptom patches:** When a local behavior change spreads through controllers, views, endpoints or multiple layers, read [Root-Fix Gate](skills/root-fix-gate/SKILL.md). Trace the owner of the domain invariant, compare a coherent source correction with consumer workarounds, and inspect actual change paths. Do not assume the model owns every rule or that few files prove safety.
17. **Future-Scale Gate for irreversible foundations:** Before locking in a core runtime, public contract, persistence model, or platform boundary for a long-lived product, read [Future-Scale Gate](skills/future-scale-gate/SKILL.md). Establish credible future operating scenarios, assess reversal cost and run a bounded evolution proof. Design the cheap necessary foundation now; defer speculative infrastructure with measurable revisit triggers. Lack of a present bottleneck does not disprove future architectural constraints.
18. **Paranoid Principal Architect for 10M scale & zero-trust:** When designing system architectures, generating backend/frontend code, refactoring critical paths, conducting adversarial security reviews, or diagnosing scale bottlenecks, race conditions, memory leaks, and EDoS vulnerabilities, read [Paranoid Principal Architect](skills/paranoid-principal-architect/SKILL.md). Enforce the 10,000,000 Concurrent Users Axiom and Active Battlefield Zero-Trust mindset. Reject happy-path assumptions, unbounded async loops, hot keys, client authority, and unparsed inputs from line one.
19. **Deterministic Simulation & Property Testing (MSR & AWS Rigor):** When verifying distributed consensus, stateful lifecycles, concurrency protocols, serialization codecs, or untrusted boundaries, read [Deterministic Simulation & Property Testing](skills/deterministic-simulation-and-property-testing/SKILL.md). Reject example-based test complacency: mandate Property-Based Testing (fast-check, Hypothesis, proptest) generating >= 1,000 inputs with automated shrinking to discover minimal failing counterexamples; mandate Deterministic Simulation Testing (DST) with a virtual clock and 64-bit reproducible seed (simulating packet drops, clock skews, and message reordering; zero unseeded `Math.random()` or wall-clock sleeps); enforce explicit State Transition Tables with impossible states made unrepresentable in the type system; and enforce Structure-Aware Fuzzing on all parsers and deserializers asserting crash freedom, bounded recursion (<= 16), and payload byte caps (<= 10MB).
20. **Privacy & Data Lineage Gate (Apple Privacy & Meta Data Infra):** When designing user data architectures, processing PII/sensitive customer data, implementing GDPR/CCPA deletion lifecycles, or designing analytics/telemetry pipelines, read [Privacy & Data Lineage Gate](skills/privacy-and-data-lineage-gate/SKILL.md). Protect user data from the system itself: wrap all sensitive personal attributes in compiler-enforced branded Tainted PII types (`Redacted<T>`) with unredacted logging and serialization banned; mandate Cryptographic Erasure (Crypto-Shredding via KMS key-per-subject envelope encryption) ensuring account deletion instantaneously destroys the encryption key rendering distributed cold backups, append-only WALs, and multi-tier caches permanently unreadable; enforce Data Minimization & Mandatory Retention TTL by rejecting any table, document schema, or cache storing user data without an explicit purpose binding and automated TTL garbage collection; and maintain an audited Data Lineage DAG with telemetry egress strictly fenced against an allowlist and differential privacy ($\epsilon \le 1.0$).
21. **Type-Level & AST Slop Gate (Oxlint & Strict AST Discipline):** When writing or auditing TypeScript/JavaScript code, refactoring contracts, or configuring linters, read [Type-Level & AST Slop Gate](skills/type-level-and-ast-slop-gate/SKILL.md). Enforce the 18 generic and 5 Effect AST rules: eliminate chained type assertions (`as unknown as T`), ungrounded assertions (`as T` without nearby `// SAFETY:` invariant justification), quadratic reducer accumulator copies, eager array `.filter().map()` chaining, conditional empty spreads `...(c ? { x } : {})`, and test-oracle erosion via module mocking (`vi.mock()`). Audit diffs with `bunx anti-slop-engineering ast --base HEAD` and vendor Oxlint plugins via `bunx anti-slop-engineering install-oxlint`.
22. **API Ergonomics & Contract Governor (Microsoft TypeScript & Stripe DX):** When designing public SDKs, library interfaces, CLI commands, or internal module boundaries, read [API Ergonomics & Contract Governor](skills/api-ergonomics-and-contract-governor/SKILL.md). Enforce Pit-of-Success defaults (safe timeouts <=10s, automatic idempotent retries with full jitter, default bounded pagination), render illegal states unrepresentable via tagged discriminated unions and nominal branded types (`CustomerId`, `PaymentIntentId`), structure progressive disclosure across 3 tiers (1-liner common facade -> typed options bag -> raw transport/streaming power engine), and standardize all machine and network errors on RFC 9457 Problem Details with deterministic machine codes and remediation guidance. Audit contract records with `npx anti-slop-engineering contract audit <record.json> --json`.
23. **UI Craftsmanship, Copywriting & WCAG 2.2 Contrast Discipline:** When generating or modifying frontend user interfaces, styling, components, or marketing/product copy, read [UI & Copywriting Discipline](skills/ui-and-copy-discipline/SKILL.md). Enforce the 5 Craftsmanship Standards (C-1 Intentionality, C-2 Functional Completeness, C-3 Content-Driven Composition, C-4 Resilience & WCAG 2.2 Contrast, C-5 Performance & Motion). All visual techniques must pass the Purpose Test. Low-contrast text (<4.5:1 for normal, <3:1 for large), uniform pill buttons on inputs, decorative comment banners (`// =====`), generic AI gradient cliches (`from-blue-500 via-purple-500 to-pink-500`), and AI marketing hyperbole ("Unleash the power of AI") are strictly flagged. Verify contrast with `bunx anti-slop-engineering contrast "#FFFFFF" "#1E293B"` or `bunx anti-slop-engineering contrast --scan src/`.
24. **Apple Craft & Interaction Physics (Apple HIG & Design Engineering):** When building, refactoring, or auditing user interfaces, transitions, animations, or client state flows, read [Apple Craft & Interaction Physics](skills/apple-craft-and-interaction-physics/SKILL.md). Enforce the Four Physical Pillars: (1) Exhaustive UI State Matrix covering loading_skeleton, empty, partial_error, offline, and optimistic_rollback via Discriminated Unions with compile-time exhaustiveness; (2) Zero Cumulative Layout Shift (CLS = 0.000) via pre-reserved geometry for skeletons, images, dynamic error slots, and scrollbar-gutter: stable; (3) Interruptible Physics with velocity continuity ($F = -kx - cv$), immediate cancellation on user intent change, compositor-only transform/opacity, and epsilon-terminated rAF ($\epsilon \le 10^{-4}$); and (4) Keyboard & Focus Mastery with high-contrast :focus-visible rings (never unstyled outline: none), modal focus trap and restoration, roving tabindex for composite controls, and ARIA live regions. Audit records with `npx anti-slop-engineering apple-craft audit <record.json> --json`.
25. **Observability & SLO Architect (Google Monarch & Dapper Telemetry):** When designing telemetry architectures, instrumenting APIs, background queues, outbox workers, or database queries, read [Observability & SLO Architect](skills/observability-and-slo-architect/SKILL.md). Transform observability into proactive engineering: enforce OpenTelemetry by default with unbroken W3C `traceparent` (`00-<trace_id>-<span_id>-<flags>`) and `correlation_id` across every synchronous RPC, message broker hop (Kafka, SQS, RabbitMQ, BullMQ), Transactional Outbox, and SQLcommenter database span; mandate Google Monarch stream pre-aggregation discipline by strictly banning dynamic identifiers (`user_id`, `request_id`, `order_id`, `email`, raw URLs) in metric labels ($\prod |L_i| \le 1,000$) and collapsing unmatched 404 routes to `"__unmatched__"`; measure latencies exclusively via explicit-bucket Histograms with Trace Exemplars (never Gauge averages); emit automated RED metrics (Rate, Errors, Duration) for endpoints and USE metrics (Utilization, Saturation, Errors) for resources; and ban non-impact threshold alerts (e.g. CPU > 80%), gating production alerts strictly on Google SRE Multi-Window Multi-Burn-Rate Error Budget policies (14.4x 1h/5m for paging; 6.0x 6h/30m for ticketing). Audit telemetry records with `npx anti-slop-engineering observability audit <record.json> [--source <file>] --json`.
26. **Repo Memory & Invariant Steward (Architectural Memory & Zero-Drift Defense):** When designing architectures, conducting PR reviews, starting tasks at Gate 0, or evolving contracts, read [Repo Memory & Invariant Steward](skills/repo-memory-and-invariant-steward/SKILL.md). Prevent architectural amnesia across sessions: sync historical decision records into the compact Invariant Ledger (`.anti-slop/invariant-ledger.json` and `.anti-slop/invariant-ledger.toon`), enforce Gate 0 ingestion of active invariants before modifying governed paths, audit PRs for architectural drift (`bunx anti-slop-engineering steward drift --base HEAD`), and require formal Reassessment Triggers (`reassessment-trigger.json`) before modifying or superseding established invariants. Audit ledger records with `bunx anti-slop-engineering steward audit <file> --json`.
27. **Cognitive Bandwidth & Attention Economy Governor:** When communicating with users, drafting pull request descriptions, generating standalone deliverables, authoring documentation, or orchestrating multi-agent handoffs, read [Cognitive Bandwidth & Attention Governor](skills/cognitive-load-and-attention-governor/SKILL.md). Enforce scannability metrics ($TTP \le 20$ words, $W_{max} \le 60$ words, anchor density $\ge 3.0$ anchors per 100 words), terminal blocking-question placement, deliverable purity (zero opener/closer fluff), working memory bounding ($\le 5$ items), and non-regression discipline. Audit records with `bunx anti-slop-engineering attention --file <file> --json`.
28. **Tagore Engineering Discourse & Substance Guard:** When drafting, editing, or auditing pull request descriptions, git commit messages, Architectural Decision Records (ADRs), documentation, state notes, or agent reasoning traces, read [Tagore Engineering Discourse Guard](skills/tagore-guard/SKILL.md). Eliminate the 29 cataloged AI tells (significance inflation, copula avoidance, superficial -ing chains, rule-of-three, em-dash addiction, and promotional hype); mandate active engineering agency and empirical measurements; enforce the 8-Dimension Scoring Matrix with non-negotiable Mechanics ($\ge 35/50$) and Substance ($\ge 21/30$) subtotal floors ($\text{Total} \ge 56/80$); calibrate prose to repository ground truth via `.anti-slop/voice-profile.json`; and run the self-audit reflection loop before delivering. Audit with `bunx anti-slop-engineering tagore --file <file> --json`.

## Activation / modes

Select the relevant mode and follow the same gates:

- **BUILD:** new feature or behavior change. Baseline -> contract -> RED -> GREEN -> REFACTOR -> independent review -> evidence.
- **FIX:** reproduce observed bug first, fix smallest root cause, prove regression tests hold.
- **REVIEW:** read-only diff and repository-context audit; report findings with severity, evidence, and counterfactual.
- **CLEANUP:** establish an observable behavior baseline, isolate pure refactors from feature changes, prove no drift.
- **ATTENTION:** when communicating with human developers, writing pull request bodies, generating standalone artifacts, or compressing inter-agent handoff messages, follow [Cognitive Bandwidth & Attention Governor](skills/cognitive-load-and-attention-governor/SKILL.md) to eliminate cognitive slop.
- **NOTED_SLOP:** codify newly observed AI slop into a diagnostic catalog pattern, agent directive, and automated diff guard heuristic (see [CONTRIBUTING.md](CONTRIBUTING.md)).
- **DECIDE:** when premises, direct answers or long-term architecture choices are materially uncertain, follow [Decision Guard](skills/decision-guard/SKILL.md) before BUILD. Return to ordinary modes after a decision; skip the extra protocol for routine repairs.
- **ROOT-FIX:** when a symptom attracts scattered fixes or ownership is uncertain, follow [Root-Fix Gate](skills/root-fix-gate/SKILL.md) to establish the change boundary, then resume BUILD/FIX with regression tests.
- **FUTURE-SCALE:** when an architecture commitment would be expensive to reverse as the product evolves, follow [Future-Scale Gate](skills/future-scale-gate/SKILL.md). Skip routine reversible edits and avoid capacity theater.
- **PARANOID-ARCHITECT:** when building or reviewing systems against 10M concurrent user load, adversarial traffic, race conditions, hot-key contention, or zero-trust boundaries, follow [Paranoid Principal Architect](skills/paranoid-principal-architect/SKILL.md).
- **OBSERVABILITY-ARCHITECT:** when designing telemetry, instrumenting OpenTelemetry spans, emitting RED/USE metrics, or configuring Multi-Window Multi-Burn-Rate SLO alerting, follow [Observability & SLO Architect](skills/observability-and-slo-architect/SKILL.md).
- **INVARIANT-STEWARD:** when syncing architectural decisions into the living Invariant Ledger, ingesting constraints at Gate 0, checking PRs for architectural drift, or validating Reassessment Triggers, follow [Repo Memory & Invariant Steward](skills/repo-memory-and-invariant-steward/SKILL.md).
- **APPLE-CRAFT:** when designing or auditing client interfaces for 120Hz ProMotion interaction physics, CLS=0.000, exhaustive state matrices, interruptible spring transitions, and keyboard/screen reader accessibility, follow [Apple Craft & Interaction Physics](skills/apple-craft-and-interaction-physics/SKILL.md).
- **DETERMINISTIC-SIMULATION:** when verifying distributed protocols, concurrent actors, complex state machines, or parsers, follow [Deterministic Simulation & Property Testing](skills/deterministic-simulation-and-property-testing/SKILL.md).
- **PRIVACY-GATE:** when designing user data pipelines, processing personal identifiers, enforcing cryptographic erasure, or instrumenting telemetry egress, follow [Privacy & Data Lineage Gate](skills/privacy-and-data-lineage-gate/SKILL.md).
- **AST-SLOP:** when auditing type safety, eliminating type assertions, optimizing reducer complexity, or configuring Oxlint rules, follow [Type-Level & AST Slop Gate](skills/type-level-and-ast-slop-gate/SKILL.md).
- **API-GOVERNOR:** when designing public SDKs, library interfaces, CLI commands, or internal boundaries, follow [API Ergonomics & Contract Governor](skills/api-ergonomics-and-contract-governor/SKILL.md).
- **SYSTEM-DRIFT:** when auditing multi-surface applications for cross-route design system drift, component variant budgets, and keyboard focus ring suppression, follow [Design System Drift Guard](skills/design-system-drift-guard/SKILL.md).
- **CHROMA-DRIFT:** when auditing colors, themes, or gradients for cheerful saturation drift, OKLCH adherence, and category reflex band clichés, follow [Chromatic Drift Guard](skills/chromatic-drift-guard/SKILL.md).
- **HOUSE-TELL:** before writing code for any landing or UI surface, enforce the Gate 0 Pre-Commit Contract and contractually break at least two habits of the agent itself via [House-Tell Guard](skills/house-tell-guard/SKILL.md).
- **MOTION-RUNTIME:** when profiling or verifying animations, scroll flights, or canvas state machines under DPR 2 retina conditions and 4x CPU throttle, follow [Motion Runtime Guard](skills/motion-runtime-guard/SKILL.md).
- **ASSET-PROVENANCE:** when sourcing or embedding media, models, audio, or fonts, maintain cryptographic SHA-256 and open-license ledger tracking via [Asset Provenance Guard](skills/asset-provenance-guard/SKILL.md).
- **TAGORE:** when drafting, editing, or reviewing engineering prose, PR descriptions, commit messages, ADRs, state notes, or agent reasoning traces, eliminate the 29 cataloged tells, enforce mechanics (>=35/50) and substance (>=21/30) floors, and calibrate to repository ground truth via [Tagore Engineering Discourse Guard](skills/tagore-guard/SKILL.md).
- **AUDIT:** orchestrate all guards (Diff, SRE, AST Slop, Contrast, Privacy, Contract) into a structured, numbered markdown report `anti-slop/audit-NNN.md` via `bunx anti-slop-engineering audit`. Configure modes (`during`, `after`, `ask`) via `bunx anti-slop-engineering mode [during|after|ask]`.
- **INSTALL-AGENTS:** install and configure anti-slop skills across 14 AI coding agents via `bunx anti-slop-engineering install`. Upgrade in one shot via `bunx anti-slop-engineering update`.

For extensive audits, load [anti-pattern catalog](references/anti-pattern-catalog.md). For Google SRE discipline and distributed resilience patterns, load [google-sre-discipline](references/google-sre-discipline.md). For any test changes, load [test integrity policy](references/test-integrity.md). For a PR or merge request, load [PR review protocol](references/pr-review.md). For elevated permissions, sensitive code, network access, or deployment, load [security and execution boundaries](references/security-and-operations.md). For project-specific exceptions, load [judgment and exceptions](references/engineering-judgment.md). For community contributions, follow [contributor guidelines](CONTRIBUTING.md).

## The seven gates

### Gate 0: Discover; do not improvise the repo

- Read root and scoped instructions (AGENTS.md, CLAUDE.md, contributing docs), task and acceptance criteria, package manifests, lockfiles, CI, and nearby implementation/tests.
- Identify language/framework versions from the actual repo, not what is newest. Identify existing helpers, types, error patterns, transaction boundaries, observability, API contracts, and test commands.
- Read relevant open issues/PRs when available to avoid duplicates or fighting in-flight changes. Do not require network access to proceed when unavailable.
- Record working tree status; do not overwrite user changes, reset, stash, or modify unrelated files without authorization.
- Run an appropriate baseline build/test if feasible; label any existing failure as baseline, not caused by this change.
- For a derived-answer task, inspect existing direct sources before constructing proxies. For an architectural commitment, inspect the product's actual rendering, workload, operations and persistence needs instead of defaulting to a familiar provider bundle. Load `skills/decision-guard/SKILL.md` only when this uncertainty is material.
- For a proposed cross-layer patch, identify the first incorrect boundary and trace writes/reads before editing consumers. Load `skills/root-fix-gate/SKILL.md` when the same symptom would otherwise be patched in several places.
- For a foundational architectural commitment, classify credible future stresses and costly reversal points before using today's workload as an excuse to hard-wire the system. Load `skills/future-scale-gate/SKILL.md` only for consequential choices and verify an actual evolution path before claiming future readiness.
- For new projects, services, components, or SDK integrations, identify the official installer, CLI generator, and canonical starter boilerplate before writing code. Do not manually assemble configurations or directory trees from memory. Never generate unprompted documentation files, submission dossiers, or speculative third-party platform guides.

### Gate 1: Establish a change contract

Before editing, note: **what changes, what must not change, business invariants, external APIs, expected failures, data impacts, security implications, rollback plan, and proof requirements.** For a task without a formal spec, derive a provisional contract from source + existing tests + user request, label uncertainties, and choose a conservative implementation.

Create a tiny scope plan: target files, candidate reuse, test points, risk areas. Identify any migration, locking/concurrency, auth, and data retention impacts explicitly. Ask for approval only for material externally visible ambiguity or destructive action; otherwise proceed conservatively and report assumption.

### Gate 2: Lock the baseline tests without freezing legitimate evolution

- Inspect existing regression tests **before implementation**. Prefer independently specified expected outcomes.
- On bug fixes, write a failing reproduction first where practical. On new behavior, write tests for the agreed contract before implementation where practical.
- Existing assertions/fixtures/snapshots are protected: if a test fails after a change, investigate implementation/regression first. Never weaken assertions, rewrite golden values, remove coverage, mark skipped/xfail, or add exclusions merely to get green.
- Existing tests *may* change when the approved behavior genuinely changes, an assertion was incorrect, or a justified test refactor is necessary. Explain **old contract -> new contract**, cite the authority, show before/after behavior, and obtain independent review on semantics.
- Do not blindly ban test edits or insist on unit tests for every I/O interaction. Select unit/integration/contract/E2E based on risk. See [test integrity](references/test-integrity.md).

### Gate 3: Implement with minimum justified complexity

- **Official tooling over manual scaffolding:** When initializing an application, module, or SDK integration, invoke the official CLI installer / starter generator rather than manually typing out build configurations (`tsconfig.json`, `package.json`, `pyproject.toml`, Dockerfiles, etc.).
- **Strict latest stable dependency pinning:** When adding new dependencies or SDKs, always query the package manager or registry to install the latest stable release (e.g. `bun add <pkg>@latest`, `uv add <pkg>`). Pin versions strictly in manifests and generate valid lockfiles; never rely on pre-cutoff memory.
- **Frontend taste & zero dev-notes leakage:**
  - Strip out all internal developer/agent annotations, reminders, or mock warnings (`"TODO: Wire backend"`, `"Note: Mock data"`, `"Agent notice:"`) from user-visible DOM/JSX.
  - Practice visual restraint: prevent crowded navbars, multi-row icon spam, or redundant controls in headers. Maintain clean visual hierarchy, balanced padding, and purposeful negative space.
  - Enforce concise microcopy: avoid walls of explanatory text, repetitive instructions for obvious user actions, and defensive disclaimers. Every string in the UI must be concise and production-grade.
- **Anti-logorrhea in code & interfaces:** Avoid writing unnecessary boilerplate, sprawling repetitive wrappers, or comments that merely narrate obvious syntax. Never bloat code or copy just to feel comprehensive.
- **Zero-obviousness & anti-truism:** Reject code comments that narrate obvious syntax (`// return response`, `// increment i`, `// check if null`), tautological docstrings that merely restate symbol names, patronizing UI microcopy under obvious inputs (`"Please enter your email"` under an Email field), and documentation padded with trivial prerequisite truisms ("requires internet and keyboard"). High engineering discipline favors silence over noise.
- Modify the existing abstraction whenever it fits; do not add parallel services, helpers, frameworks, compatibility layers, or configurable interfaces without a current need.
- Keep business logic separate from transport and presentation when supported by the architecture; avoid both god objects and needless micro-files.
- Use existing dependencies and repo conventions. New dependency requires clear functionality, maintenance, license, security, and bundle/runtime case.
- Maintain error semantics, resource cleanup, cancellation, idempotency, state isolation, data validation, correct authorization, transactions, and backwards compatibility where required.
- Avoid broad formatting/restructuring in functional PRs; remove incidental scaffolding that adds no value. Do not delete working behavior to make the diff smaller.

### Gate 4: Verify beyond green tests

- Run targeted tests and impacted full-suite checks supported by repo; report commands and outcomes verbatim or as reproducible summaries.
- Inspect changed tests against the baseline; manually verify independently expected outcomes. Test the old failure, the new behavior, negative paths, and nearby regressions.
- Exercise boundary tests relevant to change: contract/integration, concurrency, migrations, browser flow, performance, security and accessibility where applicable. Prefer real integration evidence over test doubles at critical seams.
- Treat test coverage, lint, snapshot updates, and static-scan results as *signals*, never proof. Use mutation tests for fragile business rules when available.
- If tools/environment prevent verification, say **NOT VERIFIED**; list exact blockers and do not claim completion.

### Gate 5: Audit the diff as a skeptical reviewer

Run `git diff --check` and inspect `git diff --stat`, changed files, changed assertions, added dependencies, config, and documentation. Triage can be executed via high-performance native Rust/Go microservices or portable Python scripts:

```bash
# Native Rust Engine (SHIT Boundary Interceptor & Senior Dev Ladder):
bunx anti-slop-engineering rust triage
bunx anti-slop-engineering rust shit-check --diff patch.diff

# Go High-Throughput SRE Engine (KISS nesting, DRY token window, Toil & Error Budget):
bunx anti-slop-engineering toil audit
bunx anti-slop-engineering toil stream

# Zero-dependency Python Core Fallback:
python scripts/diff_guard.py --base HEAD --json
python scripts/sre_guard.py --base HEAD --strict --json

# In-Flight Real-Time Action Execution Guard:
bunx anti-slop-engineering exec status
bunx anti-slop-engineering exec check-action --tool <tool> --args '<json>'
bunx anti-slop-engineering cases
```

Replace `origin/main` with your actual target branch; if unavailable, compare with a known commit using `--base HEAD`. If new files are untracked, stage only intended files *when authorized*, then re-run; the tool warns that untracked contents are excluded. **Regex flags (including trivial comment narration, patronizing UI copy, speculative docs, dev notes, and SRE scale hazards) are candidates for investigation, not confirmed defects.** The tool neither runs tests nor performs SAST.

Ask explicitly: Could a smaller design do the same thing (KISS)? Did I create two sources of truth (DRY)? Are all parameters and options actively used (YAGNI)? Will retries trigger thundering herds or retry storms under scale (SCALE)? Did I silently expand scope?

### Gate 6: Evidence and release decision

Use [PR review protocol](references/pr-review.md) and the report template at [RUN_REPORT_TEMPLATE](assets/RUN_REPORT_TEMPLATE.md).

- **BLOCK:** demonstrated critical regression; authorization/security/privacy failure; disabled or falsified tests without approved change contract; broken build; destructive migration without safety plan.
- **REWORK:** meaningful duplication, needless architecture, unjustified new dependency, test-only-for-implementation, unexplained contract drift, unreviewable mixed changes.
- **REVIEW:** large coherent changes, cosmetic smells, static heuristics, deliberate test updates or exceptions requiring context.
- **PASS:** requirements met with observable evidence; no unresolved BLOCK or REWORK, risks and exceptions documented. PASS is not a warranty.

Before proposing merge, report: intent, changed files, exact test evidence, baseline test delta, remaining uncertainty, findings, and decision. Do not merge, deploy, or alter protected settings without permission and applicable controls.

## Non-negotiable anti-cheating rules

- Do not change a test's expected output to match the observed buggy output unless the new output is explicitly authorized by product contract.
- Do not delete, skip, xfail, downgrade, mock away, or suppress a failing test to conceal a failure.
- Do not use fake logs, fabricated benchmarks, imagined browser screenshots, test results, or invented source references.
- Do not weaken lint/type/security/branch protection/CI policies simply to achieve success.
- Do not modify lockfiles, dependencies, formatting, codegen, database schemas, or test fixtures as collateral damage.
- Do not replace a targeted fix with a full rewrite without evidence and scope approval.
- Do not manually scaffold project skeletons or hand-stitch configuration files when official language, framework, or SDK installers and boilerplates are available.
- Do not pin outdated, deprecated, or guessed dependency versions from model training memory; always resolve and enforce the latest stable version from the official registry.
- Do not render developer notes, agent reminders, mock disclaimers, or architectural apologies into user-facing JSX/HTML views.
- Do not overcrowd headers, navbars, or dashboards with uncurated icons, redundant buttons, or gratuitous widgets that lack visual hierarchy.
- Do not bloat UI copy with walls of explanatory text, defensive disclaimers, or verbose narration of obvious UI controls.
- Do not write trivial syntax-narration comments (e.g. `// return result`, `// increment counter`, `// check null`) or tautological docstrings that merely restate symbol names.
- Do not add patronizing UI microcopy or obvious instructional labels underneath self-evident controls (e.g. `"Please enter your email"`, `"Click here to submit"`).
- Do not pad documentation, READMEs, or setup guides with obvious truisms, trivial prerequisite lists, or tautological summaries.
- Do not violate the Direct Payload Invariant: never write affordance narration (explaining how to click, expand, play, scroll, or copy standard controls), conversational preambles ("The following section discusses..."), bilingual title-stacking (e.g. `Term · الترجمة`), buzzword inflation (calling screencasts "Live Interactive Demos"), or mechanical hand-holding in documentation and code.
- Do not generate speculative submission dossiers (e.g., `docs/*SUBMISSION*.md`, `docs/*DOSSIER*.md`) or invent publishing guides for unrequested third-party platforms.
- Do not cite dead, deprecated, or hallucinated platform URLs (e.g., `platform.openai.com/plugins`).
- Do not sprawl the repository with ceremonial markdown files or pad READMEs with marketing filler, fake prompt examples, or repetitive note callouts.
- Do not use arbitrary `sleep()` or hardcoded delay loops as a synchronization band-aid for async races or flaky tests.
- Do not retry failing network operations without exponential backoff and randomized full jitter.
- Do not spawn unbounded parallel tasks, workers, or promises without explicit concurrency limiters or backpressure signals.
- Do not swallow errors silently with empty `except: pass` or `catch {}` blocks without structured logging or metric counters.
- Do not introduce speculative parameters (`_unused_param`, `future_kwargs`), dead feature toggles (`if False:`), or unreferenced extension points.
- Do not duplicate domain invariants, validation rules, or error models across multiple modules; maintain a single authoritative source of truth.
- Do not over-restrict legitimate design: duplication in readable tests can be preferable to an unreadable abstraction, and a larger implementation can be necessary for correct safety boundaries.

## In-flight task directives and execution control

Apply the Stop Ladder to balance task responsibility and boundary enforcement:
1. Understand current responsibility (explicit contract, affected callers, data migrations).
2. Start with a direct solution (existing codebase helpers, platform built-ins, standard library).
3. Expand only to close concrete gaps (supported inputs, real obligations).
4. Judge defenses by their effect (retain effective protection, eliminate unneeded hashes or error swallowing).
5. Verify the result and finish (no circular verification or redundant multi-agent loops).

Directive syntax:
```text
$anti-slop [mode] [level] [files=...] [hash=...] [deps=...] [agents=N] -- [task]
```

- `mode`: `change` (default write), `review` (read-only), `answer` (read-only), `monitor` (read-only), `unconfirmed` (passive).
- `level`: `guard` (enforcing block), `watch` (advisory warning), `off` (disabled).
- `files=path1|path2|dir/**`: file boundary lock. Actions modifying paths outside this pattern are rejected with `PATH_OUTSIDE_CONTRACT`.
- `hash=deny|ask|allow`: cryptographic checksum and hash policy.
- `deps=deny|ask|allow`: dependency installation policy. When `deps=ask`, generates single-use runner tickets.
- `agents=N`: concurrent subagent budget.

## Deliverable contract

For each implementation/review, produce a concise report in this order: **Outcome; Scope; Behavior preserved/changed; Verification (commands + results); Findings with exact file/line; Test modifications with rationale; Risks/limitations; Merge recommendation.** If available, distinguish baseline failures from new failures. Use `NOT RUN` and `UNKNOWN` literally when applicable.

The [catalog](references/anti-pattern-catalog.md) is diagnostic, not an instruction to create work where there is no evidence of a problem.
