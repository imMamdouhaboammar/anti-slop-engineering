import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "claude_hooks.py"
GUARD = ROOT / "scripts" / "exec_guard.py"
BAD_SOURCE = "value = 1\nprivate_fixture_marker = (\n"
GOOD_SOURCE = "value = 1\n"


class ClaudeCheckpointBudgetTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / "isolated project"
        self.project.mkdir()
        self.arm("$anti-slop change guard files=snippet.py|other.py -- Edit examples")
        self.source = self.project / "snippet.py"
        self.source.write_text(BAD_SOURCE)

    def arm(self, directive):
        proc = subprocess.run([sys.executable, str(GUARD), "parse-prompt", directive],
                              cwd=self.project, capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def invoke(self, phase, name="snippet.py", session="sess-1", tool="Write", raw_path=None):
        file_path = raw_path if raw_path is not None else str(self.project / name)
        payload = {
            "hook_event_name": phase,
            "tool_name": tool,
            "tool_use_id": "toolu_budget_001",
            "tool_input": {"file_path": file_path, "content": "fixture only"},
            "cwd": str(self.project),
        }
        if session is not None:
            payload["session_id"] = session
        result = subprocess.run(
            [sys.executable, str(HOOK), "evaluate", "--project", str(self.project),
             "--phase", phase],
            cwd=self.project, input=json.dumps(payload),
            capture_output=True, text=True, timeout=8, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def post_message(self, **kwargs):
        result = self.invoke("PostToolUse", **kwargs)
        return result["hookSpecificOutput"]["additionalContext"]

    def test_budget_exhaustion_denies_further_writes(self):
        first = self.post_message()
        self.assertIn("Python syntax error at line 2", first)
        self.assertNotIn("budget exhausted", first)
        second = self.post_message()
        self.assertEqual(second, first)
        third = self.post_message()
        self.assertIn("Python syntax error at line 2", third)
        self.assertIn("budget exhausted", third)

        denied = self.invoke("PreToolUse")
        output = denied["hookSpecificOutput"]
        self.assertEqual(output["permissionDecision"], "deny")
        self.assertIn("budget", output["permissionDecisionReason"])
        self.assertIn("has not happened", output["permissionDecisionReason"])
        self.assertIn("checkpoint-override.json", output["permissionDecisionReason"])

        self.assertEqual(self.invoke("PreToolUse", session="sess-2"), {})
        self.assertEqual(self.invoke("PreToolUse", name="other.py"), {})

    def test_corrected_write_clears_attempts(self):
        self.post_message()
        self.post_message()
        self.source.write_text(GOOD_SOURCE)
        self.assertEqual(self.invoke("PostToolUse"), {})
        self.source.write_text(BAD_SOURCE)
        self.post_message()
        message = self.post_message()
        self.assertNotIn("budget exhausted", message)
        self.assertEqual(self.invoke("PreToolUse"), {})

    def test_override_restores_writes_and_is_audited(self):
        self.post_message(raw_path="./snippet.py")
        self.post_message(raw_path=str(self.project / "." / "snippet.py"))
        third = self.post_message()
        self.assertIn("budget exhausted", third)
        self.assertNotEqual(self.invoke("PreToolUse", raw_path="./snippet.py"), {})
        override = self.project / ".anti-slop" / "checkpoint-override.json"
        override.write_text(json.dumps({
            "session_id": "sess-1",
            "target": "snippet.py",
            "reason": "operator reviewed the failure",
        }))
        self.assertEqual(self.invoke("PreToolUse"), {})
        self.assertFalse(override.exists())
        audit = (self.project / ".anti-slop" / "checkpoint-audit.jsonl").read_text()
        self.assertIn("override", audit)
        self.assertIn("operator reviewed the failure", audit)
        message = self.post_message()
        self.assertNotIn("budget exhausted", message)

    def test_corrupt_budget_state_degrades_to_stateless_checkpoint(self):
        self.post_message()
        state = self.project / ".anti-slop" / "checkpoint-state.json"
        state.write_text("{not json")
        message = self.post_message()
        self.assertIn("Python syntax error at line 2", message)
        self.assertNotIn("budget exhausted", message)
        self.assertEqual(json.loads(state.read_text()), {"sess-1\nsnippet.py": {"failures": 1}})
        self.assertEqual(self.invoke("PreToolUse"), {})
        audit_path = self.project / ".anti-slop" / "checkpoint-audit.jsonl"
        outside = self.project / "outside.jsonl"
        outside.write_text("")
        audit_path.unlink()
        audit_path.symlink_to(outside)
        message = self.post_message()
        self.assertIn("Python syntax error at line 2", message)
        self.assertEqual(outside.read_text(), "")

    def test_skipped_checks_do_not_consume_budget(self):
        self.source.write_bytes(b"x" * (64 * 1024 + 1))
        for _ in range(3):
            message = self.post_message()
            self.assertIn("exceeds 64 KiB", message)
        self.source.write_text(BAD_SOURCE)
        message = self.post_message()
        self.assertIn("Python syntax error at line 2", message)
        self.assertNotIn("budget exhausted", message)

    def test_missing_session_id_keeps_stateless_behavior(self):
        for _ in range(4):
            message = self.post_message(session=None)
            self.assertIn("Python syntax error at line 2", message)
            self.assertNotIn("budget exhausted", message)
        self.assertEqual(self.invoke("PreToolUse", session=None), {})


if __name__ == "__main__":
    unittest.main()
