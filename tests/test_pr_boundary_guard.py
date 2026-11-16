# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from scripts.pr_boundary_guard import (
    count_emojis,
    count_code_references,
    parse_markdown_sections,
    audit_pr_boundary,
    run_git,
)


class TestPrBoundaryGuard(unittest.TestCase):
    def test_count_emojis_unicode_and_shortcodes(self):
        text = "Hello world! 🚀 Fix issue #123 with :sparkles: and 🛡️ and :+1:."
        count = count_emojis(text)
        self.assertGreaterEqual(count, 4)

    def test_count_code_references(self):
        text = "Modified `foo.py`, called `calculate_metrics()`, and updated path `src/utils/math.ts`."
        refs = count_code_references(text)
        self.assertGreaterEqual(refs, 3)

    def test_parse_markdown_sections_and_checkboxes(self):
        md = """## Type of Change
- [ ] Bugfix
- [x] Feature
- [ ] Breaking change

## Verification
- [x] Unit tests passed
"""
        sections = parse_markdown_sections(md)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["title"], "Type of Change")
        self.assertEqual(len(sections[0]["checkboxes"]), 3)
        self.assertFalse(sections[0]["checkboxes"][0]["checked"])
        self.assertTrue(sections[0]["checkboxes"][1]["checked"])

    def test_radio_button_violation_when_multiple_checked(self):
        template = """## Type of Change
- [ ] Bugfix
- [ ] Feature
- [ ] Documentation
"""
        body = """## Type of Change
- [x] Bugfix
- [x] Feature
- [ ] Documentation
"""
        record = audit_pr_boundary(
            pr_body=body,
            template_content=template,
        )
        violations = [f for f in record["findings"] if f["rule"] == "RADIO_BUTTON_TEMPLATE_VIOLATION"]
        self.assertEqual(len(violations), 1)
        self.assertIn("mutually exclusive", violations[0]["message"])

    def test_hallucinated_extra_sections_detected(self):
        template = """## Description
Explain changes here.

## Testing
Test checklist.
"""
        body = """## Description
Clean description.

## Testing
All tests pass.

## AI Rationale
Hallucinated reasoning.

## Comprehensive Impact Analysis
Extra unnecessary section.

## Future Recommendations
Another hallucinated section.
"""
        record = audit_pr_boundary(
            pr_body=body,
            template_content=template,
        )
        hallucinations = [f for f in record["findings"] if f["rule"] == "HALLUCINATED_EXTRA_SECTIONS"]
        self.assertEqual(len(hallucinations), 1)

    def test_clean_pr_passes_without_findings(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_git(["init"], cwd=temp_dir)
            run_git(["config", "user.name", "Test Committer"], cwd=temp_dir)
            run_git(["config", "user.email", "test@example.com"], cwd=temp_dir)
            run_git(["commit", "--allow-empty", "-m", "feat(engine): initial commit"], cwd=temp_dir)

            template = """## Type of Change
- [ ] Bugfix
- [ ] Feature

## Summary
Brief explanation.
"""
            body = """## Type of Change
- [ ] Bugfix
- [x] Feature

## Summary
Refactor core mathematical calculation for cleaner separation.
"""
            record = audit_pr_boundary(
                repo_root=temp_dir,
                pr_title="feat(engine): refactor core calculation",
                pr_body=body,
                template_content=template,
                require_conventional=True,
                blocked_source_branches=[],
            )
            self.assertEqual(record["code"], "NO_PR_BOUNDARY_FINDINGS")
            self.assertEqual(len(record["findings"]), 0)

    def test_blocked_source_branch_flags_review(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_git(["init"], cwd=temp_dir)
            run_git(["checkout", "-b", "blocked-branch"], cwd=temp_dir)
            run_git(["config", "user.name", "Test Committer"], cwd=temp_dir)
            run_git(["config", "user.email", "test@example.com"], cwd=temp_dir)
            run_git(["commit", "--allow-empty", "-m", "feat: initial commit"], cwd=temp_dir)
            record = audit_pr_boundary(
                repo_root=temp_dir,
                pr_title="feat: update feature",
                blocked_source_branches=["blocked-branch"],
            )
            branch_findings = [f for f in record["findings"] if f["rule"] == "BLOCKED_SOURCE_BRANCH"]
            self.assertEqual(len(branch_findings), 1)
            self.assertEqual(branch_findings[0]["severity"], "review")


REPO_ROOT = Path(__file__).resolve().parents[1]
GUARD_SCRIPT = REPO_ROOT / "scripts" / "pr_boundary_guard.py"


def _action_template_default():
    lines = (REPO_ROOT / "action.yml").read_text(encoding="utf-8").splitlines()
    for i, line in enumerate(lines):
        if line.strip() == "template-file:":
            for following in lines[i + 1:]:
                match = re.match(r'\s+default:\s*"([^"]+)"', following)
                if match:
                    return match.group(1)
                if following.strip() and not following.startswith(" " * 4):
                    break
    raise AssertionError("template-file default not found in action.yml")


class TestPrBoundaryGuardCli(unittest.TestCase):
    def _run_cli(self, repo_root, *extra_args):
        return subprocess.run(
            [sys.executable, str(GUARD_SCRIPT), "--base", "HEAD",
             "--repo", str(repo_root), "--json", *extra_args],
            cwd=REPO_ROOT, text=True, capture_output=True,
        )

    def _make_repo(self, temp_dir):
        run_git(["init"], cwd=temp_dir)
        run_git(["checkout", "-b", "feature/cli-test"], cwd=temp_dir)
        run_git(["config", "user.name", "Test Committer"], cwd=temp_dir)
        run_git(["config", "user.email", "test@example.com"], cwd=temp_dir)
        run_git(["commit", "--allow-empty", "-m", "feat: initial commit"], cwd=temp_dir)

    def test_missing_template_file_fails_loudly(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._make_repo(temp_dir)
            body = Path(temp_dir) / "body.md"
            body.write_text("## Type of Change\n- [x] Bugfix\n", encoding="utf-8")
            missing = Path(temp_dir) / "does-not-exist.md"
            result = self._run_cli(temp_dir, "--pr-body-file", str(body),
                                   "--template-file", str(missing))
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertNotIn("NO_PR_BOUNDARY_FINDINGS", result.stdout)
            record = json.loads(result.stdout)
            errors = [f for f in record["findings"]
                      if f["rule"] == "TEMPLATE_FILE_NOT_FOUND"]
            self.assertEqual(len(errors), 1, record["findings"])
            self.assertIn(errors[0]["severity"], ("blocker", "error"))

    def test_violating_body_flagged_via_action_default_template(self):
        default = _action_template_default()
        self.assertEqual(default, ".github/PULL_REQUEST_TEMPLATE.md")
        template_path = REPO_ROOT / default
        self.assertTrue(template_path.is_file(), f"missing {template_path}")
        with tempfile.TemporaryDirectory() as temp_dir:
            self._make_repo(temp_dir)
            body = Path(temp_dir) / "body.md"
            body.write_text(
                "## Scope & compatibility\n"
                "- [x] Change is one coherent review unit or larger scope is justified\n"
                "- [x] Existing consumers and old contracts assessed\n"
                "- [ ] Unrelated refactors/dependency/config churn excluded or justified\n",
                encoding="utf-8",
            )
            result = self._run_cli(temp_dir, "--pr-body-file", str(body),
                                   "--template-file", str(template_path))
            record = json.loads(result.stdout)
            violations = [f for f in record["findings"]
                          if f["rule"] == "RADIO_BUTTON_TEMPLATE_VIOLATION"]
            self.assertEqual(len(violations), 1, record["findings"])

    def test_skill_doc_uses_correct_template_path(self):
        skill = (REPO_ROOT / "skills" / "pr-boundary-guard" / "SKILL.md").read_text(
            encoding="utf-8")
        self.assertIn("--template-file .github/PULL_REQUEST_TEMPLATE.md", skill)
        self.assertNotIn(".github/pull_request_template.md", skill)


if __name__ == "__main__":
    unittest.main()
