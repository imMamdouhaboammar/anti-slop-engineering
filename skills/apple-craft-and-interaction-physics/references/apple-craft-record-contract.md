# Apple Craft & Interaction Physics Record Contract

When designing, refactoring, or auditing high-craft user interfaces, client state machines, animation pipelines, or interactive components, record the evaluation as a persistent JSON record (`apple-craft-record.json`) to enforce compliance before shipping.

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "AppleCraftRecord",
  "type": "object",
  "required": [
    "schema_version",
    "surface",
    "exhaustive_state_matrix",
    "zero_layout_shift",
    "interruptible_physics",
    "keyboard_and_focus_mastery",
    "frame_budget_and_hardware",
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
        "frame_budget_ms": { "type": "number", "enum": [8.3, 8.33, 16.6, 16.67] }
      }
    },
    "exhaustive_state_matrix": {
      "type": "object",
      "required": [
        "pattern",
        "boolean_soup_absent",
        "exhaustiveness_checked",
        "modeled_states",
        "draft_preservation_mechanism"
      ],
      "properties": {
        "pattern": { "type": "string", "const": "discriminated_union" },
        "boolean_soup_absent": { "type": "boolean", "const": true },
        "exhaustiveness_checked": { "type": "boolean", "const": true },
        "modeled_states": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 8
        },
        "draft_preservation_mechanism": { "type": "string", "minLength": 15 }
      }
    },
    "zero_layout_shift": {
      "type": "object",
      "required": [
        "cumulative_layout_shift_target",
        "geometry_reservation_mechanisms",
        "media_aspect_ratios_enforced"
      ],
      "properties": {
        "cumulative_layout_shift_target": { "type": "number", "const": 0.0 },
        "geometry_reservation_mechanisms": {
          "type": "array",
          "items": { "type": "string" },
          "minItems": 2
        },
        "media_aspect_ratios_enforced": { "type": "boolean", "const": true }
      }
    },
    "interruptible_physics": {
      "type": "object",
      "required": [
        "immediate_interruption_supported",
        "velocity_inheritance_enforced",
        "spring_physics_parameters",
        "raf_epsilon_termination",
        "animated_properties",
        "transition_all_forbidden",
        "reduced_motion_supported"
      ],
      "properties": {
        "immediate_interruption_supported": { "type": "boolean", "const": true },
        "velocity_inheritance_enforced": { "type": "boolean", "const": true },
        "spring_physics_parameters": {
          "type": "object",
          "required": ["stiffness", "damping", "mass"],
          "properties": {
            "stiffness": { "type": "number", "minimum": 1 },
            "damping": { "type": "number", "minimum": 1 },
            "mass": { "type": "number", "minimum": 0.1 }
          }
        },
        "raf_epsilon_termination": { "type": "number", "maximum": 0.001 },
        "animated_properties": {
          "type": "array",
          "items": { "type": "string", "enum": ["transform", "opacity"] }
        },
        "transition_all_forbidden": { "type": "boolean", "const": true },
        "reduced_motion_supported": { "type": "boolean", "const": true }
      }
    },
    "keyboard_and_focus_mastery": {
      "type": "object",
      "required": [
        "full_keyboard_operable",
        "focus_visible_ring",
        "dialog_focus_management",
        "roving_tabindex_implemented",
        "aria_live_regions_declared"
      ],
      "properties": {
        "full_keyboard_operable": { "type": "boolean", "const": true },
        "focus_visible_ring": {
          "type": "object",
          "required": ["contrast_ratio", "stroke_px", "offset_px", "outline_none_bare_absent"],
          "properties": {
            "contrast_ratio": { "type": "number", "minimum": 3.0 },
            "stroke_px": { "type": "integer", "minimum": 2 },
            "offset_px": { "type": "integer", "minimum": 2 },
            "outline_none_bare_absent": { "type": "boolean", "const": true }
          }
        },
        "dialog_focus_management": {
          "type": "object",
          "required": ["trapped", "restored_on_close", "escape_dismissable"],
          "properties": {
            "trapped": { "type": "boolean", "const": true },
            "restored_on_close": { "type": "boolean", "const": true },
            "escape_dismissable": { "type": "boolean", "const": true }
          }
        },
        "roving_tabindex_implemented": { "type": "boolean", "const": true },
        "aria_live_regions_declared": { "type": "boolean", "const": true }
      }
    },
    "frame_budget_and_hardware": {
      "type": "object",
      "required": [
        "layout_thrashing_eliminated",
        "dom_read_write_separation",
        "main_thread_max_task_ms",
        "heavy_work_offload_strategy",
        "touch_scroll_hijacking_absent",
        "min_hit_target_px"
      ],
      "properties": {
        "layout_thrashing_eliminated": { "type": "boolean", "const": true },
        "dom_read_write_separation": { "type": "string", "minLength": 15 },
        "main_thread_max_task_ms": { "type": "number", "maximum": 16.0 },
        "heavy_work_offload_strategy": {
          "type": "string",
          "enum": ["web_worker", "scheduler_yield_slices", "indexeddb_async", "none_required_lightweight"]
        },
        "touch_scroll_hijacking_absent": { "type": "boolean", "const": true },
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
          "items": { "type": "string" },
          "minItems": 1
        }
      }
    }
  }
}
```

## Mandatory UI States in `modeled_states`
The `exhaustive_state_matrix.modeled_states` array MUST contain all 8 canonical operational states:
1. `loading_skeleton`
2. `empty`
3. `partial_error`
4. `offline`
5. `optimistic_rollback`
6. `loaded_fresh`
7. `revalidating_stale`
8. `terminal_error`

## Accepted Geometry Reservation Mechanisms
- `pixel_matched_skeleton`
- `explicit_aspect_ratio`
- `intrinsic_width_height_attrs`
- `reserved_error_track`
- `scrollbar_gutter_stable`
- `font_metric_overrides`

## CLI Verification
Validate any record and its target source code using:
```bash
npx anti-slop-engineering apple-craft audit <record.json> --source <component.ts> --json
```
