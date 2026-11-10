---
name: motion-runtime-guard
description: Validate runtime motion performance, long tasks, audio autoplay safety, and reduced-motion parity under DPR-2 retina conditions (1440x900@2x = 5.2MP) with 4x CPU throttling, filtering dev-server false failures.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# DPR-2 Runtime Motion & Fillrate Sentry

> Enforce honest runtime performance measurement under retina display conditions (5.2MP) with 4x CPU throttling, long-task bounding, audio autoplay gesture gating, and dev-server false-positive filtering.

## Why This Skill Is Needed & Target State

Static linters and frozen screenshots are blind to time:
1. **Fillrate-Aware Motion Pricing**: Fullscreen post-processing passes (bloom, grain, depth of field, full-frame shaders) cost per pixel, not per geometry. Measuring at DPR 1 quarters the pixel fillrate cost and reports 60 FPS for a scene that stutters on a retina laptop (5.2MP at DPR 2).
2. **Dev-Server False Failures**: Dev servers (Vite HMR, Webpack hot updates, Next.js dev bundles) cost roughly $2\times$ per frame, triggering false failures that cause developers to needlessly butcher performant production scenes.
3. **Long Tasks & Audio Autoplay**: Unbounded JavaScript blocks the main thread, while unmuted autoplaying media violates user experience standards.

The target state is honest SRE measurement: evaluating production builds at DPR 2 with 4x CPU throttling, bounding long tasks ($LT \le 50\text{ms}$), locking audio behind explicit user gestures, and verifying `prefers-reduced-motion` art-direction parity.

## Invariant Rules

1. **Retina Resolution Mandate:** Motion performance benchmarks must be conducted at $\text{DPR} \ge 2.0$ ($1440 \times 900 \times 2 = 5.184\text{MP}$) with 4x CPU throttling.
2. **FPS & Long-Task Bounds:** Minimum acceptable frame rate is $\ge 50$ FPS; maximum individual long task is $\le 50\text{ms}$.
3. **Gesture-Initiated Audio:** Audio and video elements must remain silent/muted on initial load; sound starts exclusively upon an explicit user interaction.
4. **Reduced-Motion Alternative Art Direction:** Reduced-motion branches must provide an intentional alternative composition (calm stills, rich editorial cuts), never blank scenes or broken layouts.
5. **Dev-Server Discrimination:** Flag and isolate dev-server measurements to prevent optimizing already-efficient scenes.

## CLI Usage

```bash
# Validate pre-recorded runtime motion report
bunx anti-slop-engineering motion-runtime --file .anti-slop/motion-report.json

# Check inline performance metrics under DPR 2
bunx anti-slop-engineering motion-runtime --fps 58.5 --dpr 2.0 --longtask 24.0 --json

# Enforce strict zero-warning exit code
bunx anti-slop-engineering motion-runtime --file runtime.json --strict
```
