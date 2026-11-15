# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "diff_guard.py"


class DiffLifecycleTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(prefix="diff hooks ")
        self.addCleanup(tmp.cleanup)
        self.root = pathlib.Path(tmp.name).resolve()
        self.repo = self.root / "reviewed"
        self.hooks = self.root / "trusted hooks"
        self.hooks.mkdir()
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("-c", "user.email=test@example.invalid", "-c", "user.name=Test",
                 "commit", "--allow-empty", "-qm", "baseline")
        (self.repo / "feature.py").write_text("ready = True\n", encoding="utf-8")
        self.git("add", "feature.py")
        self.events = self.hooks / "events.jsonl"

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.repo, check=True, capture_output=True)

    def install_hooks(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        for name in ("pre_scan", "post_scan"):
            (directory / f"{name}.py").write_text(
                "import json, os, pathlib, sys\n"
                "event = json.load(sys.stdin)\n"
                "with pathlib.Path('events.jsonl').open('a', encoding='utf-8') as stream:\n"
                "    stream.write(json.dumps({"
                "'event': event, 'caller_value': os.environ.get('DIFF_HOOK_CALLER_VALUE')"
                "}) + '\\n')\n",
                encoding="utf-8",
            )

    def scan(self, *options, check=True, env=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--repo", str(self.repo), "--json", *options],
            cwd=self.root, check=check, capture_output=True, text=True, env=env,
        )

    def test_default_scan_ignores_checkout_hooks(self):
        checkout_hooks = self.repo / ".anti-slop" / "hooks"
        self.install_hooks(checkout_hooks)

        report = json.loads(self.scan().stdout)

        self.assertEqual(report["summary"]["changed_files"], 1)
        self.assertFalse(list(self.root.rglob("events.jsonl")))

    def test_explicit_hooks_receive_ordered_events_without_changing_report(self):
        self.install_hooks(self.hooks)
        self.install_hooks(self.repo / ".anti-slop" / "hooks")
        baseline_report = json.loads(self.scan().stdout)
        result = self.scan(
            "--hooks-dir", str(self.hooks), check=False,
            env={**os.environ, "DIFF_HOOK_CALLER_VALUE": "benign-marker"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)

        actual = [json.loads(line) for line in self.events.read_text().splitlines()]
        self.assertEqual(
            [(entry["event"]["event_type"], entry["event"]["repo"],
              entry["event"]["base"], entry["caller_value"]) for entry in actual],
            [("pre_scan", str(self.repo), "HEAD", None),
             ("post_scan", str(self.repo), "HEAD", None)],
        )
        self.assertEqual(actual[0]["event"]["payload"], {"review_lines": 400})
        self.assertEqual(actual[1]["event"]["payload"], {"summary": baseline_report["summary"]})
        self.assertEqual(list(self.root.rglob("events.jsonl")), [self.events])
        self.assertEqual(report, baseline_report)
        self.scan()
        self.assertEqual(len(self.events.read_text().splitlines()), 2)

    def test_checkout_hook_directory_is_rejected_even_when_explicit(self):
        checkout_hooks = self.repo / ".anti-slop" / "hooks"
        self.install_hooks(checkout_hooks)

        result = self.scan("--hooks-dir", str(checkout_hooks), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("outside the scanned repository", json.loads(result.stdout)["error"])
        self.assertFalse(list(self.root.rglob("events.jsonl")))

    def test_checkout_alias_to_external_hooks_is_rejected(self):
        self.install_hooks(self.hooks)
        alias = self.repo / "hooks"
        alias.symlink_to(self.hooks, target_is_directory=True)

        result = self.scan("--hooks-dir", str(alias), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("outside the scanned repository", json.loads(result.stdout)["error"])
        self.assertFalse(self.events.exists())

    def test_external_alias_into_checkout_is_rejected(self):
        checkout_hooks = self.repo / "hooks"
        self.install_hooks(checkout_hooks)
        alias = self.root / "link"
        alias.symlink_to(checkout_hooks, target_is_directory=True)

        result = self.scan("--hooks-dir", str(alias), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("outside the scanned repository", json.loads(result.stdout)["error"])
        self.assertFalse(list(self.root.rglob("events.jsonl")))

    def test_symlinked_hook_fails_before_any_hook_runs(self):
        self.install_hooks(self.hooks)
        another = self.root / "another"
        self.install_hooks(another)
        symlink = self.hooks / "post_scan.py"
        symlink.unlink()
        symlink.symlink_to(another / "post_scan.py")

        result = self.scan("--hooks-dir", str(self.hooks), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("post_scan.py", json.loads(result.stdout)["error"])
        self.assertFalse(self.events.exists())

    def test_pre_scan_failure_stops_the_post_scan(self):
        self.install_hooks(self.hooks)
        (self.hooks / "pre_scan.py").write_text("raise SystemExit(7)\n", encoding="utf-8")

        result = self.scan("--hooks-dir", str(self.hooks), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("pre_scan.py exited with code 7", json.loads(result.stdout)["error"])
        self.assertFalse(self.events.exists())

    def test_only_explicit_absolute_hook_paths_are_accepted(self):
        self.install_hooks(self.hooks)

        result = self.scan("--hooks-dir", self.hooks.name, check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("absolute", json.loads(result.stdout)["error"])
        self.assertFalse(self.events.exists())

    def test_empty_hook_directory_reports_configuration_error(self):
        result = self.scan("--hooks-dir", str(self.hooks), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("neither pre_scan.py nor post_scan.py", json.loads(result.stdout)["error"])

    def test_post_scan_timeout_is_reported(self):
        (self.hooks / "post_scan.py").write_text("import time\ntime.sleep(7)\n", encoding="utf-8")

        result = self.scan("--hooks-dir", str(self.hooks), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("post_scan.py timed out after 5 seconds", json.loads(result.stdout)["error"])

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "POSIX access control requires an unprivileged user")
    def test_inaccessible_hook_path_reports_configuration_error(self):
        parent = self.root / "inaccessible"
        parent.mkdir()
        hooks = parent / "hooks"
        self.install_hooks(hooks)
        parent.chmod(0)
        self.addCleanup(parent.chmod, 0o700)

        result = self.scan("--hooks-dir", str(hooks), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("could not resolve --hooks-dir", json.loads(result.stdout)["error"].lower())

    def test_case_alias_cannot_hide_checkout_hook_directory(self):
        checkout_hooks = self.repo / "hooks"
        self.install_hooks(checkout_hooks)
        case_alias = self.repo.with_name(self.repo.name.upper())

        if case_alias.is_dir():
            candidate = case_alias / "hooks"
        else:
            candidate = checkout_hooks

        result = self.scan("--hooks-dir", str(candidate), check=False)

        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("outside the scanned repository", json.loads(result.stdout)["error"])
        self.assertFalse(list(self.root.rglob("events.jsonl")))
