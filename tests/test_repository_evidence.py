import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from test_decision_guard import architecture_packet

ROOT = Path(__file__).resolve().parents[1]


def digest(data):
    return hashlib.sha256(data).hexdigest()


class RepositoryEvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.repo = Path(directory.name)
        self.git("init", "-q")
        self.path = self.repo / "src.py"
        self.path.write_text("version = 1\n", encoding="utf-8")
        self.git("add", "src.py")
        self.git("commit", "-qm", "initial")
        self.base = self.git("rev-parse", "HEAD").strip().decode()
        self.path.write_text("version = 2\n", encoding="utf-8")
        self.git("add", "src.py")
        self.git("commit", "-qm", "fix version")
        self.head = self.git("rev-parse", "HEAD").strip().decode()

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-c", "core.abbrev=12", "-c", "user.name=Test", "-c", "user.email=test@example.com",
             "-c", "commit.gpgsign=false", "-C", str(self.repo), *args],
            env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull},
        )

    def packet(self):
        packet = architecture_packet()
        patch = self.git("diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                         "--no-color", "--no-relative", "--diff-algorithm=myers", "--no-indent-heuristic",
                         "--src-prefix=a/", "--dst-prefix=b/", "--unified=3",
                         self.base, self.head, "--", "src.py")
        packet["repository_evidence"] = {
            "version": 1, "base_commit": self.base, "head_commit": self.head,
            "paths": [{"path": "src.py", "blob_sha256": digest(self.path.read_bytes()),
                       "patch_sha256": digest(patch)}],
            "check": {"name": "git_diff_check", "exit_code": 0,
                      "stdout_sha256": digest(b""), "stderr_sha256": digest(b"")},
        }
        return packet

    def run_audit(self, packet, *args, guard="decision_guard.py"):
        record = self.repo / "decision.json"
        record.write_text(json.dumps(packet), encoding="utf-8")
        env = os.environ.copy()
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / guard), "audit", str(record),
             "--repo", str(self.repo), "--json", *args], capture_output=True, text=True, env=env,
        )
        self.assertTrue(proc.stdout, proc.stderr)
        return proc.returncode, json.loads(proc.stdout)

    def test_existing_output_is_compatible_and_evidence_is_opt_in(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / "scripts/decision_guard.py"), "audit",
             str(ROOT / "skills/decision-guard/examples/architecture-record.json"), "--json"],
            capture_output=True, text=True,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertTrue(result["machine_check_only"])
        self.assertNotIn("evidence_status", result)

    def test_live_git_evidence_is_independent_of_uncommitted_files(self):
        packet = self.packet()
        self.path.write_text("uncommitted version\n", encoding="utf-8")
        code, result = self.run_audit(packet, "--verify-evidence")
        self.assertEqual(code, 0, result)
        self.assertTrue(result["record_valid"])
        self.assertEqual(result["evidence_status"], "implementation_verified")
        self.assertEqual(self.path.read_text(encoding="utf-8"), "uncommitted version\n")

    def test_live_git_evidence_uses_committed_attributes(self):
        packet = self.packet()
        (self.repo / ".gitattributes").write_text("src.py -diff\n", encoding="utf-8")

        code, result = self.run_audit(packet, "--verify-evidence")

        self.assertEqual(code, 0, result)
        self.assertEqual(result["evidence_status"], "implementation_verified")
        self.assertTrue(result["evidence_checks"]["paths"][0]["patch_matches"])

    def test_manually_asserted_check_does_not_receive_verification(self):
        packet = self.packet()
        packet["repository_evidence"]["check"]["stdout_sha256"] = digest(b"fabricated output")
        code, result = self.run_audit(packet, "--verify-evidence")
        self.assertEqual(code, 3, result)
        self.assertTrue(result["record_valid"])
        self.assertEqual(result["evidence_status"], "inconclusive")
        self.assertEqual(result["evidence_checks"]["diff_check"]["exit_code"], 0)

    def test_incomplete_or_stale_git_evidence_is_inconclusive(self):
        for field, value in (("path", "missing.py"), ("path", "../src.py"),
                             ("patch_sha256", digest(b"other patch")),
                             ("blob_sha256", digest(b"other bytes"))):
            with self.subTest(field=field, value=value):
                packet = self.packet()
                packet["repository_evidence"]["paths"][0][field] = value
                code, result = self.run_audit(packet, "--verify-evidence")
                self.assertEqual(code, 3, result)
                self.assertEqual(result["evidence_status"], "inconclusive")
        packet = self.packet()
        packet["repository_evidence"]["head_commit"] = self.base
        code, result = self.run_audit(packet, "--verify-evidence")
        self.assertEqual(code, 3, result)
        self.assertEqual(result["evidence_status"], "inconclusive")

    def test_other_record_entrypoints_accept_same_evidence(self):
        samples = {
            "root_fix_guard.py": "skills/root-fix-gate/examples/email-checkout-record.json",
            "paranoid_guard.py": "skills/paranoid-principal-architect/examples/paranoid-architecture-record.json",
        }
        for guard, sample in samples.items():
            with self.subTest(guard=guard):
                record = json.loads((ROOT / sample).read_text(encoding="utf-8"))
                record["repository_evidence"] = self.packet()["repository_evidence"]
                code, result = self.run_audit(record, "--verify-evidence", guard=guard)
                self.assertEqual(code, 0, result)
                self.assertEqual(result["evidence_status"], "implementation_verified")

    def test_record_fields_cannot_launch_commands_or_redirect_git(self):
        packet = self.packet()
        marker = self.repo / "command-marker"
        packet["repository_evidence"]["check"]["command"] = [sys.executable, "-c", "open(%r,'w').close()" % str(marker)]
        code, result = self.run_audit(packet, "--verify-evidence")
        self.assertEqual(code, 3, result)
        self.assertEqual(result["evidence_status"], "inconclusive")
        self.assertFalse(marker.exists())

    def test_git_is_not_required_for_structural_checks_but_absence_is_visible(self):
        packet = self.packet()
        no_git = self.repo / "missing-git-bin"
        no_git.mkdir()
        record = self.repo / "decision.json"
        record.write_text(json.dumps(packet), encoding="utf-8")
        cmd = [sys.executable, str(ROOT / "scripts/decision_guard.py"), "audit", str(record),
               "--repo", str(self.repo), "--json"]
        env = {**os.environ, "PATH": str(no_git)}
        legacy = subprocess.run(cmd, capture_output=True, text=True, env=env)
        opted_in = subprocess.run(cmd + ["--verify-evidence"], capture_output=True, text=True, env=env)
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertEqual(opted_in.returncode, 3, opted_in.stderr)
        self.assertEqual(json.loads(opted_in.stdout)["evidence_status"], "inconclusive")

    def test_invalid_record_and_missing_evidence_are_distinct(self):
        packet = architecture_packet()
        missing_code, missing = self.run_audit(packet, "--verify-evidence")
        self.assertEqual(missing_code, 3, missing)
        self.assertTrue(missing["record_valid"])
        self.assertEqual(missing["evidence_status"], "inconclusive")
        del packet["kind"]
        invalid_code, invalid = self.run_audit(packet, "--verify-evidence")
        self.assertEqual(invalid_code, 2, invalid)
        self.assertFalse(invalid["record_valid"])
        self.assertEqual(invalid["evidence_status"], "inconclusive")
