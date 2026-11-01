# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Decision Guard agentic module for direct-answer discovery, assumption checks, independent architecture comparison, operational horizons and premise-changing interruptions.
- Zero-dependency `decision audit` CLI check, example record, semantic evaluation cases and regression tests. Structural validation does not certify decision correctness.

## [1.0.0] - 2026-10-31

### Added
- **General Availability (GA) 1.0.0 Release:**
  - Production-ready polyglot architecture unifying zero-dependency Python stdlib guards, native Rust AST & Senior Dev engines, and native Go Google SRE toil engines.
  - Automatic Agent Skill onboarding: npm/bun `postinstall` hook runs `npx skills add imMamdouhaboammar/anti-slop-engineering` to arm coding agents across Claude, Cursor, Codex, OpenCode, and Antigravity automatically.
  - Multi-engine CLI distribution (`bin/cli.js`) published to npm registry as `anti-slop-engineering` with binary fallbacks and lean production packaging (`dist/`).
  - Native microservice daemons for continuous development loop integration: Axum HTTP server (`:9091`) and Go SRE HTTP server (`:9092`) with Prometheus metrics and healthz checks.
  - Complete verification across polyglot test pyramid: 32 Python tests, 10 Rust unit tests, 19 Go unit tests, and 0 diff/SRE violations.

## [0.4.0] - 2026-10-30

### Added
- **Native Rust Microservice Engine (`services/anti-slop-rust` & CLI `bunx anti-slop-engineering rust`):**
  - High-performance, memory-safe engine inspired by clean-room reverse-engineering analysis of `DietrichGebert/ponytail`, `lennney/stop-that-shit`, `ilindaniel/ponytail-lite`, and `alvindemesadev/boring-engineering`.
  - **SHIT Boundary Interceptor:** Halts Scope creep (`S`), Hypothetical hardening/unread companion hashes (`H`), Intent violation (`I`), and Task thrashing (`T`).
  - **Senior Dev Ladder & Name-The-Built-In Auditor:** Audits code additions for platform built-ins (`crypto.randomUUID()`, `URLSearchParams`, `structuredClone()`) and flags hand-rolled reimplementations.
  - **Practical DRY 3-Point Barrier:** Gates abstractions on multi-consumer necessity and non-conjunction naming.
  - **Axum Microservice Daemon:** Provides high-speed continuous AST triage via HTTP endpoints `/health`, `/v1/triage`, `/v1/shit-check`, and `/v1/ladder-audit`.
  - Full Rust unit tests (`cargo test`) with 100% green status.
- **Native Go SRE Microservice Engine (`services/toil-guard-go` & CLI `bunx anti-slop-engineering toil`):**
  - High-throughput concurrent engine for Google SRE metric verification and live git diff telemetry.
  - **KISS Complexity Analyzer:** Verifies control flow nesting depth (<=4) and function line bounds (<=80 lines).
  - **Cross-File Sliding-Window DRY Scanner:** Detects duplicate logic blocks (>=4 lines) across files using SHA-256 rolling windows.
  - **Toil & Scale Detector:** Flags blind sleep synchronization, fixed retry loops without exponential backoff + jitter, and diagnostic black hole error swallowing.
  - **SLI / SLO Error Budget Engine:** Computes slop index metrics and real-time error budget consumption.
  - **Production Go HTTP Daemon:** Exposes `/healthz`, Prometheus `/metrics`, `/v1/audit`, and `/v1/sli-budget` endpoints with graceful shutdown.
  - 100% standard library Go implementation with zero third-party dependency bloat.
  - Full Go unit tests (`go test -v ./...`) with 100% green status.
- **Clean-Room Reconnaissance Dossier (`references/clean-room-recon.md`):**
  - Complete architectural mapping, taxonomy synthesis, and attribution ledgers for Ponytail, Stop-That-Shit, Ponytail-Lite, and Boring-Engineering following the `/rea` protocol.
- **Unified Multi-Engine CLI & Build Automation (`bin/cli.js` & `Makefile`):**
  - Subcommands `rust`, `toil`, `serve-rust`, `serve-go`, `build`, and transparent fallback to standard library Python guards.
  - Makefile targets `build-rust`, `build-go`, `build-services`, `test-rust`, `test-go`, `test-all`, `check-all`.
- **44 Total Verified Tests Across 3 Runtimes:**
  - 30 Python unit tests + 7 Rust unit tests + 7 Go unit tests passing green.

## [0.3.0] - 2026-10-30

### Added
- **Google Site Reliability Engineering (SRE) Guard Engine (`scripts/sre_guard.py` & CLI `bunx anti-slop-engineering sre`):**
  - Standalone and integrated SRE static analysis engine enforcing Google SRE's four foundational principles: Simplicity (KISS), Single Source of Truth (DRY), Anti-Speculation (YAGNI), and Fixing Issues at Scale (Eliminating Toil).
  - **KISS Enforcer:** Detects cyclomatic/indentation nesting >4 levels (`KISS_DEEP_NESTING`) with bracket-aware line parsing, and functions exceeding 80 lines (`KISS_FUNCTION_BLOAT`).
  - **DRY Enforcer:** Detects duplicated logic blocks across codebase files (>=4 lines) using sliding-window hashing (`DRY_CODE_DUPLICATION`) while permitting DAMP in test fixtures.
  - **YAGNI Enforcer:** Detects speculative placeholder comments (`YAGNI_SPECULATIVE_COMMENT`), dead feature flags like `if False:` (`YAGNI_DEAD_SPECULATIVE_FLAG`), and unreferenced parameters (`YAGNI_SPECULATIVE_PARAMETER`).
  - **Fix Issues at Scale Enforcer:** Detects flat/unbounded retries without exponential backoff & jitter (`SCALE_UNBOUNDED_OR_FLAT_RETRY`), sleep synchronization band-aids (`SCALE_SLEEP_BAND_AID`), unbounded concurrency mapping (`SCALE_UNBOUNDED_CONCURRENCY`), silent exception swallowing causing operational toil (`SCALE_TOIL_ERROR_SWALLOW`), and misleading health check probes (`SCALE_MISLEADING_HEALTH_CHECK`).
  - CLI flags: `--strict` (exit code 2 on blockers), `--files`, `--max-nesting`, `--min-dup-lines`, `--max-function-lines`, `--json`.
- **Diff Guard SRE Heuristics (`scripts/diff_guard.py`):**
  - Integrated SRE pattern checks (`SRE_SCALE_FLAT_RETRY`, `SRE_SCALE_SLEEP_BAND_AID`, `SRE_SCALE_UNBOUNDED_CONCURRENCY`, `SRE_YAGNI_SPECULATIVE_CODE`, `SRE_YAGNI_DEAD_FLAG`) into standard pre-commit diff triage.
  - Modularized `scan` into single-responsibility subroutines `audit_file_metadata` and `audit_patch_lines` (fulfilling KISS and DRY).
- **Google SRE Discipline Playbook (`references/google-sre-discipline.md`):**
  - Added comprehensive architectural guide covering Simplicity (Google SRE Book Ch. 9), Single Source of Truth, Anti-Speculation, and Fixing Issues at Scale (Google SRE Book Ch. 5: Eliminating Toil), with distributed resilience patterns (exponential backoff with full jitter, circuit breakers, bounded concurrency, idempotency, and liveness vs readiness probes).
- **12 New SRE Anti-Pattern Catalog Entries (201 -> 213 in `references/anti-pattern-catalog.md`):**
  - Section N: Google SRE Invariants (`SRE-01` through `SRE-12`).
- **SKILL.md & AGENTS.md Constitution Updates:**
  - Added Operating Priority 13, Gate 5 SRE triage, and Agent Directive 14 mandating Google SRE discipline.
- **Comprehensive Test Suite Expansion:**
  - Added `tests/test_sre_guard.py` and updated `tests/test_diff_guard.py`, expanding test coverage to 30 unit tests (100% passing).

## [0.2.1] - 2026-10-17

### Added
- **The Direct Payload & Zero Affordance Narration Invariant:** Codified a universal, general doctrine in `SKILL.md` (Operating Priority 12, Gate 3, Gate 5, Non-Negotiable Rules) and `AGENTS.md` (Directive 13) eradicating the entire class of meta-preambles, affordance narration, and ceremonial mechanical hand-holding. Mandates direct transition from domain headers to technical payloads (code, tables, media, schemas) with zero transitional conversational fluff, zero affordance coaching, and zero dual-language title-stacking.
- **The Direct Payload & Affordance Principle in Engineering Judgment:** Added foundational trade-off guidance in `references/engineering-judgment.md` establishing that any sentence explaining a tool's mechanism instead of its domain value is pure cognitive debt.
- **201st Anti-Pattern Catalog Entry (`references/anti-pattern-catalog.md`):**
  - `REV-19 | Affordance narration, meta-preambles & mechanical hand-holding (The Over-Clarification Syndrome)`: Systematically diagnoses and remedies affordance narrations (explaining how to play videos, expand accordions, copy snippets), conversational preambles ("The following table outlines..."), bilingual title-stacking, and buzzword inflation for mundane artifacts.
- **Automated Diff Guard Detection (`scripts/diff_guard.py`):**
  - `META_PREAMBLE_AND_AFFORDANCE_NARRATION`: Generalized heuristic regex scanning markdown and documentation files to detect conversational preambles, affordance narrations ("click to expand", "watch without leaving page", "copy to clipboard"), and bilingual title-stacking (`English · عربي`).
- **Comprehensive Unit Tests (`tests/test_diff_guard.py`):** Added tests covering affordance narration, conversational preambles, and clean direct payloads (all 16 unit tests passing).

## [0.2.0] - 2026-10-17

### Added
- **The Zero-Obviousness & Anti-Truism Doctrine:** Codified a strict engineering discipline in `SKILL.md` (Operating Priority 12, Gate 3, Gate 5, and Non-Negotiable Anti-Cheating Rules) and `AGENTS.md` (Directive 12) banning trivial syntax narration in comments, tautological docstrings, patronizing UI microcopy, and ceremonial documentation truisms. High engineering discipline values silence over noise.
- **The Non-Obviousness Test in Engineering Judgment:** Added explicit trade-off guidance in `references/engineering-judgment.md` stating that comments and UI text are justified ONLY if an educated engineer or user cannot deduce the implementation or intent from the types, names, UI affordances, and tests alone.
- **200 Diagnostic Anti-Pattern Milestone (+4 New Patterns):** Reached a landmark 200 cataloged patterns in `references/anti-pattern-catalog.md`:
  - `SIM-16 | Tautological docstrings and symbol restatement`: Comments or docstrings merely restating function/variable names without adding invariants or constraints.
  - `SIM-17 | Syntax play-by-play & obvious code narration`: Line-by-line syntax commentary (`// increment counter`, `// return result`, `// check if null`).
  - `UI-17 | Patronizing UI microcopy & label restatement`: Redundant instructions beneath obvious controls (`<small>Please enter your email</small>`, `Click here to submit`).
  - `REV-18 | Ceremonial documentation truisms & prerequisite inflation`: Padding setup guides with trivial prerequisites ("requires computer and keyboard") and obvious truisms.
- **Automated Diff Guard Detection (`scripts/diff_guard.py`):**
  - `TRIVIAL_COMMENT_NARRATION`: Detects syntax narration comments in code files (`// return result`, `// increment i`, `# initialize state`, `# check if null`), while preserving valid invariant comments.
  - `PATRONIZING_UI_COPY`: Flags obvious, condescending instructions in JSX/HTML templates (`"Please enter your..."`, `"Click here to..."`).
- **Comprehensive Unit Tests (`tests/test_diff_guard.py`):** Added `test_flags_patronizing_ui_microcopy`, `test_flags_trivial_comment_narration`, and `test_permits_meaningful_invariant_comments` (all 14 unit tests passing).

## [0.1.5] - 2026-10-17

### Added
- **Zero Speculative Documentation & File Sprawl Mandate:** Enforced strict prohibitions in `SKILL.md` (Priority 11, Gate 0, and Anti-Cheating Rules) and `AGENTS.md` (Directive 11) forbidding agents from inventing unrequested third-party platform submission guides, reviewer packets, or distribution dossiers (e.g., claiming tools are OpenAI ChatGPT plugins, fabricating `docs/OPENAI_SUBMISSION.md`, or linking to dead submission portals).
- **Automated Diff Guard Detection (`scripts/diff_guard.py`):**
  - `SPECULATIVE_DOC_CANDIDATE`: Flags unrequested submission dossiers and reviewer packets created in `docs/` (`docs/*submission*.md`, `docs/*dossier*.md`, `docs/*reviewer_packet*.md`).
  - `HALLUCINATED_DOC_URL`: Detects deprecated or hallucinated plugin submission URLs (such as `platform.openai.com/plugins` or `developers.openai.com/plugins`).
- **3 New Anti-Pattern Catalog Entries (193 -> 196):**
  - `REV-15 | Speculative platform submission & hallucinated distribution guides`: Unprompted creation of third-party submission dossiers and fake reviewer packets with dead URLs.
  - `REV-16 | Documentation file sprawl & markdown inflation`: Sprawling the repository with dozens of unprompted, superficial markdown files that nobody asked for.
  - `REV-17 | Documentation logorrhea & filler sections`: Stuffing READMEs and docs with excessive note callouts, speculative marketing copy, redundant disclaimers, and fake prompt examples.
- **Unit Test Coverage:** Added `test_flags_speculative_submission_dossier_files` and `test_flags_hallucinated_deprecated_platform_urls` in `tests/test_diff_guard.py` (all 11 unit tests passing).

## [0.1.4] - 2026-10-17

### Added
- **Community Noted Slop Contribution Policy (`CONTRIBUTING.md`):** Established a comprehensive protocol for developers and researchers to contribute observed AI slop patterns via GitHub Issues (Path A: Report Only) or Pull Requests (Path B: Problem + Solution).
- **Dedicated Noted Slop Issue Template (`.github/ISSUE_TEMPLATE/noted_slop.yml`):** Form template capturing observed code diffs, agent/model context, negative impact analysis, and proposed remediation.
- **PR Template Checklist for Anti-Patterns (`.github/PULL_REQUEST_TEMPLATE.md`):** Added specific verification steps for catalog entry allocation, agent directive updates, and diff guard heuristics.
- **CLI `contribute` Command (`bin/cli.js`):** Run `npx anti-slop-engineering contribute` or `bunx anti-slop-engineering contribute` to view contribution guidelines and quick links.
- **NOTED_SLOP Mode (`SKILL.md`):** Added explicit activation mode for AI coding agents to codify newly observed slop into catalog patterns, directives, and diff guard heuristics.
- **Documentation & Intake Links:** Added prominent "Contributing Noted Slop" section and navigation links in `README.md`.

## [0.1.3] - 2026-10-17

### Added
- **UI Anti-Slop Discipline & Zero Dev-Notes Leakage:** Enforced strict prohibitions in `SKILL.md` (Priorities 9 & 10, Gate 3) preventing agents from leaking internal developer notes, TODOs, mock data alerts, or agent instructions into user-facing DOM, JSX, or templates.
- **Visual Restraint & Clean UI Microcopy:** Added design taste guidelines against navbar/header overcrowding, compulsive widget decoration, and walls of explanatory text.
- **DEV_NOTE_IN_UI Guard Check:** Added automated heuristic detection in `scripts/diff_guard.py` scoped to UI components (`.tsx`, `.jsx`, `.html`, `.vue`, `.svelte`, `.astro`) that flags leaked dev notes and mock data alerts with exit code 2 blocker severity.
- **5 New Anti-Pattern Catalog Entries (188 -> 193):**
  - `SIM-15 | Logorrhea and code narration`: Compulsive verbosity in code comments, obvious line-by-line narration, and bloated wrappers.
  - `UI-13 | Dev-notes and agent instructions leaked in UI`: Internal developer notes and TODOs rendered into client DOM.
  - `UI-14 | Wall-of-text microcopy & over-instruction`: Excessive prose, patronizing instructions, and wordy explanations cluttering UI.
  - `UI-15 | Visual overcrowding & navbar clutter`: Overcrowded headers, navigation bars, and screens with gratuitous icons and widgets.
  - `UI-16 | Compulsive decoration & gratuitous widgets`: Meaningless stat pills, redundant badges, and fake progress bars.
- **Unit Test Coverage:** Added `test_flags_dev_notes_leaked_in_ui_components` in `tests/test_diff_guard.py`.

## [0.1.2] - 2026-10-17

### Added
- **Universal Multi-Agent Installer (`install.sh`):** Installs Anti-Slop into Claude Code, Antigravity / Gemini CLI, Codex / OpenCode, and Universal Agent Kernel in one shot. Supports both local execution and `curl -fsSL ... | bash`.
- **Zero-Install CLI (`bin/cli.js`):** Node.js and Bun compatible executable wrapper for fast diff guard triage via `npx anti-slop-engineering` and `bunx anti-slop-engineering`.
- **Multi-Agent Manifests:** Added `package.json`, `marketplace.json` (Claude plugin marketplace), and `.skills.json` (Skills.sh hub).
- **High-Presence README:** Redesigned hero header with Shields.io flat-square badges, GitHub-safe Mermaid workflow diagram, and multi-channel installation matrix following `repo-craft-and-distribute` standards.
- **CI Validation:** Added GitHub Actions jobs for Bun & Node.js CLI execution, universal installer verification, and manifest schema validation.

## [0.1.1] - 2026-10-17

### Added
- **Official Boilerplate Mandate:** Explicit operating priority and Gate 0/3 rules requiring agents to rely on official language/framework CLI installers, boilerplates, and starter generators rather than hand-crafting manual scaffolding.
- **Strict Latest Stable Versioning:** Enforced strict resolution and pinning of the latest stable version from package registries for any new library, SDK, or dependency.
- **ARC-15 Anti-Pattern:** Diagnostic pattern for manual scaffolding improvisation (`references/anti-pattern-catalog.md`).
- **CI-15 Anti-Pattern:** Diagnostic pattern for stale or guessed dependency versioning (`references/anti-pattern-catalog.md`).
- Directives added to `AGENTS.md` and `references/engineering-judgment.md`.

## [0.1.0] - 2026-10-17

### Added
- Seven-gate engineering procedure in `SKILL.md` (Gate 0 through Gate 6) for BUILD, FIX, REVIEW, and CLEANUP modes.
- 186 diagnostic anti-pattern catalog spanning architecture, data, security, testing, concurrency, workflow, and agent autonomy (`references/anti-pattern-catalog.md`).
- Test integrity protocol protecting test oracles and preventing silent rebaselining (`references/test-integrity.md`).
- Evidence-based PR review protocol with structured severity ratings (`references/pr-review.md`).
- Security trust boundaries and operational safety guidelines (`references/security-and-operations.md`).
- Engineering judgment and legitimate exceptions framework (`references/engineering-judgment.md`).
- Primary sources, empirical papers, and literature limitations (`references/evidence-and-sources.md`).
- 12 blinded evaluation test scenarios and scoring rubrics (`references/evaluation-cases.md`).
- Read-only heuristic Git diff triage script (`scripts/diff_guard.py`) with zero third-party dependencies (stdlib Python 3).
- Automated test suite for diff guard (`tests/test_diff_guard.py`).
- Run report and PR review Markdown templates (`assets/`).
- GitHub Actions CI workflow supporting Python 3.9 through 3.13.
- Issue and PR templates for evidence-first collaboration.
