---
name: anti-slop-engineering
description: Prevent, detect, and repair AI coding slop and dirty engineering in repositories. Use for planning features, writing code, changing tests, reviewing pull requests, refactoring, hardening CI, debugging regressions, or auditing agent-generated changes. Enforces behavioral contracts, focused diffs, test integrity, repo conventions, security boundaries, and evidence-based completion.
author: Mamdouh Aboammar <mamdouhfces1997@gmail.com>
license: MIT
metadata:
  version: "0.1.3"
  focus: "engineering-discipline"
  repository: "https://github.com/imMamdouhaboammar/anti-slop-engineering"
---

# Anti-Slop Engineering

**Mission:** Deliver the smallest *coherent, correct, maintainable* change supported by independent evidence. Never trade contract integrity, security, or reviewability for a green CI badge. This skill applies to human and AI-authored changes equally.

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

## Activation / modes

Select the relevant mode and follow the same gates:

- **BUILD:** new feature or behavior change. Baseline -> contract -> RED -> GREEN -> REFACTOR -> independent review -> evidence.
- **FIX:** reproduce observed bug first, fix smallest root cause, prove regression tests hold.
- **REVIEW:** read-only diff and repository-context audit; report findings with severity, evidence, and counterfactual.
- **CLEANUP:** establish an observable behavior baseline, isolate pure refactors from feature changes, prove no drift.

For extensive audits, load [anti-pattern catalog](references/anti-pattern-catalog.md). For any test changes, load [test integrity policy](references/test-integrity.md). For a PR or merge request, load [PR review protocol](references/pr-review.md). For elevated permissions, sensitive code, network access, or deployment, load [security and execution boundaries](references/security-and-operations.md). For project-specific exceptions, load [judgment and exceptions](references/engineering-judgment.md).

## The seven gates

### Gate 0: Discover; do not improvise the repo

- Read root and scoped instructions (AGENTS.md, CLAUDE.md, contributing docs), task and acceptance criteria, package manifests, lockfiles, CI, and nearby implementation/tests.
- Identify language/framework versions from the actual repo, not what is newest. Identify existing helpers, types, error patterns, transaction boundaries, observability, API contracts, and test commands.
- Read relevant open issues/PRs when available to avoid duplicates or fighting in-flight changes. Do not require network access to proceed when unavailable.
- Record working tree status; do not overwrite user changes, reset, stash, or modify unrelated files without authorization.
- Run an appropriate baseline build/test if feasible; label any existing failure as baseline, not caused by this change.
- For new projects, services, components, or SDK integrations, identify the official installer, CLI generator, and canonical starter boilerplate before writing code. Do not manually assemble configurations or directory trees from memory.

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

Run `git diff --check` and inspect `git diff --stat`, changed files, changed assertions, added dependencies, config, and documentation. If Python 3 and git are available, optional read-only triage:

```bash
python /path/to/anti-slop-engineering/scripts/diff_guard.py --repo . --base "$(git merge-base HEAD origin/main)" --json
```

Replace `origin/main` with your actual target branch; if unavailable, compare with a known commit using `--base HEAD`. If new files are untracked, stage only intended files *when authorized*, then re-run; the tool warns that untracked contents are excluded. **Regex flags are candidates for investigation, not confirmed defects.** The tool neither runs tests nor performs SAST.

Ask explicitly: Could a smaller design do the same thing? Did I create two sources of truth? Could I explain each added file? Would existing consumers or tests now change behavior? Can a reviewer understand the causal chain? Did I silently expand scope?

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
- Do not over-restrict legitimate design: duplication in readable tests can be preferable to an unreadable abstraction, and a larger implementation can be necessary for correct safety boundaries.

## Deliverable contract

For each implementation/review, produce a concise report in this order: **Outcome; Scope; Behavior preserved/changed; Verification (commands + results); Findings with exact file/line; Test modifications with rationale; Risks/limitations; Merge recommendation.** If available, distinguish baseline failures from new failures. Use `NOT RUN` and `UNKNOWN` literally when applicable.

The [catalog](references/anti-pattern-catalog.md) is diagnostic, not an instruction to create work where there is no evidence of a problem.
