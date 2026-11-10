# SPDX-License-Identifier: MIT
# Unit tests for scripts/invariant_steward_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "invariant_steward_guard.py"
EXAMPLE_LEDGER = ROOT / "skills" / "repo-memory-and-invariant-steward" / "examples" / "invariant-ledger-example.json"
EXAMPLE_TRIGGER = ROOT / "skills" / "repo-memory-and-invariant-steward" / "examples" / "reassessment-trigger-example.json"

sys.path.insert(0, str(ROOT / "scripts"))
import invariant_steward_guard  # noqa: E402


def valid_ledger():
    return json.loads(EXAMPLE_LEDGER.read_text(encoding="utf-8"))


def valid_trigger():
    return json.loads(EXAMPLE_TRIGGER.read_text(encoding="utf-8"))


class InvariantStewardGuardTests(unittest.TestCase):
    def test_complete_ledger_is_structurally_valid(self):
        ledger = valid_ledger()
        result = invariant_steward_guard.audit_ledger(ledger)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])
        self.assertGreater(result["invariants_count"], 0)

    def test_empty_or_non_list_invariants_fails(self):
        ledger = valid_ledger()
        ledger["invariants"] = []
        result = invariant_steward_guard.audit_ledger(ledger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("EMPTY_INVARIANTS", codes)

    def test_missing_invariant_id_fails(self):
        ledger = valid_ledger()
        ledger["invariants"][0]["id"] = ""
        result = invariant_steward_guard.audit_ledger(ledger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_INVARIANT_ID", codes)

    def test_invalid_category_fails(self):
        ledger = valid_ledger()
        ledger["invariants"][0]["category"] = "unsupported_vague_category"
        result = invariant_steward_guard.audit_ledger(ledger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_CATEGORY", codes)

    def test_duplicate_invariant_ids_fail(self):
        ledger = valid_ledger()
        ledger["invariants"][1]["id"] = ledger["invariants"][0]["id"]
        result = invariant_steward_guard.audit_ledger(ledger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("DUPLICATE_INVARIANT_ID", codes)

    def test_invalid_status_fails(self):
        ledger = valid_ledger()
        ledger["invariants"][0]["status"] = "forgotten"
        result = invariant_steward_guard.audit_ledger(ledger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_STATUS", codes)

    def test_valid_reassessment_trigger_passes(self):
        trigger = valid_trigger()
        result = invariant_steward_guard.audit_reassessment_trigger(trigger)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])
        self.assertEqual(result["target_invariant_id"], "INV-PARANOID-IDEMPOTENCY")

    def test_reassessment_trigger_missing_justification_fails(self):
        trigger = valid_trigger()
        trigger["justification"] = "too short"
        result = invariant_steward_guard.audit_reassessment_trigger(trigger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_JUSTIFICATION", codes)

    def test_reassessment_trigger_missing_trade_off_fails(self):
        trigger = valid_trigger()
        trigger["trade_off_delta"] = {"gain": "faster"}
        result = invariant_steward_guard.audit_reassessment_trigger(trigger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_RISK", codes)

    def test_reassessment_trigger_invalid_action_fails(self):
        trigger = valid_trigger()
        trigger["action"] = "silently_bypass"
        result = invariant_steward_guard.audit_reassessment_trigger(trigger)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_REASSESSMENT_ACTION", codes)

    def test_sync_extracts_invariants_and_writes_toon(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            out_file = Path(tmpdir) / "test-ledger.json"
            res = invariant_steward_guard.sync_ledger(
                [ROOT / "skills" / "repo-memory-and-invariant-steward" / "examples"],
                out_file
            )
            self.assertEqual(res["sync_status"], "complete")
            self.assertTrue(out_file.exists())
            toon_file = out_file.with_suffix(".toon")
            self.assertTrue(toon_file.exists())
            toon_content = toon_file.read_text(encoding="utf-8")
            self.assertIn("invariant_ledger", toon_content)

    def test_drift_detection_clean_diff_passes(self):
        ledger = valid_ledger()
        diff = """
diff --git a/src/utils/math.ts b/src/utils/math.ts
--- a/src/utils/math.ts
+++ b/src/utils/math.ts
@@ -1,3 +1,3 @@
-export function add(a: number, b: number) { return a + b; }
+export function add(a: number, b: number) { return Number(a) + Number(b); }
"""
        res = invariant_steward_guard.detect_drift(ledger, diff, ["src/utils/math.ts"])
        self.assertFalse(res["drift_detected"])
        self.assertEqual(res["findings"], [])

    def test_drift_detection_forbidden_pattern_fails(self):
        ledger = valid_ledger()
        diff = """
diff --git a/src/api/routes/checkout.ts b/src/api/routes/checkout.ts
--- a/src/api/routes/checkout.ts
+++ b/src/api/routes/checkout.ts
@@ -1,3 +1,3 @@
-const token = crypto.randomUUID();
+const token = "token_" + Math.random();
"""
        res = invariant_steward_guard.detect_drift(ledger, diff, ["src/api/routes/checkout.ts"])
        self.assertTrue(res["drift_detected"])
        codes = [f["code"] for f in res["findings"]]
        self.assertIn("INVARIANT_FORBIDDEN_PATTERN", codes)

    def test_drift_detection_required_pattern_removal_fails(self):
        ledger = valid_ledger()
        diff = """
diff --git a/src/api/checkout.ts b/src/api/checkout.ts
--- a/src/api/checkout.ts
+++ b/src/api/checkout.ts
@@ -10,3 +10,1 @@
-  const key = req.headers["Idempotency-Key"];
-  if (!key) throw new Error();
+  // removed check
"""
        res = invariant_steward_guard.detect_drift(ledger, diff, ["src/api/checkout.ts"])
        self.assertTrue(res["drift_detected"])
        codes = [f["code"] for f in res["findings"]]
        self.assertIn("INVARIANT_PATTERN_REMOVED", codes)

    def test_drift_detection_waived_with_valid_reassessment(self):
        ledger = valid_ledger()
        trigger = valid_trigger()
        reassessment = invariant_steward_guard.audit_reassessment_trigger(trigger)
        diff = """
diff --git a/src/api/checkout.ts b/src/api/checkout.ts
--- a/src/api/checkout.ts
+++ b/src/api/checkout.ts
@@ -10,3 +10,1 @@
-  const key = req.headers["Idempotency-Key"];
+  // replaced by database unique constraint
"""
        res = invariant_steward_guard.detect_drift(
            ledger, diff, ["src/api/checkout.ts"], reassessment=reassessment
        )
        self.assertFalse(res["drift_detected"])
        self.assertIn("inv-paranoid-idempotency", res["waived_invariants"])

    def test_cli_invocation_text_and_json(self):
        cmd = [sys.executable, str(SCRIPT), "audit", str(EXAMPLE_LEDGER), "--json"]
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
        self.assertEqual(data["record_status"], "complete")

        reassess_cmd = [sys.executable, str(SCRIPT), "reassess", str(EXAMPLE_TRIGGER), "--json"]
        reassess_proc = subprocess.run(reassess_cmd, capture_output=True, text=True, check=True)
        reassess_data = json.loads(reassess_proc.stdout)
        self.assertEqual(reassess_data["record_status"], "complete")


if __name__ == "__main__":
    unittest.main()
