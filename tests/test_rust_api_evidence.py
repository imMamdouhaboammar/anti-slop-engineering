import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "rust_api_evidence.py"

LIB_RS = (
    "pub fn published() {}\n"
    "\n"
    "pub const VERSION: &str = \"0.3.2\";\n"
    "\n"
    "pub fn multiline(\n"
    "    input: u32,\n"
    ") -> u32 { input }\n"
)


class RustApiEvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.installed = Path(directory.name) / "lease-rs"
        (self.installed / "src").mkdir(parents=True)
        self.manifest = self.installed / "Cargo.toml"
        self.manifest.write_text(
            "[package]\nname = \"lease-rs\"\nversion = \"0.3.2\"\nedition = \"2021\"\n",
            encoding="utf-8",
        )
        self.lib = self.installed / "src" / "lib.rs"
        self.lib.write_text(LIB_RS, encoding="utf-8")

    def check(self, rustc, crate="lease-rs", symbol="published"):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), "--installed", str(self.installed),
             "--crate", crate, "--symbol", symbol, "--rustc", str(rustc)],
            capture_output=True, text=True,
        )
        self.assertTrue(process.stdout, process.stderr)
        return process.returncode, json.loads(process.stdout)

    def test_missing_toolchain_is_not_checked(self):
        code, result = self.check("/unlikely/invalid/rustc")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["compiler"]["status"], "not_checked")
        self.assertEqual(result["installed_api"]["status"], "not_checked")

    def test_invalid_symbol_is_inconclusive(self):
        code, result = self.check("/unlikely/invalid/rustc", symbol="published;process.exit(1)")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")


@unittest.skipUnless(shutil.which("rustc"), "Live rustc proof requires rustc on PATH")
class RustApiEvidenceLiveTests(RustApiEvidenceTests):
    def setUp(self):
        super().setUp()
        self.rustc = shutil.which("rustc")
        version_output = subprocess.run(
            [self.rustc, "--version"], capture_output=True, text=True).stdout
        self.toolchain_version = version_output.split()[1]

    def test_present_api_is_declared_with_span_and_provenance(self):
        code, result = self.check(self.rustc)
        self.assertEqual(code, 0, result)
        self.assertEqual(result["compiler"]["toolchain"], "rustc")
        self.assertEqual(result["compiler"]["version"], self.toolchain_version)
        self.assertEqual(result["compiler"]["status"], "passed")
        api = result["installed_api"]
        self.assertEqual(api["status"], "declared")
        self.assertEqual(api["version"], "0.3.2")
        self.assertEqual(api["declaration_span"], {
            "path": "src/lib.rs", "line": 1, "column": 0, "end_line": 1, "end_column": 21,
        })
        self.assertEqual(api["provenance"]["module"], "src/lib.rs")

    def test_multiline_signature_span_covers_the_whole_signature(self):
        code, result = self.check(self.rustc, symbol="multiline")
        self.assertEqual(code, 0, result)
        span = result["installed_api"]["declaration_span"]
        self.assertEqual(span["line"], 5)
        self.assertEqual(span["end_line"], 7)

    def test_removed_api_is_not_declared(self):
        code, result = self.check(self.rustc, symbol="removed")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "not_declared")
        self.assertEqual(result["installed_api"]["version"], "0.3.2")
        self.assertNotIn("declaration_span", result["installed_api"])

    def test_crate_name_mismatch_is_inconclusive(self):
        code, result = self.check(self.rustc, crate="other-crate")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_corrupted_manifest_is_inconclusive(self):
        self.manifest.write_text("[package]\nname = \"lease-rs\"\n", encoding="utf-8")
        code, result = self.check(self.rustc)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_conflicting_lockfile_is_inconclusive(self):
        (self.installed / "Cargo.lock").write_text(
            "[[package]]\nname = \"lease-rs\"\nversion = \"9.9.9\"\n", encoding="utf-8")
        code, result = self.check(self.rustc)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_build_script_and_dependencies_are_inconclusive(self):
        (self.installed / "build.rs").write_text("fn main() {}\n", encoding="utf-8")
        code, result = self.check(self.rustc)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")
        (self.installed / "build.rs").unlink()
        self.manifest.write_text(
            "[package]\nname = \"lease-rs\"\nversion = \"0.3.2\"\n\n[dependencies]\nserde = \"1\"\n",
            encoding="utf-8")
        code, result = self.check(self.rustc)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_reexported_and_conditional_symbols_are_inconclusive(self):
        self.lib.write_text("pub use crate::inner::published;\nmod inner {\n"
                            "    pub fn published() {}\n}\n", encoding="utf-8")
        code, result = self.check(self.rustc)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")
        self.lib.write_text("#[cfg(feature = \"extra\")]\npub fn published() {}\n", encoding="utf-8")
        code, result = self.check(self.rustc)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_broken_source_is_a_compiler_diagnostic(self):
        self.lib.write_text("pub fn published( {\n", encoding="utf-8")
        code, result = self.check(self.rustc)
        self.assertEqual(code, 1, result)
        self.assertEqual(result["compiler"]["status"], "diagnostic")
        self.assertEqual(result["installed_api"]["status"], "not_checked")


if __name__ == "__main__":
    unittest.main()
