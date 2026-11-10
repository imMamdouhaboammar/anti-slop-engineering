# Audit & Eliminate Latency Jank (120Hz & 60Hz UI Physics)

Use this workflow when auditing frontend interactions, animations, gestures, scroll handlers, or client rendering pipelines suffering from frame drops or main-thread freezing.

## Step-by-Step Procedure

### 1. Interrogate Against the Frame Budget (8.33ms / 16.67ms)
1. Determine the target display refresh rate: **120Hz ProMotion** (Apple iPad Pro, iPhone Pro, MacBook Pro, gaming monitors) requires frames delivered within **`8.33ms`**; standard 60Hz displays require **`16.67ms`**.
2. Measure JavaScript task execution times in Chrome DevTools or Safari Web Inspector. Identify any script execution exceeding **`4.0ms`** per frame.
3. Check for any task exceeding **`50ms`** (Long Task) on the Main Thread.

### 2. Identify and Eliminate Layout Thrashing
1. Search code for interleaved DOM writes and reads:
   - Writes: `element.style.* = ...`, `classList.add(...)`, DOM insertions.
   - Reads: `offsetHeight`, `offsetWidth`, `clientHeight`, `clientWidth`, `getBoundingClientRect()`, `scrollTop`, `scrollLeft`, `getComputedStyle()`.
2. Restructure the code to follow FastDOM phase separation: perform ALL geometric reads first, then perform ALL style/DOM mutations in a batched `requestAnimationFrame` callback.

### 3. Enforce Compositor-Only Transitions
1. Search stylesheets and inline styles for `transition: all` or transitions on layout properties (`width`, `height`, `top`, `left`, `margin`, `padding`).
2. Replace them strictly with GPU compositor properties: `transform` (`translate3d`, `scale`) and `opacity`.
3. If an element's layout geometry must change, compute dimensions using the FLIP (First, Last, Invert, Play) technique and animate via `transform`.

### 4. Offload Heavy Work from Main Thread
1. Identify heavy computations running on the main thread: JSON serialization, heavy array sorting/filtering, cryptographic operations, regex scans over large text.
2. Offload them to a dedicated **Web Worker** using Transferable Objects (`ArrayBuffer`).
3. If worker offloading is impractical, use **`scheduler.yield()`** or time-slicing to yield control back to the compositor every `< 3ms`.

### 5. Verify & Audit
Run the automated guard against the component source code:
```bash
python3 scripts/perf_guard.py audit <record.json> --source <component.tsx> --json
```
Verify that all source hazards are resolved with zero findings.
