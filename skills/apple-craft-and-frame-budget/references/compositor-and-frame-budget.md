# Compositor & 60/120Hz Frame Budget Reference

---

## 1. Frame Budget Breakdown (`16.67ms` vs `8.33ms`)

| Metric | 60Hz Display | 120Hz ProMotion Display | Hard Failure Threshold |
| --- | --- | --- | --- |
| **Total Frame Interval** | `16.67ms` | `8.33ms` | `> 16.67ms` (Dropped Frame) |
| **Max JavaScript Execution Slice** | `6.00ms` | `4.00ms` | `> 10.00ms` |
| **Style + Layout + Paint + Composite** | `<= 10.67ms` | `<= 4.33ms` | `> 6.67ms` at 120Hz |
| **Main-Thread Long Task Ceiling** | `< 50.00ms` | `< 50.00ms` | `>= 50.00ms` (INP Degradation) |
| **Input-to-Next-Paint (INP) Target** | `< 50.00ms` | `< 32.00ms` | `> 200.00ms` |

---

## 2. CSS Property Rendering Cost Matrix

| CSS Property / Mutation | Layout (Reflow) | Paint (Raster) | GPU Composite | Verdict |
| --- | --- | --- | --- | --- |
| `transform: translate3d(x, y, 0)` | No | No | **Yes** | **PERMITTED (120Hz Safe)** |
| `transform: scale(sx, sy)` / `rotate()` | No | No | **Yes** | **PERMITTED (120Hz Safe)** |
| `opacity: 0..1` | No | No | **Yes** | **PERMITTED (120Hz Safe)** |
| `background-color` / `color` / `box-shadow` | No | **Yes** | Yes | **RESTRICT** (Static hover/focus only; never continuous drag/scroll) |
| `width` / `height` / `min-height` | **Yes** | **Yes** | Yes | **PROHIBITED in animations** (Use `scale` or FLIP) |
| `top` / `left` / `right` / `bottom` | **Yes** | **Yes** | Yes | **PROHIBITED in animations** (Use `translate3d`) |
| `margin` / `padding` / `border-width` | **Yes** | **Yes** | Yes | **PROHIBITED in animations** |
| `transition: all ...` | **Yes** | **Yes** | Yes | **BANNED** (Explicitly list `transform, opacity`) |

---

## 3. Main-Thread Time-Slicing & Web Worker Offloading Patterns

### A. Yielding Long Loops Across Frames (`scheduler.yield` Fallback)

When processing a batch on the client where a Web Worker is not applicable, slice execution into `< 4ms` budgets so pending user clicks and 120Hz animations never stall:

```typescript
async function yieldToMainThread(): Promise<void> {
  const g = globalThis as { scheduler?: { yield?: () => Promise<void> } };
  if (typeof g.scheduler?.yield === "function") {
    await g.scheduler.yield();
    return;
  }
  await new Promise<void>((resolve) => {
    const channel = new MessageChannel();
    channel.port1.onmessage = () => resolve();
    channel.port2.postMessage(null);
  });
}

export async function processInFrameBudgetSlices<T, R>(
  items: readonly T[],
  fn: (item: T) => R,
  maxSliceMs = 3.5
): Promise<R[]> {
  const results: R[] = new Array(items.length);
  let sliceStart = performance.now();

  for (let i = 0; i < items.length; i++) {
    results[i] = fn(items[i]);
    if (performance.now() - sliceStart >= maxSliceMs) {
      await yieldToMainThread();
      sliceStart = performance.now();
    }
  }
  return results;
}
```

### B. Epsilon-Terminated Spring Loop Contract

Never run an unconditional `requestAnimationFrame(step)` loop. Always bound convergence with $\epsilon = 10^{-4}$:

```typescript
export interface SpringConfig {
  stiffness: number;
  damping: number;
  mass: number;
  epsilon?: number;
}

export function stepDampedSpring(
  current: number,
  target: number,
  velocity: number,
  dtSeconds: number,
  config: SpringConfig = { stiffness: 280, damping: 26, mass: 1, epsilon: 1e-4 }
): { value: number; velocity: number; settled: boolean } {
  const eps = config.epsilon ?? 1e-4;
  const displacement = current - target;
  const springForce = -config.stiffness * displacement;
  const dampingForce = -config.damping * velocity;
  const acceleration = (springForce + dampingForce) / config.mass;

  const nextVelocity = velocity + acceleration * dtSeconds;
  const nextValue = current + nextVelocity * dtSeconds;

  if (Math.abs(target - nextValue) < eps && Math.abs(nextVelocity) < eps) {
    return { value: target, velocity: 0, settled: true };
  }
  return { value: nextValue, velocity: nextVelocity, settled: false };
}
```
