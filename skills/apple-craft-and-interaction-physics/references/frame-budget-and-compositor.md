# 60/120Hz Frame Budget & Compositor Reference

> A 120Hz ProMotion screen refreshes every 8.33 milliseconds. A single unbatched DOM read can drop an entire frame.

## The Frame Budget Breakdown

On a modern ProMotion display (Apple Silicon Macs, iPads, iPhone 13 Pro+), the display updates 120 times per second:

$$T_{\text{frame}} = \frac{1000\text{ms}}{120} \approx 8.33\text{ms}$$

Within this 8.33ms window, the browser pipeline must sequentially execute:
1. **Input Events:** Pointer, touch, wheel, key events.
2. **JavaScript Execution:** State updates, event handlers, animation ticks.
3. **Style Recalculation:** Resolving CSS cascade and computed values.
4. **Layout:** Calculating geometric coordinates and line boxes.
5. **Paint:** Rasterizing vector paths, text glyphs, and shadows into bitmap tiles.
6. **Composite:** Sending GPU layers to the display compositor.

To guarantee zero dropped frames, the JavaScript budget is:

$$\text{Max JS Execution per Frame} \le 4.0\text{ms}$$

Any long task taking $> 50\text{ms}$ blocks the main thread, causing catastrophic frame drops and unresponsive user gestures.

---

## Zero Layout Thrashing (Forced Synchronous Layout)

The most common source of frame drops in AI-generated code is **Layout Thrashing**: interleaving DOM writes and layout reads within the same synchronous execution block.

### The Mechanism of Layout Thrashing
- When JavaScript writes to `element.style.top = '100px'`, the browser marks the layout tree as **dirty**.
- If JavaScript immediately reads `otherElement.offsetHeight`, the browser CANNOT wait for the normal layout phase; it is forced to immediately halt JS execution, parse all styles, and calculate layout synchronously.
- If this read-write cycle repeats inside a loop or scroll listener, the browser re-computes layout 60 times in a single frame, taking 80ms+ and dropping 10 consecutive frames.

```typescript
// BANNED: Forced Synchronous Layout Thrashing
for (let i = 0; i < items.length; i++) {
  items[i].style.width = '200px'; // WRITE (dirties layout)
  const height = items[i].offsetHeight; // READ (forces synchronous reflow!)
  items[i].style.height = `${height * 1.5}px'; // WRITE
}

// MANDATORY: FastDOM Read-Before-Write Batching
// Phase 1: Pure geometry reads (batch read)
const heights = items.map(item => item.offsetHeight);

// Phase 2: Pure style writes inside requestAnimationFrame (batch write)
requestAnimationFrame(() => {
  for (let i = 0; i < items.length; i++) {
    items[i].style.width = '200px';
    items[i].style.height = `${heights[i] * 1.5}px`;
  }
});
```

---

## Geometry Read Hazard List
Never read any of these properties immediately after mutating DOM styles or classes:
- `getBoundingClientRect()`
- `getClientRects()`
- `offsetWidth`, `offsetHeight`, `offsetLeft`, `offsetTop`
- `clientWidth`, `clientHeight`, `clientLeft`, `clientTop`
- `scrollWidth`, `scrollHeight`, `scrollLeft`, `scrollTop`
- `window.getComputedStyle()`
- `innerText`

Isolate geometric reads inside `ResizeObserver` or `IntersectionObserver` callbacks, which execute natively before the browser paints.

---

## Heavy Work Offloading Strategies

| Workload | Main-Thread Risk | Hardened Strategy |
| --- | --- | --- |
| Parsing 2MB+ JSON | Synchronous freeze (`30-80ms`) | Web Worker (`worker.postMessage`) |
| Filtering 5,000 items | CPU spike during keystrokes | Web Worker or chunked via `scheduler.yield()` |
| Storing user draft | Synchronous disk I/O | `IndexedDB` async transactions or debounced local storage |
| Image resizing / canvas filters | CPU-bound pixel manipulation | `OffscreenCanvas` in a Web Worker |

---

## Passive Listeners & Native Touch Inertia

Touch screens provide highly tuned, hardware-accelerated momentum scrolling implemented in the operating system kernel:
- Never attach non-passive `touchstart` or `touchmove` listeners unless strictly building an interactive drawing canvas.
- Always declare `{ passive: true }`:
  ```typescript
  window.addEventListener('scroll', onScroll, { passive: true });
  window.addEventListener('touchstart', onTouch, { passive: true });
  ```
- **Ban touch scroll hijacking:** Never replace native touch inertia with JavaScript momentum smoothing libraries on mobile/tablet viewports.
