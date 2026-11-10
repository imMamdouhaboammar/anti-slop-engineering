# Playbook 1: 60/120Hz Frame Budget & Compositor Physics

Apple's Human Interface Guidelines (HIG) treat user interfaces as physical surfaces governed by mass, spring inertia, and direct manipulation. When an interface drops frames during a gesture or stalls the main thread for `120ms` during a button press, the illusion of direct physical manipulation shatters.

---

## 1. The 16.6ms (60Hz) and 8.3ms (120Hz ProMotion) Frame Pipeline

Every display frame must traverse a five-stage pipeline before VSync:

$$\text{JavaScript} \longrightarrow \text{Style Recalc} \longrightarrow \text{Layout (Reflow)} \longrightarrow \text{Paint} \longrightarrow \text{GPU Composite}$$

| Display Rate | Frame Window | Max JS Budget per Frame | Browser Layout/Paint/Composite Headroom |
| --- | --- | --- | --- |
| **60Hz Standard** | `16.67ms` | `<= 6.0ms` | `~10.67ms` |
| **120Hz ProMotion** | `8.33ms` | `<= 4.0ms` | `~4.33ms` |

### The Three Rendering Paths

1. **Full Pipeline (`Layout -> Paint -> Composite` — EXPENSIVE):** Mutating `width`, `height`, `top`, `left`, `margin`, `padding`, `font-size`, or `border-width` dirties the box tree, forcing the browser to recompute geometry for the element, its children, and often the entire document.
2. **Paint Pipeline (`Paint -> Composite` — MODERATE):** Mutating `background-color`, `color`, `box-shadow`, or `border-Radius` skips layout geometry calculation but still rasterizes pixels on the CPU/GPU.
3. **Compositor Fast-Path (`Composite Only` — 120Hz GOLD STANDARD):** Mutating `transform` (`translate3d`, `scale`, `rotate`) and `opacity` bypasses both Layout and Paint completely. The GPU compositor thread transforms existing textures directly at 120Hz even if the main thread is briefly busy.

---

## 2. Eradicating Forced Synchronous Layout (Layout Thrashing)

A **Forced Synchronous Layout** occurs when JavaScript mutates the DOM or styles (dirtying layout) and then immediately queries a geometric property before the browser's scheduled Layout phase. The browser is forced to halt JavaScript execution and run the Layout engine synchronously on the spot. When performed inside a loop, this degrades an $O(N)$ update into an $O(N^2)$ layout catastrophe.

### Layout-Reading Properties That Trigger Reflow When Layout Is Dirty

- **Element Box Metrics:** `offsetWidth`, `offsetHeight`, `offsetTop`, `offsetLeft`, `clientWidth`, `clientHeight`, `getBoundingClientRect()`, `getClientRects()`
- **Scroll Metrics:** `scrollTop`, `scrollLeft`, `scrollWidth`, `scrollHeight`, `window.scrollX`, `window.scrollY`
- **Computed Styles & Text:** `window.getComputedStyle(el)`, `innerText`

### The FastDOM Two-Phase Discipline (Read All -> Write All)

```typescript
// PROHIBITED: Interleaved Write -> Read inside a loop (Layout Thrashing)
for (const card of cards) {
  card.style.width = `${containerWidth}px`; // Dirty layout
  const height = card.offsetHeight;         // FORCED SYNCHRONOUS REFLOW on every iteration!
  card.style.height = `${height * 1.2}px`;
}

// APPLE-CRAFT STANDARD: Strict Phase 1 (Batch Reads) -> Phase 2 (Batch Writes via transform)
const measurements = cards.map((card) => ({
  card,
  rect: card.getBoundingClientRect(),
}));

requestAnimationFrame(() => {
  for (const { card, rect } of measurements) {
    const scaleX = containerWidth / Math.max(rect.width, 1);
    card.style.transform = `scale3d(${scaleX}, 1.2, 1)`;
  }
});
```

---

## 3. FLIP (First, Last, Invert, Play) for Complex Layout Transitions

When an element must visually change size or move to a new flex/grid container, never animate `width`, `height`, or `top`/`left`. Use **FLIP**:
1. **First:** Measure the initial bounding rect (`first = el.getBoundingClientRect()`).
2. **Last:** Apply the final DOM/class change instantaneously and measure the final bounding rect (`last = el.getBoundingClientRect()`).
3. **Invert:** Calculate the delta ($\Delta x = \text{first.left} - \text{last.left}$, $\Delta y = \text{first.top} - \text{last.top}$, $s_x = \text{first.width} / \text{last.width}$, $s_y = \text{first.height} / \text{last.height}$) and apply an instantaneous inverse `transform: translate3d(dx, dy, 0) scale(sx, sy)` so the element appears unmoved.
4. **Play:** In the next frame, animate `transform` to `translate3d(0, 0, 0) scale(1, 1)` on the GPU compositor.

---

## 4. Epsilon-Terminated Spring Physics & Hardware Ergonomics

1. **Epsilon Convergence (`1e-4`):** Every `requestAnimationFrame` spring or lerp loop must check both position delta and velocity magnitude:
   ```typescript
   const EPSILON = 1e-4;
   if (Math.abs(target - current) < EPSILON && Math.abs(velocity) < EPSILON) {
     current = target;
     velocity = 0;
     applyTransform(current);
     cancelAnimationFrame(rafHandle);
     rafHandle = null;
     return;
   }
   ```
2. **Touch Device Native Inertia Guard:** Never hijack native iOS/Android scroll physics. Gate any custom desktop momentum scroll engine behind:
   ```typescript
   const canUseCustomMomentumScroll =
     !window.matchMedia("(pointer: coarse)").matches && window.innerWidth >= 768;
   ```
3. **Main-Thread Offloading:** Any payload parsing (`> 100KB` JSON), client-side full-text search, cryptographic hashing, or storage serialization must execute in a dedicated **Web Worker** (`postMessage` with `Transferable` `ArrayBuffer`) or yield back to the browser input/render queue every `< 4ms` using `await scheduler.yield()`.
