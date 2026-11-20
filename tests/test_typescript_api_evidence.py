import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "typescript_api_evidence.py"


class TypeScriptApiEvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.workspace = Path(directory.name)
        package = self.workspace / "node_modules" / "lease-ts"
        package.mkdir(parents=True)
        (package / "package.json").write_text(
            json.dumps({"name": "lease-ts", "version": "3.1.4", "types": "index.d.ts"}),
            encoding="utf-8",
        )
        self.declarations = package / "index.d.ts"
        self.declarations.write_text(
            "export declare function published(): void;\nexport declare const version: string;\n",
            encoding="utf-8",
        )

    def check(self, node, tsc_js, package="lease-ts", symbol="published"):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--workspace", str(self.workspace),
             "--package", package, "--symbol", symbol,
             "--node", str(node), "--tsc-js", str(tsc_js)],
            capture_output=True, text=True,
        )
        self.assertTrue(process.stdout, process.stderr)
        return process.returncode, json.loads(process.stdout)

    def test_missing_compiler_is_not_checked(self):
        code, result = self.check("/unlikely/invalid/node", "/unlikely/invalid/tsc.js")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["compiler"]["status"], "not_checked")
        self.assertEqual(result["installed_api"]["status"], "not_checked")

    def test_invalid_symbol_is_inconclusive(self):
        code, result = self.check("/unlikely/invalid/node", "/unlikely/invalid/tsc.js",
                                  symbol="published;process.exit(1)")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    @unittest.skipUnless(
        os.environ.get("ANTI_SLOP_TEST_TSC_JS") and shutil.which("node"),
        "Live compiler proof requires Node and ANTI_SLOP_TEST_TSC_JS",
    )
    def test_installed_compiler_cases(self):
        node = shutil.which("node")
        tsc_js = Path(os.environ["ANTI_SLOP_TEST_TSC_JS"])
        compiler_version = json.loads(
            (tsc_js.parents[1] / "package.json").read_text(encoding="utf-8"))["version"]

        code, result = self.check(node, tsc_js)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["compiler"]["toolchain"], "typescript")
        self.assertEqual(result["compiler"]["version"], compiler_version)
        self.assertEqual(result["compiler"]["status"], "passed")
        api = result["installed_api"]
        self.assertEqual(api["status"], "declared")
        self.assertEqual(api["version"], "3.1.4")
        self.assertEqual(api["declaration_span"], {
            "path": "node_modules/lease-ts/index.d.ts",
            "line": 1, "column": 0, "end_line": 1, "end_column": 42,
        })
        self.assertEqual(api["provenance"]["module"], "node_modules/lease-ts/index.d.ts")

        code, result = self.check(node, tsc_js, symbol="removed")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "not_declared")
        self.assertEqual(result["installed_api"]["version"], "3.1.4")
        self.assertNotIn("declaration_span", result["installed_api"])

        code, result = self.check(node, tsc_js, package="not-installed")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")


if __name__ == "__main__":
    unittest.main()
