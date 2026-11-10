# SPDX-License-Identifier: MIT
# Unit tests for scripts/apple_craft_guard.py

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "apple_craft_guard.py"
EXAMPLE = (
    ROOT
    / "skills"
    / "apple-craft-and-interaction-physics"
    / "examples"
    / "apple-craft-record.json"
)
TS_EXAMPLE = (
    ROOT
    / "skills"
    / "apple-craft-and-interaction-physics"
    / "examples"
    / "interactive-craft-component.ts"
)

sys.path.insert(0, str(ROOT / "scripts"))
import apple_craft_guard  # noqa: E402


def valid_record():
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class AppleCraftGuardTests(unittest.TestCase):
    def test_complete_proceed_record_is_structurally_valid(self):
        record = valid_record()
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "proceed")
        self.assertEqual(result["findings"], [])

    def test_missing_required_ui_states_fails(self):
        record = valid_record()
        record["exhaustive_state_matrix"]["modeled_states"] = [
            "loading_skeleton",
            "loaded_fresh",
            "terminal_error",
        ]
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_REQUIRED_UI_STATES", codes)

    def test_missing_draft_preservation_fails(self):
        record = valid_record()
        record["exhaustive_state_matrix"]["draft_preservation_mechanism"] = "short"
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MISSING_DRAFT_PRESERVATION_MECHANISM", codes)

    def test_non_zero_cls_or_insufficient_geometry_locks_fails(self):
        record = valid_record()
        record["zero_layout_shift"]["cumulative_layout_shift_target"] = 0.12
        record["zero_layout_shift"]["geometry_reservation_mechanisms"] = ["only_one_mechanism"]
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("NON_ZERO_CLS_TARGET", codes)
        self.assertIn("INSUFFICIENT_GEOMETRY_LOCKS", codes)

    def test_media_aspect_ratios_disabled_fails(self):
        record = valid_record()
        record["zero_layout_shift"]["media_aspect_ratios_enforced"] = False
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MEDIA_ASPECT_RATIOS_NOT_ENFORCED", codes)

    def test_non_interruptible_physics_or_missing_velocity_inheritance_fails(self):
        record = valid_record()
        record["interruptible_physics"]["immediate_interruption_supported"] = False
        record["interruptible_physics"]["velocity_inheritance_enforced"] = False
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("NON_INTERRUPTIBLE_PHYSICS", codes)
        self.assertIn("MISSING_VELOCITY_INHERITANCE", codes)

    def test_invalid_spring_params_or_epsilon_fails(self):
        record = valid_record()
        record["interruptible_physics"]["spring_physics_parameters"] = {
            "stiffness": -10,
            "damping": 0,
            "mass": 1.0,
        }
        record["interruptible_physics"]["raf_epsilon_termination"] = 0.05
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("INVALID_SPRING_PARAMETERS", codes)
        self.assertIn("INVALID_RAF_EPSILON", codes)

    def test_non_compositor_animation_properties_fails(self):
        record = valid_record()
        record["interruptible_physics"]["animated_properties"] = ["transform", "height", "top"]
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("NON_COMPOSITOR_ANIMATION_PROPERTIES", codes)

    def test_keyboard_navigation_or_focus_ring_disabled_fails(self):
        record = valid_record()
        record["keyboard_and_focus_mastery"]["full_keyboard_operable"] = False
        record["keyboard_and_focus_mastery"]["focus_visible_ring"]["contrast_ratio"] = 1.5
        record["keyboard_and_focus_mastery"]["focus_visible_ring"]["outline_none_bare_absent"] = False
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("KEYBOARD_NAVIGATION_DISABLED", codes)
        self.assertIn("FOCUS_VISIBLE_RING_DISABLED", codes)

    def test_modal_focus_trap_missing_fails(self):
        record = valid_record()
        record["keyboard_and_focus_mastery"]["dialog_focus_management"]["trapped"] = False
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("MODAL_FOCUS_TRAP_MISSING", codes)

    def test_roving_tabindex_or_aria_live_missing_fails(self):
        record = valid_record()
        record["keyboard_and_focus_mastery"]["roving_tabindex_implemented"] = False
        record["keyboard_and_focus_mastery"]["aria_live_regions_declared"] = False
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("ROVING_TABINDEX_MISSING", codes)
        self.assertIn("ARIA_LIVE_REGIONS_MISSING", codes)

    def test_layout_thrashing_not_eliminated_or_task_exceeds_budget_fails(self):
        record = valid_record()
        record["frame_budget_and_hardware"]["layout_thrashing_eliminated"] = False
        record["frame_budget_and_hardware"]["main_thread_max_task_ms"] = 35.0
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("LAYOUT_THRASHING_NOT_ELIMINATED", codes)
        self.assertIn("MAIN_THREAD_TASK_EXCEEDS_BUDGET", codes)

    def test_touch_scroll_hijacking_present_fails(self):
        record = valid_record()
        record["frame_budget_and_hardware"]["touch_scroll_hijacking_absent"] = False
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("TOUCH_SCROLL_HIJACKING_PRESENT", codes)

    def test_hit_target_below_44px_fails(self):
        record = valid_record()
        record["frame_budget_and_hardware"]["min_hit_target_px"] = 32
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("HIT_TARGET_BELOW_44PX", codes)

    def test_120hz_with_16ms_budget_fails(self):
        record = valid_record()
        record["surface"]["target_refresh_rate_hz"] = 120
        record["surface"]["frame_budget_ms"] = 16.67
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "incomplete")
        codes = [f["code"] for f in result["findings"]]
        self.assertIn("FRAME_BUDGET_EXCEEDS_120HZ", codes)

    def test_pause_and_refuse_verdicts(self):
        record = valid_record()
        record["verdict"]["action"] = "pause"
        record["verdict"]["rationale"] = (
            "Pausing UI rollout until physics spring convergence is calibrated at 120Hz."
        )
        record.pop("exhaustive_state_matrix", None)
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "pause")

        record["verdict"]["action"] = "refuse"
        record["verdict"]["rationale"] = (
            "Refusing to deploy interface with un-interruptible animation lock-in and layout shift."
        )
        result = apple_craft_guard.audit(record)
        self.assertEqual(result["record_status"], "complete")
        self.assertEqual(result["verdict_action"], "refuse")

    def test_source_scanner_accepts_clean_example(self):
        source = TS_EXAMPLE.read_text(encoding="utf-8")
        findings = apple_craft_guard.scan_source_hazards(source)
        self.assertEqual(findings, [])

    def test_source_scanner_flags_transition_all(self):
        bad_source = "const buttonStyle = { transition: 'all 300ms ease' };"
        findings = apple_craft_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_TRANSITION_ALL_FORBIDDEN", codes)

    def test_source_scanner_flags_layout_thrashing(self):
        bad_source = """
        function updatePosition(el) {
          el.style.top = '50px';
          const height = el.getBoundingClientRect().height;
          return height;
        }
        """
        findings = apple_craft_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_FORCED_SYNCHRONOUS_LAYOUT_THRASH", codes)

    def test_source_scanner_flags_boolean_soup(self):
        bad_source = """
        const [isLoading, setIsLoading] = useState(false);
        const [isError, setIsError] = useState(false);
        const [isSuccess, setIsSuccess] = useState(false);
        const [isEmpty, setIsEmpty] = useState(false);
        """
        findings = apple_craft_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_BOOLEAN_SOUP_STATE", codes)

    def test_source_scanner_flags_sync_storage_json(self):
        bad_source = "localStorage.setItem('cache', JSON.stringify(largePayload));"
        findings = apple_craft_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_MAIN_THREAD_SYNC_STORAGE_JSON", codes)

    def test_source_scanner_flags_bare_outline_suppression(self):
        bad_source = "button:focus { outline: none; }"
        findings = apple_craft_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_BARE_OUTLINE_SUPPRESSION", codes)

    def test_source_scanner_flags_non_compositor_transition(self):
        bad_source = ".drawer { transition: height 300ms ease-out; }"
        findings = apple_craft_guard.scan_source_hazards(bad_source)
        codes = [f["code"] for f in findings]
        self.assertIn("SOURCE_NON_COMPOSITOR_ANIMATION", codes)

    def test_cli_invocation_text_and_json(self):
        cmd_text = [sys.executable, str(SCRIPT), "audit", str(EXAMPLE), "--source", str(TS_EXAMPLE)]
        proc_text = subprocess.run(cmd_text, capture_output=True, text=True)
        self.assertEqual(proc_text.returncode, 0)
        self.assertIn("complete", proc_text.stdout)

        cmd_json = [
            sys.executable,
            str(SCRIPT),
            "audit",
            str(EXAMPLE),
            "--source",
            str(TS_EXAMPLE),
            "--json",
        ]
        proc_json = subprocess.run(cmd_json, capture_output=True, text=True)
        self.assertEqual(proc_json.returncode, 0)
        payload = json.loads(proc_json.stdout)
        self.assertEqual(payload["record_status"], "complete")
        self.assertEqual(payload["verdict_action"], "proceed")

        with tempfile.NamedTemporaryFile("w+", suffix=".json") as tmp:
            bad = valid_record()
            bad["zero_layout_shift"]["cumulative_layout_shift_target"] = 0.5
            json.dump(bad, tmp)
            tmp.flush()

            proc_bad = subprocess.run(
                [sys.executable, str(SCRIPT), "audit", tmp.name],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc_bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
