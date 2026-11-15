#!/usr/bin/env python3

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class InstalledAuditTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.project = Path(directory.name).resolve()
        self.env = {**os.environ, "HOME": str(self.project)}
        subprocess.run(["git", "init", "-q"], cwd=self.project, env=self.env, check=True)
        subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.test",
             "commit", "--allow-empty", "-qm", "fixture"],
            cwd=self.project, env=self.env, check=True,
        )
        self.target = self.project / ".codex" / "skills"
        self.manifest = self.target / ".anti-slop-selection.json"
        self.write_selection()

    def write_selection(self, *skills):
        for skill in ("anti-slop-engineering", *skills):
            entry = self.target / skill / "SKILL.md"
            entry.parent.mkdir(parents=True, exist_ok=True)
            entry.write_text(f"---\nname: {skill}\n---\n", encoding="utf-8")
        self.manifest.write_text(json.dumps({
            "format": 1, "version": "1.8.0", "scope": "project", "agents": ["codex"],
            "skills": ["anti-slop-engineering", *skills],
        }), encoding="utf-8")

    def run_audit(self, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_runner.py"), "audit", "--json", *args],
            cwd=self.project, env=self.env, capture_output=True, text=True, timeout=45,
        )

    def test_core_selection_only_skips_curated_optional_review_guards(self):
        result = self.run_audit("--installed-selection", str(self.manifest))
        self.assertEqual(result.returncode, 0, result.stderr)
        guards = json.loads(result.stdout)["guards"]
        self.assertEqual(guards["tagore_guard"]["skip_type"], "not-selected")
        for name in ("diff_guard", "sre_guard", "forensic_hunter", "demock_guard", "asset_provenance_guard"):
            self.assertEqual(guards[name]["status"], "PASS", name)

    def test_default_audit_ignores_installation_manifest(self):
        result = self.run_audit()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["guards"]["tagore_guard"]["status"], "PASS")

    def test_selected_installed_review_skill_runs_guard_and_stale_file_is_skipped(self):
        self.write_selection("tagore-guard")
        arg = ("--installed-selection", str(self.manifest))
        result = self.run_audit(*arg)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["guards"]["tagore_guard"]["status"], "PASS")
        (self.target / "tagore-guard" / "SKILL.md").unlink()
        result = self.run_audit(*arg)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["guards"]["tagore_guard"]["skip_type"], "not-selected")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO fixtures require POSIX support")
    def test_fifo_manifest_fails_without_waiting_for_a_writer(self):
        self.manifest.unlink()
        os.mkfifo(self.manifest)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "audit_runner.py"), "audit", "--json",
             "--installed-selection", str(self.manifest)],
            cwd=self.project, env=self.env, capture_output=True, text=True, timeout=8,
        )
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["status"], "ERROR")
        self.assertEqual(report["guards"]["tagore_guard"]["status"], "PASS")

    def test_invalid_selection_fails_with_json_error(self):
        self.manifest.write_text('{"format":1,"skills":["../forensic-hunter"]}', encoding="utf-8")
        result = self.run_audit("--installed-selection", str(self.manifest))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)["status"], "ERROR")


if __name__ == "__main__":
    unittest.main()
