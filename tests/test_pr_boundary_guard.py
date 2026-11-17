# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch
from scripts.pr_boundary_guard import (
    count_emojis,
    count_code_references,
    is_exact_case_file,
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

    def test_cli_invalid_base_fails_closed(self):
        root = Path(__file__).resolve().parents[1]
        _, tree_sha, _ = run_git(["rev-parse", "HEAD^{tree}"], cwd=str(root))
        for bad_base in ("NOPE_INVALID_REF", "--symbolic-full-name", tree_sha):
            with self.subTest(base=bad_base):
                proc = subprocess.run(
                    [sys.executable, str(root / "scripts" / "pr_boundary_guard.py"),
                     f"--base={bad_base}", "--json"],
                    cwd=root, capture_output=True, text=True, check=False,
                )
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn(bad_base, proc.stdout + proc.stderr)

    def test_base_matching_filename_succeeds_for_diff_checks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            run_git(["init", "-q", "-b", "main"], cwd=temp_dir)
            run_git(["config", "user.name", "Test Committer"], cwd=temp_dir)
            run_git(["config", "user.email", "test@example.com"], cwd=temp_dir)
            (Path(temp_dir) / "main").write_text("binary placeholder\n", encoding="utf-8")
            (Path(temp_dir) / "README.md").write_text("Initial\n", encoding="utf-8")
            run_git(["add", "."], cwd=temp_dir)
            run_git(["commit", "-qm", "feat: initial"], cwd=temp_dir)
            run_git(["checkout", "-q", "-b", "feat/docs"], cwd=temp_dir)
            (Path(temp_dir) / "README.md").write_text("Initial\nSmall tweak\n", encoding="utf-8")
            run_git(["add", "README.md"], cwd=temp_dir)
            run_git(["commit", "-qm", "docs: tiny readme update"], cwd=temp_dir)

            record = audit_pr_boundary(
                base="main",
                repo_root=temp_dir,
                pr_title="docs: tiny readme update",
                blocked_source_branches=[],
            )
            rules = [f["rule"] for f in record["findings"]]
            self.assertIn("METADATA_ONLY_MICRO_EDIT", rules)

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


def _load_composite_action():
    lines = (REPO_ROOT / "action.yml").read_text(encoding="utf-8").splitlines()
    inputs_defaults = {}
    env_bindings = {}
    run_lines = []
    section = None
    current_input = None
    in_env = False
    run_indent = None

    for line in lines:
        stripped = line.strip()
        if run_indent is not None:
            if stripped and (len(line) - len(line.lstrip())) <= run_indent:
                run_indent = None
            else:
                run_lines.append(line)
                continue

        if not stripped or stripped.startswith("#"):
            continue
        indent = len(line) - len(line.lstrip())
        if indent == 0 and stripped.endswith(":"):
            section = stripped[:-1]
            current_input = None
            in_env = False
            continue
        if section == "inputs":
            if indent == 2 and stripped.endswith(":"):
                current_input = stripped[:-1]
                inputs_defaults[current_input] = ""
            elif indent == 4 and current_input and stripped.startswith("default:"):
                raw = stripped.split(":", 1)[1].strip()
                inputs_defaults[current_input] = raw.strip('"').strip("'")
        elif section == "runs":
            if stripped == "env:":
                in_env = True
            elif stripped == "run: |":
                in_env = False
                run_indent = indent
            elif in_env and ":" in stripped:
                key, val = stripped.split(":", 1)
                env_bindings[key.strip()] = val.strip()

    return inputs_defaults, env_bindings, textwrap.dedent("\n".join(run_lines))


def _run_composite_action(workspace, **input_overrides):
    inputs_defaults, env_bindings, shell = _load_composite_action()
    inputs = {**inputs_defaults, **input_overrides}
    env = os.environ.copy()
    env["GITHUB_WORKSPACE"] = str(workspace)
    output_file = Path(workspace) / "github_output"
    env["GITHUB_OUTPUT"] = str(output_file)
    for var_name, expr in env_bindings.items():
        if expr == "${{ github.action_path }}":
            env[var_name] = str(REPO_ROOT)
        elif expr.startswith("${{ inputs.") and expr.endswith(" }}"):
            input_key = expr[len("${{ inputs."):-len(" }}")].strip()
            env[var_name] = inputs[input_key]
    proc = subprocess.run(
        ["bash", "-eo", "pipefail", "-c", shell],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
    )
    outputs = {}
    if output_file.exists():
        for line in output_file.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                k, v = line.split("=", 1)
                outputs[k] = v
    result_path = Path(workspace) / "audit_result.json"
    report = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
    return proc, outputs, report


class TestPrBoundaryGuardCli(unittest.TestCase):
    def _run_cli(self, repo_root, *extra_args):
        return subprocess.run(
            [sys.executable, str(GUARD_SCRIPT), "--base", "HEAD",
             "--repo", str(repo_root), "--json", *extra_args],
            cwd=REPO_ROOT, text=True, capture_output=True,
        )

    def _make_repo(self, temp_dir, branch="feature/cli-test"):
        run_git(["init"], cwd=temp_dir)
        run_git(["checkout", "-b", branch], cwd=temp_dir)
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

    def test_directory_template_file_reports_boundary_finding(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._make_repo(temp_dir)
            tpl_dir = Path(temp_dir) / ".github" / "PULL_REQUEST_TEMPLATE"
            tpl_dir.mkdir(parents=True)
            result = self._run_cli(temp_dir, "--template-file", str(tpl_dir))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            self.assertNotIn("IsADirectoryError", result.stderr)
            record = json.loads(result.stdout)
            errors = [f for f in record["findings"]
                      if f["rule"] == "TEMPLATE_FILE_NOT_FOUND"]
            self.assertEqual(len(errors), 1, record["findings"])
            self.assertEqual(errors[0]["severity"], "blocker")

    def test_wrong_case_path_rejected_on_case_insensitive_fs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            github_dir = Path(temp_dir) / ".github"
            github_dir.mkdir()
            (github_dir / "PULL_REQUEST_TEMPLATE.md").write_text("## Summary\n", encoding="utf-8")
            wrong_case = str(github_dir / "pull_request_template.md")
            exact_case = str(github_dir / "PULL_REQUEST_TEMPLATE.md")
            with patch("scripts.pr_boundary_guard.os.path.isfile", return_value=True):
                self.assertFalse(is_exact_case_file(wrong_case))
                self.assertTrue(is_exact_case_file(exact_case))

    def test_missing_template_preserves_prior_findings_and_guidance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            self._make_repo(temp_dir, branch="main")
            missing = Path(temp_dir) / "missing-template.md"
            result = self._run_cli(temp_dir, "--template-file", str(missing))
            self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
            record = json.loads(result.stdout)
            rules = [f["rule"] for f in record["findings"]]
            self.assertIn("BLOCKED_SOURCE_BRANCH", rules)
            self.assertIn("TEMPLATE_FILE_NOT_FOUND", rules)
            self.assertNotEqual(record["code"], "ERR_TEMPLATE_FILE_NOT_FOUND")
            self.assertIn("branch topology", record["remediation"]["guidance"])
            self.assertIn("--template-file", record["remediation"]["guidance"])

    def test_action_default_flags_violating_body_with_repo_template(self):
        template_src = REPO_ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
        self.assertTrue(template_src.is_file(), f"missing {template_src}")
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            self._make_repo(temp_dir)
            (workspace / ".github").mkdir()
            (workspace / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text(
                template_src.read_text(encoding="utf-8"), encoding="utf-8"
            )
            body = workspace / "body.md"
            body.write_text(
                "## Scope & compatibility\n"
                "- [x] Change is one coherent review unit or larger scope is justified\n"
                "- [x] Existing consumers and old contracts assessed\n"
                "- [ ] Unrelated refactors/dependency/config churn excluded or justified\n",
                encoding="utf-8",
            )
            run_git(["add", ".github/PULL_REQUEST_TEMPLATE.md", "body.md"], cwd=temp_dir)
            run_git(["commit", "-m", "chore: add template fixture"], cwd=temp_dir)

            proc, outputs, report = _run_composite_action(
                workspace,
                **{"base": "HEAD", "pr-body-file": "body.md"},
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertIsNotNone(report)
            self.assertEqual(outputs["status"], "PASSED")
            self.assertEqual(report["guards"]["pr_boundary_guard"]["status"], "FINDINGS")
            violations = [
                f for f in report["findings"]
                if f["guard"] == "pr_boundary_guard"
                and f["rule"] == "RADIO_BUTTON_TEMPLATE_VIOLATION"
            ]
            self.assertEqual(len(violations), 1, report["findings"])

    def test_action_default_passes_without_repo_template(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            self._make_repo(temp_dir)
            proc, outputs, report = _run_composite_action(workspace, base="HEAD")
            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(outputs["status"], "PASSED")
            self.assertEqual(outputs["blockers-count"], "0")
            self.assertIsNotNone(report)
            self.assertEqual(report["guards"]["pr_boundary_guard"]["status"], "PASS")

    def test_action_explicit_missing_template_blocks(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            self._make_repo(temp_dir)
            proc, outputs, report = _run_composite_action(
                workspace,
                **{"base": "HEAD", "template-file": "does-not-exist.md"},
            )
            self.assertEqual(proc.returncode, 2, proc.stderr)
            self.assertEqual(outputs["status"], "BLOCKED")
            self.assertEqual(outputs["blockers-count"], "1")
            self.assertIsNotNone(report)
            errors = [
                f for f in report["findings"]
                if f["guard"] == "pr_boundary_guard"
                and f["rule"] == "TEMPLATE_FILE_NOT_FOUND"
            ]
            self.assertEqual(len(errors), 1, report["findings"])
            self.assertEqual(errors[0]["severity"], "BLOCKER")

    def test_skill_doc_uses_correct_template_path(self):
        skill = (REPO_ROOT / "skills" / "pr-boundary-guard" / "SKILL.md").read_text(
            encoding="utf-8")
        self.assertIn("--template-file .github/PULL_REQUEST_TEMPLATE.md", skill)
        self.assertNotIn(".github/pull_request_template.md", skill)


if __name__ == "__main__":
    unittest.main()
