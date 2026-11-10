#!/usr/bin/env python3
"""Check Apple Craft & Interaction Physics records and frontend source files.

Enforces Apple HIG craft, 120Hz ProMotion interaction physics, Zero CLS (0.000)
geometry pre-reservation, Exhaustive UI State Matrices (8 states), and Keyboard
& Focus Mastery across web, desktop, and mobile interfaces.
"""

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
    "reserved_error_track",
    "scrollbar_gutter_stable",
    "font_metric_overrides",
    "fixed_validation_error_track",
}
REQUIRED_UI_STATES = {
    "loading_skeleton",
    "empty",
    "partial_error",
    "offline",
    "optimistic_rollback",
    "loaded_fresh",
    "revalidating_stale",
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
    require(
        filled(surface.get("component_or_flow"), 10),
        "MISSING_COMPONENT_OR_FLOW",
        "surface.component_or_flow must be at least 10 characters",
    )
    hz = surface.get("target_refresh_rate_hz")
    budget = surface.get("frame_budget_ms")
    require(
        isinstance(hz, int) and hz in VALID_REFRESH_RATES,
        "INVALID_REFRESH_RATE_HZ",
        "surface.target_refresh_rate_hz must be 60 or 120",
    )
    require(
        isinstance(budget, (int, float)) and float(budget) in VALID_FRAME_BUDGETS,
        "INVALID_FRAME_BUDGET_MS",
        "surface.frame_budget_ms must be 16.6/16.67 (60Hz) or 8.3/8.33 (120Hz)",
    )
    if hz == 120 and isinstance(budget, (int, float)):
        require(
            float(budget) <= 8.34,
            "FRAME_BUDGET_EXCEEDS_120HZ",
            "120Hz surface must enforce an 8.3ms / 8.33ms frame budget",
        )


def check_exhaustive_state_matrix(record, require):
    sm = record.get("exhaustive_state_matrix")
    require(
        isinstance(sm, dict),
        "INVALID_EXHAUSTIVE_STATE_MATRIX",
        "exhaustive_state_matrix must be a dictionary",
    )
    if not isinstance(sm, dict):
        return

    require(
        sm.get("pattern") == "discriminated_union",
        "NON_DISCRIMINATED_UNION_STATE",
        "exhaustive_state_matrix.pattern must be 'discriminated_union'",
    )
    require(
        sm.get("boolean_soup_absent") is True,
        "BOOLEAN_SOUP_PRESENT",
        "exhaustive_state_matrix.boolean_soup_absent must be true",
    )
    require(
        sm.get("exhaustiveness_checked") is True,
        "MISSING_EXHAUSTIVENESS_CHECK",
        "exhaustive_state_matrix.exhaustiveness_checked must be true",
    )

    states = sm.get("modeled_states")
    state_set = set(states) if isinstance(states, list) else set()
    missing = sorted(REQUIRED_UI_STATES - state_set)
    require(
        not missing,
        "MISSING_REQUIRED_UI_STATES",
        "exhaustive_state_matrix.modeled_states is missing required operational states: %s"
        % ", ".join(missing),
    )
    require(
        filled(sm.get("draft_preservation_mechanism"), 15),
        "MISSING_DRAFT_PRESERVATION_MECHANISM",
        "exhaustive_state_matrix.draft_preservation_mechanism must explain user draft recovery on rollback",
    )


def check_zero_layout_shift(record, require):
    cls_obj = record.get("zero_layout_shift")
    require(
        isinstance(cls_obj, dict),
        "INVALID_ZERO_LAYOUT_SHIFT",
        "zero_layout_shift must be a dictionary",
    )
    if not isinstance(cls_obj, dict):
        return

    cls_target = cls_obj.get("cumulative_layout_shift_target")
    require(
        isinstance(cls_target, (int, float)) and float(cls_target) == 0.0,
        "NON_ZERO_CLS_TARGET",
        "zero_layout_shift.cumulative_layout_shift_target must be strictly 0.0",
    )

    locks = cls_obj.get("geometry_reservation_mechanisms")
    require(
        isinstance(locks, list)
        and len(locks) >= 2
        and all(isinstance(k, str) and k in VALID_GEOMETRY_LOCKS for k in locks),
        "INSUFFICIENT_GEOMETRY_LOCKS",
        "zero_layout_shift.geometry_reservation_mechanisms must list at least 2 valid Zero-CLS locks",
    )

    require(
        cls_obj.get("media_aspect_ratios_enforced") is True,
        "MEDIA_ASPECT_RATIOS_NOT_ENFORCED",
        "zero_layout_shift.media_aspect_ratios_enforced must be true",
    )


def check_interruptible_physics(record, require):
    physics = record.get("interruptible_physics")
    require(
        isinstance(physics, dict),
        "INVALID_INTERRUPTIBLE_PHYSICS",
        "interruptible_physics must be a dictionary",
    )
    if not isinstance(physics, dict):
        return

    require(
        physics.get("immediate_interruption_supported") is True,
        "NON_INTERRUPTIBLE_PHYSICS",
        "interruptible_physics.immediate_interruption_supported must be true",
    )
    require(
        physics.get("velocity_inheritance_enforced") is True,
        "MISSING_VELOCITY_INHERITANCE",
        "interruptible_physics.velocity_inheritance_enforced must be true",
    )

    spring = physics.get("spring_physics_parameters")
    require(
        isinstance(spring, dict)
        and isinstance(spring.get("stiffness"), (int, float))
        and spring["stiffness"] > 0
        and isinstance(spring.get("damping"), (int, float))
        and spring["damping"] > 0
        and isinstance(spring.get("mass"), (int, float))
        and spring["mass"] > 0,
        "INVALID_SPRING_PARAMETERS",
        "interruptible_physics.spring_physics_parameters must define positive stiffness, damping, and mass",
    )

    eps = physics.get("raf_epsilon_termination")
    require(
        isinstance(eps, (int, float)) and 0 < float(eps) <= 0.001,
        "INVALID_RAF_EPSILON",
        "interruptible_physics.raf_epsilon_termination must be between 0 and 0.001 (e.g. 0.0001)",
    )

    props = physics.get("animated_properties")
    require(
        isinstance(props, list)
        and bool(props)
        and all(isinstance(p, str) and p in VALID_COMPOSITOR_PROPS for p in props),
        "NON_COMPOSITOR_ANIMATION_PROPERTIES",
        "interruptible_physics.animated_properties must contain only GPU compositor properties ('transform', 'opacity')",
    )

    require(
        physics.get("transition_all_forbidden") is True,
        "TRANSITION_ALL_PERMITTED",
        "interruptible_physics.transition_all_forbidden must be true",
    )

    require(
        physics.get("reduced_motion_supported") is True,
        "REDUCED_MOTION_IGNORED",
        "interruptible_physics.reduced_motion_supported must be true",
    )


def check_keyboard_and_focus_mastery(record, require):
    kb = record.get("keyboard_and_focus_mastery")
    require(
        isinstance(kb, dict),
        "INVALID_KEYBOARD_AND_FOCUS_MASTERY",
        "keyboard_and_focus_mastery must be a dictionary",
    )
    if not isinstance(kb, dict):
        return

    require(
        kb.get("full_keyboard_operable") is True,
        "KEYBOARD_NAVIGATION_DISABLED",
        "keyboard_and_focus_mastery.full_keyboard_operable must be true",
    )

    ring = kb.get("focus_visible_ring")
    require(
        isinstance(ring, dict)
        and isinstance(ring.get("contrast_ratio"), (int, float))
        and float(ring["contrast_ratio"]) >= 3.0
        and isinstance(ring.get("stroke_px"), int)
        and ring["stroke_px"] >= 2
        and isinstance(ring.get("offset_px"), int)
        and ring["offset_px"] >= 2
        and ring.get("outline_none_bare_absent") is True,
        "FOCUS_VISIBLE_RING_DISABLED",
        "keyboard_and_focus_mastery.focus_visible_ring must have contrast >= 3.0, stroke >= 2px, offset >= 2px, and no bare outline:none",
    )

    dialog = kb.get("dialog_focus_management")
    require(
        isinstance(dialog, dict)
        and dialog.get("trapped") is True
        and dialog.get("restored_on_close") is True
        and dialog.get("escape_dismissable") is True,
        "MODAL_FOCUS_TRAP_MISSING",
        "keyboard_and_focus_mastery.dialog_focus_management must be trapped, restored on close, and escape dismissable",
    )

    require(
        kb.get("roving_tabindex_implemented") is True,
        "ROVING_TABINDEX_MISSING",
        "keyboard_and_focus_mastery.roving_tabindex_implemented must be true for composite controls",
    )

    require(
        kb.get("aria_live_regions_declared") is True,
        "ARIA_LIVE_REGIONS_MISSING",
        "keyboard_and_focus_mastery.aria_live_regions_declared must be true",
    )


def check_frame_budget_and_hardware(record, require):
    hw = record.get("frame_budget_and_hardware")
    require(
        isinstance(hw, dict),
        "INVALID_FRAME_BUDGET_AND_HARDWARE",
        "frame_budget_and_hardware must be a dictionary",
    )
    if not isinstance(hw, dict):
        return

    require(
        hw.get("layout_thrashing_eliminated") is True,
        "LAYOUT_THRASHING_NOT_ELIMINATED",
        "frame_budget_and_hardware.layout_thrashing_eliminated must be true",
    )
    require(
        filled(hw.get("dom_read_write_separation"), 15),
        "MISSING_DOM_READ_WRITE_SEPARATION",
        "frame_budget_and_hardware.dom_read_write_separation must explain how DOM reads precede writes",
    )

    max_task = hw.get("main_thread_max_task_ms")
    require(
        isinstance(max_task, (int, float)) and 0 < float(max_task) <= 16.0,
        "MAIN_THREAD_TASK_EXCEEDS_BUDGET",
        "frame_budget_and_hardware.main_thread_max_task_ms must be > 0 and <= 16.0ms",
    )

    require(
        choice(hw.get("heavy_work_offload_strategy"), VALID_OFFLOAD_STRATEGIES),
        "INVALID_OFFLOAD_STRATEGY",
        "frame_budget_and_hardware.heavy_work_offload_strategy must be one of: %s"
        % ", ".join(sorted(VALID_OFFLOAD_STRATEGIES)),
    )

    require(
        hw.get("touch_scroll_hijacking_absent") is True,
        "TOUCH_SCROLL_HIJACKING_PRESENT",
        "frame_budget_and_hardware.touch_scroll_hijacking_absent must be true",
    )

    hit_px = hw.get("min_hit_target_px")
    require(
        isinstance(hit_px, int) and hit_px >= 44,
        "HIT_TARGET_BELOW_44PX",
        "frame_budget_and_hardware.min_hit_target_px must be >= 44",
    )


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(
        choice(action, {"proceed", "pause", "refuse"}),
        "INVALID_ACTION",
        "Verdict action must be proceed, pause, or refuse",
    )
    require(
        filled(verdict.get("rationale"), 20),
        "MISSING_RATIONALE",
        "Verdict rationale must be at least 20 characters",
    )
    triggers = verdict.get("revisit_triggers")
    require(
        isinstance(triggers, list) and bool(triggers) and all(filled(t) for t in triggers),
        "MISSING_REVISIT_TRIGGERS",
        "Verdict must declare at least one revisit trigger",
    )
    return action


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    # 1. Check for transition: all
    has_transition_all = bool(
        re.search(r"transition\s*:\s*['\"]?\s*all\b|transition-all\b", source_text)
    )
    require(
        not has_transition_all,
        "SOURCE_TRANSITION_ALL_FORBIDDEN",
        "Detected 'transition: all' or 'transition-all'; explicitly animate only compositor 'transform' and 'opacity'",
    )

    # 2. Check for layout thrashing (write followed immediately by read)
    has_layout_thrash = bool(
        re.search(
            r"\.style\.(?:top|left|width|height)\s*=[^;]+;[\s\S]{0,160}?\.(?:getBoundingClientRect\s*\(|offsetWidth\b|offsetHeight\b|clientHeight\b)",
            source_text,
        )
    )
    require(
        not has_layout_thrash,
        "SOURCE_FORCED_SYNCHRONOUS_LAYOUT_THRASH",
        "Detected DOM style geometry write followed immediately by synchronous layout read (Layout Thrashing)",
    )

    # 3. Check for Boolean Soup state management
    boolean_flags = re.findall(
        r"\b(isLoading|isError|isSuccess|isEmpty|isSubmitted|isFetching)\b", source_text
    )
    distinct_flags = set(boolean_flags)
    require(
        len(distinct_flags) < 3,
        "SOURCE_BOOLEAN_SOUP_STATE",
        "Detected Boolean Soup (%s); replace independent boolean flags with a Discriminated Union State Machine"
        % ", ".join(sorted(distinct_flags)),
    )

    # 4. Check for synchronous main thread storage with JSON
    has_sync_storage_json = bool(
        re.search(
            r"\b(?:localStorage|sessionStorage)\.setItem\s*\([^,]+,\s*JSON\.stringify\s*\(",
            source_text,
        )
    )
    require(
        not has_sync_storage_json,
        "SOURCE_MAIN_THREAD_SYNC_STORAGE_JSON",
        "Detected synchronous localStorage/sessionStorage.setItem(JSON.stringify(...)) blocking the Main Thread",
    )

    # 5. Check for bare outline suppression without :focus-visible
    has_bare_outline = bool(
        re.search(r"\boutline\s*:\s*(?:none|0)\b", source_text)
    ) and not bool(re.search(r":focus-visible", source_text))
    require(
        not has_bare_outline,
        "SOURCE_BARE_OUTLINE_SUPPRESSION",
        "Detected 'outline: none' or 'outline: 0' without an accessible :focus-visible replacement",
    )

    # 6. Check for non-compositor transition declarations (height, width, top, left, margin)
    has_non_compositor_transition = bool(
        re.search(
            r"transition\s*:\s*[^;]*\b(?:height|width|top|left|right|bottom|margin|padding)\b",
            source_text,
        )
    )
    require(
        not has_non_compositor_transition,
        "SOURCE_NON_COMPOSITOR_ANIMATION",
        "Detected non-compositor property in CSS transition; animate strictly 'transform' and 'opacity'",
    )

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(
        findings, ok, code, message, severity
    )

    check_surface(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_exhaustive_state_matrix(record, require)
        check_zero_layout_shift(record, require)
        check_interruptible_physics(record, require)
        check_keyboard_and_focus_mastery(record, require)
        check_frame_budget_and_hardware(record, require)

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
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="Optional UI component file to scan for layout thrashing, transition:all, Boolean Soup, bare outline:none, or sync storage stalls",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid Apple Craft & Interaction Physics record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(
            "Apple Craft & Interaction Physics record: %s (%s)"
            % (result["record_status"], result["verdict_action"])
        )
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print(
            "Structural audit only: 120Hz frame timing, CLS=0.000, interruptible physics, and keyboard accessibility must be verified in runtime tests."
        )

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
