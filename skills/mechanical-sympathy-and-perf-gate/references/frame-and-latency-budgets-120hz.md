# Frame & Latency Budgets (120Hz ProMotion & 60Hz Physics)

## 1. Frame Deadlines & The Browser Compositor Pipeline

Modern Apple and mobile displays run at **120Hz ProMotion** (1 frame every `8.33ms`). Standard displays run at **60Hz** (1 frame every `16.67ms`).

```
|-------------------------- 8.33ms Frame Window (120Hz) --------------------------|
[ JavaScript Work (< 4ms) ] [ Recalc Style ] [ Layout / Reflow ] [ Paint ] [ Composite ]
```

If JavaScript execution, style recalculation, or layout exceeds `8.33ms`, the frame drops, producing visible stutter, jank, and input lag.

### The 4.0ms JavaScript Execution Ceiling
To guarantee that the browser has sufficient headroom for layout recalculation, rasterization, paint, and GPU compositing, per-frame JavaScript work on the Main Thread must remain strictly **$\le 4.0\text{ms}$**.

---

## 2. Forced Synchronous Layout Thrashing

The most common cause of dropped frames is **Layout Thrashing**: interleaving DOM writes (which invalidate the layout tree) with synchronous geometry reads (which force an immediate synchronous layout calculation before the script can continue).

### Prohibited Thrashing Pattern
```javascript
// BAD: Forces 100 full-page synchronous reflows inside a single frame!
for (const element of elements) {
  element.style.width = "200px";     // WRITE (invalidates layout)
  const top = element.offsetTop;     // READ (forces immediate synchronous reflow!)
}
```

### FastDOM Phase Separation
Separate geometry reads from style mutations across distinct execution phases:
```javascript
// GOOD: Phase 1 - Batch all reads
const offsets = elements.map(el => el.offsetTop);

// Phase 2 - Batch all writes in requestAnimationFrame
requestAnimationFrame(() => {
  elements.forEach((el, i) => {
    el.style.transform = `translate3d(0, ${offsets[i]}px, 0)`;
  });
});
```

---

## 3. Compositor-Only Properties vs Paint/Layout Properties

| Trigger Level | Properties Animated | Performance Profile |
| --- | --- | --- |
| **Compositor Only** (120Hz Safe) | `transform`, `opacity` | Executed directly on GPU compositor thread; 0ms main thread blocking |
| **Paint Trigger** (High Cost) | `background-color`, `box-shadow`, `color`, `visibility` | Re-rasters bitmap layers; easily drops frames on large surfaces |
| **Layout Trigger** (Catastrophic) | `width`, `height`, `top`, `left`, `margin`, `padding` | Invalidates entire document layout tree; causes instant jank |

**The Absolute Rule:** Never use `transition: all`. Animate strictly `transform` and `opacity`. Use FLIP (First, Last, Invert, Play) technique when animating positional layout changes.

---

## 4. Main-Thread Offloading & Time-Slicing

Any task exceeding **`50ms`** is classified by Chromium and WebKit as a **Long Task**, blocking the main thread and freezing user clicks and inputs.

### Strategies
1. **Web Workers with Transferable Objects:** Offload heavy computational tasks (parsing, sorting, filtering, crypto) to a dedicated Web Worker, transferring ownership of the `ArrayBuffer` without cloning (`worker.postMessage({ buffer }, [buffer])`).
2. **`scheduler.yield()` Chunking:** For non-worker tasks, divide iterations into `< 3ms` slices and yield execution to the event loop:
   ```typescript
   if ("scheduler" in globalThis && typeof (globalThis as any).scheduler?.yield === "function") {
     await (globalThis as any).scheduler.yield();
   } else {
     await new Promise(resolve => setTimeout(resolve, 0));
   }
   ```
3. **Passive Event Listeners:** Always pass `{ passive: true }` to `wheel`, `touchstart`, and `touchmove` listeners so the compositor can scroll independently without waiting for JavaScript.
