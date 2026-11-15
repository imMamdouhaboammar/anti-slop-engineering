# SPDX-License-Identifier: MIT
# Unit tests for scripts/verification_oracle_guard.py

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verification_oracle_guard.py"
EXAMPLE = ROOT / "skills" / "verification-oracle-architect" / "examples" / "verification-oracle-record.json"
TS_EXAMPLE = ROOT / "skills" / "verification-oracle-architect" / "examples" / "verified-fake-property-chaos-oracle.ts"

sys.path.insert(0, str(ROOT / "scripts"))
import verification_oracle_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


def _init_git_repo(tmp_path: Path):
    env = os.environ.copy()
    env["GIT_AUTHOR_NAME"] = "Test Author"
    env["GIT_AUTHOR_EMAIL"] = "test@example.com"
    env["GIT_COMMITTER_NAME"] = "Test Committer"
    env["GIT_COMMITTER_EMAIL"] = "test@example.com"

    def run_git(*args):
        return subprocess.run(
            ["git", "-C", str(tmp_path), *args],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )

    run_git("init")
    run_git("config", "user.name", "Test Author")
    run_git("config", "user.email", "test@example.com")
    run_git("config", "commit.gpgsign", "false")
    return run_git


class VerificationOracleGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_contract_parity_or_rollback_mechanic_fails(self):
        record = valid_record()
        record["verified_in_memory_fakes"]["contract_parity_verified"] = False
        record["verified_in_memory_fakes"]["enforced_fake_mechanics"] = [
            "unique_and_check_constraint_enforcement",
            "optimistic_concurrency_version_cas",
            "composite_tenant_isolation",
        ]
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("CONTRACT_PARITY_NOT_VERIFIED", codes)
        self.assertIn("MISSING_CORE_FAKE_ISOLATION_OR_ROLLBACK", codes)

    def test_low_property_runs_or_missing_shrinking_fails(self):
        record = valid_record()
        record["property_and_metamorphic_oracles"]["generated_runs_per_property"] = 10
        record["property_and_metamorphic_oracles"]["shrinking_enabled"] = False
        record["property_and_metamorphic_oracles"]["invariants_verified"] = [
            record["property_and_metamorphic_oracles"]["invariants_verified"][0]
        ]
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INSUFFICIENT_GENERATED_PROPERTY_RUNS", codes)
        self.assertIn("SHRINKING_NOT_ENABLED", codes)
        self.assertIn("INSUFFICIENT_INVARIANTS_VERIFIED", codes)

    def test_missing_seeded_chaos_post_commit_or_mutation_falsification_fails(self):
        record = valid_record()
        record["deterministic_chaos_testing"]["reproduction_seeds"] = ["not-a-hex-seed"]
        record["deterministic_chaos_testing"]["injected_fault_modes"] = [
            "pre_commit_connection_drop",
            "transient_cas_version_conflict",
        ]
        record["mutation_falsification"]["red_green_falsification_verified"] = False
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_REPRODUCTION_SEEDS", codes)
        self.assertIn("MISSING_PRE_OR_POST_COMMIT_CHAOS_FAULTS", codes)
        self.assertIn("RED_GREEN_FALSIFICATION_NOT_VERIFIED", codes)

    def test_source_scanner_flags_banned_mocks_unseeded_random_sleep_and_weak_asserts(self):
        bad_test_source = """
        // oxlint-disable-next-line anti-slop/no-module-mocking
        vi.mock("../db/postgresLedgerStorage");
        test("weak flaky mock test", async () => {
          if (Math.random() < 0.5) {
            await new Promise((r) => setTimeout(r, 100));
          }
          expect(true).toBe(true);
          expect(result).toBeDefined();
        });
        """
        result = verification_oracle_guard.audit(valid_record(), source_text=bad_test_source)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SOURCE_BANNED_MODULE_MOCK", codes)
        self.assertIn("SOURCE_UNSEEDED_RANDOM_IN_TEST", codes)
        self.assertIn("SOURCE_WALL_CLOCK_SLEEP_IN_TEST", codes)
        self.assertIn("SOURCE_TAUTOLOGICAL_OR_WEAK_ASSERTION", codes)

    def test_source_scanner_accepts_clean_verified_fake_property_chaos_example(self):
        clean_ts = TS_EXAMPLE.read_text(encoding="utf-8")
        result = verification_oracle_guard.audit(valid_record(), source_text=clean_ts)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])

    def test_refuse_verdict_permits_rejecting_mock_slop_suite(self):
        record = {
            "schema_version": "1.0",
            "target_system": {
                "module_under_test": "MarketplaceEscrowSettlementEngine (src/ledger/settlementEngine.ts)",
                "domain_category": "financial_ledger_and_payments",
                "module_mocking_banned": True,
            },
            "verdict": {
                "action": "refuse",
                "rationale": "Refusing PR test suite that suppresses anti-slop/no-module-mocking with vi.mock(), tests only 1 static happy-path split, and uses setTimeout(200) instead of a Contract-Verified In-Memory Fake and Seeded Chaos Harness.",
                "revisit_triggers": [
                    "Replace vi.mock with InMemoryLedgerStorage verified by verifyLedgerStorageContract",
                    "Add >=100 property runs and Mulberry32 + VirtualClock chaos fault injection",
                ],
            },
        }
        result = verification_oracle_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "refuse")
        self.assertEqual(result["findings"], [])

    def test_cli_invocation_success(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tmp:
            json.dump(valid_record(), tmp)
            tmp_path = Path(tmp.name)
        try:
            res = subprocess.run(
                [sys.executable, str(SCRIPT), "audit", str(tmp_path), "--source", str(TS_EXAMPLE), "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0)
            payload = json.loads(res.stdout)
            self.assertEqual(payload["record_status"], "complete")
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_is_test_file_patterns(self):
        self.assertTrue(verification_oracle_guard.is_test_file("tests/test_foo.py"))
        self.assertTrue(verification_oracle_guard.is_test_file("test/bar.test.ts"))
        self.assertTrue(verification_oracle_guard.is_test_file("spec/codec_spec.js"))
        self.assertTrue(verification_oracle_guard.is_test_file("src/foo_test.go"))
        self.assertTrue(verification_oracle_guard.is_test_file("tests/bar_test.rs"))
        self.assertFalse(verification_oracle_guard.is_test_file("scripts/audit_runner.py"))
        self.assertFalse(verification_oracle_guard.is_test_file("tests/fixtures/data.json"))
        self.assertFalse(verification_oracle_guard.is_test_file("docs/test-guide.md"))

    def test_classify_test_output_modes(self):
        # Assertion failure
        cls_type, reason = verification_oracle_guard.classify_test_output({
            "exit_code": 1,
            "stdout": "test_add (test_calc.CalcTest) ... FAIL",
            "stderr": "AssertionError: 1 != 2",
            "timed_out": False,
        })
        self.assertEqual(cls_type, "assertion_failure")
        self.assertIn("AssertionError", reason)

        # Infrastructure / import failure
        cls_type, reason = verification_oracle_guard.classify_test_output({
            "exit_code": 1,
            "stdout": "",
            "stderr": "ModuleNotFoundError: No module named 'new_lib'",
            "timed_out": False,
        })
        self.assertEqual(cls_type, "infrastructure_error")
        self.assertIn("ModuleNotFoundError", reason)

        # Dependency / missing runner
        cls_type, reason = verification_oracle_guard.classify_test_output({
            "exit_code": 127,
            "stdout": "sh: nonexistent-runner: command not found",
            "stderr": "",
            "timed_out": False,
        })
        self.assertEqual(cls_type, "dependency_failure")

        # Passed
        cls_type, reason = verification_oracle_guard.classify_test_output({
            "exit_code": 0,
            "stdout": "OK",
            "stderr": "",
            "timed_out": False,
        })
        self.assertEqual(cls_type, "passed")

        # Timed out
        cls_type, reason = verification_oracle_guard.classify_test_output({
            "exit_code": None,
            "stdout": "",
            "stderr": "",
            "timed_out": True,
            "error": "Timed out after 30 seconds",
        })
        self.assertEqual(cls_type, "timed_out")

    def test_counterfactual_proof_verified_regression(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_git = _init_git_repo(tmp_path)

            calc_file = tmp_path / "calc.py"
            calc_file.write_text("def add(a, b):\n    return a\n", encoding="utf-8")
            readme = tmp_path / "README.md"
            readme.write_text("# Project\n", encoding="utf-8")
            run_git("add", "calc.py", "README.md")
            run_git("commit", "-m", "chore: initial buggy implementation")

            calc_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            test_file = tests_dir / "test_calc.py"
            test_file.write_text(
                "import unittest\nfrom calc import add\n\n"
                "class CalcTest(unittest.TestCase):\n"
                "    def test_add(self):\n"
                "        self.assertEqual(add(2, 3), 5)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )
            run_git("add", "calc.py", "tests/test_calc.py")
            run_git("commit", "-m", "fix: correct add logic and add test")

            res = verification_oracle_guard.run_counterfactual_proof(
                repo_root=tmp_path,
                base="HEAD~1",
                test_files=["tests/test_calc.py"],
            )
            self.assertEqual(res["status"], "verified")
            self.assertEqual(res["verdict"], "proceed")
            self.assertTrue(res["red_green_verified"])
            self.assertEqual(res["results"]["tests/test_calc.py"]["baseline"]["classification"], "assertion_failure")
            self.assertEqual(res["results"]["tests/test_calc.py"]["current"]["classification"], "passed")

    def test_counterfactual_proof_tautological_test(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_git = _init_git_repo(tmp_path)

            calc_file = tmp_path / "calc.py"
            calc_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")
            run_git("add", "calc.py")
            run_git("commit", "-m", "chore: baseline working math")

            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            test_file = tests_dir / "test_tautology.py"
            test_file.write_text(
                "import unittest\nfrom calc import add\n\n"
                "class TautologyTest(unittest.TestCase):\n"
                "    def test_tautology(self):\n"
                "        self.assertEqual(add(2, 3), 5)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )
            run_git("add", "tests/test_tautology.py")
            run_git("commit", "-m", "test: add test without implementation change")

            res = verification_oracle_guard.run_counterfactual_proof(
                repo_root=tmp_path,
                base="HEAD~1",
                test_files=["tests/test_tautology.py"],
            )
            self.assertEqual(res["status"], "tautological")
            self.assertEqual(res["verdict"], "refuse")
            self.assertFalse(res["red_green_verified"])
            self.assertEqual(res["results"]["tests/test_tautology.py"]["baseline"]["classification"], "passed")
            self.assertEqual(res["results"]["tests/test_tautology.py"]["current"]["classification"], "passed")

    def test_counterfactual_baseline_preserves_files_omitted_from_archives(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            git = _init_git_repo(root)
            (root / ".gitattributes").write_text("fixture.txt export-ignore\n", encoding="utf-8")
            (root / "fixture.txt").write_text("fixture", encoding="utf-8")
            git("add", ".gitattributes", "fixture.txt")
            git("commit", "-m", "chore: add fixture outside export archives")
            (root / "test_fixture.py").write_text(
                "import unittest\nfrom pathlib import Path\n\n"
                "class FixtureTest(unittest.TestCase):\n"
                "    def test_fixture_is_present(self):\n"
                "        self.assertTrue(Path('fixture.txt').is_file())\n",
                encoding="utf-8",
            )

            result = verification_oracle_guard.run_counterfactual_proof(root, base="HEAD")

            self.assertEqual(result["status"], "tautological", result)
            self.assertFalse(result["red_green_verified"])
            self.assertEqual(result["results"]["test_fixture.py"]["baseline"]["classification"], "passed")
            self.assertEqual(result["results"]["test_fixture.py"]["current"]["classification"], "passed")

    def test_counterfactual_proof_inconclusive_infrastructure_never_asserts_fraud(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_git = _init_git_repo(tmp_path)

            readme = tmp_path / "README.md"
            readme.write_text("# Project\n", encoding="utf-8")
            run_git("add", "README.md")
            run_git("commit", "-m", "chore: initial commit")

            new_mod = tmp_path / "new_service.py"
            new_mod.write_text("def process():\n    return 'ok'\n", encoding="utf-8")
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            test_file = tests_dir / "test_new_service.py"
            test_file.write_text(
                "import unittest\nfrom new_service import process\n\n"
                "class NewServiceTest(unittest.TestCase):\n"
                "    def test_process(self):\n"
                "        self.assertEqual(process(), 'ok')\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )
            run_git("add", "new_service.py", "tests/test_new_service.py")
            run_git("commit", "-m", "feat: brand new service and test")

            res = verification_oracle_guard.run_counterfactual_proof(
                repo_root=tmp_path,
                base="HEAD~1",
                test_files=["tests/test_new_service.py"],
            )
            self.assertEqual(res["status"], "inconclusive_infrastructure")
            self.assertEqual(res["verdict"], "pause")
            self.assertFalse(res["red_green_verified"])
            self.assertEqual(res["results"]["tests/test_new_service.py"]["baseline"]["classification"], "infrastructure_error")

    def _proof_cli(self, root, *files, extra=()):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "counterfactual", "--base", "HEAD",
             "--tests", *files, *extra, "--json"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        return proc.returncode, json.loads(proc.stdout)

    @unittest.skipUnless(shutil.which("go"), "Go toolchain is unavailable")
    def test_counterfactual_go_runs_the_selected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = _init_git_repo(root)
            (root / "go.mod").write_text("module example.test/proof\n\ngo 1.23\n")
            source = root / "value.go"
            source.write_text("package proof\nfunc value() int { return 1 }\n")
            (root / "prior_test.go").write_text(
                'package proof\nimport "testing"\n'
                'func TestPrior(t *testing.T) { if value() != 2 { t.Fatal("wrong prior value") } }\n'
            )
            git("add", ".")
            git("commit", "-m", "add prior value contract")
            source.write_text("package proof\nfunc value() int { return 2 }\n")
            test_file = "selected_test.go"
            for condition, code, status in (("value() < 1", 2, "tautological"), ("value() != 2", 0, "verified")):
                with self.subTest(status=status):
                    (root / test_file).write_text(
                        'package proof\nimport "testing"\n'
                        f'func TestSelected(t *testing.T) {{ if {condition} {{ t.Fatal("wrong selected value") }} }}\n'
                    )
                    exit_code, result = self._proof_cli(root, test_file)
                    self.assertEqual(exit_code, code, result)
                    self.assertEqual(result["status"], status, result)
                    for side in ("baseline", "current"):
                        output = result["results"][test_file][side]["stdout"]
                        self.assertIn("=== RUN   TestSelected", output)
                        self.assertNotIn("=== RUN   TestPrior", output)
            (root / test_file).write_text("package proof\nfunc helper() {}\n")
            exit_code, result = self._proof_cli(root, test_file)
            self.assertNotEqual(exit_code, 0, result)
            self.assertTrue(result["status"].startswith("inconclusive"), result)

    @unittest.skipUnless(shutil.which("go"), "Go toolchain is unavailable")
    def test_counterfactual_go_keeps_the_package_test_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = _init_git_repo(root)
            (root / "go.mod").write_text("module example.test/proof\n\ngo 1.23\n")
            (root / "value.go").write_text("package proof\nfunc value() int { return 1 }\n")
            (root / "setup_test.go").write_text(
                'package proof\nimport ("os"; "testing")\n'
                'var initialized bool\n'
                'func TestMain(m *testing.M) { initialized = true; os.Exit(m.Run()) }\n'
                'func TestUnrelated(t *testing.T) { t.Fatal("must not run") }\n'
            )
            git("add", ".")
            git("commit", "-m", "add package test setup")
            (root / "value.go").write_text("package proof\nfunc value() int { return 2 }\n")
            name = "selected_test.go"
            (root / name).write_text(
                'package proof\nimport "testing"\n'
                'func TestSelected(t *testing.T) {\n'
                'if !initialized { t.Fatal("missing setup") }\n'
                'if value() != 2 { t.Fatal("selected assertion") }\n'
                '}\n'
            )
            exit_code, result = self._proof_cli(root, name)
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "verified", result)
            self.assertIn("selected assertion", result["results"][name]["baseline"]["stdout"])
            self.assertNotIn("TestUnrelated", result["results"][name]["baseline"]["stdout"])

    @unittest.skipUnless(shutil.which("bun"), "Bun toolchain is unavailable")
    def test_counterfactual_bun_runs_the_selected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = _init_git_repo(root)
            test_file = "identity.test.js"
            source = root / "value.js"
            source.write_text("export const value = 1;\n")
            (root / "unrelated").mkdir()
            (root / "unrelated" / test_file).write_text(
                "import {expect, test} from 'bun:test';\nimport {value} from '../value.js';\n"
                "test('prior value', () => expect(value).toBe(2));\n"
            )
            git("add", ".")
            git("commit", "-m", "add prior value contract")
            source.write_text("export const value = 2;\n")
            for assertion, code, status in (("toBeGreaterThan(0)", 2, "tautological"), ("toBe(2)", 0, "verified")):
                with self.subTest(status=status):
                    (root / test_file).write_text(
                        "import {expect, test} from 'bun:test';\nimport {value} from './value.js';\n"
                        f"test('selected value', () => expect(value).{assertion});\n"
                    )
                    exit_code, result = self._proof_cli(root, test_file)
                    self.assertEqual(exit_code, code, result)
                    self.assertEqual(result["status"], status, result)
                    for side in ("baseline", "current"):
                        output = result["results"][test_file][side]["stderr"]
                        self.assertIn("selected value", output)
                        self.assertNotIn("prior value", output)
            (root / test_file).write_text(
                "import {test} from 'bun:test';\n"
                "test.skip('selected skip', () => { throw Error('skipped'); });\n"
            )
            exit_code, result = self._proof_cli(root, test_file)
            self.assertNotEqual(exit_code, 0, result)
            self.assertTrue(result["status"].startswith("inconclusive"), result)

    def test_counterfactual_python_runs_the_selected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = _init_git_repo(root)
            value = root / "value.txt"
            value.write_text("old")
            (root / "unrelated").mkdir()
            (root / "unrelated" / "__init__.py").touch()
            (root / "unrelated" / "test_selected.py").write_text(
                "import unittest\nfrom pathlib import Path\n"
                "class Prior(unittest.TestCase):\n"
                "    def test_prior_value(self):\n"
                "        self.assertEqual(Path('value.txt').read_text(), 'new')\n"
            )
            git("add", ".")
            git("commit", "-m", "add unrelated same-named test")
            value.write_text("new")
            (root / "test_selected.py").write_text(
                "import unittest\nfrom pathlib import Path\n"
                "class Selected(unittest.TestCase):\n"
                "    def test_selected_value(self):\n"
                "        self.assertTrue(Path('value.txt').read_text())\n"
            )
            exit_code, result = self._proof_cli(root, "test_selected.py")
            self.assertEqual(exit_code, 2, result)
            self.assertEqual(result["status"], "tautological", result)
            for side in ("baseline", "current"):
                output = result["results"]["test_selected.py"][side]["stderr"]
                self.assertIn("test_selected_value", output)
                self.assertNotIn("test_prior_value", output)

    def test_counterfactual_cannot_attribute_an_opaque_runner(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = _init_git_repo(root)
            (root / "value.txt").write_text("old")
            (root / "wrapper.py").write_text(
                "import unittest\nfrom pathlib import Path\n"
                "class UnrelatedTest(unittest.TestCase):\n"
                "    def test_unrelated_value(self):\n"
                "        self.assertEqual(Path('value.txt').read_text(), 'new')\n"
                "if __name__ == '__main__':\n"
                "    unittest.main(argv=['wrapper.py'])\n"
            )
            git("add", ".")
            git("commit", "-m", "add baseline and custom runner")
            (root / "value.txt").write_text("new")
            (root / "test_selected.py").write_text("raise RuntimeError('never executed')\n")
            exit_code, result = self._proof_cli(
                root, "test_selected.py",
                extra=("--test-cmd", shlex.join((sys.executable, "wrapper.py", "{test_file}"))),
            )
            self.assertEqual(exit_code, 2, result)
            self.assertEqual(result["status"], "inconclusive", result)
            self.assertIn("test_unrelated_value", result["results"]["test_selected.py"]["baseline"]["stderr"])

    def test_counterfactual_every_invocation_starts_from_a_fresh_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            git = _init_git_repo(root)
            (root / "value.txt").write_text("old")
            git("add", ".")
            git("commit", "-m", "add baseline value")
            (root / "value.txt").write_text("new")
            files = ("test_a.py", "test_b.py")
            for name in files:
                (root / name).write_text(
                    "import unittest\nfrom pathlib import Path\n"
                    "class FreshTest(unittest.TestCase):\n"
                    "    def test_value(self):\n"
                    "        marker = Path('marker.txt')\n"
                    "        self.assertFalse(marker.exists(), 'another run left a marker')\n"
                    "        marker.touch()\n"
                    "        self.assertEqual(Path('value.txt').read_text(), 'new')\n"
                )
            exit_code, result = self._proof_cli(root, *files, extra=("--check-flaky",))
            self.assertEqual(exit_code, 0, result)
            self.assertEqual(result["status"], "verified", result)
            for name in files:
                self.assertIn("'old' != 'new'", result["results"][name]["baseline"]["stderr"])
            self.assertFalse((root / "marker.txt").exists())

    def test_counterfactual_proof_dependency_failure(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_git = _init_git_repo(tmp_path)

            readme = tmp_path / "README.md"
            readme.write_text("# Project\n", encoding="utf-8")
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            (tests_dir / "test_dummy.py").write_text("import unittest\n", encoding="utf-8")
            run_git("add", "README.md", "tests/test_dummy.py")
            run_git("commit", "-m", "chore: initial commit")

            res = verification_oracle_guard.run_counterfactual_proof(
                repo_root=tmp_path,
                base="HEAD",
                test_files=["tests/test_dummy.py"],
                test_cmd="nonexistent_binary_xyz_12345 {test_file}",
            )
            self.assertEqual(res["status"], "dependency_failure")
            self.assertEqual(res["verdict"], "pause")
            self.assertFalse(res["red_green_verified"])

    def test_counterfactual_proof_uncommitted_changes_preserved_and_cleaned(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_git = _init_git_repo(tmp_path)

            calc_file = tmp_path / "calc.py"
            calc_file.write_text("def multiply(a, b):\n    return 0\n", encoding="utf-8")
            run_git("add", "calc.py")
            run_git("commit", "-m", "chore: initial multiply")

            calc_file.write_text("def multiply(a, b):\n    return a * b\n", encoding="utf-8")
            uncommitted_file = tmp_path / "scratch_notes.txt"
            uncommitted_file.write_text("sensitive uncommitted developer notes\n", encoding="utf-8")
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            test_file = tests_dir / "test_multiply.py"
            test_file.write_text(
                "import unittest\nfrom pathlib import Path\nfrom calc import multiply\n\n"
                "class MultiplyTest(unittest.TestCase):\n"
                "    def test_mult(self):\n"
                "        Path('run-marker.txt').write_text('ran')\n"
                "        self.assertEqual(multiply(3, 4), 12)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )

            status_before = run_git("status", "--porcelain").stdout
            worktrees_before = run_git("worktree", "list").stdout

            res = verification_oracle_guard.run_counterfactual_proof(
                repo_root=tmp_path,
                base="HEAD",
            )
            self.assertEqual(res["status"], "verified")
            self.assertTrue(res["red_green_verified"])

            status_after = run_git("status", "--porcelain").stdout
            worktrees_after = run_git("worktree", "list").stdout

            self.assertEqual(status_before, status_after, "Working tree state must be untouched")
            self.assertEqual(worktrees_before, worktrees_after, "Worktree list must contain zero leftover worktrees")
            self.assertTrue(uncommitted_file.is_file())
            self.assertEqual(uncommitted_file.read_text(encoding="utf-8"), "sensitive uncommitted developer notes\n")

    def test_counterfactual_does_not_treat_runner_crash_as_an_assertion(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            git = _init_git_repo(root)
            version = root / "version.txt"
            version.write_text("old", encoding="utf-8")
            git("add", "version.txt")
            git("commit", "-m", "chore: initial version")
            version.write_text("new", encoding="utf-8")
            test_file = root / "test_example.py"
            test_file.write_text(
                "import unittest\nfrom pathlib import Path\n\n"
                "class ExampleTest(unittest.TestCase):\n"
                "    def test_feature(self):\n"
                "        if Path('version.txt').read_text() == 'old':\n"
                "            raise RuntimeError('runner crashed')\n",
                encoding="utf-8",
            )

            result = verification_oracle_guard.run_counterfactual_proof(root, base="HEAD")

            self.assertEqual(result["status"], "inconclusive")
            self.assertFalse(result["red_green_verified"])

    def test_counterfactual_compares_repeated_runs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "repo"
            root.mkdir()
            counter = root.parent / "variant"
            git = _init_git_repo(root)
            version = root / "version.txt"
            version.write_text("old", encoding="utf-8")
            git("add", "version.txt")
            git("commit", "-m", "chore: initial version")
            version.write_text("new", encoding="utf-8")
            test_file = root / "test_toggle.py"
            test_file.write_text(
                "import unittest\nfrom pathlib import Path\n\n"
                "class ToggleTest(unittest.TestCase):\n"
                "    def test_toggle(self):\n"
                "        if Path('version.txt').read_text() == 'old':\n"
                f"            marker = Path({str(counter)!r})\n"
                "            first_run = not marker.exists()\n"
                "            marker.touch()\n"
                "            self.assertFalse(first_run)\n",
                encoding="utf-8",
            )

            result = verification_oracle_guard.run_counterfactual_proof(
                root, base="HEAD", check_flaky=True,
            )

            self.assertEqual(result["status"], "flaky_nondeterministic")
            self.assertFalse(result["red_green_verified"])
            self.assertFalse((root / "run-marker.txt").exists())

    def test_cli_counterfactual_and_proof_subcommand_invocations(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            run_git = _init_git_repo(tmp_path)

            calc_file = tmp_path / "calc.py"
            calc_file.write_text("def sub(a, b):\n    return 0\n", encoding="utf-8")
            run_git("add", "calc.py")
            run_git("commit", "-m", "chore: initial subtract")

            calc_file.write_text("def sub(a, b):\n    return a - b\n", encoding="utf-8")
            tests_dir = tmp_path / "tests"
            tests_dir.mkdir(parents=True, exist_ok=True)
            test_file = tests_dir / "test_sub.py"
            test_file.write_text(
                "import unittest\nfrom calc import sub\n\n"
                "class SubTest(unittest.TestCase):\n"
                "    def test_sub(self):\n"
                "        self.assertEqual(sub(10, 4), 6)\n\n"
                "if __name__ == '__main__':\n"
                "    unittest.main()\n",
                encoding="utf-8",
            )
            run_git("add", "calc.py", "tests/test_sub.py")
            run_git("commit", "-m", "fix: correct subtract and add test")

            # test counterfactual --json
            res = subprocess.run(
                [sys.executable, str(SCRIPT), "counterfactual", "--base", "HEAD~1", "--tests", "tests/test_sub.py", "--json"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res.returncode, 0, f"CLI stderr: {res.stderr}")
            payload = json.loads(res.stdout)
            self.assertEqual(payload["status"], "verified")
            self.assertTrue(payload["red_green_verified"])

            # test proof alias (human output)
            res2 = subprocess.run(
                [sys.executable, str(SCRIPT), "proof", "--base", "HEAD~1", "--tests", "tests/test_sub.py"],
                cwd=str(tmp_path),
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(res2.returncode, 0)
            self.assertIn("VERIFIED", res2.stdout)


if __name__ == "__main__":
    unittest.main()
