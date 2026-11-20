import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from scripts import rule_registry

ROOT = Path(__file__).resolve().parents[1]


class RuleRegistryTests(unittest.TestCase):
    def test_engine_id_calibration_preserves_raw_rule_and_catalog(self):
        expected = {
            "ERROR_SWALLOW_CANDIDATE": "OPS-01",
            "SCALE_TOIL_ERROR_SWALLOW": "OPS-01",
            "STS-H02": "OPS-01",
            "SRE-SCALE-SWALLOW": "OPS-01",
            "KISS_DEEP_NESTING": "SRE-01",
            "SKIPPED_TEST": "TST-03",
        }
        for raw, target in expected.items():
            with self.subTest(raw=raw):
                result = rule_registry.lookup(raw)
                self.assertEqual(result["engine_code"], raw)
                self.assertEqual(result["catalog_id"], target)
                self.assertTrue((ROOT / result["skill_path"]).is_file())

    def test_calibrated_detector_provenance_resolves_to_live_code(self):
        cases = {
            "TRIVIAL_COMMENT_NARRATION": ("SIM-17", "scripts/diff_guard.py"),
            "SRE-YAGNI_DEAD_FLAG": None,
            "SRE_YAGNI_DEAD_FLAG": ("SRE-05", "scripts/diff_guard.py"),
            "SRE-SCALE-SLEEP": ("SRE-07", "services/toil-guard-go/pkg/sre/toil.go"),
            "SRE-SCALE-RETRY": ("SRE-08", "services/toil-guard-go/pkg/sre/toil.go"),
            "SRE_SCALE_UNBOUNDED_CONCURRENCY": ("SRE-09", "scripts/diff_guard.py"),
            "SCALE_MISLEADING_HEALTH_CHECK": ("SRE-12", "scripts/sre_guard.py"),
            "SKIPPED_TEST": ("TST-03", "scripts/diff_guard.py"),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                result = rule_registry.lookup(raw)
                if expected is None:
                    self.assertFalse(result["found"])
                    continue
                catalog_id, source = expected
                self.assertEqual(result["catalog_id"], catalog_id)
                detector = next(rule for rule in result["related_rules"] if rule["engine_code"] == raw)
                self.assertEqual(detector["source"], source)
                self.assertIn(raw, (ROOT / source).read_text(encoding="utf-8"))

    def test_health_calibration_reports_false_positive(self):
        detector = "sre_guard:SCALE_MISLEADING_HEALTH_CHECK"
        receipt = {detector: {"tp": 1, "fp": 1, "tn": 1, "fn": 0}}
        report = rule_registry.build_coverage(receipt)
        self.assertEqual(report["fixture_precision"][detector], 0.5)
        self.assertEqual(report["patterns"]["SRE-12"]["fixtures"], receipt)
        self.assertEqual(report["detectors"][detector]["source"], rule_registry.SRE_SOURCE)

    def test_all_catalog_ids_can_be_explained_and_copies_match(self):
        path = ROOT / "references" / "anti-pattern-catalog.md"
        mirror = ROOT / "skills" / "anti-slop-engineering" / "references" / path.name
        self.assertEqual(path.read_bytes(), mirror.read_bytes())
        entries = list(rule_registry.iter_catalog())
        self.assertEqual(len(entries), 217)
        for entry in entries:
            explained = rule_registry.lookup(entry["catalog_id"])
            self.assertTrue(explained["found"])
            self.assertEqual(explained["remediation"], entry["remediation"])
            self.assertTrue((ROOT / explained["evidence_rubric"]).is_file())
        self.assertEqual(rule_registry.lookup("con-12")["related_rules"], [])
        self.assertFalse(rule_registry.lookup("CON-12")["mapped"])
        self.assertFalse(rule_registry.lookup("NO-SUCH-99")["found"])

    def test_catalog_rejects_malformed_and_duplicate_entries(self):
        valid = "- **OPS-01 | Empty catch.** Surface the failure.\n"
        for text in (valid + valid, "- **OPS-01 | broken entry\n"):
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "catalog.md"
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ValueError):
                    list(rule_registry.iter_catalog(path))

    def test_catalog_exact_query_can_stop_at_matching_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.md"
            path.write_text(
                "- **OPS-01 | Empty catch.** Surface the failure.\n- **OPS-02 | incomplete\n",
                encoding="utf-8",
            )
            self.assertEqual(rule_registry.lookup("ops-01", path)["catalog_id"], "OPS-01")

    def test_cli_invalid_and_missing_queries_have_distinct_status(self):
        script = [sys.executable, str(ROOT / "scripts" / "rule_registry.py")]
        known = subprocess.run([*script, "OPS-01", "--json"], capture_output=True, text=True)
        self.assertEqual(known.returncode, 0, known.stderr)
        self.assertIn("STS-H02", {r["engine_code"] for r in json.loads(known.stdout)["related_rules"]})
        missing = subprocess.run([*script, "NO-SUCH-99", "--json"], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1, missing.stderr)
        self.assertFalse(json.loads(missing.stdout)["found"])
        invalid = subprocess.run([*script, "--search", "  "], capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 2)
        self.assertEqual(invalid.stdout, "")

    def test_no_automatic_coverage_without_fixture_observation(self):
        report = rule_registry.build_coverage({})
        self.assertEqual(report["total_patterns"], 217)
        self.assertEqual(report["counts"]["automatic"], 0)
        self.assertEqual(report["counts"]["manual-review"], 0)
        self.assertEqual(report["counts"]["unobserved"], 217)

    def test_measured_failure_is_manual_review_not_unobserved(self):
        fixture = {"diff_guard:ERROR_SWALLOW_CANDIDATE": {"tp": 0, "fp": 1, "tn": 1, "fn": 1}}
        report = rule_registry.build_coverage(fixture)
        self.assertEqual(report["patterns"]["OPS-01"]["status"], "manual-review")
        self.assertEqual(report["patterns"]["OPS-01"]["fixtures"], fixture)
        self.assertEqual(report["counts"]["automatic"], 0)
        self.assertEqual(report["counts"]["manual-review"], 1)
        self.assertEqual(report["counts"]["unobserved"], report["total_patterns"] - 1)
        self.assertEqual(sum(report["counts"].values()), report["total_patterns"])

    def test_categories_without_evidence_are_labelled_not_counted(self):
        report = rule_registry.build_coverage({})
        self.assertEqual(report["categories_without_evidence"], ["out-of-scope", "planned"])
        self.assertNotIn("out-of-scope", report["counts"])
        self.assertNotIn("planned", report["counts"])

    def test_precision_denominator_is_reported_alongside_precision(self):
        detector = "sre_guard:SCALE_MISLEADING_HEALTH_CHECK"
        receipt = {detector: {"tp": 1, "fp": 1, "tn": 1, "fn": 0}}
        report = rule_registry.build_coverage(receipt)
        self.assertEqual(report["fixture_precision"][detector], 0.5)
        self.assertEqual(report["fixture_denominators"][detector], 2)
        positives_only = {"diff_guard:ERROR_SWALLOW_CANDIDATE": {"tp": 1, "fp": 0, "tn": 0, "fn": 0}}
        report = rule_registry.build_coverage(positives_only)
        self.assertIsNone(report["fixture_precision"]["diff_guard:ERROR_SWALLOW_CANDIDATE"])
        self.assertEqual(report["fixture_denominators"]["diff_guard:ERROR_SWALLOW_CANDIDATE"], 1)

    def test_report_requires_positive_and_negative_evidence(self):
        fixture = {"diff_guard:ERROR_SWALLOW_CANDIDATE": {"tp": 1, "fp": 0, "tn": 1, "fn": 0}}
        report = rule_registry.build_coverage(fixture)
        self.assertEqual(report["counts"]["automatic"], 1)
        self.assertEqual(report["patterns"]["OPS-01"]["status"], "automatic")
        self.assertEqual(report["patterns"]["OPS-01"]["fixtures"], fixture)
        fixture["diff_guard:ERROR_SWALLOW_CANDIDATE"]["tn"] = 0
        self.assertEqual(rule_registry.build_coverage(fixture)["counts"]["automatic"], 0)

    def test_duplicate_rules_or_dangling_catalog_mappings_fail_validation(self):
        entry = rule_registry.Rule("engine", "REUSED", "OPS-01", rule_registry.DIFF_SOURCE)
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            rule_registry.validate_registry((entry, entry))
        dangling = rule_registry.Rule("engine", "DANGLING", "NO-SUCH", rule_registry.DIFF_SOURCE)
        with self.assertRaisesRegex(ValueError, "catalog"):
            rule_registry.validate_registry((dangling,))
        unknown_skill = rule_registry.Rule("engine", "UNKNOWN", "OPS-01", rule_registry.DIFF_SOURCE, skill="unavailable")
        with self.assertRaisesRegex(ValueError, "skill"):
            rule_registry.validate_registry((unknown_skill,))
        unknown_source = rule_registry.Rule("engine", "UNKNOWN", "OPS-01", "no-such-script")
        with self.assertRaisesRegex(ValueError, "source"):
            rule_registry.validate_registry((unknown_source,))
        rule_registry.validate_registry(rule_registry.RULES)

    def test_report_does_not_infer_precision_from_only_positive_cases(self):
        fixture = {"diff_guard:ERROR_SWALLOW_CANDIDATE": {"tp": 1, "fp": 0, "tn": 0, "fn": 0}}
        report = rule_registry.build_coverage(fixture)
        self.assertIsNone(report["fixture_precision"]["diff_guard:ERROR_SWALLOW_CANDIDATE"])

    def test_engine_output_preserves_severity_and_explicit_unmapped_fields(self):
        from scripts import audit_runner

        mapped = audit_runner.normalize_finding(
            "sre_guard", {"id": "KISS_DEEP_NESTING", "severity": "review", "message": "dense"}, {}
        )
        unmapped = audit_runner.normalize_finding(
            "sre_guard", {"id": "UNVERIFIED_CODE", "severity": "review", "message": "unmapped"}, {}
        )
        self.assertEqual(mapped["rule"], "KISS_DEEP_NESTING")
        self.assertEqual(mapped["severity"], unmapped["severity"])
        self.assertTrue(mapped["mapped"])
        self.assertFalse(unmapped["mapped"])
        self.assertIsNone(unmapped["catalog_id"])
        self.assertIsNone(unmapped["skill_path"])

    def test_text_includes_evidence_and_remediation(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(rule_registry.explain_cli(["STS-H02"]), 0)
        for value in ("OPS-01", "STS-H02", "engineering-judgment.md", "Failures swallowed"):
            self.assertIn(value, output.getvalue())


if __name__ == "__main__":
    unittest.main()
