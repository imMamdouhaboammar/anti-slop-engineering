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
