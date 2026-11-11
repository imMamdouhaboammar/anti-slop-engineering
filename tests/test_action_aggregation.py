import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_action_security import action_step


REPO = Path(__file__).resolve().parents[1]
GUARD_NAMES = (
    "diff_guard", "sre_guard", "ast_slop_guard", "contrast_guard",
    "comment_budget_guard", "pr_boundary_guard", "invariant_steward_guard",
    "attention_guard", "system_drift_guard", "chroma_drift_guard",
    "styleseed_guard", "honeypot_trap_guard",
)


def report_for(findings=(), status="PASS", error_guard=None):
    checks = {
        name: {"status": "SKIPPED" if name in {"invariant_steward_guard", "honeypot_trap_guard"} else "PASS",
               "applicable": name not in {"invariant_steward_guard", "honeypot_trap_guard"},
               "exit_code": None if name in {"invariant_steward_guard", "honeypot_trap_guard"} else 0,
               "findings_count": 0}
        for name in GUARD_NAMES
    }
    if error_guard:
        checks[error_guard].update(status="ERROR", applicable=True, error="broken scanner")
    for finding in findings:
        check = checks[finding["guard"]]
        check.update(status="FINDINGS", applicable=True, exit_code=0)
        check["findings_count"] += 1
    return {
        "status": status,
        "total_findings": len(findings),
        "blockers_count": sum(item["severity"] == "BLOCKER" for item in findings),
        "findings": list(findings),
        "guards": checks,
    }


class CompositeActionAggregationTests(unittest.TestCase):
    def run_action(self, report, audit_exit=0, fail_on_blocker="true", malformed=False, canary=""):
        with tempfile.TemporaryDirectory() as temp:
            workspace = Path(temp)
            subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-q", "--allow-empty", "-m", "fixture"],
                cwd=workspace, check=True,
            )
            scripts = workspace / "fake-action" / "scripts"
            scripts.mkdir(parents=True)
            (workspace / "fixture.json").write_text(
                "not-json" if malformed else json.dumps(report), encoding="utf-8"
            )
            (scripts / "audit_runner.py").write_text(
                "import os, sys\n"
                "def guard_commands(base='HEAD', canary_token='', **kwargs):\n"
                "    optional = {'invariant_steward_guard'}\n"
                "    if not canary_token: optional.add('honeypot_trap_guard')\n"
                "    return [(name, None if name in optional else ['python']) "
                "for name in os.environ['EXPECTED_GUARDS'].split(',')]\n"
                "if __name__ == '__main__':\n"
                "    print(open(os.environ['AUDIT_FIXTURE'], encoding='utf-8').read())\n"
                "    sys.exit(int(os.environ['AUDIT_EXIT']))\n",
                encoding="utf-8",
            )
            for name in ("pr_boundary_guard", "honeypot_trap_guard", "comment_budget_guard"):
                (scripts / (name + ".py")).write_text(
                    'print("{\\\"findings\\\": []}")\n', encoding="utf-8"
                )
            if (REPO / "scripts/action_result.py").exists():
                (scripts / "action_result.py").write_bytes(
                    (REPO / "scripts/action_result.py").read_bytes()
                )
            _, shell = action_step()
            env = os.environ.copy()
            env.update({
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(workspace / "outputs"),
                "ACTION_PATH": str(scripts.parent),
                "AUDIT_BASE": "HEAD",
                "PR_TITLE": "",
                "PR_BODY_FILE": "",
                "TEMPLATE_FILE": "",
                "CANARY_TOKEN": canary,
                "FAIL_ON_BLOCKER": fail_on_blocker,
                "AUDIT_FIXTURE": str(workspace / "fixture.json"),
                "AUDIT_EXIT": str(audit_exit),
                "EXPECTED_GUARDS": ",".join(GUARD_NAMES),
            })
            proc = subprocess.run(
                ["bash", "-eo", "pipefail", "-c", shell],
                cwd=workspace, env=env, text=True, capture_output=True,
            )
            output = (workspace / "outputs").read_text() if (workspace / "outputs").exists() else ""
            files = sorted(path.name for path in workspace.glob("*_result.json"))
        return proc, output, files

    def assert_outputs(self, text, status, findings, blockers):
        lines = text.splitlines()
        self.assertEqual(len(lines), 3, text)
        self.assertEqual(dict(line.split("=", 1) for line in lines), {
            "status": status,
            "findings-count": str(findings),
            "blockers-count": str(blockers),
        })

    def test_clean_with_optional_results_absent(self):
        proc, output, files = self.run_action(report_for())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(files, ["audit_result.json"])
        self.assert_outputs(output, "PASSED", 0, 0)

    def test_unified_audit_only_blocker(self):
        finding = {"guard": "diff_guard", "severity": "BLOCKER", "message": "unsafe"}
        proc, output, _ = self.run_action(report_for([finding], "BLOCKED"), audit_exit=1)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assert_outputs(output, "BLOCKED", 1, 1)

    def test_optional_honeypot_blocker(self):
        finding = {"guard": "honeypot_trap_guard", "severity": "BLOCKER", "message": "canary"}
        proc, output, files = self.run_action(
            report_for([finding], "BLOCKED"), audit_exit=1, canary="harmless-token"
        )
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(files, ["audit_result.json"])
        self.assert_outputs(output, "BLOCKED", 1, 1)

    def test_multiple_blockers_counted_once(self):
        findings = [
            {"guard": "comment_budget_guard", "severity": "BLOCKER", "message": "syntax narration"},
            {"guard": "diff_guard", "severity": "BLOCKER", "message": "disabled test"},
        ]
        proc, output, _ = self.run_action(report_for(findings, "BLOCKED"), audit_exit=1)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assert_outputs(output, "BLOCKED", 2, 2)

    def test_fail_on_blocker_false_still_reports_blocked(self):
        finding = {"guard": "pr_boundary_guard", "severity": "BLOCKER", "message": "invalid"}
        proc, output, _ = self.run_action(
            report_for([finding], "BLOCKED"), audit_exit=1, fail_on_blocker="false"
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assert_outputs(output, "BLOCKED", 1, 1)

    def test_malformed_mandatory_audit_is_error(self):
        proc, output, _ = self.run_action(report_for(), malformed=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assert_outputs(output, "ERROR", 0, 0)

    def test_guard_execution_error_cannot_be_ignored(self):
        proc, output, _ = self.run_action(
            report_for(status="ERROR", error_guard="sre_guard"), audit_exit=2,
            fail_on_blocker="false",
        )
        self.assertNotEqual(proc.returncode, 0)
        self.assert_outputs(output, "ERROR", 0, 0)

    def test_audit_exit_must_match_json_status(self):
        proc, output, _ = self.run_action(report_for(), audit_exit=1, fail_on_blocker="false")
        self.assertNotEqual(proc.returncode, 0)
        self.assert_outputs(output, "ERROR", 0, 0)

    def test_guard_cannot_claim_pass_without_execution(self):
        report = report_for()
        report["guards"]["sre_guard"]["exit_code"] = None
        proc, output, _ = self.run_action(report)
        self.assertNotEqual(proc.returncode, 0)
        self.assert_outputs(output, "ERROR", 0, 0)

    def test_guard_finding_count_must_match_normalized_findings(self):
        finding = {"guard": "diff_guard", "severity": "BLOCKER", "message": "unsafe"}
        report = report_for([finding], "BLOCKED")
        report["guards"]["diff_guard"]["findings_count"] = 0
        proc, output, _ = self.run_action(report, audit_exit=1)
        self.assertNotEqual(proc.returncode, 0)
        self.assert_outputs(output, "ERROR", 0, 0)

    def test_malformed_guard_collection_still_emits_error_outputs(self):
        report = report_for()
        report["guards"] = ["not-a-guard-map"]
        proc, output, _ = self.run_action(report)
        self.assertNotEqual(proc.returncode, 0)
        self.assert_outputs(output, "ERROR", 0, 0)


if __name__ == "__main__":
    unittest.main()
