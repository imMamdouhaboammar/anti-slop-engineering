import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "scripts" / "codex_hooks.py"
GUARD = ROOT / "scripts" / "exec_guard.py"


class CodexHookTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.project = Path(temp.name)
        self.settings = self.project / ".codex" / "hooks.json"
        existing = {"description": "project metadata", "hooks": {"Stop": []}}
        self.settings.parent.mkdir()
        self.settings.write_text(json.dumps(existing))
        self.original = existing

    def invoke(self, *args, payload=None):
        return subprocess.run(
            [sys.executable, str(HOOK), *args, "--project", str(self.project)],
            cwd=self.project, input=json.dumps(payload) if payload is not None else None,
            capture_output=True, text=True, timeout=8, check=False,
        )

    def arm(self, directive):
        subprocess.run([sys.executable, str(GUARD), "parse-prompt", directive], cwd=self.project,
                       capture_output=True, check=True)

    def payload(self, patch, phase="PreToolUse"):
        return {
            "hook_event_name": phase, "tool_name": "apply_patch", "tool_use_id": "fixture-call",
            "tool_input": {"command": patch}, "cwd": str(self.project),
        }

    def test_explicit_project_setup_and_rollback(self):
        old = self.settings.read_bytes()
        result = self.invoke("install", "--dry-run")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.settings.read_bytes(), old)
        result = self.invoke("install", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        configured = json.loads(self.settings.read_text())
        self.assertIn("apply_patch", configured["hooks"]["PreToolUse"][0]["matcher"])
        self.assertEqual(configured["hooks"]["Stop"], self.original["hooks"]["Stop"])
        result = self.invoke("uninstall", "--yes")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(self.settings.read_text()), self.original)

    def test_file_patch_uses_explicit_allowed_targets(self):
        self.arm("$anti-slop change guard files=docs/** -- Working on docs")
        allowed = "*** Begin Patch\n*** Add File: docs/note.txt\n+synthetic\n*** End Patch\n"
        denied = "*** Begin Patch\n*** Add File: notes.txt\n+synthetic\n*** End Patch\n"
        result = self.invoke("evaluate", "--phase", "PreToolUse", payload=self.payload(allowed))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {})
        result = self.invoke("evaluate", "--phase", "PreToolUse", payload=self.payload(denied))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertNotIn("synthetic", result.stdout + result.stderr)

    def test_move_policy_checks_source_and_destination(self):
        self.arm("$anti-slop change guard files=docs/** -- Working on docs")
        patch = (
            "*** Begin Patch\n*** Update File: docs/old.txt\n"
            "*** Move to: notes.txt\n@@\n-Old\n+New\n*** End Patch\n"
        )
        result = self.invoke("evaluate", "--phase", "PreToolUse", payload=self.payload(patch))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_invalid_patch_is_not_given_an_allow_decision(self):
        self.arm("$anti-slop review guard -- Review only")
        result = self.invoke("evaluate", "--phase", "PreToolUse", payload=self.payload("opaque event"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hookSpecificOutput"]["permissionDecision"], "deny")
        result = self.invoke("evaluate", "--phase", "PostToolUse", payload=self.payload("opaque event", "PostToolUse"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("could not", json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_post_action_returns_advisory_feedback(self):
        self.arm("$anti-slop review watch -- Review only")
        patch = "*** Begin Patch\n*** Add File: note.txt\n+synthetic\n*** End Patch\n"
        result = self.invoke("evaluate", "--phase", "PostToolUse", payload=self.payload(patch, "PostToolUse"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("does not authorize", json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"])
