import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "claude_hooks.py"
GUARD = ROOT / "scripts" / "exec_guard.py"


class ClaudeHookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name) / "isolated project"
        self.project.mkdir()
        self.settings = self.project / ".claude" / "settings.local.json"
        self.existing = {
            "permissions": {"deny": ["Glob"]},
            "hooks": {"PreToolUse": [{"matcher": "Read", "hooks": [{"type": "command", "command": "fixture"}]}]},
        }
        self.event = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_use_id": "toolu_test_001",
            "tool_input": {"file_path": str(self.project / "note.txt"), "content": "synthetic marker"},
            "cwd": str(self.project),
        }

    def invoke(self, *args, payload=None):
        return subprocess.run(
            [sys.executable, str(HOOK), *args], cwd=self.project,
            input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, timeout=8, check=False,
        )

    def configure(self, *args):
        return self.invoke(*args, "--project", str(self.project))

    def arm(self, directive):
        proc = subprocess.run([sys.executable, str(GUARD), "parse-prompt", directive], cwd=self.project,
                              capture_output=True, text=True, check=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_dry_run_changes_nothing_and_explicit_install_is_idempotent(self):
        proc = self.configure("install", "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "would_change")
        self.assertFalse(self.settings.parent.exists())
        proc = self.configure("install")
        self.assertNotEqual(proc.returncode, 0)
        self.assertFalse(self.settings.parent.exists())
        proc = self.configure("install", "--yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        settings = json.loads(self.settings.read_text())
        groups = settings["hooks"]
        pre = groups["PreToolUse"][0]["hooks"][0]
        post = groups["PostToolUse"][0]["hooks"][0]
        self.assertEqual(set(groups), {"PreToolUse", "PostToolUse"})
        self.assertIsInstance(pre["args"], list)
        self.assertEqual(pre["onFailure"], "block")
        self.assertNotIn("onFailure", post)
        previous = self.settings.read_bytes()
        proc = self.configure("install", "--yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["status"], "unchanged")
        self.assertEqual(self.settings.read_bytes(), previous)

    def test_install_and_uninstall_preserve_existing_settings(self):
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps(self.existing))
        proc = self.configure("install", "--yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        installed = json.loads(self.settings.read_text())
        self.assertEqual(installed["permissions"], self.existing["permissions"])
        self.assertIn(self.existing["hooks"]["PreToolUse"][0], installed["hooks"]["PreToolUse"])
        proc = self.configure("uninstall", "--yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(self.settings.read_text()), self.existing)

    def test_malformed_and_symlinked_settings_stop_before_a_write(self):
        self.settings.parent.mkdir()
        self.settings.write_text("not json")
        proc = self.configure("install", "--yes")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(self.settings.read_text(), "not json")
        outside = self.project / "unrelated.json"
        outside.write_text("{}")
        self.settings.unlink()
        self.settings.symlink_to(outside)
        proc = self.configure("install", "--yes")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(outside.read_text(), "{}")

    def test_pre_hook_denies_before_write_and_allows_without_overriding_host(self):
        self.arm("$anti-slop review guard -- Review only")
        proc = self.invoke("evaluate", "--project", str(self.project), "--phase", "PreToolUse", payload=self.event)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertFalse((self.project / "note.txt").exists())
        self.arm("$anti-slop change guard files=note.txt -- Edit note")
        proc = self.invoke("evaluate", "--project", str(self.project), "--phase", "PreToolUse", payload=self.event)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {})

    def test_fresh_default_state_leaves_registered_actions_to_host_permissions(self):
        proc = self.invoke("evaluate", "--project", str(self.project), "--phase", "PreToolUse", payload=self.event)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {})
        self.assertFalse((self.project / ".anti-slop").exists())

    def test_uninstall_refuses_to_remove_user_modified_entry(self):
        proc = self.configure("install", "--yes")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        configured = json.loads(self.settings.read_text())
        configured["hooks"]["PreToolUse"][0]["hooks"][0]["timeout"] = 9
        self.settings.write_text(json.dumps(configured))
        proc = self.configure("uninstall", "--yes")
        self.assertNotEqual(proc.returncode, 0)
        self.assertEqual(json.loads(self.settings.read_text()), configured)

    def test_post_hook_reports_violation_without_blocking_or_logging_contents(self):
        self.arm("$anti-slop review guard -- Review only")
        event = dict(self.event, hook_event_name="PostToolUse", tool_response="synthetic response")
        proc = self.invoke("evaluate", "--project", str(self.project), "--phase", "PostToolUse", payload=event)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        result = json.loads(proc.stdout)
        self.assertEqual(result["hookSpecificOutput"]["hookEventName"], "PostToolUse")
        self.assertIn("does not authorize", result["hookSpecificOutput"]["additionalContext"])
        self.assertNotIn("synthetic", proc.stdout + proc.stderr)

    def python_post(self, name, tool="Write"):
        payload = dict(self.event, hook_event_name="PostToolUse", tool_name=tool,
                       tool_input={"file_path": str(self.project / name), "content": "fixture only"})
        result = self.invoke("evaluate", "--project", str(self.project), "--phase", "PostToolUse", payload=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def test_confirmed_write_reports_python_syntax_and_clears_after_correction(self):
        self.arm("$anti-slop change guard files=snippet.py -- Edit only the example")
        source = self.project / "snippet.py"
        source.write_text("value = 1\nprivate_fixture_marker = (\n")
        initial = self.python_post("snippet.py")
        message = initial["hookSpecificOutput"]["additionalContext"]
        self.assertIn("Python syntax error at line 2", message)
        self.assertNotIn("private_fixture_marker", message)
        self.assertNotIn("fixture only", message)
        self.assertEqual(self.python_post("snippet.py"), initial)
        self.assertTrue(source.exists())
        source.write_text("raise RuntimeError('must not execute')\n")
        self.assertEqual(self.python_post("snippet.py", tool="Edit"), {})

    def test_checkpoint_is_excluded_for_unconfirmed_read_only_and_non_python_actions(self):
        source = self.project / "snippet.py"
        source.write_text("value = (\n")
        self.assertEqual(self.python_post("snippet.py"), {})
        self.arm("$anti-slop change watch files=snippet.py|note.txt -- Edit examples")
        self.assertEqual(self.python_post("snippet.py", tool="Read"), {})
        (self.project / "note.txt").write_text("value = (\n")
        self.assertEqual(self.python_post("note.txt"), {})
        self.arm("$anti-slop review watch -- Review only")
        message = self.python_post("snippet.py")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("does not authorize", message)
        self.assertNotIn("Python syntax", message)

    def test_checkpoint_reports_skips_for_large_or_unsafe_sources(self):
        self.arm("$anti-slop change guard -- Edit examples")
        source = self.project / "snippet.py"
        source.write_bytes(b"x" * (64 * 1024 + 1))
        message = self.python_post("snippet.py")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("exceeds 64 KiB", message)
        source.unlink()
        regular = self.project / "example.txt"
        regular.write_text("value = (\n")
        source.symlink_to(regular)
        message = self.python_post("snippet.py")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("could not read a project-local regular file", message)
        self.assertNotIn("Python syntax error at line", message)
        source.unlink()
        message = self.python_post("snippet.py")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("could not read a project-local regular file", message)
        actual = self.project / "actual"
        actual.mkdir()
        (actual / "snippet.py").write_text("value = (\n")
        (self.project / "alias").symlink_to(actual, target_is_directory=True)
        message = self.python_post("alias/snippet.py")["hookSpecificOutput"]["additionalContext"]
        self.assertIn("could not read a project-local regular file", message)
        self.assertNotIn("Python syntax error at line", message)

    def test_checkpoint_does_not_report_or_leak_a_syntax_warning(self):
        self.arm("$anti-slop change guard -- Edit examples")
        (self.project / "snippet.py").write_text("value = 1 is 2\n")
        payload = dict(self.event, hook_event_name="PostToolUse", tool_input={"file_path": "snippet.py"})
        result = self.invoke("evaluate", "--project", str(self.project), "--phase", "PostToolUse", payload=payload)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        self.assertEqual(result.stderr, "")


    def test_invalid_payload_returns_error_and_does_not_reclassify_unsupported_tool(self):
        wrong_phase = dict(self.event, hook_event_name="PostToolUse")
        proc = self.invoke("evaluate", "--project", str(self.project), "--phase", "PreToolUse", payload=wrong_phase)
        self.assertEqual(proc.returncode, 1)
        self.assertNotIn("synthetic", proc.stdout + proc.stderr)
        self.assertIn("invalid Claude hook event", proc.stderr)
        unsupported = dict(self.event, tool_name="Glob")
        proc = self.invoke("evaluate", "--project", str(self.project), "--phase", "PreToolUse", payload=unsupported)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {})


if __name__ == "__main__":
    unittest.main()
