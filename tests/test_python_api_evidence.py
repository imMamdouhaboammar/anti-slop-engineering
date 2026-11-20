import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "python_api_evidence.py"


class PythonApiEvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.site = self.root / "site"
        self.site.mkdir()
        self.source = self.root / "consumer.py"
        self.source.write_text("from leasepkg import published\n", encoding="utf-8")
        self.module = self.site / "leasepkg"
        self.module.mkdir()
        self.marker = self.root / "ran"
        (self.module / "__init__.py").write_text(
            "from pathlib import Path\nPath(%r).touch()\n" % str(self.marker), encoding="utf-8",
        )
        (self.module / "__init__.pyi").write_text("def published() -> None: ...\n", encoding="utf-8")
        metadata = self.site / "lease_pkg-2.3.0.dist-info"
        metadata.mkdir()
        (metadata / "METADATA").write_text("Name: lease-pkg\nVersion: 2.3.0\n", encoding="utf-8")
        (metadata / "RECORD").write_text(
            "leasepkg/__init__.py,,\nleasepkg/__init__.pyi,,\n", encoding="utf-8",
        )

    def check(self, distribution="lease-pkg"):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.source), "--site-packages", str(self.site),
             "--distribution", distribution, "--module", "leasepkg", "--symbol", "published"],
            capture_output=True, text=True,
        )
        self.assertTrue(process.stdout, process.stderr)
        self.assertFalse(self.marker.exists())
        return process.returncode, json.loads(process.stdout)

    def test_reports_stub_declaration_and_installed_version_without_import(self):
        code, result = self.check()
        self.assertEqual(code, 0, result)
        self.assertEqual(result["compiler"]["status"], "passed")
        api = result["installed_api"]
        self.assertEqual(api["status"], "declared")
        self.assertEqual(api["version"], "2.3.0")
        self.assertEqual((api["path"], api["line"]), ("leasepkg/__init__.pyi", 1))

    def test_compiler_error_is_reported_with_source(self):
        self.source.write_text("return 1\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 1, result)
        self.assertEqual(result["compiler"]["status"], "diagnostic")
        self.assertEqual(result["compiler"]["line"], 1)
        self.assertEqual(result["installed_api"]["status"], "not_checked")

    def test_missing_dependency_has_no_pass(self):
        code, result = self.check("not-installed")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_removed_and_dynamic_declarations_are_not_confirmed(self):
        stub = self.module / "__init__.pyi"
        stub.write_text("def replacement() -> None: ...\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "not_declared")
        stub.unlink()
        (self.module / "__init__.py").write_text("def __getattr__(name): ...\n", encoding="utf-8")
        code, result = self.check()
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_candidate_outside_selected_installation_is_inconclusive(self):
        stub = self.module / "__init__.pyi"
        stub.unlink()
        external = self.root / "external.pyi"
        external.write_text("def published() -> None: ...\n", encoding="utf-8")
        stub.symlink_to(external)
        code, result = self.check()
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def check_consumer(self, site=None):
        process = subprocess.run(
            [sys.executable, str(SCRIPT), str(self.source), "--site-packages", str(site or self.site),
             "--distribution", "lease-pkg", "--consumer-import"],
            capture_output=True, text=True,
        )
        self.assertTrue(process.stdout, process.stderr)
        self.assertFalse(self.marker.exists())
        return process.returncode, json.loads(process.stdout)

    def test_consumer_import_links_import_span_to_declaration_span(self):
        code, result = self.check_consumer()
        self.assertEqual(code, 0, result)
        api = result["installed_api"]
        self.assertEqual(api["status"], "declared")
        self.assertEqual(api["version"], "2.3.0")
        self.assertEqual(api["module"], "leasepkg")
        self.assertEqual(api["symbol"], "published")
        self.assertEqual(api["import_span"], {"line": 1, "column": 0, "end_line": 1, "end_column": 30})
        self.assertEqual(api["declaration_span"], {
            "path": "leasepkg/__init__.pyi", "line": 1, "column": 0, "end_line": 1, "end_column": 28,
        })
        self.assertEqual(api["provenance"]["module"], "leasepkg/__init__.pyi")

    def test_consumer_import_removed_symbol_is_not_declared(self):
        (self.module / "__init__.pyi").write_text("def replacement() -> None: ...\n", encoding="utf-8")
        code, result = self.check_consumer()
        self.assertEqual(code, 2, result)
        api = result["installed_api"]
        self.assertEqual(api["status"], "not_declared")
        self.assertEqual(api["import_span"]["line"], 1)
        self.assertNotIn("declaration_span", api)

    def test_consumer_import_ambiguous_ownership_is_inconclusive(self):
        other = self.site / "lease-pkg-9.9.9.dist-info"
        other.mkdir()
        (other / "METADATA").write_text("Name: lease-pkg\nVersion: 9.9.9\n", encoding="utf-8")
        (other / "RECORD").write_text("leasepkg/__init__.pyi,,\n", encoding="utf-8")
        code, result = self.check_consumer()
        self.assertEqual(code, 2, result)
        api = result["installed_api"]
        self.assertEqual(api["status"], "inconclusive")
        self.assertIn("ambiguous", api["reason"])

    def test_consumer_import_dynamic_export_is_inconclusive(self):
        (self.module / "__init__.pyi").unlink()
        (self.module / "__init__.py").write_text("def __getattr__(name): ...\n", encoding="utf-8")
        code, result = self.check_consumer()
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")

    def test_consumer_import_selection_must_be_single_and_present(self):
        self.source.write_text("import os\n", encoding="utf-8")
        code, result = self.check_consumer()
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "inconclusive")
        self.source.write_text("from leasepkg import published\nfrom leasepkg import other\n", encoding="utf-8")
        code, result = self.check_consumer()
        self.assertEqual(code, 2, result)
        api = result["installed_api"]
        self.assertEqual(api["status"], "inconclusive")
        self.assertIn("more than one", api["reason"])

    def test_consumer_import_unavailable_installation_is_not_checked(self):
        code, result = self.check_consumer(site=self.root / "missing-site")
        self.assertEqual(code, 2, result)
        self.assertEqual(result["installed_api"]["status"], "not_checked")
