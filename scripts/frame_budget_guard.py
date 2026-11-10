#!/usr/bin/env python3
"""Check Apple Craft & Frame Budget records and frontend source files for 60/120Hz frame-budget physics, sub-50ms Optimistic UI with rollback snapshots, Zero CLS geometry reservation, Discriminated Union State Machines, and Apple HIG hardware/dialog ergonomics."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_REFRESH_RATES = {60, 120}
VALID_FRAME_BUDGETS = {16.6, 16.67, 8.3, 8.33}
VALID_COMPOSITOR_PROPS = {"transform", "opacity"}
VALID_OFFLOAD_STRATEGIES = {
    "web_worker",
    "scheduler_yield_slices",
    "indexeddb_async",
    "none_required_lightweight",
}
VALID_GEOMETRY_LOCKS = {
    "pixel_matched_skeleton",
    "explicit_aspect_ratio",
    "intrinsic_width_height_attrs",
    "font_metric_overrides",
    "fixed_validation_error_track",
    "scrollbar_gutter_stable",
}
REQUIRED_CORE_STATES = {
    "loading_initial",
    "loaded_empty",
    "loaded_fresh",
    "revalidating_stale",
    "optimistic_mutating",
    "partial_failure",
    "offline_queued",
    "terminal_error",
}


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_surface(record, require):
    surface = record.get("surface")
    require(isinstance(surface, dict), "INVALID_SURFACE", "surface must be a dictionary")
    if not isinstance(surface, dict):
        return
    require(filled(surface.get("component_or_flow"), 10),
            "MISSING_COMPONENT_OR_FLOW",
            "surface.component_or_flow must be at least 10 characters")
    hz = surface.get("target_refresh_rate_hz")
    budget = surface.get("frame_budget_ms")
    require(isinstance(hz, int) and hz in VALID_REFRESH_RATES,
            "INVALID_REFRESH_RATE_HZ",
            "surface.target_refresh_rate_hz must be 60 or 120")
    require(isinstance(budget, (int, float)) and float(budget) in VALID_FRAME_BUDGETS,
            "INVALID_FRAME_BUDGET_MS",
            "surface.frame_budget_ms must be 16.6/16.67 (60Hz) or 8.3/8.33 (120Hz)")
    if hz == 120 and isinstance(budget, (int, float)):
        require(float(budget) <= 8.34,
                "FRAME_BUDGET_EXCEEDS_120HZ",
                "120Hz surface must enforce an 8.3ms / 8.33ms frame budget")


def check_frame_budget_physics(record, require):
    physics = record.get("frame_budget_physics")
    require(isinstance(physics, dict), "INVALID_FRAME_BUDGET_PHYSICS",
            "frame_budget_physics must be a dictionary")
    if not isinstance(physics, dict):
        return

    require(physics.get("layout_thrashing_eliminated") is True,
            "LAYOUT_THRASHING_NOT_ELIMINATED",
            "frame_budget_physics.layout_thrashing_eliminated must be true")
    require(filled(physics.get("dom_read_write_separation"), 15),
            "MISSING_DOM_READ_WRITE_SEPARATION",
            "frame_budget_physics.dom_read_write_separation must explain how DOM reads precede writes")

    props = physics.get("animated_properties")
    require(isinstance(props, list) and bool(props)
            and all(isinstance(p, str) and p in VALID_COMPOSITOR_PROPS for p in props),
            "NON_COMPOSITOR_ANIMATION_PROPERTIES",
            "frame_budget_physics.animated_properties must contain only GPU compositor properties ('transform', 'opacity')")

    max_task = physics.get("main_thread_max_task_ms")
    require(isinstance(max_task, (int, float)) and 0 < float(max_task) <= 16.0,
            "MAIN_THREAD_TASK_EXCEEDS_BUDGET",
            "frame_budget_physics.main_thread_max_task_ms must be > 0 and <= 16.0ms")

    require(choice(physics.get("heavy_work_offload_strategy"), VALID_OFFLOAD_STRATEGIES),
            "INVALID_OFFLOAD_STRATEGY",
            "frame_budget_physics.heavy_work_offload_strategy must be one of: %s"
            % ", ".join(sorted(VALID_OFFLOAD_STRATEGIES)))

    eps = physics.get("raf_epsilon_termination")
    require(isinstance(eps, (int, float)) and 0 < float(eps) <= 0.001,
            "INVALID_RAF_EPSILON",
            "frame_budget_physics.raf_epsilon_termination must be between 0 and 0.001 (e.g. 0.0001)")


def check_optimistic_ui_and_cls(record, require):
    opt = record.get("optimistic_ui_and_cls")
    require(isinstance(opt, dict), "INVALID_OPTIMISTIC_UI_AND_CLS",
            "optimistic_ui_and_cls must be a dictionary")
    if not isinstance(opt, dict):
        return

    feedback_ms = opt.get("optimistic_feedback_budget_ms")
    require(isinstance(feedback_ms, (int, float)) and 0 < float(feedback_ms) <= 50.0,
            "OPTIMISTIC_FEEDBACK_TOO_SLOW",
            "optimistic_ui_and_cls.optimistic_feedback_budget_ms must be <= 50.0ms")
    require(opt.get("rollback_snapshot_captured") is True,
            "MISSING_ROLLBACK_SNAPSHOT",
            "optimistic_ui_and_cls.rollback_snapshot_captured must be true")
    require(filled(opt.get("rollback_recovery_behavior"), 15),
            "MISSING_ROLLBACK_RECOVERY_BEHAVIOR",
            "optimistic_ui_and_cls.rollback_recovery_behavior must describe graceful server rejection recovery")
    require(opt.get("preserves_user_draft_on_failure") is True,
            "DRAFT_LOST_ON_ROLLBACK",
            "optimistic_ui_and_cls.preserves_user_draft_on_failure must be true")

    cls_target = opt.get("cumulative_layout_shift_target")
    require(isinstance(cls_target, (int, float)) and float(cls_target) == 0.0,
            "NON_ZERO_CLS_TARGET",
            "optimistic_ui_and_cls.cumulative_layout_shift_target must be strictly 0.0")

    locks = opt.get("geometry_reservation_mechanisms")
    require(isinstance(locks, list) and len(locks) >= 2
            and all(isinstance(k, str) and k in VALID_GEOMETRY_LOCKS for k in locks),
            "INSUFFICIENT_GEOMETRY_LOCKS",
            "optimistic_ui_and_cls.geometry_reservation_mechanisms must list at least 2 valid Zero-CLS locks")


def check_state_machine_contract(record, require):
    sm = record.get("state_machine_contract")
    require(isinstance(sm, dict), "INVALID_STATE_MACHINE_CONTRACT",
            "state_machine_contract must be a dictionary")
    if not isinstance(sm, dict):
        return

    require(sm.get("pattern") == "discriminated_union",
            "NON_DISCRIMINATED_UNION_STATE",
            "state_machine_contract.pattern must be 'discriminated_union'")
    require(sm.get("boolean_soup_absent") is True,
            "BOOLEAN_SOUP_PRESENT",
            "state_machine_contract.boolean_soup_absent must be true")
    require(sm.get("exhaustiveness_checked") is True,
            "MISSING_EXHAUSTIVENESS_CHECK",
            "state_machine_contract.exhaustiveness_checked must be true")

    states = sm.get("modeled_states")
    state_set = set(states) if isinstance(states, list) else set()
    missing = sorted(REQUIRED_CORE_STATES - state_set)
    require(not missing,
            "MISSING_REQUIRED_UI_STATES",
            "state_machine_contract.modeled_states is missing required operational states: %s"
            % ", ".join(missing))


def check_hardware_and_a11y_physics(record, require):
    hw = record.get("hardware_and_a11y_physics")
    require(isinstance(hw, dict), "INVALID_HARDWARE_AND_A11Y_PHYSICS",
            "hardware_and_a11y_physics must be a dictionary")
    if not isinstance(hw, dict):
        return

    require(hw.get("touch_scroll_hijacking_absent") is True,
            "TOUCH_SCROLL_HIJACKING_PRESENT",
            "hardware_and_a11y_physics.touch_scroll_hijacking_absent must be true")
    require(hw.get("reduced_motion_respected") is True,
            "REDUCED_MOTION_IGNORED",
            "hardware_and_a11y_physics.reduced_motion_respected must be true")
    require(hw.get("modal_dialog_a11y_enforced") is True,
            "MODAL_A11Y_PHYSICS_MISSING",
            "hardware_and_a11y_physics.modal_dialog_a11y_enforced must be true")
    hit_px = hw.get("min_hit_target_px")
    require(isinstance(hit_px, int) and hit_px >= 44,
            "HIT_TARGET_BELOW_44PX",
            "hardware_and_a11y_physics.min_hit_target_px must be >= 44")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(choice(action, {"proceed", "pause", "refuse"}), "INVALID_ACTION",
            "Verdict action must be proceed, pause, or refuse")
    require(filled(verdict.get("rationale"), 20),
            "MISSING_RATIONALE", "Verdict rationale must be at least 20 characters")
    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and bool(triggers) and all(filled(t) for t in triggers),
            "MISSING_REVISIT_TRIGGERS", "Verdict must declare at least one revisit trigger")
    return action


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    has_transition_all = bool(re.search(r"transition\s*:\s*all\b|transition-all\b", source_text))
    require(not has_transition_all, "SOURCE_TRANSITION_ALL_FORBIDDEN",
            "Detected 'transition: all' or 'transition-all'; explicitly animate only compositor 'transform' and 'opacity'")

    has_layout_thrash = bool(
        re.search(
            r"\.style\.(?:top|left|width|height)\s*=[^;]+;[\s\S]{0,160}?\.(?:getBoundingClientRect\s*\(|offsetWidth\b|offsetHeight\b|clientHeight\b)",
            source_text,
        )
    )
    require(not has_layout_thrash, "SOURCE_FORCED_SYNCHRONOUS_LAYOUT_THRASH",
            "Detected DOM style geometry write followed immediately by synchronous layout read (Layout Thrashing)")

    boolean_flags = re.findall(r"\b(isLoading|isError|isSuccess|isEmpty|isSubmitted|isFetching)\b", source_text)
    distinct_flags = set(boolean_flags)
    require(len(distinct_flags) < 3, "SOURCE_BOOLEAN_SOUP_STATE",
            "Detected Boolean Soup (%s); replace independent boolean flags with a Discriminated Union State Machine"
            % ", ".join(sorted(distinct_flags)))

    has_sync_storage_json = bool(
        re.search(r"\b(?:localStorage|sessionStorage)\.setItem\s*\([^,]+,\s*JSON\.stringify\s*\(", source_text)
    )
    require(not has_sync_storage_json, "SOURCE_MAIN_THREAD_SYNC_STORAGE_JSON",
            "Detected synchronous localStorage/sessionStorage.setItem(JSON.stringify(...)) blocking the Main Thread")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_surface(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_frame_budget_physics(record, require)
        check_optimistic_ui_and_cls(record, require)
        check_state_machine_contract(record, require)
        check_hardware_and_a11y_physics(record, require)

    if source_text is not None:
        findings.extend(scan_source_hazards(source_text))

    return {
        "record_status": "incomplete" if findings else "complete",
        "verdict_action": action,
        "machine_check_only": True,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--source", type=Path, default=None,
                        help="Optional UI component file to scan for layout thrashing, transition:all, Boolean Soup, or sync storage stalls")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid Apple Craft & Frame Budget record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Apple Craft & Frame Budget record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: 120Hz frame timing, CLS=0.000, and optimistic rollback behavior must be verified in runtime tests.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
