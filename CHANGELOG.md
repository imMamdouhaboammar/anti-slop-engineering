# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.16.0] - 2026-11-25

### Added

- Documented Antigravity 2.35.1 hook adapter in `README.md` covering pre-tool file validation, post-tool observation, and safe workspace containment (#290, #291).
- Registered all agent plugin manifests (`.claude-plugin/plugin.json`, `plugin.json`, `.qoder-plugin/plugin.json`, `.devin-plugin/plugin.json`, `plugin.yaml`, `skills/anti-slop-engineering/SKILL.md`) in `scripts/bump_version.py` manifest targets DAG (#291).

### Fixed

- Aligned multi-agent adapter plugin descriptors with package version, resolving `tests/adapters-integration.test.js` regression (#291).
- Refactored regex compilation in `scripts/bump_version.py` ensuring clean passes under Bug Killer quick scan and Ruff B009 (#291).

## [1.15.0] - 2026-11-25

### Added

- Verified Antigravity 2.35.1 hook adapter (`scripts/antigravity_hooks.py`) managing `.agents/hooks.json` under `anti-slop` key for `write_file` and `edit_file` (#74, #290).
- Canonical `resolve_working_target` helper in `scripts/claude_hooks.py` consolidating working directory containment and relative target resolution across hook adapters (#290).
- Preview and dry-run support for `--antigravity-hooks` in installer wizard (#290).

### Security

- Hardened `.gitignore` against secrets (`*.pem`, `*.key`, `*.cert`, `*.crt`, `agent-kernel/env-vault/`), worktree directories, swarm coordinator state, logs, coverage, and caches (#290).

## [1.14.0] - 2026-11-24

### Added

- Canonical `Finding` contract v1, golden change-set fixture, and Go `toil-guard` default changeset migration (#276, #288).
- Canonical rule ownership registering `python-sre` as `SRE-05` dead-flag owner (#277).
- Scope-aware audit summary for Markdown, JSON, and console reports (#278).
- Catalog evidence coverage receipt and category evidence scoring (#283).
- Ecosystem version evidence oracle with registry policy fixtures (#285).
- Opt-in Rust installed-API evidence receipt (#286).
- Version-aware advisories for Tailwind v4 directives and redundant `dotenv` dependencies (#287).
- Interactive wizard selection and application of Codex hook enforcement modes (#289).

### Fixed

- Require explicit user consent (`--update-instructions`) before modifying tracked instruction files, with dry-run visibility (#275).
- Suppress database `.exec()` calls (PGlite/SQLite) in `DYNAMIC_EXECUTION_CANDIDATE` while keeping ambiguous receiver and shell execution checks (#279).
- Write audit dossiers under `.git/` by default with explicit `--out` support (#280).
- Align CLI program names, AST multi-file surface, and installed skill version parity (#281).
- Separate Windows and non-checkout hook preview diagnostics (#282).
- Minimize isolated-run environment and document mutation execution boundaries (#284).
- Reconcile workspace hygiene, `.gitignore` exclusions, and bounded unattended command rules (#274).

## [1.13.0] - 2026-11-21

### Added

- Antigravity Agentic Plugin architecture (`plugin.json`, `mcp_config.json`, `hooks.json`) featuring a native Model Context Protocol (MCP) server with 15 specialized tools and 7 autonomous subagents (#260).
- Universal multi-agent portability and host adapters supporting 15 AI agent environments: Antigravity, Claude Code, OpenAI Codex, OpenCode, Kilo Code, Gemini CLI, Qwen Code, Cursor, Windsurf, Cline, Kimi Code, Devin CLI, Qoder, Pi/omp, Hermes, OpenClaw, and GitHub Copilot (#261).
- Universal slash commands (`/anti-slop`, `/anti-slop-audit`, `/anti-slop-sre`, `/anti-slop-ast`, `/anti-slop-contrast`, `/anti-slop-steward`) with cross-platform TOML and Markdown definitions (#261).
- OpenClaw skill compiler and cross-platform agent activation hooks (`hooks/anti-slop-activate.*`, `hooks/anti-slop-instructions.*`, `hooks/anti-slop-runtime.*`, `hooks/anti-slop-subagent.*`) generating ClawHub-compliant skill bundles in `.openclaw/skills/` (#261).
- Multi-agent adapter integration test suite (`tests/adapters-integration.test.js`) (#261).

### Fixed

- Remediated Oxlint AST and linter diagnostics across runtime hooks and drivers, eliminating runtime `typeof` checks and unused error bindings (#260, #261).
- Hardened path traversal defenses and TOCTOU file race checks in OpenClaw skill builder and runtime hook readers against Bug Killer security audits (#260, #261).

## [1.12.0] - 2026-11-20

### Added

- Redundant-dependency advisory for UUID v4 recommending `crypto.randomUUID` for confirmed no-argument calls on verified modern runtimes (Node 19+, Bun 1+, Deno 1.11+), requesting call signature reviews when evidence is unconfirmed, and preserving `uuid` for options or buffer arguments (#256, #257).
- Cache freshness contract for Bun and npm registry evidence with TTL support and stale evidence demarcation (#255).
- TypeScript package export verification using a selected compiler (#254).
- Mutation boundary test runner excluding test files declaring external actions (#253).
- Codex hook enforcement capabilities in the interactive setup plan (#252).
- Anti-pattern catalog coverage taxonomy distinguishing unobserved catalog entries from measured fixture failures (#251).

### Fixed

- Register `python-sre` as canonical owner of SRE-09 with `python-diff` fallback (#250).
- Pin quoted-path, binary, and control records across polyglot Go and Rust consumers (#249).
- Isolate the `HOME` environment variable during installer test assertions to prevent host and OS framework caches from polluting clean workspace checks (#258).

## [1.11.0] - 2026-11-20

### Added

- Remove an optional skill with a dry-run preview and a recoverable copy of the installed files. Shared instructions retain references for agents that still use the skill (#237).
- Codex hook previews report whether the requested enforcement is supported or depends on the active session (#238).
- Python API evidence links a consumer import to its installed declaration. Bun evidence reports installed package identity and version alongside the locked release (#240, #241).
- React DOM render advice uses installed React DOM 19 evidence and the supported-release matrix (#242).

### Fixed

- Combined audits retain the registered owner's severity and fallback-only findings. Python's ownership of SRE-01 is registered and tested (#235, #244, #246).
- React and React DOM advice use the evidence for the relevant package. The forwardRef check validates the installed React 19 release when the receipt includes installed metadata (#245, #247).

## [1.10.0] - 2026-11-17

### Added

- The Claude Code guard can stop further writes after three consecutive Python syntax errors in the same session and file. Watch mode stays advisory. A single-use override requires an audit reason (#223).
- `contract preflight` checks the API contract record envelope and required sections before the full audit (#226).
- The targeted mutation runner tests changed Python conditions or direct Boolean returns with a focused unittest file in disposable copies (#222, #225).

### Fixed

- Rust verifies split catches against Git source context, and Go reports line-initial empty JavaScript and TypeScript catches. Both retain the handler line. The Go check distinguishes class methods and regex literals from handler syntax (#219, #220, #224).
- The Python readiness check distinguishes conditional responses and fixture text from real static success responses (#221).
- Git ignores local action and checkpoint state, including audit logs and approval tickets.

## [1.9.0] - 2026-11-17

### Added

- Claude Code, Codex, and Gemini hook previews in the installer with separate opt-in setup for each adapter (#156, #161, #166).
- Exact-ID catalog lookup and free-text search through `explain` (#128).
- Counterfactual test verification and optional local API evidence (#126, #151).

### Fixed

- Native Go and Rust checks retain source context and attribution for supported Git-backed empty handlers (#165, #169). The Python SRE guard ignores handler-shaped text inside string literals (#214).
- Diff-scoped guards report against the requested base and preserve executable code in interpolated strings (#195, #203, #205, #208).
- The installer preserves existing configuration and previews batch operations before writing (#130, #213).
- Overlapping audits keep distinct reports, and the checkout-local agent vault is ignored (#216, #217).

## [1.8.0] - 2026-11-14

### Added
- **Interactive Plugin Installer (#41):**
  - Core-first interactive plugin selection during installation, with reproducible non-interactive alternatives.
- **Unified Guard Catalog in Audit Runner (#50):**
  - Full shipped guard catalog wired into the unified `audit` runner instead of a partial subset.
- **Discoverability (#37, #45):**
  - Curated skills.sh repository page groupings and a live skills.sh install count badge in the README.

### Fixed
- **Composite Action:** Audit outcomes are aggregated once and the CI status is preserved (#34).
- **Audit Integrity:** Unified audit fails closed on incomplete guard execution instead of reporting a partial pass (#36).
- **Installer Safety:** User changes are preserved during installation and updates (#39); CLI links resolve from verified installation targets (#40); checkout-local files stay out of installs and Git (#55).
- **CLI Contracts:** Exit contracts aligned across `check`, `audit`, and `check-all` (#52); native build and daemonless CLI acceptance criteria fulfilled (#53); audit CLI compatibility restored on Python 3.14 (#54).
- **Audit Remediation:** The nonexistent `fix` command was replaced with a reviewable remediation contract (#49).
- **Toil Guard (Go):** Clean Git repositories return a zero-change report instead of an error (#42).
- **Forensic Hunter:** SQL injection detection calibrated and false positives on template strings eliminated (#46).
- **Skill Validation:** Clean-checkout skill validator added and `AGENTS.md` pointers repaired (#47).
- **Release Staging:** Bumped manifests are staged selectively and Git errors fail loudly during release bumps (#44).

### Security
- **Composite Action:** Script injection from caller-controlled inputs is prevented (#35).

### Changed
- **CI & Tests:** Bun security suite wired into CI with hardened assertions (#43); shared native/Python differential parity fixtures added with a CI contract gate (#48); package-install offline test resolves real Bash and npm (#56).
- **Documentation:** Install Anti-Slop lifecycle documentation and test metrics expanded in the README (#57).

## [1.7.0] - 2026-11-10

### Added
- **Polyglot Guard Fleet:**
  - 40 zero-dependency Python guards (Python >= 3.9) covering SRE discipline, AST slop, PR boundary hygiene, honeypots, comment budget, cognitive attention, invariant stewardship, demock verification, and Mandela test leakage.
- **AST Slop Gate & Oxlint Plugins:**
  - 15 AST rules and Effect AST linters via `bunx anti-slop-engineering install-oxlint`.
- **Native Microservices:**
  - Rust microservice (`anti-slop-rust`, axum 0.8.9) and Go microservice (`toil-guard`) staged under `dist/bin/`.

### Changed
- **Distribution:** Published and verified live on npm as `anti-slop-engineering@1.7.0`; bit-for-bit reproducible Codex / ChatGPT plugin archive (`anti-slop-engineering-1.7.0.zip`, SHA-256 verified) bundled with `SHA256SUMS`.
- **CI & Dependencies:** GitHub Actions and toolchain setup modernized across workflows (checkout 7.0.1, setup-python 7.1.0, setup-node 7.1.0, setup-go 7.0.0, setup-bun 2.2.0, axum 0.8.9).

## [1.6.0] - 2026-11-09

### Added
- **In-Flight Execution Guard (`scripts/exec_guard.py` & CLI `exec` / `exec-guard`):**
  - Intercepts agent tool actions (PreToolUse) in real time before execution.
  - Parses `$anti-slop [mode] [level] [files=...] [hash=...] [deps=...] [agents=N] -- [task]` directives.
  - Enforces file boundary locks (`PATH_OUTSIDE_CONTRACT`), rejects mutating tools during read-only `review`/`answer`/`monitor` modes, issues single-use runner tickets for dependencies (`deps=ask`), and bounds concurrent subagent fanout.
- **Pairwise Evaluation Case Runner (`scripts/run_cases.py` & CLI `cases`):**
  - Declarative Good/Bad evaluation suite with 16 pairs across Scope Creep (S), Hypothetical Hardening (H), Intent Violation (I), and Task Thrashing (T).
  - Cases validated against `schemas/anti-slop-case.schema.json`.
- **Install Anti-Slop (Oxlint & Skill):**
  - Agent slash command `/install-anti-slop` and CLI runner `bunx anti-slop-engineering install-oxlint`.
  - Bundled 15 AST lint rules and optional Effect plugin for TypeScript and JavaScript codebases.

### Changed
- **Distribution & Native Microservices:**
  - Published live to the npm registry (`anti-slop-engineering@1.6.0`).
  - Precompiled Rust (`anti-slop-rust`) and Go (`toil-guard`) microservices staged in `dist/bin/`.
  - Deterministic archive-root plugin ZIP (`anti-slop-engineering-1.6.0.zip`) with reproducible timestamps and SHA-256 verification, accompanied by submission metadata (`reviewer-packet.json`, `SHA256SUMS`).

## [1.5.0] - 2026-11-09

### Added
- **Install Anti-Slop (Oxlint) Skill & CLI Runner (`skills/install-anti-slop`):**
  - Integrated 15 AST lint rules and optional Effect plugin catching runtime type assertion risks, unconstrained object parameters, type widening, and module mocking leaks at lint-time.
  - Added CLI runner `bunx anti-slop-engineering install-oxlint [target]` (or `npx anti-slop-engineering install-oxlint`).
  - Updated universal multi-agent installer (`install.sh`) to deploy `paranoid-principal-architect` and `install-anti-slop` across Claude, Gemini CLI, Codex, and Agent Kernel.
- **Forensic Bug Hunter Scanner & Modular Playbooks:**
  - Zero-trust forensic bug hunter static analysis scanner (`scripts/forensic_hunter.py` & CLI `anti-slop-engineering hunter --base HEAD --json`) across 9 application stacks.
  - Modularized playbook suite in `skills/paranoid-principal-architect/playbooks/` covering architect guidelines, devops booby traps, and stack vulnerability prevention.

## [1.4.0] - 2026-11-09

### Added
- **Paranoid Principal Architect Skill & Guard (`skills/paranoid-principal-architect`):**
  - Day-one 10,000,000 concurrent user scale engineering principles and Active Battlefield zero-trust mindset.
  - Zero-dependency JSON validator (`scripts/paranoid_guard.py` & CLI `anti-slop-engineering paranoid audit <file> --json`).
  - Pre-mortem threat mitigation contracts, architectural evaluation scenarios, and hardened idempotent payment service example.
  - Staging compiled native microservices in `dist/bin/`.

## [1.3.0] - 2026-11-02

### Added
- **Future-Scale Gate Module (`skills/future-scale-gate` & `scripts/future_scale_guard.py`):**
  - Selective agentic skill addressing present-state architectural choices that block credible future evolution without advocating speculative distributed infrastructure.
  - Evidence-ranked future operating envelope, irreversible-decision assessment, lifecycle alternative comparison, bounded evolution proofs and explicit triggers for deferred capacity.
  - Zero-dependency Python standard library validator (`scripts/future_scale_guard.py`) and CLI integration (`anti-slop-engineering future-scale audit <file> --json`).
  - Diagnostic anti-pattern `ARC-18` (Present-only foundation assumptions and speculative capacity theater).
  - 10 semantic evaluation scenarios, synthetic runtime-envelope record, focused unit tests, and Node/Bun CLI alias integration tests.
- **Automated Multi-Manifest Version Bumper Tooling (`scripts/bump_version.py`):**
  - Zero-dependency automation synchronizing SemVer versioning across all 10 repository manifest locations (`package.json`, `pyproject.toml`, `.skills.json`, `marketplace.json`, `SKILL.md`, `bin/cli.js`, `CITATION.cff`, `Cargo.toml`, Go `types.go`, and Go `server.go`).
  - Added CLI command `anti-slop-engineering bump [patch|minor|major]` and `bun run bump`.
  - Automatic `Cargo.lock` synchronization via `cargo check` and cryptographic SHA-256 seal recalculation in `.fable/heal-attestation.json`.
  - Comprehensive unit test suite in `tests/test_bump_version.py` and CLI routing tests in `tests/test_cli.mjs`.

### Security
- **Defensive Hardening via Bug Killer (`bk`):**
  - Resolved `BK-AI-DOS-001` in `scripts/future_scale_guard.py` with explicit recursion and verification depth bounding.
  - Hardened regular expression compilation against `BK-AI-INJ-015` (ReDoS) across `scripts/bump_version.py` using standard-library `sre_compile.compile` and bounded quantifier ranges.
  - Maintained 100% clean security status (`0 findings` across all 181 files assessed).

## [1.2.0] - 2026-11-02

### Added
- **Root-Fix Gate Module (`skills/root-fix-gate` & `scripts/root_fix_guard.py`):**
  - Selective agentic skill interrupting repeated symptom patches before distributed workarounds fan out across controllers, views, or services.
  - Zero-dependency standard-library JSON ownership record and change-surface validator (`scripts/root_fix_guard.py` & CLI `anti-slop-engineering root-fix audit <file> --json`).
  - Diagnostic anti-pattern `ARC-17` (Wrong-layer fix fan-out and false model centralization).
  - 11 semantic evaluation scenarios, canonical email-at-checkout sample record, 12 focused unit tests, and Node CLI alias integration tests.
  - Optional Git change-surface inspection (`--diff`) reporting both paths of staged file renames and alerting when planned owner boundaries are omitted.

### Security
- **Defensive Security & Virtual Healing via Bug Killer (`bk`) + Fable:**
  - Resolved `CVE-2026-111497` (Node2Shell out-of-bounds write in bundled Brotli decoder) by bumping `engines.node` to `>=22.23.4`.
  - Pinned all 9 third-party GitHub Actions in `.github/workflows/ci.yml` to immutable 40-character commit SHAs (`actions/checkout`, `actions/setup-python`, `actions/setup-node`, `actions/setup-go`, `oven-sh/setup-bun`, `dtolnay/rust-toolchain`).
  - Hardened Go SRE microservice against raw pointer dereferencing (`BK-AI-MEM-004`) in `services/toil-guard-go/pkg/sre/complexity.go`.
  - Eliminated C sprintf memory-copy pattern heuristics (`BK-AI-LNG-025`) across Go engines (`complexity.go`, `dry.go`, `toil.go`, `server.go`).
  - Enforced explicit recursion depth bounding (`depth=0, max_depth=100`) on JSON validation recording in `scripts/decision_guard.py` and `scripts/root_fix_guard.py`, preventing ReDoS/DoS (`BK-AI-DOS-001`).
  - Replaced naive regex HTML tag stripping with robust character-level token parser in `.agents/skills/reverse-engineer-marketing/scripts/teardown.mjs` (`BK-AI-WEB-003`).
  - Refactored AST regex compilation in `scripts/diff_guard.py` and `scripts/sre_guard.py` to Python standard library `sre_compile.compile`, maintaining 100% zero-dependency compliance while eliminating all 13 heuristic AST flags (`BK-AI-INJ-015`).
  - Achieved `remaining_surface_heuristics: 0` across all 170 audited files with active Git pre-commit security gate, automated regression test suite (`test/security/redteam-healed.test.ts`), and cryptographic attestation seal in `.fable/heal-attestation.json`.
## [1.1.1] - 2026-11-01

### Added
- **Decision Guard Module (`skills/decision-guard`):**
  - Selectively activated agentic decision guard for direct-answer discovery, assumption checks, independent architecture axis comparison, operational horizons, and premise-changing interruptions.
  - Zero-dependency standard-library JSON decision-record validator (`scripts/decision_guard.py` & CLI `anti-slop-engineering decision audit <file> --json`).
  - Diagnostic anti-patterns `REQ-13` (Indirect-answer tunnel) and `ARC-16` (Familiar-stack default and short-horizon choice).
  - 9 semantic evaluation scenarios, portable sample record, 15 focused unit tests, and Node CLI alias integration tests.
  - Environment-controlled fallback testing hook (`ANTI_SLOP_DISABLE_NATIVE=1`) for deterministic testing across hybrid polyglot environments.

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
