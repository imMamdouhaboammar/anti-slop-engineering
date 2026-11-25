import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "antigravity_hooks.py"
GUARD = ROOT / "scripts" / "exec_guard.py"


@unittest.skipUnless(os.name == "posix", "Antigravity adapter uses POSIX hook commands")
class AntigravityHookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory(prefix="antigravity adapter ")
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name).resolve()
        self.settings = self.project / ".agents" / "hooks.json"

    def invoke(self, *args, payload=None):
        return subprocess.run(
            [sys.executable, str(HOOK), *args, "--project", str(self.project)],
            cwd=self.project,
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )

    def arm(self, directive):
        subprocess.run(
            [sys.executable, str(GUARD), "parse-prompt", directive],
            cwd=self.project,
            capture_output=True,
            check=True,
        )

    def native_output(self, project_file, phase="PreToolUse", tool="write_file", **extra):
        args = {"Path": project_file, "Content": "fixture content"} if project_file is not None else {}
        payload = {
            "hookEventName": phase,
            "conversationId": "fixture-session",
            "cwd": str(self.project),
            "toolCall": {
                "id": "toolu_fixture_01",
                "name": tool,
                "args": args,
            },
        }
        payload.update(extra)
        result = self.invoke("evaluate", "--phase", phase, payload=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("fixture content", result.stdout + result.stderr)
        return json.loads(result.stdout)

    def test_review_guard_denies_write_and_edit_before_mutation(self):
        self.arm("$anti-slop review guard -- Review only")
        for tool in ("write_file", "edit_file"):
            result = self.native_output("note.txt", tool=tool)
            self.assertEqual(result["decision"], "deny")
            self.assertIn("does not authorize", result["reason"])
        self.assertFalse((self.project / "note.txt").exists())

    def test_policy_allows_scoped_write_without_granting_host_permission(self):
        self.assertEqual(self.native_output("note.txt"), {})
        self.arm("$anti-slop change guard files=note.txt -- Edit one file")
        self.assertEqual(self.native_output("note.txt"), {})
        self.assertEqual(self.native_output("other.txt")["decision"], "deny")
        self.assertEqual(self.native_output("other.txt", tool="run_command"), {})

    def test_advisory_watch_and_error_paths(self):
        self.arm("$anti-slop review watch -- Review only")
        pre = self.native_output("note.txt")
        self.assertEqual(pre["decision"], "ask")
        self.assertIn("does not authorize", pre["reason"])
        post = self.native_output("note.txt", phase="PostToolUse")
        self.assertEqual(post, {})
        malformed = self.native_output(None)
        self.assertEqual(malformed["decision"], "deny")
        self.assertIn("could not evaluate", malformed["reason"])
        self.assertEqual(self.native_output(None, phase="PostToolUse"), {})

    def test_opt_in_configuration_preserves_other_hooks_and_removes_only_anti_slop(self):
        self.settings.parent.mkdir()
        original = {"other-hook": {"PostToolUse": [{"matcher": "run_command", "hooks": [{"type": "command", "command": "true"}]}]}}
        self.settings.write_text(json.dumps(original))
        before = self.settings.read_bytes()
        plan = self.invoke("install", "--dry-run")
        self.assertEqual(plan.returncode, 0, plan.stderr)
        self.assertEqual(json.loads(plan.stdout)["status"], "would_change")
        self.assertEqual(self.settings.read_bytes(), before)
        result = self.invoke("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        settings = json.loads(self.settings.read_text())
        self.assertEqual(settings["other-hook"], original["other-hook"])
        self.assertEqual(settings["anti-slop"]["PreToolUse"][0]["matcher"], "write_file|edit_file")
        self.assertEqual(settings["anti-slop"]["PostToolUse"][0]["hooks"][0]["timeout"], 5)
        self.assertEqual(self.invoke("install", "--yes").returncode, 0)
        self.assertEqual(json.loads(self.settings.read_text()), settings)
        self.assertEqual(self.invoke("uninstall", "--yes").returncode, 0)
        self.assertEqual(json.loads(self.settings.read_text()), original)

    def test_refuses_symlink_and_preserves_locally_modified_hook(self):
        self.settings.parent.mkdir()
        other = self.project / "unrelated.json"
        other.write_text("{}")
        self.settings.symlink_to(other)
        self.assertNotEqual(self.invoke("install", "--yes").returncode, 0)
        self.assertEqual(other.read_text(), "{}")
        self.settings.unlink()
        installed = self.invoke("install", "--yes")
        self.assertEqual(installed.returncode, 0, installed.stderr)
        settings = json.loads(self.settings.read_text())
        settings["anti-slop"]["PreToolUse"][0]["matcher"] = ".*"
        self.settings.write_text(json.dumps(settings))
        self.assertNotEqual(self.invoke("uninstall", "--yes").returncode, 0)
        self.assertEqual(json.loads(self.settings.read_text()), settings)


if __name__ == "__main__":
    unittest.main()
