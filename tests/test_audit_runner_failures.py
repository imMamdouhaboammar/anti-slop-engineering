import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
import audit_runner


MANDATORY = (
    "diff_guard", "sre_guard", "ast_slop_guard", "contrast_guard",
    "comment_budget_guard", "pr_boundary_guard", "attention_guard",
    "system_drift_guard", "chroma_drift_guard", "styleseed_guard",
)


class AuditRunnerFailureContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scripts = self.root / "scripts"
        self.scripts.mkdir()
        for name in MANDATORY:
            self.set_guard(name, {"findings": []})

    def set_guard(self, name, payload, exit_code=0, sleep_seconds=0):
        script = self.scripts / (name + ".py")
        script.write_text(
            "import sys, time\n"
            + f"time.sleep({sleep_seconds!r})\n"
            + f"print({json.dumps(json.dumps(payload))})\n"
            + f"sys.exit({exit_code})\n",
            encoding="utf-8",
        )

    def run_report(self, json_mode=True, timeout=None, **audit_inputs):
        output = io.StringIO()
        original_cwd = Path.cwd()
        try:
            os.chdir(self.root)
            with contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(audit_runner, "__file__", str(self.scripts / "audit_runner.py")))
                stack.enter_context(patch.object(audit_runner, "AUDIT_DIR", self.root / "reports"))
                if timeout is not None:
                    stack.enter_context(patch.object(audit_runner, "GUARD_TIMEOUT_SECONDS", timeout, create=True))
                with contextlib.redirect_stdout(output):
                    exit_code = audit_runner.run_audit(base="HEAD", json_output=json_mode, **audit_inputs)
        finally:
            os.chdir(original_cwd)
        return exit_code, json.loads(output.getvalue()) if json_mode else output.getvalue()

    def test_clean_execution_reports_all_mandatory_checks(self):
        exit_code, report = self.run_report()
        self.assertEqual(exit_code, 0)
        self.assertEqual(report["status"], "PASS")
        self.assertEqual(report["total_findings"], 0)
        self.assertTrue(all(report["guards"][name]["status"] == "PASS" for name in MANDATORY))
        self.assertEqual(report["guards"]["invariant_steward_guard"]["status"], "SKIPPED")

    def test_valid_blocker_exit_is_not_execution_error(self):
        self.set_guard("diff_guard", {
            "findings": [{"severity": "blocker", "category": "TEST-ORACLE",
                          "file": "src/app.py", "line": 4, "message": "test disabled"}],
        }, exit_code=2)
        exit_code, report = self.run_report()
        self.assertNotEqual(exit_code, 0)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blockers_count"], 1)
        self.assertEqual(report["guards"]["diff_guard"]["status"], "FINDINGS")
        self.assertEqual(report["guards"]["diff_guard"]["exit_code"], 2)
        self.assertEqual(self.run_report(json_mode=False)[0], exit_code)

    def test_invalid_settings_file_reports_fallback_reason(self):
        config = self.root / "settings.json"
        config.write_text("invalid-json", encoding="utf-8")
        diagnostics = io.StringIO()
        with patch.object(audit_runner, "get_settings_file", return_value=config):
            with contextlib.redirect_stderr(diagnostics):
                settings = audit_runner.load_settings()
        self.assertEqual(settings, {"mode": "during"})
        self.assertIn("settings.json", diagnostics.getvalue())

    def test_failed_child_does_not_report_pass(self):
        self.set_guard("sre_guard", {"findings": []}, exit_code=1)
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(report["guards"]["sre_guard"]["exit_code"], 1)
        self.assertEqual(report["guards"]["sre_guard"]["status"], "ERROR")

    def test_malformed_json_is_execution_error(self):
        (self.scripts / "ast_slop_guard.py").write_text("print('not-json')\n", encoding="utf-8")
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertIn("JSON", report["guards"]["ast_slop_guard"]["error"])

    def test_timed_out_child_is_incomplete(self):
        self.set_guard("contrast_guard", {"findings": []}, sleep_seconds=0.25)
        code, report = self.run_report(timeout=0.02)
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertTrue(report["guards"]["contrast_guard"]["timed_out"])

    def test_missing_mandatory_script_is_incomplete(self):
        (self.scripts / "comment_budget_guard.py").unlink()
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(report["guards"]["comment_budget_guard"]["status"], "ERROR")

    def test_json_failure_status_with_zero_exit_cannot_pass(self):
        self.set_guard("pr_boundary_guard", {"status": "FAIL", "findings": []})
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(report["guards"]["pr_boundary_guard"]["status"], "ERROR")

    def test_ast_and_sre_blocker_severity_is_preserved(self):
        finding = {"severity": "blocker", "id": "BAD", "file": "code.py", "line": 1,
                   "evidence": "dangerous code"}
        self.set_guard("ast_slop_guard", {"findings": [finding]})
        self.set_guard("sre_guard", {"findings": [finding]})
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["blockers_count"], 2)

    def test_high_severity_is_not_downgraded_by_guard_fallback(self):
        self.set_guard("ast_slop_guard", {"findings": [
            {"severity": "high", "file": "code.py", "message": "unsafe cast"},
        ]})
        code, report = self.run_report()
        self.assertEqual(code, 0)
        self.assertEqual(report["findings"][0]["severity"], "HIGH")

    def test_contrast_guard_finding_exit_one_is_valid(self):
        self.set_guard("contrast_guard", {
            "findings": [{"file": "ui.css", "line": 3, "fg": "#888", "bg": "#fff", "ratio": 3.5}],
        }, exit_code=1)
        code, report = self.run_report()
        self.assertEqual(code, 0)
        self.assertEqual(report["total_findings"], 1)
        self.assertEqual(report["guards"]["contrast_guard"]["status"], "FINDINGS")

    def test_invalid_finding_schema_fails_closed(self):
        self.set_guard("attention_guard", {"findings": [None]})
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertIn("schema", report["guards"]["attention_guard"]["error"])

    def test_unknown_severity_cannot_be_downgraded(self):
        self.set_guard("sre_guard", {"findings": [
            {"severity": "blockr", "file": "code.py", "message": "unsafe"},
        ]})
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")

    def test_missing_executable_is_not_a_clean_scan(self):
        with patch.object(audit_runner.sys, "executable", "/missing/python"):
            code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertIn("Unable to execute", report["guards"]["diff_guard"]["error"])

    def test_execution_error_preserves_other_valid_findings(self):
        self.set_guard("sre_guard", {"findings": []}, exit_code=1)
        self.set_guard("diff_guard", {
            "findings": [{"severity": "blocker", "file": "src/hi.py", "line": 2,
                          "message": "unsafe"}],
        })
        code, report = self.run_report()
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(report["blockers_count"], 1)
        self.assertEqual(report["total_findings"], 1)

    def test_pr_metadata_reaches_guard_as_literal_arguments(self):
        title = 'fix: "quoted" $(touch unintended)\n${{ github.event.pull_request.title }}'
        (self.scripts / "pr_boundary_guard.py").write_text(
            "import json,sys\n"
            "print(json.dumps({'findings': [], 'pr_metadata': "
            "{'title': sys.argv[sys.argv.index('--pr-title')+1]}}))\n",
            encoding="utf-8",
        )
        code, report = self.run_report(pr_title=title)
        self.assertEqual(code, 0)
        self.assertEqual(report["guards"]["pr_boundary_guard"]["pr_metadata"]["title"], title)
        self.assertFalse((self.root / "unintended").exists())

    def test_optional_canary_guard_is_scanned_once(self):
        self.set_guard("honeypot_trap_guard", {"findings": [
            {"severity": "blocker", "trap_id": "CANARY", "message": "active canary echoed"},
        ]})
        code, report = self.run_report(canary_token="fixture-token")
        self.assertNotEqual(code, 0)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertEqual(report["total_findings"], 1)
        self.assertEqual(report["guards"]["honeypot_trap_guard"]["findings_count"], 1)
        self.assertEqual(report["guards"]["comment_budget_guard"]["findings_count"], 0)
        self.assertEqual(report["findings"][0]["rule"], "CANARY")


if __name__ == "__main__":
    unittest.main()
