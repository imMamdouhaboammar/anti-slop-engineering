# AGENTS.md

> Operating rules and behavioral guidelines for AI coding agents working on this repository.

## Repository Mission

Anti-Slop Engineering is an open-source playbook, agent skill, and lightweight triage guard for preventing code bloat, test-oracle erosion, security shortcuts, and uncontrolled complexity in AI-assisted software development.

## Directives for AI Agents

1. **Follow the Seven Gates:** You MUST review and adhere to `SKILL.md` before generating or modifying any code in this repository.
2. **Preserve Zero-Dependency Mandate:** `scripts/diff_guard.py` and `scripts/sre_guard.py` MUST remain compatible with standard library Python (>=3.9) without requiring `pip install` or external packages.
3. **Protect the Test Suite:**
   - Run tests using `python3 -m unittest discover -s tests -v`.
   - Never weaken assertions, delete tests, or add skips to bypass failures.
   - All tests in `tests/test_diff_guard.py` and `tests/test_sre_guard.py` must remain green.
4. **Self-Diff Verification:** Run `python3 scripts/diff_guard.py --base HEAD` and `python3 scripts/sre_guard.py --base HEAD` before concluding any work session.
5. **No Hallucinated Pass Badges:** Only report tests and checks that were executed and verified against real terminal outputs.
6. **The Canonical Grounding & Authority Invariant (Official Boilerplate & Generators First):** Never improvise project scaffolding, directory layouts, configuration files, or dependencies from LLM statistical memory when an official CLI installer (`uv init`, `cargo init`, `bun create`) or package registry exists. Always ground against official upstream tooling.
7. **The Dependency Determinism Invariant (Strict Latest Stable Pinning):** When adding new libraries, frameworks, or SDKs, strictly query the registry and pin the latest stable release. Never guess obsolete versions based on training cutoff dates.
8. **The Audience Boundary & Zero Meta-Leakage Invariant (Zero Dev-Notes Leakage in UI):** Enforce complete physical separation between internal engineering meta-context (agent commentary, developer notes, TODOs, mock data banners, system instructions) and external user-facing surfaces (UI/DOM, API contracts, production logs, public documentation).
9. **The Visual Restraint & Single-Purpose Density Invariant (Layout Restraint & Noise Reduction):** Every UI component, navbar item, button, icon, and card must justify its existence through a distinct, non-redundant primary user objective. Ban cosmetic clutter masquerading as functionality (overcrowded headers/navbars, multi-row icon spam, repetitive buttons, nested cards, ornamental badges). Prioritize purposeful white space, hierarchy, and quiet functional utility.
10. **The Anti-Logorrhea & Functional Economy Invariant (Zero Fluff in Code & UI):** Strip away conversational chatter, redundant text blocks, over-explanatory tooltips, and obvious code narration. Let clean interfaces and self-explanatory code speak for themselves.
11. **The Speculative Artifact Prohibition Invariant (Zero Hallucinated Scaffolding & File Sprawl):** Never generate unrequested documentation files (e.g., submission dossiers, third-party platform publishing guides, fake reviewer packets like `docs/OPENAI_SUBMISSION.md`) or invent distribution workflows. Document only what is real, requested, and verifiable in the repository. Keep READMEs and docs lean, high-signal, and factual—no marketing filler or ceremonial note callouts.
12. **The Zero-Obviousness & Anti-Truism Doctrine (Silence Over Noise):** High engineering discipline values silence over noise. Never emit code comments that narrate obvious syntax (e.g. `// increment count`, `// return result`, `// check if null`), tautological docstrings that merely restate symbol names, patronizing UI microcopy under self-evident controls (e.g. `"Please enter your email"` under an Email field), or ceremonial documentation truisms (e.g. prerequisite inflation like "requires computer, internet, and text editor"). If a concept is obvious to a competent engineer or user, do not write it.
13. **The Direct Payload & Zero Affordance Narration Mandate (Direct Technical Transition):** Enforce the Direct Payload Invariant across all documentation, markdown files, PR descriptions, and UI copy. Transition directly from domain headers to payloads (tables, code blocks, media, schemas) with zero meta-preambles ("The following table outlines...", "In this section we will explore..."), zero affordance instructions ("click to play/expand/copy/scroll", "watch here without leaving the page"), zero mechanical hand-holding ("open your terminal", "save the file"), zero bilingual title-stacking (`English · عربي`), and zero buzzword inflation (calling screencasts "Live Interactive Demos"). If an affordance is standard (player, chevron, copy button, table, link), never explain how to use it.
14. **The Google Site Reliability Engineering (SRE) Mandate:** Strictly enforce KISS, DRY, YAGNI, and Fix Issues at Scale across all changes:
    - **KISS:** Maintain control flow nesting <=4 levels. Decompose functions >80 lines into cohesive, single-responsibility units. Remove trivial wrapper hops.
    - **DRY:** Consolidate duplicate code blocks (>=4 lines) and duplicate validation patterns into canonical modules. Single source of truth is mandatory.
    - **YAGNI:** Ban speculative parameters (`_unused_param`, `future_kwargs`), dead branches (`if False:`), and placeholder comments (`TODO(future)`). Build for current verified contracts only.
    - **Fix Issues at Scale:** Eliminate operational toil through automation. Never use flat retries or blind `sleep()` synchronization band-aids; implement exponential backoff with full jitter. Bound concurrency with pools or semaphores. Ban silent exception swallowing (`except Exception: pass`). Enforce idempotency on state-changing operations.
15. **The Clean-Room Senior Dev Ladder & SHIT Interceptor Mandate (Ponytail, STS, Boring Engineering):**
    - Intercept the four SHIT hazards: Scope creep (`S`), Hypothetical hardening/unread companion hashes (`H`), Intent violation (`I`), and Task thrashing (`T`).
    - Climb the Senior Dev Ladder before generating code: verify necessity, reuse codebase helpers, prioritize standard library built-ins, prefer native platform features, use existing dependencies, and emit minimal sufficient code.
    - **Name the Built-in:** Never hand-roll primitives provided by the platform/runtime (`crypto.randomUUID()`, `URLSearchParams`, `structuredClone()`, etc.).
    - **Practical DRY 3-Point Barrier:** Abstract only with >=2 real existing call-sites, identical mutation requirements, and clean non-conjunction naming.
    - **Polyglot Test Discipline:** All tiers (`python3 -m unittest discover -s tests -v`, `cargo test` in `services/anti-slop-rust`, `go test -v ./...` in `services/toil-guard-go`) must remain 100% green.
16. **The Decision Guard Mandate:** Before committing to a consequential architecture, vendor, database, or derived-metric approach, read `skills/decision-guard/SKILL.md`. Search for an existing direct answer, distinguish the user objective from the proposed method, compare independent alternatives and operational horizons, and interrupt obsolete work when new evidence changes its premise. Do not apply its full decision workflow to narrow bug fixes or routine changes.

