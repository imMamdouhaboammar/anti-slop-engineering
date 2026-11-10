# Playbook: Client Runtime 120Hz/60Hz Frame Budget & Compositor Physics

## 1. The 120Hz ProMotion & 60Hz Physics

Every frame rendered on a client device is governed by a non-negotiable temporal budget:
- **120Hz Displays:** $1000\text{ms} / 120 = \mathbf{8.33\text{ms}}$ per frame.
- **60Hz Displays:** $1000\text{ms} / 60 = \mathbf{16.67\text{ms}}$ per frame.

Within this window, the browser engine must execute:
1. **JavaScript Task:** Event listeners, state reducers, requestAnimationFrame callbacks. Budget: **$< 4.0\text{ms}$**.
2. **Style Calculation:** CSS selector matching and computed style updates.
3. **Layout / Reflow:** Geometric bounding box calculation.
4. **Paint / Rasterization:** Converting vector shapes into pixel bitmaps on GPU layers.
5. **Compositing:** Blending GPU layers onto the screen.

If any stage exceeds the budget, the frame deadline is missed, resulting in a dropped frame and visual stutter.

---

## 2. FastDOM Read-Write Separation (Eliminating Layout Thrashing)

Layout Thrashing occurs when JavaScript writes to the DOM and immediately queries geometric properties:

```
[ JavaScript Thread ]
  ├── WRITE: el.style.height = "100px"  --> Invalidates layout tree
  ├── READ:  el.offsetHeight             --> FORCES immediate synchronous reflow (STALL!)
  ├── WRITE: el2.style.height = "150px" --> Invalidates layout tree again
  └── READ:  el2.offsetHeight            --> FORCES second synchronous reflow (STALL!)
```

### The Solution: Two-Phase Execution
- **Phase 1 (Read Phase):** Read all required dimensions from DOM nodes (`getBoundingClientRect()`, `offsetWidth`, `scrollTop`).
- **Phase 2 (Write Phase):** Batch all style mutations into a single `requestAnimationFrame` callback.

---

## 3. Compositor-Only Transitions

Transitions and animations must execute directly on the GPU compositor thread without triggering document reflow or paint:

- **Strictly Allowed:** `transform` (`translate3d`, `scale`, `rotate`), `opacity`.
- **Strictly Prohibited:** `transition: all`, `width`, `height`, `top`, `left`, `right`, `bottom`, `margin`, `padding`.

### The FLIP Technique for Layout Animations
When an element changes its position in the DOM hierarchy:
1. **First:** Record starting layout geometry (`firstRect = el.getBoundingClientRect()`).
2. **Last:** Apply state change to final position and record final layout geometry (`lastRect = el.getBoundingClientRect()`).
3. **Invert:** Apply an immediate CSS `transform: translate3d(dx, dy, 0)` so the element appears at its original location without reflow.
4. **Play:** Animate `transform` to `translate3d(0, 0, 0)` with a cubic-bezier easing curve on the GPU compositor.

---

## 4. Main-Thread Offload & Micro-Task Time Slicing

Never run long-running calculations on the main thread:
1. Offload heavy computational tasks (NDJSON parsing, spatial indexes, sorting > 1,000 items) to a Web Worker.
2. Use Transferable Objects (`postMessage({ buffer }, [buffer])`) for zero-copy data handoff.
3. Chunk iterations across frames using `scheduler.yield()` so UI input handlers remain responsive (< 50ms Long Task limit).
