# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Tests for lifecycle hook dispatching and error fencing in core triage loops."""
import json
import os
import pathlib
import stat
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_DIFF = ROOT / "scripts" / "diff_guard.py"

from scripts.hook_dispatcher import (
    VALID_HOOK_EVENTS,
    create_hook_event,
    dispatch_hook,
    discover_hooks,
    dispatch_lifecycle_event,
)


def git(path, *args):
    return subprocess.run(
        ["git", *args], cwd=path, text=True, capture_output=True, check=True
    ).stdout.strip()


class HookDispatcherContractTests(unittest.TestCase):
    def test_create_hook_event_schema(self):
        event = create_hook_event(
            event_type="pre_scan",
            repo="/path/to/repo",
            base="HEAD",
            payload={"custom": 123},
            context={"mode": "after"},
        )
        self.assertIn("event_id", event)
        self.assertTrue(event["event_id"].startswith("evt_"))
        self.assertEqual(event["event_type"], "pre_scan")
        self.assertEqual(event["repo"], "/path/to/repo")
        self.assertEqual(event["base"], "HEAD")
        self.assertEqual(event["payload"], {"custom": 123})
        self.assertEqual(event["context"]["mode"], "after")
        self.assertIsInstance(event["timestamp"], (int, float))

    def test_create_hook_event_rejects_unknown_event(self):
        with self.assertRaises(ValueError):
            create_hook_event("invalid_event", "/repo", "HEAD")

    def test_dispatch_hook_success(self):
        with tempfile.TemporaryDirectory() as td:
            hook_file = pathlib.Path(td) / "test_hook.py"
            hook_file.write_text(
                "import sys, json\n"
                "event = json.load(sys.stdin)\n"
                "res = {'decision': 'allow', 'message': f'Handled {event[\"event_type\"]}'}\n"
                "json.dump(res, sys.stdout)\n"
            )
            event = create_hook_event("pre_scan", td, "HEAD")
            res = dispatch_hook([sys.executable, str(hook_file)], event, timeout=3.0)
            self.assertEqual(res["status"], "success")
            self.assertEqual(res["decision"], "allow")
            self.assertIn("Handled pre_scan", res["message"])
            self.assertFalse(res["timed_out"])
            self.assertEqual(res["returncode"], 0)

    def test_dispatch_hook_findings_injection(self):
        with tempfile.TemporaryDirectory() as td:
            hook_file = pathlib.Path(td) / "finding_hook.py"
            hook_file.write_text(
                "import sys, json\n"
                "json.dump({\n"
                "  'decision': 'warn',\n"
                "  'findings': [{'id': 'HOOK_FINDING', 'severity': 'review', 'file': 'foo.py', 'evidence': 'found something'}]\n"
                "}, sys.stdout)\n"
            )
            event = create_hook_event("post_scan", td, "HEAD")
            res = dispatch_hook([sys.executable, str(hook_file)], event, timeout=3.0)
            self.assertEqual(res["decision"], "warn")
            self.assertEqual(len(res["findings"]), 1)
            self.assertEqual(res["findings"][0]["id"], "HOOK_FINDING")

    def test_dispatch_hook_timeout_guard(self):
        with tempfile.TemporaryDirectory() as td:
            hook_file = pathlib.Path(td) / "slow_hook.py"
            hook_file.write_text("import time\ntime.sleep(5)\n")
            event = create_hook_event("pre_scan", td, "HEAD")
            res = dispatch_hook([sys.executable, str(hook_file)], event, timeout=0.3)
            self.assertEqual(res["status"], "timeout")
            self.assertTrue(res["timed_out"])
            self.assertEqual(res["decision"], "error")
            self.assertIn("timed out", res["error"])

    def test_dispatch_hook_error_fencing_non_zero_exit(self):
        with tempfile.TemporaryDirectory() as td:
            hook_file = pathlib.Path(td) / "fail_hook.py"
            hook_file.write_text("import sys\nsys.stderr.write('Fatal crash')\nsys.exit(42)\n")
            event = create_hook_event("pre_scan", td, "HEAD")
            res = dispatch_hook([sys.executable, str(hook_file)], event, timeout=3.0)
            self.assertEqual(res["status"], "error")
            self.assertEqual(res["returncode"], 42)
            self.assertEqual(res["decision"], "error")
            self.assertIn("Fatal crash", res["error"])

    def test_dispatch_hook_error_fencing_invalid_json(self):
        with tempfile.TemporaryDirectory() as td:
            hook_file = pathlib.Path(td) / "bad_json_hook.py"
            hook_file.write_text("print('not json at all')\n")
            event = create_hook_event("pre_scan", td, "HEAD")
            res = dispatch_hook([sys.executable, str(hook_file)], event, timeout=3.0)
            self.assertEqual(res["status"], "error")
            self.assertEqual(res["decision"], "error")
            self.assertIn("Invalid JSON", res["error"])

    def test_dispatch_hook_missing_executable(self):
        event = create_hook_event("pre_scan", "/tmp", "HEAD")
        res = dispatch_hook(["/path/does/not/exist/hook.sh"], event, timeout=3.0)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["decision"], "error")
        self.assertIn("not found", res["error"].lower())

    def test_environment_sanitization_in_hook(self):
        with tempfile.TemporaryDirectory() as td:
            hook_file = pathlib.Path(td) / "env_check.py"
            hook_file.write_text(
                "import os, sys, json\n"
                "leaked = [k for k in os.environ if any(x in k.upper() for x in ['KEY', 'SECRET', 'TOKEN', 'PASSWORD'])]\n"
                "json.dump({'decision': 'allow', 'leaked': leaked}, sys.stdout)\n"
            )
            old_env = os.environ.get("SUPER_SECRET_TOKEN")
            os.environ["SUPER_SECRET_TOKEN"] = "sensitive1234"
            try:
                event = create_hook_event("pre_scan", td, "HEAD")
                res = dispatch_hook([sys.executable, str(hook_file)], event, timeout=3.0)
                self.assertEqual(res["status"], "success")
                raw = json.loads(res.get("raw_stdout", "{}"))
                self.assertEqual(raw.get("leaked"), [])
            finally:
                if old_env is None:
                    os.environ.pop("SUPER_SECRET_TOKEN", None)
                else:
                    os.environ["SUPER_SECRET_TOKEN"] = old_env


class HookDiscoveryAndIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.repo = pathlib.Path(self.temp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "test@example.invalid")
        git(self.repo, "config", "user.name", "Test")
        (self.repo / "src").mkdir()
        (self.repo / "src" / "sample.py").write_text("print('hello')\n")
        git(self.repo, "add", ".")
        git(self.repo, "commit", "-qm", "baseline")

    def tearDown(self):
        self.temp.cleanup()

    def test_discover_hooks_from_directory(self):
        hooks_dir = self.repo / ".anti-slop" / "hooks"
        hooks_dir.mkdir(parents=True)
        pre_hook = hooks_dir / "pre_scan.py"
        pre_hook.write_text("import sys, json\njson.dump({'decision': 'allow'}, sys.stdout)\n")
        
        post_dir = hooks_dir / "post_scan"
        post_dir.mkdir()
        post_hook = post_dir / "01_check.py"
        post_hook.write_text("import sys, json\njson.dump({'decision': 'allow'}, sys.stdout)\n")

        discovered = discover_hooks(repo=self.repo, hooks_dir=hooks_dir)
        self.assertIn("pre_scan", discovered)
        self.assertEqual(len(discovered["pre_scan"]), 1)
        self.assertIn("post_scan", discovered)
        self.assertEqual(len(discovered["post_scan"]), 1)

    def test_discover_hooks_from_settings(self):
        settings_file = self.repo / ".anti-slop" / "settings.json"
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(json.dumps({
            "mode": "after",
            "hooks": {
                "pre_scan": ["scripts/custom_pre.py"]
            }
        }))
        discovered = discover_hooks(repo=self.repo)
        self.assertIn("pre_scan", discovered)
        self.assertTrue(any("scripts/custom_pre.py" in h for h in discovered["pre_scan"]))

    def test_diff_guard_executes_hooks(self):
        hooks_dir = self.repo / "hooks"
        hooks_dir.mkdir()
        post_hook = hooks_dir / "post_scan.py"
        post_hook.write_text(
            "import sys, json\n"
            "data = json.load(sys.stdin)\n"
            "json.dump({\n"
            "  'decision': 'warn',\n"
            "  'findings': [{'id': 'HOOK_SECURITY_AUDIT', 'severity': 'review', 'file': 'src/sample.py', 'evidence': 'Hook verified'}]\n"
            "}, sys.stdout)\n"
        )
        (self.repo / "src" / "sample.py").write_text("print('modified')\n")

        res = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIFF),
                "--repo",
                str(self.repo),
                "--base",
                "HEAD",
                "--json",
                "--hooks-dir",
                str(hooks_dir),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        report = json.loads(res.stdout)
        self.assertIn("hook_results", report)
        self.assertGreaterEqual(len(report["hook_results"]), 1)
        finding_ids = [f["id"] for f in report["findings"]]
        self.assertIn("HOOK_SECURITY_AUDIT", finding_ids)

    def test_diff_guard_blocking_hook_causes_fail_on_blocker(self):
        hooks_dir = self.repo / "hooks"
        hooks_dir.mkdir()
        post_hook = hooks_dir / "post_scan.py"
        post_hook.write_text(
            "import sys, json\n"
            "json.dump({\n"
            "  'decision': 'block',\n"
            "  'findings': [{'id': 'HOOK_BLOCKED', 'severity': 'blocker', 'file': 'src/sample.py', 'evidence': 'Blocked by hook'}]\n"
            "}, sys.stdout)\n"
        )
        (self.repo / "src" / "sample.py").write_text("print('modified')\n")

        res = subprocess.run(
            [
                sys.executable,
                str(SCRIPT_DIFF),
                "--repo",
                str(self.repo),
                "--base",
                "HEAD",
                "--json",
                "--hooks-dir",
                str(hooks_dir),
                "--fail-on-blocker",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2)
        report = json.loads(res.stdout)
        finding_ids = [f["id"] for f in report["findings"]]
        self.assertIn("HOOK_BLOCKED", finding_ids)


if __name__ == "__main__":
    unittest.main()
