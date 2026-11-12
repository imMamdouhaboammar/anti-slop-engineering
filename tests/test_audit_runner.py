#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import re
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import audit_runner
from audit_runner import (
    generate_audit_markdown,
    get_next_audit_file,
    handle_mode,
    load_settings,
    save_settings,
)


def extract_bash_commands(markdown_text: str) -> list[str]:
    """Extract non-comment command lines from ```bash blocks in markdown."""
    commands = []
    in_block = False
    for line in markdown_text.splitlines():
        if line.strip() == "```bash":
            in_block = True
            continue
        if in_block and line.strip() == "```":
            in_block = False
            continue
        if in_block:
            cleaned = line.strip()
            if cleaned and not cleaned.startswith("#"):
                commands.append(cleaned)
    return commands


class AuditRunnerTests(unittest.TestCase):
    def setUp(self):
        self.sample_findings = [
            {
                "id": "FINDING-001",
                "guard": "diff_guard",
                "rule": "SEVEN-GATES",
                "severity": "BLOCKER",
                "file": "src/index.ts",
                "line": 10,
                "message": "Direct modification without contract",
                "snippet": "const a = 1;",
                "remediation": "Follow Gate 1 contract",
            },
            {
                "id": "FINDING-002",
                "guard": "contrast_guard",
                "rule": "WCAG-2.2",
                "severity": "MEDIUM",
                "file": "src/App.tsx",
                "line": 42,
                "message": "Low contrast: #777 on white",
                "snippet": "<div className='text-[#777] bg-white'>",
                "remediation": "Increase contrast",
            },
        ]

    def test_mode_management(self):
        # Setting mode to during
        ret = handle_mode(["during"])
        self.assertEqual(ret, 0)
        self.assertEqual(load_settings().get("mode"), "during")

        # Setting mode to after
        ret = handle_mode(["after"])
        self.assertEqual(ret, 0)
        self.assertEqual(load_settings().get("mode"), "after")

        # Invalid mode returns 2
        ret = handle_mode(["invalid_mode"])
        self.assertEqual(ret, 2)

    def test_generate_audit_markdown(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_test.md"
        try:
            content = generate_audit_markdown(self.sample_findings, tmp_file)
            self.assertIn("# Anti-Slop Engineering Audit Report", content)
            self.assertIn("FINDING-001", content)
            self.assertIn("BLOCKER", content)
            self.assertIn("WCAG-2.2", content)
            self.assertTrue(tmp_file.exists())
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_cli_invocation(self):
        script = str(SCRIPTS_DIR / "audit_runner.py")
        res = subprocess.run([sys.executable, script, "mode"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("Current anti-slop-engineering mode:", res.stdout)

    def test_docstring_does_not_advertise_fix_command(self):
        doc = audit_runner.__doc__ or ""
        self.assertNotIn("fix --finding", doc)
        self.assertNotIn("scripts/audit_runner.py fix", doc)

    def test_dossier_remediation_workflow_during_mode(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_during.md"
        try:
            content = generate_audit_markdown(self.sample_findings, tmp_file, mode="during")
            self.assertIn("DURING Mode", content)
            self.assertNotIn("AFTER Mode", content)
            self.assertNotIn("bunx anti-slop-engineering fix", content)
            self.assertNotIn("audit_runner.py fix", content)
            self.assertIn("`FINDING-001`", content)
            self.assertIn("`FINDING-002`", content)
            self.assertIn("Follow Gate 1 contract", content)

            commands = extract_bash_commands(content)
            self.assertTrue(len(commands) > 0, "Dossier should provide at least one verification command")
            for cmd in commands:
                self.assertNotIn("fix", cmd.lower())
                # Verify that every printed command actually exists and runs
                args = shlex.split(cmd)
                if args[0] == "python3":
                    args[0] = sys.executable
                proc = subprocess.run(args, cwd=ROOT_DIR, capture_output=True, text=True)
                # Audit command returns 0 (pass) or 1 (blocked findings), but must NOT fail with error 2 or 127
                self.assertIn(proc.returncode, (0, 1), f"Command '{cmd}' failed: {proc.stderr}")
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_dossier_remediation_workflow_after_mode(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_after.md"
        try:
            content = generate_audit_markdown(self.sample_findings, tmp_file, mode="after")
            self.assertIn("AFTER Mode", content)
            self.assertNotIn("DURING Mode", content)
            self.assertNotIn("bunx anti-slop-engineering fix", content)
            self.assertNotIn("audit_runner.py fix", content)
            self.assertIn("`FINDING-001`", content)
            self.assertIn("`FINDING-002`", content)

            commands = extract_bash_commands(content)
            self.assertTrue(len(commands) > 0)
            for cmd in commands:
                self.assertNotIn("fix", cmd.lower())
                args = shlex.split(cmd)
                if args[0] == "python3":
                    args[0] = sys.executable
                proc = subprocess.run(args, cwd=ROOT_DIR, capture_output=True, text=True)
                self.assertIn(proc.returncode, (0, 1), f"Command '{cmd}' failed: {proc.stderr}")
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_dossier_remediation_workflow_zero_findings(self):
        tmp_file = Path(__file__).resolve().parent / "tmp_audit_clean.md"
        try:
            content = generate_audit_markdown([], tmp_file, mode="during")
            self.assertIn("0 findings", content)
            self.assertNotIn("bunx anti-slop-engineering fix", content)
            commands = extract_bash_commands(content)
            self.assertTrue(len(commands) > 0)
            for cmd in commands:
                self.assertNotIn("fix", cmd.lower())
        finally:
            if tmp_file.exists():
                tmp_file.unlink()

    def test_fix_command_rejected_truthfully(self):
        script = str(SCRIPTS_DIR / "audit_runner.py")
        res = subprocess.run([sys.executable, script, "fix"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 2)
        self.assertIn("not supported", res.stderr.lower())
