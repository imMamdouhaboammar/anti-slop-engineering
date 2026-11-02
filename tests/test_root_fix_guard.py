import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "root_fix_guard.py"


def example_packet():
    return {
        "problem": "Require email only when placing an order, not when creating an account",
        "symptom": "Agent proposed filtering emails in multiple profile controllers",
        "root_cause": {
            "cause": "Order contact information is incorrectly owned by the user profile",
            "owner": "User identity contract and order contact boundary",
            "evidence": [
                {"source": "app/models/user.py", "finding": "Email is required on every account", "level": "observed"},
                {"source": "app/models/order.py", "finding": "Checkout has a separate contact field", "level": "observed"},
            ],
        },
        "options": [
            {"approach": "Hide emails in each controller", "tradeoff": "Leaves the invalid domain contract", "selected": False},
            {"approach": "Fix the domain ownership", "tradeoff": "Requires auth and migration checks", "selected": True},
        ],
        "planned_changes": [
            {"path": "app/models/user.py", "role": "owner", "reason": "Change user email contract"},
            {"path": "tests/test_checkout.py", "role": "test", "reason": "Check checkout and account behavior"},
        ],
        "invariants": [
            {"rule": "Checkout requires a contact email", "proof": "Checkout integration test"},
            {"rule": "Password reset remains safe", "proof": "Authentication regression test"},
        ],
        "data_impact": {"mode": "additive"},
        "decision": {
            "action": "proceed",
            "reason": "Replace scattered behavior with ownership correction after compatibility checks",
            "invalidated_by": "Auth provider requires identity email for all accounts",
        },
    }


def audit(packet, extra_args=()):
    with tempfile.TemporaryDirectory() as directory:
        record = Path(directory) / "record.json"
        record.write_text(json.dumps(packet), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "audit", str(record), "--json", *extra_args],
            cwd=ROOT, capture_output=True, text=True, check=False,
        )
        return result, json.loads(result.stdout) if result.stdout else None


class RootFixGuardTests(unittest.TestCase):
    def test_grounded_owner_and_comparison_permit_structural_proceed(self):
        result, output = audit(example_packet())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")
        self.assertEqual(output["decision_action"], "proceed")
        self.assertTrue(output["machine_check_only"])
        self.assertEqual(output["diff_status"], "not_run")

    def test_proceed_requires_grounded_owner_evidence(self):
        packet = example_packet()
        packet["root_cause"]["evidence"][0]["level"] = "inferred"
        packet["root_cause"]["evidence"][1]["level"] = "inferred"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("OWNER_UNGROUNDED", {item["code"] for item in output["findings"]})

    def test_near_duplicate_options_do_not_count_as_alternatives(self):
        packet = example_packet()
        packet["options"][1]["approach"] = "  HIDE EMAILS IN EACH CONTROLLER "
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("DUPLICATE_OPTIONS", {item["code"] for item in output["findings"]})

    def test_proceed_requires_a_named_ownership_change(self):
        packet = example_packet()
        packet["planned_changes"][0]["role"] = "consumer"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("NO_OWNER_CHANGE", {item["code"] for item in output["findings"]})

    def test_planned_paths_must_be_canonical_and_unique(self):
        for unsafe in ("../outside.py", "/etc/passwd", "./app/models/user.py", "app//models/user.py"):
            with self.subTest(path=unsafe):
                packet = example_packet()
                packet["planned_changes"][0]["path"] = unsafe
                result, output = audit(packet)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIn("INVALID_PLANNED_CHANGE", {item["code"] for item in output["findings"]})

        packet = example_packet()
        packet["planned_changes"].append(dict(packet["planned_changes"][0]))
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("DUPLICATE_PLANNED_PATH", {item["code"] for item in output["findings"]})

    def test_destructive_change_needs_authority_and_recovery(self):
        packet = example_packet()
        packet["data_impact"] = {"mode": "destructive"}
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("DESTRUCTIVE_CHANGE_UNAUTHORIZED", {item["code"] for item in output["findings"]})

        packet["data_impact"].update({
            "approval_ref": "Owner-approved migration ticket #44", "recovery": "Verified backup and restore rehearsal"
        })
        result, output = audit(packet)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("MANUAL_AUTHORITY_CHECK", {item["code"] for item in output["findings"]})

    def test_unknown_owner_can_pause_without_fake_certainty(self):
        packet = example_packet()
        packet["root_cause"]["evidence"] = []
        packet["decision"]["action"] = "pause"
        packet["options"] = []
        packet["planned_changes"] = []
        result, output = audit(packet)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["decision_action"], "pause")

    def test_invalid_enum_structures_return_findings_not_tracebacks(self):
        for field, mutate in (
            ("action", lambda packet: packet["decision"].update(action=[])),
            ("level", lambda packet: packet["root_cause"]["evidence"][0].update(level=[])),
            ("role", lambda packet: packet["planned_changes"][0].update(role=[])),
            ("impact", lambda packet: packet["data_impact"].update(mode=[])),
        ):
            with self.subTest(field=field):
                packet = example_packet()
                mutate(packet)
                result, output = audit(packet)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertIsNotNone(output)

    def test_git_diff_reports_unplanned_files_as_review_not_block(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            (repo / "app").mkdir()
            (repo / "app" / "models").mkdir()
            (repo / "app" / "models" / "user.py").write_text("email = 'required'\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "app/models/user.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            (repo / "app" / "models" / "user.py").write_text("email = 'optional'\n", encoding="utf-8")
            (repo / "app" / "controllers.py").write_text("pass\n", encoding="utf-8")
            result, output = audit(example_packet(), ["--repo", str(repo), "--base", "HEAD"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output["diff_status"], "checked")
            self.assertEqual(output["changed_files"], 2)
            self.assertIn("UNPLANNED_CHANGE", {item["code"] for item in output["findings"]})

    def test_git_diff_reports_both_paths_of_a_staged_rename(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            model_dir = repo / "app" / "models"
            model_dir.mkdir(parents=True)
            old = model_dir / "user.py"
            old.write_text("user_email = None\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "app/models/user.py"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            old.rename(model_dir / "identity.py")
            subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
            packet = example_packet()
            packet["planned_changes"][0]["path"] = "app/models/identity.py"
            result, output = audit(packet, ["--repo", str(repo), "--base", "HEAD"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output["changed_files"], 2)
            unplanned = [item for item in output["findings"] if item["code"] == "UNPLANNED_CHANGE"]
            self.assertEqual(len(unplanned), 1)
            self.assertIn("app/models/user.py", unplanned[0]["message"])

    def test_git_diff_warns_when_planned_owner_did_not_change(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            model_dir = repo / "app" / "models"
            model_dir.mkdir(parents=True)
            (model_dir / "user.py").write_text("email = 'required'\n", encoding="utf-8")
            consumer = repo / "app" / "controllers.py"
            consumer.write_text("email = user.email\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "app"], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "baseline"], check=True)
            consumer.write_text("email = None\n", encoding="utf-8")
            packet = example_packet()
            packet["planned_changes"][1] = {
                "path": "app/controllers.py", "role": "consumer", "reason": "Update downstream profile display"
            }
            result, output = audit(packet, ["--repo", str(repo), "--base", "HEAD"])
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(output["changed_files"], 1)
            self.assertIn("OWNER_CHANGE_NOT_OBSERVED", {item["code"] for item in output["findings"]})
            self.assertNotIn("UNPLANNED_CHANGE", {item["code"] for item in output["findings"]})

    def test_invalid_git_base_is_an_error_not_a_clean_diff(self):
        result, output = audit(example_packet(), ["--base", "not-a-real-commit-123"])
        self.assertEqual(result.returncode, 1)
        self.assertIsNone(output)
        self.assertIn("Git", result.stderr)


if __name__ == "__main__":
    unittest.main()
