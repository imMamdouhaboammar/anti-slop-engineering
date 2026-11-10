# Anti-Slop Engineering: PR Boundary, Honeypot Canary & Comment Budget Intelligence

## Context & Provenance

We reverse-engineered `peakoss/anti-slop` (850+ stars, derived from maintaining Coolify with 120+ slop PRs/month) using the Elephant-Goldfish Model (EGM), REA, Deep Digger, and Poteto Principles.

While `peakoss/anti-slop` pioneered reactive PR triage for GitHub Actions, it suffered from:
1. **Network Lock-in:** Octokit/GitHub API coupling prevented offline execution in local git pre-commit hooks, CI air-gapped runners, or agent worktrees.
2. **Naive Comment Counter:** A flat integer limit (`max-added-comments: 10`) broke legitimate, well-documented large PRs while permitting micro-PRs with 9 lines of trivial comment slop.
3. **Passive Honeypots:** Simple plaintext substring searches risked self-blocking maintainers updating PR templates or legitimate humans who left template HTML comments untouched.
4. **Lack of Agent Remediation Contracts:** Closed PRs with static text comments instead of actionable RFC 9457 / TOON contracts that autonomous coding agents can parse to self-heal.

## Solution Architecture

We elevated these concepts into our polyglot, agentic, zero-dependency architecture across three production engines:

### 1. PR Boundary & Git Topology Guard (`scripts/pr_boundary_guard.py`)
- **Offline & CI Dual Runtime:** Inspects local Git topology via standard subprocesses with graceful resilience for shallow clones (`git rev-parse --is-shallow-repository`) and detached HEADs (`git symbolic-ref -q HEAD` falling back to `$GITHUB_HEAD_REF`).
- **Branch Hygiene:** Blocks unbranched pull requests originating directly from `main` or `master`.
- **Commit Subject Length:** Restricts commit subject lines to 100 characters max, preserving up to 5,000 characters for descriptive commit bodies and git trailers.
- **Radio-Button Template Contracts:** Validates that template sections with multiple checkboxes enforce mutual exclusivity (exactly one option checked) and flags hallucinated sections.
- **Unicode Range Tables:** Eliminates non-stdlib regex crashes by using explicit Unicode codepoint tables for emoji density counting.

### 2. Honeypot Trap & Prompt Canary Guard (`scripts/honeypot_trap_guard.py`)
- **Active Canary Directives:** Generates deterministic HMAC-SHA256 canary tokens (`<!-- anti-slop-canary:canary-xxx -->`) that flag bots when echoed by an LLM in titles, bodies, or code additions.
- **Decoy Checkboxes & Issues:** Detects ungrounded bot ingestion through bait checkboxes and decoy issue references (`#9999`).
- **Template Maintenance Exemption:** Strictly exempts `.github/` templates and workflow diffs so maintainers can update repo templates without self-blocking.

### 3. Comment Budget & Syntactic Obviousness Guard (`scripts/comment_budget_guard.py` & Rust Engine)
- **Comment-to-Code Ratio (CCR):** Calculates $\text{CCR} = \frac{\text{added\_comments}}{\max(1, \text{added\_code})}$.
- **Activation Floor:** Requires $\ge 20$ added comment lines before ratio checks activate, eliminating false positives on small files.
- **Exemptions & Stripping:** Excludes markdown, YAML/TOML, JSON, and SQL files, and strips leading SPDX/license blocks (first 25 lines).
- **Zero-Obviousness Invariant:** Blocks syntax play-by-play narration comments (`// increment`, `// return result`, `// loop through`) while strictly safeguarding formal `// SAFETY:` invariants, JSDoc/TSDoc docstrings, and `///` Rust doc comments.
- **Native Rust Scanner:** Implemented `CommentAuditor` in `services/anti-slop-rust/src/comment_auditor.rs` for sub-millisecond diff analysis.

### 4. Turnkey GitHub Action & CLI Integration
- Created root `action.yml` enabling one-line CI integration via `imMamdouhaboammar/anti-slop-engineering@v1`.
- Added CLI subcommands in `bin/cli.js`: `pr-guard`, `honeypot`, `comment-guard`.
- Integrated all new checks into `scripts/audit_runner.py` for automated multi-guard audit dossier generation (`anti-slop/audit-NNN.md`).

## Verification Matrix

- **Python Test Suite:** 350/350 unit tests passing (`python3 -m unittest discover -s tests -v`).
- **Rust Engine:** 11/11 unit and integration tests passing (`cargo test --manifest-path services/anti-slop-rust/Cargo.toml`).
- **Go Engine:** 17/17 SRE unit tests passing (`cd services/toil-guard-go && go test -v ./...`).
- **CLI Suite:** 28/28 Node.js/Bun CLI tests passing (`node --test tests/test_cli.mjs`).
- **Self-Diff Verification:** Zero blockers reported by `diff_guard.py` and `sre_guard.py`.
