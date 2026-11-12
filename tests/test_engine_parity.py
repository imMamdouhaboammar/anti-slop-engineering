#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Differential contract tests for native Rust/Go engines and Python fallback guards."""

import json
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "engine-parity"
DIFF_GUARD = ROOT / "scripts" / "diff_guard.py"
SRE_GUARD = ROOT / "scripts" / "sre_guard.py"


def _resolve_rust_binary(build_dir):
    env_bin = os.environ.get("ANTI_SLOP_RUST_BIN")
    if env_bin and pathlib.Path(env_bin).is_file():
        return env_bin
    for profile in ("release", "debug"):
        candidate = ROOT / "services" / "anti-slop-rust" / "target" / profile / "anti-slop-rust"
        if candidate.is_file():
            return str(candidate)
    cargo = shutil.which("cargo")
    if not cargo:
        return None
    target_bin = pathlib.Path(build_dir) / "anti-slop-rust"
    proc = subprocess.run(
        [
            cargo,
            "build",
            "--manifest-path",
            str(ROOT / "services" / "anti-slop-rust" / "Cargo.toml"),
            "--target-dir",
            str(pathlib.Path(build_dir) / "rust-target"),
            "--quiet",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to build anti-slop-rust: {proc.stderr}")
    built = pathlib.Path(build_dir) / "rust-target" / "debug" / "anti-slop-rust"
    if built.is_file():
        return str(built)
    return str(target_bin) if target_bin.is_file() else None


def _resolve_go_binary(build_dir):
    env_bin = os.environ.get("TOIL_GUARD_BIN")
    if env_bin and pathlib.Path(env_bin).is_file():
        return env_bin
    repo_bin = ROOT / "services" / "toil-guard-go" / "bin" / "toil-guard"
    if repo_bin.is_file():
        return str(repo_bin)
    go_bin = shutil.which("go")
    if not go_bin:
        return None
    target_bin = pathlib.Path(build_dir) / "toil-guard"
    proc = subprocess.run(
        [go_bin, "build", "-o", str(target_bin), "./cmd/toil-guard"],
        cwd=str(ROOT / "services" / "toil-guard-go"),
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Failed to build toil-guard: {proc.stderr}")
    return str(target_bin)


class EngineParityContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._build_tmp = tempfile.TemporaryDirectory()
        cls.contracts = json.loads((FIXTURES_DIR / "contracts.json").read_text(encoding="utf-8"))
        cls.rust_bin = _resolve_rust_binary(cls._build_tmp.name)
        cls.go_bin = _resolve_go_binary(cls._build_tmp.name)
        cls.require_native = os.environ.get("REQUIRE_NATIVE_PARITY") == "1"

    @classmethod
    def tearDownClass(cls):
        cls._build_tmp.cleanup()

    def _require_rust(self):
        if self.rust_bin:
            return self.rust_bin
        self.fail("REQUIRE_NATIVE_PARITY=1 but anti-slop-rust binary/cargo is unavailable")

    def _require_go(self):
        if self.go_bin:
            return self.go_bin
        self.fail("REQUIRE_NATIVE_PARITY=1 but toil-guard binary/go is unavailable")

    def _isolated_git_env(self, home_dir):
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        env["GIT_CONFIG_GLOBAL"] = os.devnull
        env["GIT_CONFIG_NOSYSTEM"] = "1"
        env["HOME"] = str(home_dir)
        return env

    def _git(self, repo_dir, args, env):
        return subprocess.run(
            ["git", "-C", str(repo_dir), *args],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )

    def _create_repo(self, initial_files=None):
        root = tempfile.TemporaryDirectory()
        self.addCleanup(root.cleanup)
        base = pathlib.Path(root.name)
        home_dir = base / "home"
        home_dir.mkdir()
        repo_dir = base / "repo"
        repo_dir.mkdir()
        env = self._isolated_git_env(home_dir)

        self._git(repo_dir, ["init"], env)
        self._git(repo_dir, ["config", "user.name", "Parity Tester"], env)
        self._git(repo_dir, ["config", "user.email", "parity@example.com"], env)

        files = initial_files or {"src/app.py": "def ok():\n    return 1\n"}
        for rel_path, content in files.items():
            file_path = repo_dir / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

        self._git(repo_dir, ["add", "-A"], env)
        self._git(repo_dir, ["commit", "-m", "initial commit"], env)
        return repo_dir, env

    def _run_diff_guard(self, repo_dir, base="HEAD"):
        return subprocess.run(
            [sys.executable, str(DIFF_GUARD), "--repo", str(repo_dir), "--base", base, "--json", "--fail-on-blocker"],
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_sre_guard(self, repo_dir, base="HEAD"):
        return subprocess.run(
            [sys.executable, str(SRE_GUARD), "--repo", str(repo_dir), "--base", base, "--json", "--strict"],
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_rust_triage(self, repo_dir, base="HEAD"):
        rust_bin = self._require_rust()
        return subprocess.run(
            [rust_bin, "triage", "--base", base, "--format", "json"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=False,
        )

    def _run_go_audit(self, repo_dir, base="HEAD"):
        go_bin = self._require_go()
        return subprocess.run(
            [go_bin, "audit", "--base", base, "--format", "json"],
            cwd=str(repo_dir),
            capture_output=True,
            text=True,
            check=False,
        )

    def test_clean_repo_shared_contract(self):
        expected = self.contracts["fixtures"]["clean"]["shared"]
        repo_dir, _ = self._create_repo()

        dg = self._run_diff_guard(repo_dir)
        self.assertEqual(dg.returncode, expected["diff_guard_exit"], dg.stderr)
        dg_data = json.loads(dg.stdout)
        self.assertEqual(dg_data["status"], expected["diff_guard_status"])
        self.assertEqual(dg_data["findings"], [])

        sg = self._run_sre_guard(repo_dir)
        self.assertEqual(sg.returncode, expected["sre_guard_exit"], sg.stderr)
        sg_data = json.loads(sg.stdout)
        self.assertEqual(sg_data["summary"]["blockers"], expected["sre_guard_blockers"])
        self.assertEqual(sg_data["findings"], [])

        if self.rust_bin or self.require_native:
            rt = self._run_rust_triage(repo_dir)
            self.assertEqual(rt.returncode, expected["rust_exit"], rt.stderr)
            rt_data = json.loads(rt.stdout)
            self.assertEqual(rt_data["summary"]["status"], expected["rust_status"])
            self.assertEqual(rt_data["summary"]["total_findings"], 0)

        if self.go_bin or self.require_native:
            ga = self._run_go_audit(repo_dir)
            self.assertEqual(ga.returncode, expected["go_exit"], ga.stderr)
            ga_data = json.loads(ga.stdout)
            self.assertEqual(ga_data["sli"]["status"], expected["go_status"])
            self.assertEqual(ga_data["findings"], [])

    def test_blocker_error_swallow_shared_contract(self):
        expected = self.contracts["fixtures"]["blocker_error_swallow"]["shared"]
        repo_dir, _ = self._create_repo({"src/worker.py": "def process_job(job):\n    return job.run()\n"})
        (repo_dir / "src" / "worker.py").write_text(
            "def process_job(job):\n    try:\n        return job.run()\n    except Exception: pass\n",
            encoding="utf-8",
        )

        dg = self._run_diff_guard(repo_dir)
        self.assertEqual(dg.returncode, expected["diff_guard_exit"], dg.stderr)
        dg_data = json.loads(dg.stdout)
        self.assertEqual(dg_data["status"], expected["diff_guard_status"])
        self.assertTrue(any(f["id"] == expected["diff_guard_id"] for f in dg_data["findings"]))

        sg = self._run_sre_guard(repo_dir)
        self.assertEqual(sg.returncode, expected["sre_guard_exit"], sg.stderr)
        sg_data = json.loads(sg.stdout)
        self.assertGreaterEqual(sg_data["summary"]["blockers"], expected["sre_guard_blockers_min"])
        self.assertTrue(any(f["id"] == expected["sre_guard_id"] for f in sg_data["findings"]))

        if self.rust_bin or self.require_native:
            rt = self._run_rust_triage(repo_dir)
            self.assertEqual(rt.returncode, expected["rust_exit"], rt.stderr)
            rt_data = json.loads(rt.stdout)
            self.assertEqual(rt_data["summary"]["status"], expected["rust_status"])
            self.assertTrue(any(f["code"] == expected["rust_code"] for f in rt_data["findings"]))

        if self.go_bin or self.require_native:
            ga = self._run_go_audit(repo_dir)
            self.assertEqual(ga.returncode, expected["go_exit"], ga.stderr)
            ga_data = json.loads(ga.stdout)
            self.assertEqual(ga_data["sli"]["status"], expected["go_status"])
            self.assertTrue(any(f["code"] == expected["go_code"] for f in ga_data["findings"]))

    def test_invalid_git_ref_rejected_by_all_engines(self):
        repo_dir, _ = self._create_repo()
        for bad_ref in ("nonexistent-ref-123", "--stat"):
            dg = self._run_diff_guard(repo_dir, base=bad_ref)
            self.assertNotEqual(dg.returncode, 0, f"diff_guard unexpectedly accepted {bad_ref}")

            sg = self._run_sre_guard(repo_dir, base=bad_ref)
            self.assertNotEqual(sg.returncode, 0, f"sre_guard unexpectedly accepted {bad_ref}")

            if self.rust_bin or self.require_native:
                rt = self._run_rust_triage(repo_dir, base=bad_ref)
                self.assertNotEqual(rt.returncode, 0, f"rust triage unexpectedly accepted {bad_ref}")

            if self.go_bin or self.require_native:
                ga = self._run_go_audit(repo_dir, base=bad_ref)
                self.assertNotEqual(ga.returncode, 0, f"go audit unexpectedly accepted {bad_ref}")

    def test_deletion_only_diff_shared_contract(self):
        expected = self.contracts["fixtures"]["deletion_only"]["shared"]
        repo_dir, _ = self._create_repo({"src/legacy.py": "def deprecated():\n    return True\n"})
        (repo_dir / "src" / "legacy.py").unlink()

        dg = self._run_diff_guard(repo_dir)
        self.assertEqual(dg.returncode, expected["diff_guard_exit"], dg.stderr)
        dg_data = json.loads(dg.stdout)
        self.assertEqual(dg_data["status"], expected["diff_guard_status"])

        sg = self._run_sre_guard(repo_dir)
        self.assertEqual(sg.returncode, expected["sre_guard_exit"], sg.stderr)
        sg_data = json.loads(sg.stdout)
        self.assertEqual(sg_data["summary"]["blockers"], expected["sre_guard_blockers"])

        if self.rust_bin or self.require_native:
            rt = self._run_rust_triage(repo_dir)
            self.assertEqual(rt.returncode, expected["rust_exit"], rt.stderr)
            rt_data = json.loads(rt.stdout)
            self.assertEqual(rt_data["summary"]["status"], expected["rust_status"])

        if self.go_bin or self.require_native:
            ga = self._run_go_audit(repo_dir)
            self.assertEqual(ga.returncode, expected["go_exit"], ga.stderr)
            ga_data = json.loads(ga.stdout)
            self.assertEqual(ga_data["sli"]["status"], expected["go_status"])

    def test_renamed_whitespace_and_non_ascii_paths_do_not_crash(self):
        repo_dir, env = self._create_repo(
            {
                "src/old_worker.py": "def run_task():\n    return 42\n",
                "src/my helper.py": "def greet():\n    return 'hi'\n",
                "src/café_über.py": "def status():\n    return 'ok'\n",
            }
        )
        self._git(repo_dir, ["mv", "src/old_worker.py", "src/new_worker.py"], env)
        (repo_dir / "src" / "new_worker.py").write_text("def run_task():\n    return 43\n", encoding="utf-8")
        (repo_dir / "src" / "my helper.py").write_text("def greet():\n    return 'hello'\n", encoding="utf-8")
        (repo_dir / "src" / "café_über.py").write_text("def status():\n    return 'ready'\n", encoding="utf-8")

        dg = self._run_diff_guard(repo_dir)
        self.assertEqual(dg.returncode, 0, dg.stderr)
        self.assertEqual(json.loads(dg.stdout)["status"], "no-heuristic-findings")

        sg = self._run_sre_guard(repo_dir)
        self.assertEqual(sg.returncode, 0, sg.stderr)
        self.assertEqual(json.loads(sg.stdout)["summary"]["blockers"], 0)

        if self.rust_bin or self.require_native:
            rt = self._run_rust_triage(repo_dir)
            self.assertEqual(rt.returncode, 0, rt.stderr)
            self.assertEqual(json.loads(rt.stdout)["summary"]["blockers"], 0)

        if self.go_bin or self.require_native:
            ga = self._run_go_audit(repo_dir)
            self.assertEqual(ga.returncode, 0, ga.stderr)
            self.assertEqual(json.loads(ga.stdout)["sli"]["status"], "PASSED")

    def test_blocker_inside_whitespace_and_renamed_paths(self):
        repo_dir, env = self._create_repo(
            {
                "src/old helper.py": "def run():\n    return 1\n",
            }
        )
        self._git(repo_dir, ["mv", "src/old helper.py", "src/new helper.py"], env)
        (repo_dir / "src" / "new helper.py").write_text(
            "def run():\n    try:\n        return 1\n    except Exception: pass\n",
            encoding="utf-8",
        )

        dg = self._run_diff_guard(repo_dir)
        self.assertEqual(dg.returncode, 0, dg.stderr)
        self.assertTrue(any(f["id"] == "ERROR_SWALLOW_CANDIDATE" for f in json.loads(dg.stdout)["findings"]))

        sg = self._run_sre_guard(repo_dir)
        self.assertEqual(sg.returncode, 2, sg.stderr)
        self.assertTrue(any(f["id"] == "SCALE_TOIL_ERROR_SWALLOW" for f in json.loads(sg.stdout)["findings"]))

        if self.rust_bin or self.require_native:
            rt = self._run_rust_triage(repo_dir)
            self.assertEqual(rt.returncode, 1, rt.stderr)
            self.assertTrue(any(f["code"] == "STS-H02" for f in json.loads(rt.stdout)["findings"]))

        if self.go_bin or self.require_native:
            ga = self._run_go_audit(repo_dir)
            self.assertEqual(ga.returncode, 1, ga.stderr)
            self.assertTrue(any(f["code"] == "SRE-SCALE-SWALLOW" for f in json.loads(ga.stdout)["findings"]))


if __name__ == "__main__":
    unittest.main()
