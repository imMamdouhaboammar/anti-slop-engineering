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

from scripts import audit_runner, rule_registry

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

    def test_capability_registry_declares_one_owner_for_shared_rules(self):
        capabilities = self.contracts["capabilities"]
        self.assertEqual({entry["runtime"] for entry in capabilities}, {"node", "python", "rust", "go"})
        identifiers = set()
        covered_fixtures = set()
        for rule in self.contracts["shared_rules"]:
            self.assertTrue(rule["owner"]["engine"])
            self.assertIn(rule["fixture"], self.contracts["fixtures"])
            covered_fixtures.add(rule["fixture"])
            evidence = self.contracts["fixtures"][rule["fixture"]]["shared"]
            for entry in [rule["owner"], *rule["fallbacks"]]:
                identity = (entry["engine"], entry["id"])
                self.assertNotIn(identity, identifiers)
                identifiers.add(identity)
                self.assertEqual(entry["id"], evidence[entry["fixture_key"]])
                self.assertIn(entry["severity"], {"blocker", "review"})
        self.assertIn("blocker_error_swallow", covered_fixtures)

    def test_python_core_retains_required_git_checks_without_native_binaries(self):
        expected = self.contracts["fixtures"]["blocker_error_swallow"]["shared"]
        repo_dir, _ = self._create_repo({"worker.py": "def work():\n    return job.run()\n"})
        (repo_dir / "worker.py").write_text(
            "def work():\n    try:\n        return job.run()\n    except Exception: pass\n", encoding="utf-8"
        )
        for guard, exit_code, rule_id in (
            (DIFF_GUARD, expected["diff_guard_exit"], expected["diff_guard_id"]),
            (SRE_GUARD, expected["sre_guard_exit"], expected["sre_guard_id"]),
        ):
            strict = "--strict" if guard == SRE_GUARD else "--fail-on-blocker"
            proc = subprocess.run(
                [sys.executable, "-S", str(guard), "--repo", str(repo_dir), "--base", "HEAD", "--json", strict],
                capture_output=True, text=True, check=False,
                env=dict(os.environ, ANTI_SLOP_DISABLE_NATIVE="1"),
            )
            self.assertEqual(proc.returncode, exit_code, proc.stderr)
            self.assertIn(rule_id, [entry["id"] for entry in json.loads(proc.stdout)["findings"]])

    def test_blind_sleep_shared_contract_matches_native_severity(self):
        shared = self.contracts["fixtures"]["blind_sleep"]["shared"]
        repo_dir, _ = self._create_repo({"worker.py": "import time\n"})
        source = repo_dir / "worker.py"
        for line, expected in (("time.sleep(5)", True), ("schedule_work()", False)):
            source.write_text(f"import time\n{line}\n", encoding="utf-8")
            runs = [
                (self._run_diff_guard(repo_dir), "diff_guard_id", "id"),
                (self._run_sre_guard(repo_dir), "sre_guard_id", "id"),
            ]
            if self.go_bin or self.require_native:
                runs.append((self._run_go_audit(repo_dir), "go_code", "code"))
            for run, fixture_key, report_key in runs:
                expected_exit = shared[fixture_key + "_exit"] if expected else 0
                self.assertEqual(run.returncode, expected_exit, run.stderr)
                entries = [
                    entry for entry in json.loads(run.stdout)["findings"]
                    if entry[report_key] == shared[fixture_key]
                ]
                if expected:
                    self.assertEqual([entry["severity"].lower() for entry in entries],
                                     [shared[fixture_key + "_severity"]])
                else:
                    self.assertEqual(entries, [])

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

        self._assert_native_multiline_handler_detection()

    def _assert_catalog_normalization(self, engine, output, field):
        for finding in output["findings"]:
            rule = rule_registry.BY_CODE.get(finding[field])
            if rule is None:
                continue
            normalized = audit_runner.normalize_finding(engine, finding, output)
            self.assertEqual(normalized["rule"], finding[field])
            self.assertEqual(normalized["catalog_id"], rule.catalog_id)
            self.assertTrue((ROOT / normalized["skill_path"]).is_file())

    def _catalog_fixture_codes(self, fixture_name, source, runs):
        repo, _ = self._create_repo({"worker.py": "def baseline():\n    return None\n"})
        (repo / "worker.py").write_text(source, encoding="utf-8")
        codes = {}
        for engine, (run, field) in runs.items():
            proc = run(repo)
            with self.subTest(fixture=fixture_name, engine=engine):
                self.assertIn(proc.returncode, (0, 1, 2), proc.stderr)
                output = json.loads(proc.stdout)
                self.assertIsInstance(output["findings"], list)
                codes[fixture_name, engine] = {finding[field] for finding in output["findings"]}
                if engine in {"diff_guard", "sre_guard"}:
                    self._assert_catalog_normalization(engine, output, field)
        return codes

    def test_catalog_detector_fixture_receipt(self):
        cases = {
            "swallow_bad": "def work(job):\n    try:\n        job.run()\n    except Exception: pass\n",
            "swallow_handled": "def work(job):\n    try:\n        job.run()\n    except Exception as error:\n        raise RuntimeError('job failed') from error\n",
            "nested_bad": "def choose(x):\n    if x > 0:\n        if x < 100:\n            if x % 2 == 0:\n                if x != 4:\n                    return x\n    return 0\n",
            "nested_clear": "def choose(x):\n    if x <= 0 or x >= 100:\n        return 0\n    return x if x % 2 == 0 and x != 4 else 0\n",
            "flag_bad": "def read(job):\n    if False:\n        return job.read()\n    return None\n",
            "flag_clear": "def read(job):\n    if job.ready:\n        return job.read()\n    return None\n",
            "placeholder_bad": "def read(job):\n    # TODO(future): complete job reader\n    return None\n",
            "placeholder_clear": "def read(job):\n    return job.read()\n",
            "sleep_bad": "import time\n\ndef wait(event):\n    time.sleep(1)\n    return event.is_set()\n",
            "sleep_clear": "def wait(event):\n    return event.wait(timeout=1)\n",
            "retry_bad": "from time import sleep\n\ndef retry(op):\n    for attempt in range(3): sleep(1) if not op() else None\n",
            "retry_clear": "from time import sleep\n\ndef retry(op, jitter):\n    for attempt in range(3):\n        if op():\n            return True\n        sleep(jitter(2 ** attempt))\n    return False\n",
            "fanout_bad": "import asyncio\n\nasync def send(items, deliver):\n    return await asyncio.gather(*[deliver(item) for item in items])\n",
            "fanout_clear": "async def send(items, deliver):\n    return [await deliver(item) for item in items]\n",
            "narration_bad": "def reserve(attempt):\n    # Increment attempt\n    return attempt + 1\n",
            "narration_clear": "def reserve(attempt):\n    # Consume the retry budget before dispatch so a crash cannot grant an extra attempt.\n    return attempt + 1\n",
            "health_bad": "def readiness():\n    return 200\n",
            "health_clear": "def readiness():\n    ready = datastore.is_ready()\n    return 200 if ready else 503\n",
            "health_inline_probe": "def readiness():\n    return 200 if datastore.is_ready() else 503\n",
        }
        runs = {
            "diff_guard": (self._run_diff_guard, "id"),
            "sre_guard": (self._run_sre_guard, "id"),
        }
        if self.rust_bin or self.require_native:
            runs["rust"] = (self._run_rust_triage, "code")
        if self.go_bin or self.require_native:
            runs["go"] = (self._run_go_audit, "code")

        if os.environ.get("CATALOG_OBSERVATIONS_OUT") and not self.require_native:
            self.fail("A catalog coverage receipt requires REQUIRE_NATIVE_PARITY=1")

        outputs = {}
        for fixture_name, source in cases.items():
            outputs.update(self._catalog_fixture_codes(fixture_name, source, runs))

        fixtures = {
            "OPS-01": ("swallow_bad", "swallow_handled"),
            "SRE-01": ("nested_bad", "nested_clear"),
            "SRE-05": ("flag_bad", "flag_clear"),
            "SRE-07": ("sleep_bad", "sleep_clear"),
            "SRE-08": ("retry_bad", "retry_clear"),
            "SRE-09": ("fanout_bad", "fanout_clear"),
            "SIM-17": ("narration_bad", "narration_clear"),
            "SRE-12": ("health_bad", "health_clear"),
        }
        observations = {}
        for rule in rule_registry.RULES:
            if rule.engine not in runs:
                continue
            with self.subTest(detector=rule.evidence_key):
                positive, negative = fixtures[rule.catalog_id]
                if rule.engine_code == "SRE-YAGNI-SPECULATIVE":
                    positive, negative = "placeholder_bad", "placeholder_clear"
                hit = rule.engine_code in outputs[positive, rule.engine]
                false_alarm = rule.engine_code in outputs[negative, rule.engine]
                self.assertTrue(hit, f"{rule.evidence_key} stopped detecting its positive fixture")
                self.assertFalse(false_alarm, f"{rule.evidence_key} flags its negative fixture")
                outcomes = {"tp": int(hit), "fn": int(not hit), "fp": int(false_alarm), "tn": int(not false_alarm)}
                if rule.catalog_id == "SRE-12":
                    self.assertNotIn(rule.engine_code, outputs["health_inline_probe", rule.engine])
                    outcomes["tn"] += 1
                observations[rule.evidence_key] = outcomes

        receipt = os.environ.get("CATALOG_OBSERVATIONS_OUT")
        if receipt:
            pathlib.Path(receipt).write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")

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

    def test_rust_git_triage_parses_javascript_and_typescript_after_image(self):
        if not self.rust_bin and not self.require_native:
            self.skipTest("native Rust binary unavailable")
        tick = chr(96)
        plain = f"const note = {tick}\ncatch (err) {{}}\n{tick};\n"
        nested = f"const note = {tick}outer \x24{{{tick}inner \x24{{value}}{tick}}}{tick};\n" + plain
        recovery = "try { run(); } catch (err) {\n    report(err);\n}\n"
        empty = "try { run(); } catch (err) {\n}\n"
        wide_context = "one\ntwo\nthree\nfour\nfive\n"
        inline = "try { run(); } catch (err) {}"
        cases = (
            ("src/plain.ts", plain.replace("catch (err) {}", "old") + recovery, plain + empty, [4]),
            ("src/nested.ts", nested.replace("catch (err) {}", "old") + recovery, nested + empty, [5]),
            ("src/interpolation.ts", "", f"const note = {tick}\x24{{(() => {{ {inline} }})()}}{tick};\n", [1]),
            ("src/mid.ts", f"const note = {tick}\n{wide_context}old\n{wide_context}{tick};\n",
             f"const note = {tick}\n{wide_context}catch (err) {{}}\n{wide_context}{tick};\n", []),
            ("src/regex.js", f"const marker = /{tick}/;\n", f"const marker = /{tick}/;\n{inline}\n", [2]),
            ("src/jsx.tsx", f"const marker = <div>{tick}</div>;\n",
             f"const marker = <div>{tick}</div>;\n{inline}\n", [2]),
            ("src/escaped.ts", "", f"const note = {tick}\\\x24{{catch (err) {{}}}} \\{tick}{tick};\n{inline}\n", [2]),
            ("src/optional.mjs", "try { run(); } catch { report(); }\n", "try { run(); } catch {}", [1]),
            ("src/unrelated.ts", inline + "\nconst old = 1;\n", inline + "\nconst next = 2;\n", []),
            ("src/documented.ts", recovery,
             "try { run(); } catch (err) {\n    // expected during shutdown\n}\n", []),
            ("src/comment-before.ts", recovery, "// expected during shutdown\n" + empty, [2]),
            ("src/recovery.ts", empty, recovery, []),
            ("src/adjacent-deletion.ts", inline + "\nlet extra = true;\n", inline + "\n", []),
            ("src/invalid-fallback.ts", "const value = 1;\n",
             "const value = ;\n" + inline + "\n", [2]),
            ("src/oversize-fallback.ts", "const value = 1;\n",
             "//" + "x" * (2 * 1024 * 1024) + "\n" + inline + "\n", [2]),
            ("src/with spaces café.ts", recovery, empty, [1]),
            ("src/crlf.cts", recovery.replace("\n", "\r\n"), empty.replace("\n", "\r\n"), [1]),
        )
        for path, before, after, expected in cases:
            with self.subTest(path=path):
                repo_dir, env = self._create_repo({"README.md": "# Fixture\n"})
                file = repo_dir / path
                file.parent.mkdir(parents=True, exist_ok=True)
                if before:
                    file.write_bytes(before.encode())
                    self._git(repo_dir, ["add", "--", path], env)
                    self._git(repo_dir, ["commit", "-m", "pre-image"], env)
                file.write_bytes(after.encode())
                if not before:
                    self._git(repo_dir, ["add", "--", path], env)
                run = self._run_rust_triage(repo_dir)
                self.assertEqual(run.returncode, int(bool(expected)), run.stderr)
                findings = [
                    (item["file"], item["line"], item["severity"])
                    for item in json.loads(run.stdout)["findings"]
                    if item["code"] == "STS-H02"
                ]
                self.assertEqual(findings, [(path, line, "Blocker") for line in expected])

    def test_rust_read_only_deletion_keeps_existing_line_attribution(self):
        if not self.rust_bin and not self.require_native:
            self.skipTest("native Rust binary unavailable")
        repo_dir, _ = self._create_repo({"fixture.ts": "const removed = 1;\nconst kept = 2;\n"})
        (repo_dir / "fixture.ts").write_text("const kept = 2;\n", encoding="utf-8")
        result = subprocess.run(
            [self._require_rust(), "triage", "--base", "HEAD", "--read-only", "--format", "json"],
            cwd=repo_dir,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 1, result.stderr)
        findings = json.loads(result.stdout)["findings"]
        self.assertEqual([(item["code"], item["line"]) for item in findings], [("STS-I01", 1)])

    def test_rust_raw_patch_keeps_legacy_findings_even_with_local_source(self):
        if not self.rust_bin and not self.require_native:
            self.skipTest("native Rust binary unavailable")
        before = "const note = \x60\none\ntwo\nthree\nfour\nfive\nold\nsix\nseven\neight\n\x60;\n"
        cases = (
            ("catch (err) {}", [("STS-H02", 7)]),
            ("} catch (err) {\n}", []),
        )
        for replacement, expected in cases:
            with self.subTest(replacement=replacement):
                repo_dir, env = self._create_repo({"fixture.ts": before})
                (repo_dir / "fixture.ts").write_text(before.replace("old", replacement), encoding="utf-8")
                patch = self._git(repo_dir, ["diff", "--unified=3", "HEAD", "--"], env).stdout
                result = subprocess.run(
                    [self._require_rust(), "shit-check", "--format", "json"],
                    cwd=repo_dir, input=patch, capture_output=True, text=True, check=False,
                )
                self.assertEqual(result.returncode, int(bool(expected)), result.stderr or result.stdout)
                findings = json.loads(result.stdout)["findings"]
                self.assertEqual([(item["code"], item["line"]) for item in findings], expected)

        self._assert_rust_patch_uses_git_context()

    def _assert_rust_patch_uses_git_context(self):
        prefix = "// existing context\n" * 9
        tick = chr(96)
        text_body = f"const note = {tick}\n{prefix}old\n{tick};\n"
        cases = (
            ("literal", text_body, text_body.replace("old", "catch (err) {}"), [], False),
            ("split catch", prefix + "try { run(); } catch { report(); }\n",
             prefix + "try { run(); }\ncatch {\n}\n", [11], False),
            ("mismatched object", text_body, text_body.replace("old", "catch (err) {}"), [11], True),
        )
        for label, before, after, expected, corrupt in cases:
            with self.subTest(case=label):
                path = "src/fixture.ts"
                repo, env = self._create_repo({path: before})
                target = repo / path
                target.write_text(after, encoding="utf-8")
                patch = self._git(repo, ["diff", "--full-index", "HEAD", "--"], env).stdout
                if corrupt:
                    new_blob = self._git(repo, ["hash-object", "--", path], env).stdout.strip()
                    patch = patch.replace(new_blob, "1" * len(new_blob), 1)
                target.write_text(before, encoding="utf-8")
                run = subprocess.run(
                    [self._require_rust(), "shit-check", "--git-context", "--format", "json"],
                    cwd=repo, env=env, input=patch, capture_output=True, text=True, check=False,
                )
                self.assertEqual(run.returncode, int(bool(expected)), run.stderr or run.stdout)
                actual = [(f["file"], f["line"]) for f in json.loads(run.stdout)["findings"] if f["code"] == "STS-H02"]
                self.assertEqual(actual, [(path, line) for line in expected])

    def _assert_native_multiline_handler_detection(self):
        recovery = "try { work(); } catch (err) {\n    report(err);\n}\n"
        sources = {
            "src/removed-recovery.ts": (recovery, "try { work(); } catch (err) {\n}\n"),
            "src/optional.ts": ("const value = 1;\n", "try { work(); } catch {\n}\n"),
            "src/method.ts": ("const value = 1;\n", "class Task {\n    catch(err: Error) {\n    }\n}\n"),
            "src/removed-recovery.py": (
                "try:\n    work()\nexcept RuntimeError:\n    report()\n    pass\ndone()\n",
                "try:\n    work()\nexcept RuntimeError:\n    pass\ndone()\n",
            ),
            "src/unrelated-comment.py": (
                "done()\n",
                "try:\n    work()\nexcept RuntimeError:\n    pass\n# expected next step\ndone()\n",
            ),
        }
        repo_dir, env = self._create_repo({path: before for path, (before, _) in sources.items()})
        for path, (_, after) in sources.items():
            (repo_dir / path).write_text(after, encoding="utf-8")
        reports = []
        if self.rust_bin or self.require_native:
            patch = self._git(repo_dir, ["diff", "HEAD", "--"], env).stdout
            rust = subprocess.run(
                [self._require_rust(), "shit-check", "--format", "json"],
                cwd=repo_dir, input=patch, capture_output=True, text=True, check=False,
            )
            reports.append((rust, "STS-H02"))
        if self.go_bin or self.require_native:
            reports.append((self._run_go_audit(repo_dir), "SRE-SCALE-SWALLOW"))
        expected = [
            ("src/optional.ts", 1),
            ("src/removed-recovery.py", 3),
            ("src/removed-recovery.ts", 1),
            ("src/unrelated-comment.py", 3),
        ]
        for report, code in reports:
            with self.subTest(code=code):
                self.assertEqual(report.returncode, 1, report.stderr)
                findings = json.loads(report.stdout)["findings"]
                self.assertEqual(sorted((item["file"], item["line"]) for item in findings if item["code"] == code), expected)

    def test_go_handler_audit_uses_full_source_syntax(self):
        if not self.go_bin and not self.require_native:
            self.skipTest("native Go binary unavailable")
        after = (
            "package fixture\n\n"
            "var sample = \x60if err != nil {}\x60\n\n"
            "func check(err, ERR error) {\n"
            "    if err != nil {\n"
            "    }\n"
            "    if err := run(); err != nil {\n"
            "        // expected: this probe can already be closed\n"
            "    }\n"
            "    if err != nil { report(err) }\n"
            "    /* marker\n"
            "    */ if err != nil {\n"
            "    }\n"
            "    if ERR != nil {}\n"
            "    if err != nil /* expected: stale worker already stopped */ {}\n"
            "    if err != nil { /* expected: probe already closed */ }\n"
            "//line synthetic.go:900\n"
            "    if err != nil {\n"
            "    }\n"
            "}\n"
            "func run() error { return nil }\n"
            "func report(error) {}\n"
        )
        before = after.replace("    if err != nil {\n    }\n",
                               "    if err != nil {\n        report(err)\n    }\n", 1)
        repo_dir, _ = self._create_repo({"src/worker.go": before})
        (repo_dir / "src" / "worker.go").write_text(after, encoding="utf-8")
        report = self._run_go_audit(repo_dir)
        findings = [f for f in json.loads(report.stdout)["findings"] if f["code"] == "SRE-SCALE-SWALLOW"]
        self.assertEqual([(f["file"], f["line"]) for f in findings],
                         [("src/worker.go", 6), ("src/worker.go", 13), ("src/worker.go", 15), ("src/worker.go", 19)])
        self.assertEqual(report.returncode, 1, report.stderr or report.stdout)


if __name__ == "__main__":
    unittest.main()
