# SPDX-License-Identifier: MIT
# Unit tests for scripts/frame_budget_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "frame_budget_guard.py"
EXAMPLE = ROOT / "skills" / "apple-craft-and-frame-budget" / "examples" / "apple-craft-frame-budget-record.json"
TS_EXAMPLE = ROOT / "skills" / "apple-craft-and-frame-budget" / "examples" / "optimistic-state-machine-view.ts"

sys.path.insert(0, str(ROOT / "scripts"))
import frame_budget_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class FrameBudgetGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = frame_budget_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_layout_thrashing_or_non_compositor_animation_fails(self):
        record = valid_record()
        record["frame_budget_physics"]["layout_thrashing_eliminated"] = False
        record["frame_budget_physics"]["animated_properties"] = ["transform", "height", "top"]
        result = frame_budget_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("LAYOUT_THRASHING_NOT_ELIMINATED", codes)
        self.assertIn("NON_COMPOSITOR_ANIMATION_PROPERTIES", codes)

    def test_120hz_with_16ms_budget_or_invalid_epsilon_fails(self):
        record = valid_record()
        record["surface"]["target_refresh_rate_hz"] = 120
        record["surface"]["frame_budget_ms"] = 16.67
        record["frame_budget_physics"]["raf_epsilon_termination"] = 0.05
        result = frame_budget_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("FRAME_BUDGET_EXCEEDS_120HZ", codes)
        self.assertIn("INVALID_RAF_EPSILON", codes)

    def test_slow_optimistic_feedback_missing_rollback_or_nonzero_cls_fails(self):
        record = valid_record()
        record["optimistic_ui_and_cls"]["optimistic_feedback_budget_ms"] = 250.0
        record["optimistic_ui_and_cls"]["rollback_snapshot_captured"] = False
        record["optimistic_ui_and_cls"]["cumulative_layout_shift_target"] = 0.15
        result = frame_budget_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("OPTIMISTIC_FEEDBACK_TOO_SLOW", codes)
        self.assertIn("MISSING_ROLLBACK_SNAPSHOT", codes)
        self.assertIn("NON_ZERO_CLS_TARGET", codes)

    def test_boolean_soup_or_missing_discriminated_union_states_fails(self):
        record = valid_record()
        record["state_machine_contract"]["boolean_soup_absent"] = False
        record["state_machine_contract"]["modeled_states"] = ["idle", "loading_initial", "loaded_fresh"]
        result = frame_budget_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("BOOLEAN_SOUP_PRESENT", codes)
        self.assertIn("MISSING_REQUIRED_UI_STATES", codes)

    def test_touch_scroll_hijacking_or_small_hit_target_fails(self):
        record = valid_record()
        record["hardware_and_a11y_physics"]["touch_scroll_hijacking_absent"] = False
        record["hardware_and_a11y_physics"]["min_hit_target_px"] = 28
        result = frame_budget_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("TOUCH_SCROLL_HIJACKING_PRESENT", codes)
        self.assertIn("HIT_TARGET_BELOW_44PX", codes)

    def test_source_scanner_flags_thrashing_transition_all_boolean_soup_and_sync_storage(self):
        bad_source = """
        function BadBoard() {
          const [isLoading, setIsLoading] = useState(false);
          const [isError, setIsError] = useState(false);
          const [isSubmitted, setIsSubmitted] = useState(false);
          const css = "transition: all 0.3s ease;";
          card.style.top = nextY + "px";
          const rect = card.getBoundingClientRect();
          localStorage.setItem("board_dump", JSON.stringify(hugeBoard));
        }
        """
        result = frame_budget_guard.audit(valid_record(), source_text=bad_source)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("SOURCE_TRANSITION_ALL_FORBIDDEN", codes)
        self.assertIn("SOURCE_FORCED_SYNCHRONOUS_LAYOUT_THRASH", codes)
        self.assertIn("SOURCE_BOOLEAN_SOUP_STATE", codes)
        self.assertIn("SOURCE_MAIN_THREAD_SYNC_STORAGE_JSON", codes)

    def test_source_scanner_accepts_clean_discriminated_union_example(self):
        clean_ts = TS_EXAMPLE.read_text(encoding="utf-8")
        result = frame_budget_guard.audit(valid_record(), source_text=clean_ts)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["findings"], [])

    def test_refuse_verdict_permits_blocking_touch_scroll_hijack_and_thrashing(self):
        record = {
            "schema_version": "1.0",
            "surface": {
                "component_or_flow": "MobileProductCarousel & AnalyticsScrollHandler",
                "target_refresh_rate_hz": 120,
                "frame_budget_ms": 8.33
            },
            "verdict": {
                "action": "refuse",
                "rationale": "Refusing request to enable touch scroll-jacking on iOS Safari and run synchronous JSON.stringify localStorage writes inside the scroll listener.",
                "revisit_triggers": ["Gate custom scroll engine off coarse pointers and move analytics persistence to a Web Worker"]
            }
        }
        result = frame_budget_guard.audit(record)
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


if __name__ == "__main__":
    unittest.main()
