#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Tests for automated version bumper script."""

import json
import os
import pathlib
import stat
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


class BumpVersionGitSafetyTests(unittest.TestCase):
    def _isolated_git_env(self, home_dir, extra_path=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["HOME"] = str(home_dir)
        if extra_path:
            env["PATH"] = f"{extra_path}{os.pathsep}{env.get('PATH', '')}"
        return env

    def _run_git(self, repo_dir, args, env=None):
        return subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

    def _init_disposable_repo(self, root_dir, include_attestation=False, include_cargo=False):
        home_dir = root_dir.parent / f"{root_dir.name}-home"
        home_dir.mkdir(exist_ok=True)
        env = self._isolated_git_env(home_dir)
        self._run_git(root_dir, ["init"], env=env)
        self._run_git(root_dir, ["config", "user.name", "Release Bot"], env=env)
        self._run_git(root_dir, ["config", "user.email", "release@example.com"], env=env)

        pkg_content = json.dumps({"name": "test-pkg", "version": "1.0.0"}, indent=2) + "\n"
        (root_dir / "package.json").write_text(pkg_content, encoding="utf-8")
        (root_dir / "pyproject.toml").write_text('[project]\nversion = "1.0.0"\n', encoding="utf-8")
        (root_dir / "CITATION.cff").write_text("version: 1.0.0\ndate-released: 2026-01-01\n", encoding="utf-8")
        (root_dir / "notes.md").write_text("initial notes\n", encoding="utf-8")

        if include_attestation:
            import hashlib

            fable_dir = root_dir / ".fable"
            fable_dir.mkdir(parents=True, exist_ok=True)
            pkg_hash = hashlib.sha256(pkg_content.encode("utf-8")).hexdigest()
            (fable_dir / "heal-attestation.json").write_text(
                json.dumps({"file_hashes": {"package.json": pkg_hash}}, indent=2) + "\n",
                encoding="utf-8",
            )

        if include_cargo:
            rust_dir = root_dir / "services" / "anti-slop-rust"
            rust_dir.mkdir(parents=True, exist_ok=True)
            (rust_dir / "Cargo.toml").write_text(
                '[package]\nname = "anti-slop-rust"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )
            (rust_dir / "Cargo.lock").write_text(
                '[[package]]\nname = "anti-slop-rust"\nversion = "1.0.0"\n',
                encoding="utf-8",
            )

        self._run_git(root_dir, ["add", "-A"], env=env)
        self._run_git(root_dir, ["commit", "-m", "chore: initial commit"], env=env)
        return env

    def _run_bump_cli(self, repo_dir, args, env=None):
        return subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "bump_version.py"), *args, "--repo", str(repo_dir)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_git_commit_stages_only_bump_modified_files_on_dirty_tree(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = pathlib.Path(tmp_dir)
            repo_dir = tmp_path / "repo"
            repo_dir.mkdir()
            env = self._init_disposable_repo(repo_dir, include_attestation=True, include_cargo=True)

            fake_bin = tmp_path / "bin"
            fake_bin.mkdir()
            fake_cargo = fake_bin / "cargo"
            fake_cargo.write_text(
                "#!/bin/sh\n"
                f'printf \'[[package]]\\nname = "anti-slop-rust"\\nversion = "1.0.1"\\n\' > "{repo_dir / "services" / "anti-slop-rust" / "Cargo.lock"}"\n',
                encoding="utf-8",
            )
            fake_cargo.chmod(fake_cargo.stat().st_mode | stat.S_IXUSR)
            env_with_cargo = self._isolated_git_env(tmp_path / "repo-home", extra_path=str(fake_bin))

            (repo_dir / "notes.md").write_text("unrelated unstaged edit\n", encoding="utf-8")
            (repo_dir / "private.secret").write_text("API_KEY=do-not-commit\n", encoding="utf-8")

            res = self._run_bump_cli(
                repo_dir,
                ["patch", "--date", "2026-11-12", "--git-commit", "--git-tag", "--json"],
                env=env_with_cargo,
            )
            self.assertEqual(res.returncode, 0, msg=res.stderr)

            committed = set(
                self._run_git(repo_dir, ["show", "--name-only", "--format=", "HEAD"], env=env).stdout.splitlines()
            )
            expected = {
                "package.json",
                "pyproject.toml",
                "CITATION.cff",
                ".fable/heal-attestation.json",
                "services/anti-slop-rust/Cargo.toml",
                "services/anti-slop-rust/Cargo.lock",
            }
            self.assertEqual(committed, expected)
            self.assertNotIn("notes.md", committed)
            self.assertNotIn("private.secret", committed)

            status_lines = self._run_git(repo_dir, ["status", "--porcelain"], env=env).stdout.splitlines()
            self.assertIn(" M notes.md", status_lines)
            self.assertIn("?? private.secret", status_lines)

            tags = self._run_git(repo_dir, ["tag", "-l", "v1.0.1"], env=env).stdout.splitlines()
            self.assertEqual(tags, ["v1.0.1"])

    def test_git_commit_rejects_preexisting_staged_unrelated_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = pathlib.Path(tmp_dir)
            env = self._init_disposable_repo(repo_dir)

            (repo_dir / "notes.md").write_text("preexisting staged unrelated change\n", encoding="utf-8")
            self._run_git(repo_dir, ["add", "notes.md"], env=env)
            (repo_dir / "private.secret").write_text("secret\n", encoding="utf-8")

            res = self._run_bump_cli(repo_dir, ["patch", "--git-commit"], env=env)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("notes.md", res.stderr)
            self.assertNotIn("Bumped version:", res.stdout)

            commit_count = self._run_git(repo_dir, ["rev-list", "--count", "HEAD"], env=env).stdout.strip()
            self.assertEqual(commit_count, "1")
            self.assertEqual(read_current_version(repo_dir), "1.0.0")
            status_lines = self._run_git(repo_dir, ["status", "--porcelain"], env=env).stdout.splitlines()
            self.assertIn("M  notes.md", status_lines)
            self.assertIn("?? private.secret", status_lines)

    def test_git_commit_rejects_preexisting_dirty_release_target(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = pathlib.Path(tmp_dir)
            env = self._init_disposable_repo(repo_dir)

            pkg_data = json.loads((repo_dir / "package.json").read_text(encoding="utf-8"))
            pkg_data["description"] = "uncommitted edit"
            (repo_dir / "package.json").write_text(json.dumps(pkg_data, indent=2) + "\n", encoding="utf-8")

            res = self._run_bump_cli(repo_dir, ["patch", "--git-commit"], env=env)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("package.json", res.stderr)
            self.assertNotIn("Bumped version:", res.stdout)
            commit_count = self._run_git(repo_dir, ["rev-list", "--count", "HEAD"], env=env).stdout.strip()
            self.assertEqual(commit_count, "1")

    def test_git_commit_hook_failure_fails_loudly_and_skips_tag(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = pathlib.Path(tmp_dir)
            env = self._init_disposable_repo(repo_dir)

            hook_path = repo_dir / ".git" / "hooks" / "pre-commit"
            hook_path.write_text("#!/bin/sh\necho 'pre-commit hook blocked' >&2\nexit 1\n", encoding="utf-8")
            hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR)

            res = self._run_bump_cli(repo_dir, ["patch", "--git-commit", "--git-tag"], env=env)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("commit", res.stderr)
            self.assertIn("pre-commit hook blocked", res.stderr)
            self.assertNotIn("Bumped version:", res.stdout)

            commit_count = self._run_git(repo_dir, ["rev-list", "--count", "HEAD"], env=env).stdout.strip()
            self.assertEqual(commit_count, "1")
            tags = self._run_git(repo_dir, ["tag", "-l", "v1.0.1"], env=env).stdout.splitlines()
            self.assertEqual(tags, [])

    def test_git_commit_missing_identity_fails_loudly_and_skips_tag(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = pathlib.Path(tmp_dir)
            env = self._init_disposable_repo(repo_dir)

            self._run_git(repo_dir, ["config", "--unset", "user.name"], env=env)
            self._run_git(repo_dir, ["config", "--unset", "user.email"], env=env)
            self._run_git(repo_dir, ["config", "user.useConfigOnly", "true"], env=env)

            res = self._run_bump_cli(repo_dir, ["patch", "--git-commit", "--git-tag"], env=env)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("commit", res.stderr)
            self.assertNotIn("Bumped version:", res.stdout)

            commit_count = self._run_git(repo_dir, ["rev-list", "--count", "HEAD"], env=env).stdout.strip()
            self.assertEqual(commit_count, "1")
            tags = self._run_git(repo_dir, ["tag", "-l", "v1.0.1"], env=env).stdout.splitlines()
            self.assertEqual(tags, [])

    def test_git_tag_existing_conflict_rejected_before_mutation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = pathlib.Path(tmp_dir)
            env = self._init_disposable_repo(repo_dir)
            self._run_git(repo_dir, ["tag", "-a", "v1.0.1", "-m", "Existing release"], env=env)

            res = self._run_bump_cli(repo_dir, ["patch", "--git-commit", "--git-tag"], env=env)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("v1.0.1", res.stderr)
            self.assertNotIn("Bumped version:", res.stdout)

            commit_count = self._run_git(repo_dir, ["rev-list", "--count", "HEAD"], env=env).stdout.strip()
            self.assertEqual(commit_count, "1")
            self.assertEqual(read_current_version(repo_dir), "1.0.0")

    def test_git_tag_failure_missing_identity_reports_exact_command(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            repo_dir = pathlib.Path(tmp_dir)
            env = self._init_disposable_repo(repo_dir)

            self._run_git(repo_dir, ["config", "--unset", "user.name"], env=env)
            self._run_git(repo_dir, ["config", "--unset", "user.email"], env=env)
            self._run_git(repo_dir, ["config", "user.useConfigOnly", "true"], env=env)

            res = self._run_bump_cli(repo_dir, ["patch", "--git-tag"], env=env)
            self.assertNotEqual(res.returncode, 0)
            self.assertIn("tag", res.stderr)
            self.assertIn("v1.0.1", res.stderr)
            self.assertNotIn("Bumped version:", res.stdout)

            tags = self._run_git(repo_dir, ["tag", "-l", "v1.0.1"], env=env).stdout.splitlines()
            self.assertEqual(tags, [])


if __name__ == "__main__":
    unittest.main()
