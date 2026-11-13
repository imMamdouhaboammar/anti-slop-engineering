#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import re
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import audit_runner
from audit_runner import (
    generate_audit_markdown,
    get_next_audit_file,
    handle_mode,
    load_settings,
    save_settings,
)


def extract_bash_commands(markdown_text: str) -> list[str]:
    """Extract non-comment command lines from ```bash blocks in markdown."""
    commands = []
    in_block = False
    for line in markdown_text.splitlines():
        if line.strip() == "```bash":
            in_block = True
            continue
        if in_block and line.strip() == "```":
            in_block = False
            continue
        if in_block:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                commands.append(cleaned)
    return commands


class AuditRunnerTests(unittest.TestCase):
    def setUp(self):
        self.sample_findings = [
            {
                "id": "FINDING-001",
                "guard": "diff_guard",
                "rule": "SEVEN-GATES",
                "severity": "BLOCKER",
                "file": "src/index.ts",
                "line": 10,
                "message": "Direct modification without contract",
                "snippet": "const a = 1;",
                "remediation": "Follow Gate 1 contract",
            },
            {
                "id": "FINDING-002",
                "guard": "contrast_guard",
                "rule": "WCAG-2.2",
                "severity": "MEDIUM",
                "file": "src/App.tsx",
                "line": 42,
                "message": "Low contrast: #777 on white",
                "snippet": "<div className='text-[#777] bg-white'>",
                "remediation": "Increase contrast",
            },
        ]

    def test_mode_management(self):
        # Setting mode to during
        ret = handle_mode(["during"])
        self.assertEqual(ret, 0)
        self.assertEqual(load_settings().get("mode"), "during")

        # Setting mode to after
        ret = handle_mode(["after"])
        self.assertEqual(ret, 0)
        self.assertEqual(load_settings().get("mode"), "after")

        # Invalid mode returns 2
        ret = handle_mode(["invalid_mode"])
        self.assertEqual(ret, 2)

    def test_generate_audit_markdown(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_test.md"
        try:
            content = generate_audit_markdown(self.sample_findings, tmp_file)
            self.assertIn("# Anti-Slop Engineering Audit Report", content)
            self.assertIn("FINDING-001", content)
            self.assertIn("BLOCKER", content)
            self.assertIn("WCAG-2.2", content)
            self.assertTrue(tmp_file.exists())
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_cli_invocation(self):
        script = str(SCRIPTS_DIR / "audit_runner.py")
        res = subprocess.run([sys.executable, script, "mode"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Current anti-slop-engineering mode:", res.stdout)

    def test_docstring_does_not_advertise_fix_command(self):
        doc = audit_runner.__doc__ or ""
        self.assertNotIn("fix --finding", doc)
        self.assertNotIn("scripts/audit_runner.py fix", doc)

    def test_dossier_remediation_workflow_during_mode(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_during.md"
        try:
            content = generate_audit_markdown(self.sample_findings, tmp_file, mode="during")
            self.assertIn("DURING Mode", content)
            self.assertNotIn("AFTER Mode", content)
            self.assertNotIn("bunx anti-slop-engineering fix", content)
            self.assertNotIn("audit_runner.py fix", content)
            self.assertIn("`FINDING-001`", content)
            self.assertIn("`FINDING-002`", content)
            self.assertIn("Follow Gate 1 contract", content)

            commands = extract_bash_commands(content)
            self.assertTrue(len(commands) > 0, "Dossier should provide at least one verification command")
            for cmd in commands:
                self.assertNotIn("fix", cmd.lower())
                # Verify that every printed command actually exists and runs
                args = shlex.split(cmd)
                if args[0] == "python3":
                    args[0] = sys.executable
                proc = subprocess.run(args, cwd=ROOT_DIR, capture_output=True, text=True)
                # Audit command returns 0 (pass) or 1 (blocked findings), but must NOT fail with error 2 or 127
                self.assertIn(proc.returncode, (0, 1), f"Command '{cmd}' failed: {proc.stderr}")
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_dossier_remediation_workflow_after_mode(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_after.md"
        try:
            content = generate_audit_markdown(self.sample_findings, tmp_file, mode="after")
            self.assertIn("AFTER Mode", content)
            self.assertNotIn("DURING Mode", content)
            self.assertNotIn("bunx anti-slop-engineering fix", content)
            self.assertNotIn("audit_runner.py fix", content)
            self.assertIn("`FINDING-001`", content)
            self.assertIn("`FINDING-002`", content)

            commands = extract_bash_commands(content)
            self.assertTrue(len(commands) > 0)
            for cmd in commands:
                self.assertNotIn("fix", cmd.lower())
                args = shlex.split(cmd)
                if args[0] == "python3":
                    args[0] = sys.executable
                proc = subprocess.run(args, cwd=ROOT_DIR, capture_output=True, text=True)
                self.assertIn(proc.returncode, (0, 1), f"Command '{cmd}' failed: {proc.stderr}")
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_dossier_remediation_workflow_zero_findings(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_clean.md"
        try:
            content = generate_audit_markdown([], tmp_file, mode="during")
            self.assertIn("0 findings", content)
            self.assertNotIn("bunx anti-slop-engineering fix", content)
            commands = extract_bash_commands(content)
            self.assertTrue(len(commands) > 0)
            for cmd in commands:
                self.assertNotIn("fix", cmd.lower())
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_fix_command_rejected_truthfully(self):
        script = str(SCRIPTS_DIR / "audit_runner.py")
        res = subprocess.run([sys.executable, script, "fix"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("not supported", res.stderr.lower())

    def test_cli_guard_registry_completeness(self):
        """Regression check: Every CLI guard command in bin/cli.js must be registered or documented as excluded."""
        cli_js_path = ROOT_DIR / "bin" / "cli.js"
        self.assertTrue(cli_js_path.is_file(), "bin/cli.js must exist")
        cli_text = cli_js_path.read_text(encoding="utf-8")

        # Extract commands from the help banner in bin/cli.js
        help_match = re.search(r"Commands:([\s\S]*?)General Options:", cli_text)
        self.assertIsNotNone(help_match, "Help banner Commands: section must exist in bin/cli.js")
        
        desc_verbs = ["Run ", "Check ", "Evaluate ", "Start ", "Compile ", "Configure ", "Install ", "Upgrade ", "Print "]
        banner_commands = []
        for line in help_match.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            parts = re.split(r"\s{2,}", line)
            cmd_expr = parts[0]
            for verb in desc_verbs:
                if verb in cmd_expr:
                    cmd_expr = cmd_expr.split(verb)[0].strip()
                    break
            cmd_expr = cmd_expr.split("<")[0].split("[")[0].strip()
            for token in cmd_expr.split(","):
                token = token.strip()
                if token:
                    banner_commands.append(token)

        self.assertTrue(len(banner_commands) > 20, "Should extract all primary CLI commands")

        # Ensure registry and exclusions are exposed
        registry = getattr(audit_runner, "GUARD_REGISTRY", {})
        excluded = getattr(audit_runner, "EXCLUDED_CLI_COMMANDS", {})
        cli_map = getattr(audit_runner, "CLI_COMMAND_TO_GUARD_MAP", {})

        self.assertTrue(len(registry) >= 30, f"GUARD_REGISTRY must contain all guards, got {len(registry)}")

        for cmd in banner_commands:
            base_cmd = cmd.split()[0]
            is_registered_guard = (
                cmd in registry or cli_map.get(cmd) in registry
                or base_cmd in registry or cli_map.get(base_cmd) in registry
            )
            is_documented_exclusion = (cmd in excluded or base_cmd in excluded)
            self.assertTrue(
                is_registered_guard or is_documented_exclusion,
                f"CLI command '{cmd}' is neither registered in GUARD_REGISTRY nor documented in EXCLUDED_CLI_COMMANDS",
            )

        # Also verify all routed subcommands in bin/cli.js
        routed = set(re.findall(r'cmd === ["\']([^"\']+)["\']', cli_text))
        for cmd in routed:
            is_mapped = (
                cmd in registry or cli_map.get(cmd) in registry
                or cmd in excluded
            )
            self.assertTrue(
                is_mapped,
                f"Routed CLI command '{cmd}' must be registered in GUARD_REGISTRY, CLI_COMMAND_TO_GUARD_MAP, or EXCLUDED_CLI_COMMANDS",
            )

    def test_guard_registry_invariants(self):
        """Validate structure and required keys across all registered guards."""
        registry = getattr(audit_runner, "GUARD_REGISTRY", {})
        self.assertTrue(len(registry) >= 30)
        valid_input_types = {
            "git_diff", "workspace_scan", "pr_metadata", "ledger_record",
            "record_audit", "reactive_tool", "runtime_guard", "test_harness",
        }
        for name, spec in registry.items():
            self.assertIn("title", spec, f"{name} missing title")
            self.assertIn("script", spec, f"{name} missing script")
            self.assertIn("input_type", spec, f"{name} missing input_type")
            self.assertIn(spec["input_type"], valid_input_types, f"{name} has invalid input_type {spec['input_type']}")
            self.assertIn("description", spec, f"{name} missing description")

            if spec.get("requires_input"):
                self.assertIn("input_flag", spec, f"Record guard {name} must declare input_flag")
                self.assertIn("skip_reason", spec, f"Record guard {name} must declare skip_reason")

            if spec.get("excluded_from_audit"):
                self.assertIn("exclusion_reason", spec, f"Excluded tool {name} must declare exclusion_reason")

    def test_all_zero_input_guards_evaluated(self):
        """Verify all zero-input guards execute and are reported in audit findings."""
        findings, guards = audit_runner.collect_audit_findings(base="HEAD")
        zero_input_guards = [
            "diff_guard", "sre_guard", "ast_slop_guard", "contrast_guard",
            "comment_budget_guard", "demock_guard", "mandela_guard", "tagore_guard",
            "forensic_hunter", "system_drift_guard", "chroma_drift_guard",
            "styleseed_guard", "asset_provenance_guard",
        ]
        for name in zero_input_guards:
            self.assertIn(name, guards, f"Guard {name} must be present in guards dictionary")
            guard_status = guards[name]["status"]
            self.assertIn(
                guard_status,
                ("PASS", "FINDINGS", "BLOCKED"),
                f"Zero-input guard {name} should be evaluated (got {guard_status})",
            )
            self.assertTrue(guards[name]["applicable"])

    def test_record_based_guards_report_requires_input(self):
        """Verify record-based guards report 'requires-input' with specific guidance when unsupplied."""
        findings, guards = audit_runner.collect_audit_findings(base="HEAD")
        record_guards = [
            "decision_guard", "root_fix_guard", "future_scale_guard", "paranoid_guard",
            "perf_guard", "rollout_guard", "simulation_guard", "privacy_guard",
            "api_contract_guard", "apple_craft_guard", "observability_guard",
            "motion_runtime_guard",
        ]
        for name in record_guards:
            self.assertIn(name, guards, f"Record guard {name} must be reported in guards dictionary")
            self.assertEqual(
                guards[name]["status"],
                "SKIPPED",
                f"Guard {name} without supplied record must report 'SKIPPED'",
            )
            self.assertEqual(
                guards[name]["skip_type"],
                "requires-input",
                f"Guard {name} without supplied record must report skip_type 'requires-input'",
            )
            self.assertFalse(guards[name]["applicable"])
            self.assertTrue(bool(guards[name].get("reason")), f"Guard {name} must provide a concrete reason")

    def test_record_based_guard_evaluates_when_record_provided(self):
        """Supplying a record enables evaluation of that record-based guard."""
        example_record = ROOT_DIR / "skills" / "decision-guard" / "examples" / "architecture-record.json"
        self.assertTrue(example_record.is_file(), "architecture-record.json fixture must exist")

        findings, guards = audit_runner.collect_audit_findings(
            base="HEAD",
            decision_record=str(example_record),
        )
        self.assertIn("decision_guard", guards)
        self.assertIn(guards["decision_guard"]["status"], ("PASS", "FINDINGS"))
        self.assertTrue(guards["decision_guard"]["applicable"])

    def test_markdown_dossier_includes_coverage_table(self):
        """Markdown dossier contains comprehensive coverage and status table."""
        findings, guards = audit_runner.collect_audit_findings(base="HEAD")
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_coverage.md"
        try:
            content = generate_audit_markdown(findings, tmp_file, guards=guards, mode="during")
            self.assertIn("## Guards Coverage & Execution Status", content)
            self.assertIn("| Guard | Category | Status | Findings | Details |", content)
            self.assertIn("diff_guard", content)
            self.assertIn("privacy_guard", content)
            self.assertIn("requires-input", content)
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_records_dict_with_flag_names(self):
        """Passing flag-style keys in records dict evaluates the record-based guard."""
        example_record = ROOT_DIR / "skills" / "decision-guard" / "examples" / "architecture-record.json"
        findings, guards = audit_runner.collect_audit_findings(
            base="HEAD",
            records={"--decision-record": str(example_record)},
        )
        self.assertIn("decision_guard", guards)
        self.assertIn(guards["decision_guard"]["status"], ("PASS", "FINDINGS"))
        self.assertTrue(guards["decision_guard"]["applicable"])

    def test_remediation_workflow_distinguishes_requires_input(self):
        """When 0 findings exist but guards require input, remediation lists required records."""
        guards = {
            "diff_guard": {"status": "PASS", "title": "Diff Guard", "findings_count": 0},
            "decision_guard": {
                "status": "SKIPPED",
                "skip_type": "requires-input",
                "input_flag": "--decision-record",
                "reason": "Requires dedicated Decision Guard JSON record",
            },
        }
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_requires_input.md"
        try:
            content = generate_audit_markdown([], tmp_file, guards=guards, mode="during")
            self.assertNotIn("All guards passed with 0 findings. No remediation required.", content)
            self.assertIn("### Input Assessment Records Required", content)
            self.assertIn("--decision-record <file>", content)
            self.assertIn("decision_guard", content)
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_action_result_evaluation(self):
        """Validate that action_result evaluate_report accepts valid unified reports."""
        from action_result import evaluate_report
        findings, guards = audit_runner.collect_audit_findings(base="HEAD")
        blockers = sum(1 for f in findings if f.get("severity") == "BLOCKER")
        has_error = any(result.get("status") == "ERROR" for result in guards.values())
        expected_status = "ERROR" if has_error else ("BLOCKED" if blockers else "PASS")
        audit_exit = {"PASS": 0, "BLOCKED": 1, "ERROR": 2}[expected_status]
        report = {
            "status": expected_status,
            "total_findings": len(findings),
            "blockers_count": blockers,
            "findings": findings,
            "guards": guards,
        }
        status, total, blockers_cnt = evaluate_report(report, audit_exit=audit_exit)
        self.assertEqual(status, "PASSED" if expected_status == "PASS" else expected_status)
        self.assertEqual(total, len(findings))
        self.assertEqual(blockers_cnt, blockers)

    def test_remediation_workflow_handles_guard_errors_without_findings(self):
        """When 0 findings exist but a guard failed with an execution error, list errors."""
        guards = {
            "diff_guard": {"status": "ERROR", "title": "Diff Guard", "error": "Execution timed out"},
            "decision_guard": {
                "status": "SKIPPED",
                "skip_type": "requires-input",
                "input_flag": "--decision-record",
                "reason": "Requires dedicated Decision Guard JSON record",
            },
        }
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_guard_error.md"
        try:
            content = generate_audit_markdown([], tmp_file, guards=guards, mode="during")
            self.assertNotIn("All guards passed with 0 findings", content)
            self.assertNotIn("All evaluated guards passed with 0 findings", content)
            self.assertIn("### Guard Execution Errors", content)
            self.assertIn("diff_guard", content)
            self.assertIn("Execution timed out", content)
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_validate_report_outcome_rejects_passed_false_without_findings(self):
        """Outcome validator rejects passed=False reports that exit 0 with 0 findings."""
        process = {"exit_code": 0}
        report = {"passed": False, "status": "PASS"}
        err = audit_runner._validate_report_outcome(process, report, [])
        self.assertIsNotNone(err)
        self.assertIn("Guard reported passed=false without findings", err)

    def test_action_result_rejects_inactive_mandatory_guard(self):
        """Action result validator rejects mandatory guards marked as inactive/skipped."""
        from action_result import evaluate_report
        findings, guards = audit_runner.collect_audit_findings(base="HEAD")
        guards_copy = dict(guards)
        # Mark diff_guard (mandatory) as inactive
        guards_copy["diff_guard"] = {
            "status": "SKIPPED",
            "applicable": False,
            "exit_code": None,
            "findings_count": 0,
        }
        report = {
            "status": "PASS",
            "total_findings": 0,
            "blockers_count": 0,
            "findings": [],
            "guards": guards_copy,
        }
        with self.assertRaises(ValueError) as ctx:
            evaluate_report(report, audit_exit=0)
        self.assertIn("Mandatory guard diff_guard is incomplete", str(ctx.exception))
