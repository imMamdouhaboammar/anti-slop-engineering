# Apple Craft & Frame Budget Record Contract

When architecting, refactoring, or auditing an interactive UI view, animation pipeline, or optimistic state machine, save the assessment as a persistent JSON record (`apple-craft-frame-budget-record.json`) to verify compliance with the 16.6ms/8.3ms frame budget, sub-50ms Optimistic UI with rollback snapshots, Zero CLS geometry locks, and explicit Discriminated Union State Machines.

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AppleCraftFrameBudgetRecord",
  "type": "object",
  "required": [
    "schema_version",
    "surface",
    "frame_budget_physics",
    "optimistic_ui_and_cls",
    "state_machine_contract",
    "hardware_and_a11y_physics",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "surface": {
      "type": "object",
      "required": ["component_or_flow", "target_refresh_rate_hz", "frame_budget_ms"],
      "properties": {
        "component_or_flow": { "type": "string", "minLength": 10 },
        "target_refresh_rate_hz": { "type": "integer", "enum": [60, 120] },
        "frame_budget_ms": { "type": "number", "enum": [16.6, 16.67, 8.3, 8.33] }
      }
    },
    "frame_budget_physics": {
      "type": "object",
      "required": [
        "layout_thrashing_eliminated",
        "dom_read_write_separation",
        "animated_properties",
        "main_thread_max_task_ms",
        "heavy_work_offload_strategy",
        "raf_epsilon_termination"
      ],
      "properties": {
        "layout_thrashing_eliminated": { "type": "boolean", "const": true },
        "dom_read_write_separation": { "type": "string", "minLength": 15 },
        "animated_properties": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string", "enum": ["transform", "opacity"] }
        },
        "main_thread_max_task_ms": { "type": "number", "maximum": 16.0 },
        "heavy_work_offload_strategy": {
          "type": "string",
          "enum": ["web_worker", "scheduler_yield_slices", "indexeddb_async", "none_required_lightweight"]
        },
        "raf_epsilon_termination": { "type": "number", "maximum": 0.001, "exclusiveMinimum": 0 }
      }
    },
    "optimistic_ui_and_cls": {
      "type": "object",
      "required": [
        "optimistic_feedback_budget_ms",
        "rollback_snapshot_captured",
        "rollback_recovery_behavior",
        "preserves_user_draft_on_failure",
        "cumulative_layout_shift_target",
        "geometry_reservation_mechanisms"
      ],
      "properties": {
        "optimistic_feedback_budget_ms": { "type": "number", "maximum": 50.0, "exclusiveMinimum": 0 },
        "rollback_snapshot_captured": { "type": "boolean", "const": true },
        "rollback_recovery_behavior": { "type": "string", "minLength": 15 },
        "preserves_user_draft_on_failure": { "type": "boolean", "const": true },
        "cumulative_layout_shift_target": { "type": "number", "const": 0.0 },
        "geometry_reservation_mechanisms": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "string",
            "enum": [
              "pixel_matched_skeleton",
              "explicit_aspect_ratio",
              "intrinsic_width_height_attrs",
              "font_metric_overrides",
              "fixed_validation_error_track",
              "scrollbar_gutter_stable"
            ]
          }
        }
      }
    },
    "state_machine_contract": {
      "type": "object",
      "required": [
        "pattern",
        "boolean_soup_absent",
        "exhaustiveness_checked",
        "modeled_states"
      ],
      "properties": {
        "pattern": { "type": "string", "const": "discriminated_union" },
        "boolean_soup_absent": { "type": "boolean", "const": true },
        "exhaustiveness_checked": { "type": "boolean", "const": true },
        "modeled_states": {
          "type": "array",
          "minItems": 6,
          "items": {
            "type": "string",
            "enum": [
              "idle",
              "loading_initial",
              "loaded_empty",
              "loaded_fresh",
              "revalidating_stale",
              "optimistic_mutating",
              "partial_failure",
              "offline_queued",
              "terminal_error"
            ]
          }
        }
      }
    },
    "hardware_and_a11y_physics": {
      "type": "object",
      "required": [
        "touch_scroll_hijacking_absent",
        "reduced_motion_respected",
        "modal_dialog_a11y_enforced",
        "min_hit_target_px"
      ],
      "properties": {
        "touch_scroll_hijacking_absent": { "type": "boolean", "const": true },
        "reduced_motion_respected": { "type": "boolean", "const": true },
        "modal_dialog_a11y_enforced": { "type": "boolean", "const": true },
        "min_hit_target_px": { "type": "integer", "minimum": 44 }
      }
    },
    "verdict": {
      "type": "object",
      "required": ["action", "rationale", "revisit_triggers"],
      "properties": {
        "action": { "type": "string", "enum": ["proceed", "pause", "refuse"] },
        "rationale": { "type": "string", "minLength": 20 },
        "revisit_triggers": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

## Audit Tooling

Validate UI craft and frame-budget records or scan frontend source files for layout thrashing, non-compositor animations (`transition: all`, `top`/`left`/`width`/`height` animations), Boolean Soup (`isLoading` + `isError`), or unguarded `requestAnimationFrame` loops using:

```bash
python3 scripts/frame_budget_guard.py audit <record.json> [--source <component.tsx>] --json
# or via CLI:
npx anti-slop-engineering frame-budget audit <record.json> [--source <component.tsx>] --json
```

Exit codes:
- `0`: Structurally compliant Apple Craft & Frame Budget record (16.6ms/8.3ms compositor physics, `< 50ms` optimistic UI with rollback snapshot, `CLS = 0.0`, discriminated union state machine covering `loaded_empty`, `revalidating_stale`, `offline_queued`, and `partial_failure`, and zero runtime physics hazards in `--source`).
- `1`: JSON parsing or file access failure.
- `2`: Validation findings detected in the record or `--source` file.
