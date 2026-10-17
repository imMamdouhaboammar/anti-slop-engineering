# AGENTS.md

> Operating rules and behavioral guidelines for AI coding agents working on this repository.

## Repository Mission

Anti-Slop Engineering is an open-source playbook, agent skill, and lightweight triage guard for preventing code bloat, test-oracle erosion, security shortcuts, and uncontrolled complexity in AI-assisted software development.

## Directives for AI Agents

1. **Follow the Seven Gates:** You MUST review and adhere to `SKILL.md` before generating or modifying any code in this repository.
2. **Preserve Zero-Dependency Mandate:** `scripts/diff_guard.py` MUST remain compatible with standard library Python (>=3.9) without requiring `pip install` or external packages.
3. **Protect the Test Suite:**
   - Run tests using `python3 -m unittest discover -s tests -v`.
   - Never weaken assertions, delete tests, or add skips to bypass failures.
   - All tests in `tests/test_diff_guard.py` must remain green.
4. **Self-Diff Verification:** Run `python3 scripts/diff_guard.py --base HEAD` before concluding any work session.
5. **No Hallucinated Pass Badges:** Only report tests and checks that were executed and verified against real terminal outputs.
6. **Official Boilerplate & Generators First:** When scaffolding new projects, services, components, or SDKs, use the official CLI installer / generator (e.g. `uv init`, `cargo init`, `bun create`). Never hand-roll ad-hoc scaffolding from memory.
7. **Strict Latest Stable Dependency Pinning:** When adding new libraries or SDKs, strictly query the registry and pin the latest stable release. Never guess obsolete versions based on training cutoff dates.
8. **Zero Dev-Notes Leakage in User-Facing UI:** Never leak developer notes, TODOs, agent reminders, or "mock data displayed" banners into user-facing DOM, JSX, templates, or UI components. Keep internal coordination in commit messages, devtools logs, or test fixtures.
9. **Visual Taste & Layout Restraint:** Never overcrowd headers, navbars, or toolbars with unnecessary icons, repetitive buttons, or redundant badges. Maintain whitespace, visual hierarchy, and breathing room.
10. **Anti-Logorrhea in Code & UI:** Strip away conversational chatter, redundant text blocks, over-explanatory tooltips, and obvious code narration. Let clean interfaces and self-explanatory code speak for themselves.
11. **Zero Speculative Documentation & File Sprawl:** Never generate unprompted documentation files (e.g., submission dossiers, third-party platform publishing guides, fake reviewer packets like `docs/OPENAI_SUBMISSION.md`) or invent distribution workflows. Document only what is real, requested, and verifiable in the repository. Keep READMEs and docs lean, high-signal, and factual—no marketing filler or ceremonial note callouts.
