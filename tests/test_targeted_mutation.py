import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "targeted_mutation.py"

class TargetedMutationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repo = Path(temporary.name).resolve()
        self.git("init", "-q")
        (self.repo / "scripts").mkdir()
        (self.repo / "tests").mkdir()
        self.source = self.repo / "scripts" / "selector.py"
        self.source.write_text(
            "def select(enabled, bypass):\n"
            "    if bool(enabled):\n        return 4\n"
            "    if bool(bypass):\n        return 2\n"
            "    return 0\n", encoding="utf-8",
        )
        self.test_file = self.repo / "tests" / "test_selector.py"
        self.write_test(4)
        self.git("add", ".")
        self.git("-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
                 "commit", "-qm", "baseline")
        source = self.source.read_text(encoding="utf-8")
        self.source.write_text(source.replace("bool(enabled)", "enabled").replace("bool(bypass)", "bypass"), encoding="utf-8")

    def git(self, *args):
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            check=True, capture_output=True, text=True,
        ).stdout

    def write_test(self, expected):
        self.test_file.write_text(
            "import unittest\nfrom scripts.selector import select\n\n"
            "class SelectorTests(unittest.TestCase):\n"
            f"    def test_case(self):\n        self.assertEqual(select(True, False), {expected})\n",
            encoding="utf-8",
        )

    def run_mutation(self, *args):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--source", "scripts/selector.py",
             "--function", "select", "--test", "tests/test_selector.py", "--seed", "17", *args],
            cwd=self.repo, capture_output=True, text=True, check=False, timeout=30,
        )
        self.assertTrue(result.stdout, result.stderr)
        return result, json.loads(result.stdout)

    def test_scores_changed_conditions_without_writing_to_checkout(self):
        before = self.git("diff", "HEAD")
        result, report = self.run_mutation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["score"], {"killed": 1, "evaluated": 2})
        self.assertEqual({row["line"]: row["status"] for row in report["results"]}, {2: "killed", 4: "survived"})
        self.assertEqual(self.run_mutation()[1], report)
        self.assertEqual(self.git("diff", "HEAD"), before)
        self.assertEqual(self.git("status", "--porcelain"), " M scripts/selector.py\n")

    def test_failing_selected_baseline_is_inconclusive(self):
        self.write_test(5)
        result, report = self.run_mutation()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["status"], "inconclusive")
        self.assertEqual(report["results"], [])
        self.assertEqual(report["score"], {"killed": 0, "evaluated": 0})

    def test_scores_changed_boolean_return(self):
        source = self.source.read_text(encoding="utf-8")
        self.source.write_text(source.replace("return 0", "return False"), encoding="utf-8")
        before = self.git("diff", "HEAD")
        _, report = self.run_mutation("--operator", "flip_boolean_return")
        self.assertEqual(report["eligible"], 1)
        self.assertEqual(report["score"], {"killed": 0, "evaluated": 1})
        self.assertEqual(report["results"][0]["line"], 6)
        self.assertEqual(report["results"][0]["operator"], "flip_boolean_return")
        self.assertEqual(self.git("diff", "HEAD"), before)
        self.test_file.write_text(self.test_file.read_text(encoding="utf-8") +
            "        self.assertIs(select(False, False), False)\n", encoding="utf-8")
        _, report = self.run_mutation("--operator", "flip_boolean_return")
        self.assertEqual(report["score"], {"killed": 1, "evaluated": 1})

    def test_boolean_return_operator_ignores_non_literal_or_unchanged_returns(self):
        _, report = self.run_mutation("--operator", "flip_boolean_return")
        self.assertEqual(report["status"], "no_mutants")
        self.assertEqual(report["results"], [])

    def test_timed_out_mutant_is_inconclusive_and_excluded_from_score(self):
        self.test_file.write_text(
            "import time\nimport unittest\nfrom scripts.selector import select\n\n"
            "class SelectorTests(unittest.TestCase):\n"
            "    def test_case(self):\n"
            "        result = select(True, False)\n"
            "        if result == 0:\n            time.sleep(60)\n"
            "        self.assertEqual(result, 4)\n", encoding="utf-8",
        )
        before = self.git("diff", "HEAD")
        before_status = self.git("status", "--porcelain")
        result, report = self.run_mutation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["status"], "evaluated")
        self.assertEqual({row["line"]: row["status"] for row in report["results"]},
                         {2: "inconclusive", 4: "survived"})
        self.assertEqual({row["line"]: row["observation"] for row in report["results"]},
                         {2: "timed_out", 4: "passed"})
        self.assertEqual(report["score"], {"killed": 0, "evaluated": 1})
        self.assertEqual(self.git("diff", "HEAD"), before)
        self.assertEqual(self.git("status", "--porcelain"), before_status)

    def test_external_action_marker_excludes_run_before_any_execution(self):
        sentinel = self.repo / "external-action-sentinel.txt"
        self.test_file.write_text(
            "import os\nimport unittest\nfrom pathlib import Path\nfrom scripts.selector import select\n\n"
            "# targeted-mutation: external-action\n\n"
            "class SelectorTests(unittest.TestCase):\n"
            "    def test_case(self):\n"
            "        Path(os.environ['TARGETED_MUTATION_SENTINEL']).write_text('ran', encoding='utf-8')\n"
            "        self.assertEqual(select(True, False), 4)\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n", encoding="utf-8",
        )
        os.environ["TARGETED_MUTATION_SENTINEL"] = str(sentinel)
        self.addCleanup(os.environ.pop, "TARGETED_MUTATION_SENTINEL")
        control = subprocess.run(
            [sys.executable, str(self.test_file)],
            cwd=self.repo, capture_output=True, text=True, check=False, timeout=30,
            env={**os.environ, "PYTHONPATH": str(self.repo)},
        )
        self.assertEqual(control.returncode, 0, control.stderr)
        self.assertTrue(sentinel.exists())
        sentinel.unlink()
        before = self.git("diff", "HEAD")
        before_status = self.git("status", "--porcelain")
        result, report = self.run_mutation()
        self.assertEqual(result.returncode, 2)
        self.assertEqual(report["status"], "excluded")
        self.assertEqual(report["exclusion"], {"marker": "external-action", "line": 6})
        self.assertEqual(report["baseline"], "not_run")
        self.assertEqual(report["eligible"], 2)
        self.assertEqual(report["results"], [])
        self.assertEqual(report["score"], {"killed": 0, "evaluated": 0})
        self.assertFalse(sentinel.exists())
        self.assertEqual(self.run_mutation()[1], report)
        self.assertEqual(self.git("diff", "HEAD"), before)
        self.assertEqual(self.git("status", "--porcelain"), before_status)

    def test_erroring_mutant_is_inconclusive_and_excluded_from_score(self):
        self.test_file.write_text(
            "import unittest\nfrom scripts.selector import select\n\n"
            "class SelectorTests(unittest.TestCase):\n"
            "    def test_case(self):\n        self.assertEqual(8 // select(True, False), 2)\n",
            encoding="utf-8",
        )
        before = self.git("diff", "HEAD")
        before_status = self.git("status", "--porcelain")
        result, report = self.run_mutation()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(report["status"], "evaluated")
        self.assertEqual({row["line"]: row["status"] for row in report["results"]},
                         {2: "inconclusive", 4: "survived"})
        self.assertEqual({row["line"]: row["observation"] for row in report["results"]},
                         {2: "test_failure", 4: "passed"})
        self.assertEqual(report["score"], {"killed": 0, "evaluated": 1})
        self.assertEqual(self.git("diff", "HEAD"), before)
        self.assertEqual(self.git("status", "--porcelain"), before_status)
