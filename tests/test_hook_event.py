import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "exec_guard.py"


class HookEventTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name)
        self.state_file = self.repo / ".anti-slop" / "state.json"
        self.event = {
            "schema_version": 1,
            "agent": "fixture",
            "phase": "pre_tool",
            "tool": "edit_file",
            "operation": "write",
            "target_paths": ["src/draft.txt"],
            "payload_trust": "untrusted",
            "correlation_id": "demo-1",
        }

    def arm(self, directive):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "parse-prompt", directive],
            cwd=self.repo, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def invoke(self, event=None, *, payload=None):
        request = self.event if event is None else event
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "hook-event"], cwd=self.repo,
            input=json.dumps(request) if payload is None else payload,
            capture_output=True, text=True, timeout=5, check=False,
        )
        self.assertTrue(result.stdout, result.stderr)
        return result.returncode, json.loads(result.stdout)

    def test_equivalent_provider_events_reuse_policy_and_replay_without_writes(self):
        self.arm("$anti-slop review guard -- Review only")
        state_before = self.state_file.read_bytes()
        for provider in ("fixture-a", "fixture-b"):
            event = dict(self.event, agent=provider)
            code, decision = self.invoke(event)
            self.assertEqual(code, 2)
            self.assertEqual(decision["decision"], "block")
            self.assertEqual(decision["reason_code"], "MODE_FORBIDS_MUTATION")
            self.assertEqual(decision["correlation_id"], "demo-1")
            self.assertEqual(self.invoke(event), (code, decision))
        self.assertEqual(self.state_file.read_bytes(), state_before)
        self.assertFalse(self.state_file.with_name("events.jsonl").exists())

    def test_read_within_active_review_does_not_grant_host_permission(self):
        self.arm("$anti-slop review guard -- Review only")
        event = dict(self.event, tool="read_file", operation="read")
        code, decision = self.invoke(event)
        self.assertEqual(code, 0)
        self.assertEqual(decision["decision"], "allow")
        self.assertEqual(decision["reason_code"], "WITHIN_CONTRACT")

    def test_post_action_and_watch_return_feedback_without_preventive_result(self):
        self.arm("$anti-slop review guard -- Review only")
        code, decision = self.invoke(dict(self.event, phase="post_tool"))
        self.assertEqual((code, decision["decision"]), (0, "warn"))
        self.arm("$anti-slop review watch -- Review only")
        code, decision = self.invoke()
        self.assertEqual((code, decision["decision"]), (0, "warn"))

    def test_known_targets_are_resolved_under_trusted_working_directory(self):
        self.arm("$anti-slop change guard files=src/** -- Edit drafts")
        (self.repo / "src").mkdir()
        code, decision = self.invoke(dict(self.event, target_paths=[str(self.repo / "src" / "draft.txt")]))
        self.assertEqual((code, decision["decision"]), (0, "allow"))
        code, decision = self.invoke(dict(self.event, target_paths=["notes.txt"]))
        self.assertEqual((code, decision["decision"]), (2, "block"))
        self.assertNotIn("notes.txt", decision["message"])

    def test_path_scope_preserves_leading_dots(self):
        self.arm("$anti-slop change guard files=.settings/** -- Edit project settings")
        for path, expected in ((".settings/local.json", "allow"), ("settings/local.json", "block")):
            with self.subTest(path=path):
                code, decision = self.invoke(dict(self.event, target_paths=[path]))
                self.assertEqual(code, 0 if expected == "allow" else 2)
                self.assertEqual(decision["decision"], expected)

    def test_policy_storage_does_not_open_non_regular_files(self):
        import os

        if hasattr(os, "mkfifo"):
            self.state_file.parent.mkdir()
            os.mkfifo(self.state_file)
            code, decision = self.invoke()
            self.assertEqual((code, decision["decision"]), (1, "error"))
            self.assertEqual(decision["reason_code"], "STATE_DAMAGED")

    def test_unknown_operations_keep_read_only_authorization(self):
        self.arm("$anti-slop answer guard -- Read only")
        code, decision = self.invoke(dict(self.event, tool="opaque_tool", operation="unknown", target_paths=[]))
        self.assertEqual((code, decision["decision"]), (2, "block"))
        self.assertEqual(decision["reason_code"], "MUTABILITY_UNPROVEN")

    def test_invalid_oversized_and_unknown_version_are_bounded_errors(self):
        invalid = [
            "not JSON",
            json.dumps(dict(self.event, schema_version=2)),
            json.dumps(dict(self.event, state_dir="/not-trusted")),
            json.dumps(dict(self.event, tool=["not-a-string"])),
            json.dumps(dict(self.event, target_paths=["src/draft.txt"] * 33)),
            json.dumps(dict(self.event, tool="x" * 65536)),
            '{"schema_version":1,"schema_version":2}',
        ]
        for payload in invalid:
            with self.subTest(size=len(payload)):
                code, decision = self.invoke(payload=payload)
                self.assertEqual((code, decision["decision"]), (1, "error"))
                self.assertNotIn("not-trusted", decision["message"])
        self.assertFalse(self.state_file.parent.exists())

    def test_damaged_policy_is_explicit_error(self):
        self.state_file.parent.mkdir()
        self.state_file.write_text("broken policy", encoding="utf-8")
        code, decision = self.invoke()
        self.assertEqual((code, decision["decision"]), (1, "error"))
        self.assertEqual(decision["reason_code"], "STATE_DAMAGED")
        self.assertNotIn("broken policy", decision["message"])

    def test_unconfirmed_does_not_persist_or_arm_anything(self):
        code, decision = self.invoke()
        self.assertEqual((code, decision["decision"]), (0, "allow"))
        self.assertEqual(decision["reason_code"], "CONTROL_INACTIVE")
        self.assertFalse(self.state_file.parent.exists())

    def test_input_reader_does_not_consume_more_than_configured_bound(self):
        sys.path.insert(0, str(SCRIPT.parent))
        self.addCleanup(sys.path.pop, 0)
        from exec_guard import HOOK_EVENT_MAX_BYTES, read_hook_object

        stream = io.BytesIO(b"x" * (HOOK_EVENT_MAX_BYTES + 100))
        with self.assertRaises(ValueError):
            read_hook_object(stream)
        self.assertEqual(stream.tell(), HOOK_EVENT_MAX_BYTES + 1)


if __name__ == "__main__":
    unittest.main()
