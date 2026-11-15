import importlib.util
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "typescript_compiler_evidence.py"
SPEC = importlib.util.spec_from_file_location("typescript_compiler_evidence", SCRIPT)
EVIDENCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EVIDENCE)


class TypeScriptCompilerEvidenceTests(unittest.TestCase):
    def test_compiler_diagnostic_includes_code_and_source_position(self):
        observed = EVIDENCE.parse_diagnostics(
            b"fixture.ts(1,7): error TS2322: Type 'string' is not assignable to type 'number'.\n"
        )
        self.assertEqual(observed, [{
            "path": "fixture.ts", "line": 1, "column": 7, "code": "TS2322",
            "message": "Type 'string' is not assignable to type 'number'.",
        }])
        self.assertEqual(EVIDENCE.parse_diagnostics(b"error TS5072: configuration error\n"), [])

    def test_missing_compiler_is_explicitly_not_checked(self):
        result = EVIDENCE.collect(Path("/unlikely/invalid/node"), Path("/unlikely/invalid/tsc.js"))
        self.assertEqual(result["status"], "not_checked")

    def test_output_and_timeout_limits(self):
        if sys.platform == "win32":
            self.assertEqual(EVIDENCE.run_bounded([], Path.cwd(), {})["status"], "unavailable")
            return
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            env = {"PATH": "/usr/bin:/bin"}
            command = [sys.executable, "-c", "print('x' * 30000)"]
            large = EVIDENCE.run_bounded(command, root, env, 2, 100)
            self.assertEqual(large["status"], "output_limit")
            slow = EVIDENCE.run_bounded(
                [sys.executable, "-c", "import time; time.sleep(10)"], root, env, 0.15, 1024,
            )
            self.assertEqual(slow["status"], "timeout")

    def test_installed_compiler_with_controlled_fixture_when_selected(self):
        tsc = os.environ.get("ANTI_SLOP_TEST_TSC_JS")
        node = shutil.which("node")
        if not (tsc and node and sys.platform == "darwin"):
            return
        observed = EVIDENCE.collect(Path(node), Path(tsc))
        self.assertEqual(observed["status"], "passed", observed)
        self.assertEqual(observed["control"]["status"], "passed")
        self.assertEqual(observed["type_error"]["diagnostics"][0]["code"], "TS2322")
