#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Tests for automated version bumper script."""

import json
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from bump_version import (  # noqa: E402
    bump_repository_version,
    compute_next_version,
    parse_semver,
    read_current_version,
)


class BumpVersionTests(unittest.TestCase):
    def test_parse_semver_valid_and_invalid(self):
        valid = parse_semver("1.2.3")
        self.assertEqual(valid, {"major": 1, "minor": 2, "patch": 3, "prerelease": None})

        with_v = parse_semver("v2.0.1-alpha.1")
        self.assertEqual(with_v, {"major": 2, "minor": 0, "patch": 1, "prerelease": "alpha.1"})

        invalid = parse_semver("invalid-version")
        self.assertIsNone(invalid)

    def test_compute_next_version(self):
        self.assertEqual(compute_next_version("1.2.3", "patch"), "1.2.4")
        self.assertEqual(compute_next_version("1.2.3", "minor"), "1.3.0")
        self.assertEqual(compute_next_version("1.2.3", "major"), "2.0.0")
        self.assertEqual(compute_next_version("1.2.3", "3.0.0"), "3.0.0")
        self.assertEqual(compute_next_version("1.2.3", "v3.1.0"), "3.1.0")

        with self.assertRaises(ValueError):
            compute_next_version("1.2.3", "invalid-bump")

    def test_bump_in_mock_repository(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)

            (tmp_path / "package.json").write_text(json.dumps({"name": "test", "version": "1.0.0"}), encoding="utf-8")
            (tmp_path / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
            (tmp_path / ".skills.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
            (tmp_path / "marketplace.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")
            (tmp_path / "SKILL.md").write_text('---\nversion: "1.0.0"\n---\n', encoding="utf-8")
            (tmp_path / "bin").mkdir()
            (tmp_path / "bin" / "cli.js").write_text('console.log("Anti-Slop Engineering CLI (v1.0.0)");', encoding="utf-8")
            (tmp_path / "CITATION.cff").write_text("version: 1.0.0\ndate-released: 2026-01-01\n", encoding="utf-8")

            rust_dir = tmp_path / "services" / "anti-slop-rust"
            rust_dir.mkdir(parents=True)
            (rust_dir / "Cargo.toml").write_text('[package]\nname = "test"\nversion = "1.0.0"\n', encoding="utf-8")

            go_model = tmp_path / "services" / "toil-guard-go" / "pkg" / "model"
            go_model.mkdir(parents=True)
            (go_model / "types.go").write_text('var meta = Meta{Version: "1.0.0"}\n', encoding="utf-8")

            go_srv = tmp_path / "services" / "toil-guard-go" / "pkg" / "server"
            go_srv.mkdir(parents=True)
            (go_srv / "server.go").write_text('data := map[string]string{"version": "1.0.0"}\n', encoding="utf-8")

            # 1. Test Dry Run: files must not change
            dry_report = bump_repository_version(tmp_path, "minor", release_date="2026-11-02", dry_run=True)
            self.assertEqual(dry_report["previous_version"], "1.0.0")
            self.assertEqual(dry_report["new_version"], "1.1.0")
            self.assertEqual(len(dry_report["updated_files"]), 10)
            self.assertEqual(read_current_version(tmp_path), "1.0.0")

            # 2. Test Real Bump: files must change to 1.1.0
            real_report = bump_repository_version(tmp_path, "minor", release_date="2026-11-02", dry_run=False)
            self.assertEqual(real_report["new_version"], "1.1.0")
            self.assertEqual(read_current_version(tmp_path), "1.1.0")

            pkg_data = json.loads((tmp_path / "package.json").read_text(encoding="utf-8"))
            self.assertEqual(pkg_data["version"], "1.1.0")

            cff_content = (tmp_path / "CITATION.cff").read_text(encoding="utf-8")
            self.assertIn("version: 1.1.0", cff_content)
            self.assertIn("date-released: 2026-11-02", cff_content)

            cli_content = (tmp_path / "bin" / "cli.js").read_text(encoding="utf-8")
            self.assertIn("Anti-Slop Engineering CLI (v1.1.0)", cli_content)

            cargo_content = (rust_dir / "Cargo.toml").read_text(encoding="utf-8")
            self.assertIn('version = "1.1.0"', cargo_content)

    def test_missing_package_json_raises(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(FileNotFoundError):
                read_current_version(tmp_dir)

    def test_cli_dry_run_execution(self):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "bump_version.py"), "patch", "--dry-run", "--json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0)
        data = json.loads(result.stdout)
        self.assertTrue(data["dry_run"])
        self.assertEqual(len(data["updated_files"]), 13)


if __name__ == "__main__":
    unittest.main()
