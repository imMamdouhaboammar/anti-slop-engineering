# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
