# Apple Craft & Interaction Physics Playbooks

This directory contains executable design engineering playbooks for building 120Hz ProMotion client interfaces that satisfy the four core physical pillars of Apple Craft and Design Engineering.

## Playbook Suite

| Playbook | Focus & Scope | Primary Artifact |
| --- | --- | --- |
| **[Interaction Physics Playbook](interaction-physics-playbook.md)** | Mass-spring-damper physics, instantaneous gesture interruption, continuous velocity inheritance, and epsilon termination | Spring physics loops & gesture handlers |
| **[UI State Matrix Playbook](ui-state-matrix-playbook.md)** | Exhaustive 8-state Discriminated Union state machines, compile-time exhaustiveness, and optimistic rollback draft preservation | Typed state machines & view renderers |
| **[Zero-CLS Geometry Playbook](zero-cls-geometry-playbook.md)** | Pre-allocating layout tracks, aspect-ratio locks, pixel-matched skeletons, and stable gutters | Zero-CLS CSS layouts & skeleton components |
| **[Keyboard & Focus Mastery Playbook](keyboard-focus-mastery-playbook.md)** | Accessible `:focus-visible` rings with offset, dialog focus trapping & restoration, roving tabindex, and ARIA live regions | Keyboard handlers & accessible modal dialogs |

## CLI Guard Verification

Validate any architecture assessment record and frontend implementation using:
```bash
npx anti-slop-engineering apple-craft audit <record.json> --source <component.ts> --json
# or: python3 scripts/apple_craft_guard.py audit <record.json> --source <component.ts> --json
```
