# Use Case: Architect Interaction Physics & Client Architecture

## When to Use
Use when architecting a new interactive system, sheet/drawer component, gesture-driven flow, or complex client-side view before writing implementation code.

---

## 5-Step Architecture Design Process

### 1. Define the Surface & Frame Budget
- Identify target refresh rate: 120Hz ProMotion ($8.33\text{ms}$) or 60Hz ($16.67\text{ms}$).
- Allocate maximum JavaScript frame execution budget: $\le 4.0\text{ms}$.
- Identify heavy operations (JSON parsing, large sorting) and select offload strategy (Web Worker, `scheduler.yield()`, IndexedDB).

### 2. Specify the Exhaustive UI State Machine
- Map domain models to Discriminated Union variants.
- Define triggers and state transitions.
- Design the optimistic mutation path, rollback snapshot, and draft preservation buffer.

### 3. Engineer Zero-CLS Geometry Locks
- Pre-calculate all container bounding boxes.
- Specify exact skeleton dimension matching.
- Define media aspect ratios (`aspect-ratio: 16 / 9`, `1 / 1`, etc.).
- Reserve dedicated layout tracks for validation feedback and inline alerts.

### 4. Parameterize Physics & Velocity Continuity
- Select spring parameters ($m, k, c$) matching the interaction intent.
- Ensure all animation properties are GPU compositor-only (`transform`, `opacity`).
- Design pointer/touch tracking for continuous velocity calculation ($v_0 = \Delta x / \Delta t$).
- Set convergence epsilon threshold to $\epsilon = 10^{-4}$.

### 5. Document the Apple Craft Assessment Record
Create a persistent `apple-craft-record.json` documenting the architectural decisions and audit it against `scripts/apple_craft_guard.py`.
