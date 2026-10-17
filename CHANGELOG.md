# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
