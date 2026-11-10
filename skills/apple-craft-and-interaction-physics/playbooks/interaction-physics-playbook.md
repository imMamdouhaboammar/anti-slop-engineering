# Playbook: Interaction Physics & Velocity Continuity

## Objective
Implement physically grounded, 120Hz ProMotion-compliant interactive motion that is immediately interruptible by user gestures and preserves momentum via continuous velocity inheritance ($v_0$).

---

## The 6-Step Implementation Sequence

### Step 1: Parameterize the Mass-Spring-Damper Model
Do not use arbitrary milliseconds for transitions. Define mechanical constants:
- **Default Apple Sheet/Drawer:** $m = 1.0$, $k = 220$, $c = 26$ ($\zeta = 0.88$, smooth critically-damped deceleration).
- **Interactive Micro-Interaction (Button Press):** $m = 1.0$, $k = 300$, $c = 30$ ($\zeta = 0.87$, snappy feedback).
- **Elastic Sheet Overdrag:** $m = 1.0$, $k = 150$, $c = 20$ ($\zeta = 0.82$, gentle elastic resistance).

### Step 2: Implement Continuous Velocity Tracking
In any drag, pan, or swipe gesture listener, calculate and update the moving average velocity:
```typescript
interface PointerVelocityTracker {
  lastX: number;
  lastTime: number;
  velocity: number;
}

export function createVelocityTracker(): PointerVelocityTracker {
  return { lastX: 0, lastTime: 0, velocity: 0 };
}

export function updatePointerVelocity(tracker: PointerVelocityTracker, currentX: number): void {
  const now = performance.now();
  const dt = Math.max(1, now - tracker.lastTime);
  const dx = currentX - tracker.lastX;

  // Exponential moving average filter to remove micro-jitter
  const instantVelocity = (dx / dt) * 1000; // px/sec
  tracker.velocity = 0.8 * instantVelocity + 0.2 * tracker.velocity;
  tracker.lastX = currentX;
  tracker.lastTime = now;
}
```

### Step 3: Implement Immediate Interruption on PointerDown
The instant a user touches or clicks an animating element:
1. Immediately cancel the active animation loop (`cancelAnimationFrame(rafId)`).
2. Measure the current element transform using computed style.
3. Lock the element position directly under the pointer without resetting or snapping.

### Step 4: Inherit Velocity on Gesture Release
When the user lifts their finger or releases the mouse:
1. Pass the tracked `tracker.velocity` as the initial velocity $v_0$ into the spring solver.
2. If the user flicked the sheet downward with $v = 1500\text{px/s}$, the spring begins moving downward at $1500\text{px/s}$ and smoothly decelerates into the closed state.
3. If the user changed their mind mid-flick and dragged upward, the upward velocity immediately retargets the spring to open.

### Step 5: Enforce Epsilon Termination
Every frame step must evaluate:
```typescript
if (Math.abs(position - target) < 1e-4 && Math.abs(velocity) < 1e-4) {
  cancelAnimationFrame(rafId);
  element.style.transform = `translate3d(${target}px, 0, 0)`;
  isSettled = true;
}
```

### Step 6: Verify Compositor Isolation
Run an audit to confirm no animation references layout properties:
```bash
# Verify no transition:all or style.top/left
grep -rn "transition:\s*all" src/
grep -rn "style\.top\b" src/
```
All motion must be strictly expressed via `transform: translate3d(x, y, 0)` and `opacity`.
