# Interruptible Spring Physics Reference

> The physical world does not reset to zero velocity when you push an object while it is moving. Interaction physics must inherit momentum and yield immediately to user intent.

## The Mathematical Foundation: Mass-Spring-Damper Physics

Apple HIG motion is not based on arbitrary Bezier easing curves or fixed durations; it is governed by classical second-order Newtonian physics:

$$m \frac{d^2x}{dt^2} + c \frac{dx}{dt} + k (x - x_{\text{target}}) = 0$$

Where:
- $m$: **Mass** (inertia of the object, default $1.0$).
- $k$: **Stiffness** (spring tension; how forcefully the object seeks the target, e.g. $180$).
- $c$: **Damping** (frictional resistance; controls deceleration, e.g. $24$).

Key physical ratios:
- **Undamped Angular Frequency:** $\omega_0 = \sqrt{\frac{k}{m}}$
- **Damping Ratio:** $\zeta = \frac{c}{2\sqrt{km}}$
  - $\zeta = 1.0$: **Critically Damped** (fastest convergence with zero overshoot—ideal for navigation sheets and drawers).
  - $0.7 \le \zeta < 1.0$: **Slightly Underdamped** (natural, subtle deceleration with minimal overshoot—classic Apple HIG feel).
  - $\zeta < 0.7$: **Bouncy** (use with extreme restraint, only for small delightful micro-interactions).

---

## The Law of Immediate Interruption & Velocity Inheritance

### Why Duration-Based CSS Transitions Fail
Standard CSS transitions are inherently unphysical:
```css
/* ANTI-PATTERN: Rigid Canned Transition */
.sheet {
  transition: transform 400ms cubic-bezier(0.25, 1, 0.5, 1);
}
```
1. **The Lock-In Trap:** If a user swipes a sheet upward and suddenly changes their mind mid-flight (at 200ms) to flick it downward, a standard transition either ignores the new gesture until 400ms elapses, or resets the curve from 0 velocity, resulting in a jarring visual stutter.
2. **The Duration Trap:** Moving a sheet 500px takes 400ms; moving it 10px also takes 400ms. Fixed durations feel sluggish over short distances and frantic over long distances.

### The Spring Solution: Velocity Continuity ($v_0$)
When an animation is interrupted at time $t_i$:
1. Measure the instantaneous velocity:
   $$v_0 = \frac{x(t_i) - x(t_i - \Delta t)}{\Delta t}$$
2. Re-target the spring equation with:
   $$\text{position}(0) = x(t_i), \quad \text{velocity}(0) = v_0$$
3. The motion continues smoothly in the new direction without any discontinuity in velocity or acceleration.

---

## Epsilon-Terminated Convergence

Never leave `requestAnimationFrame` running indefinitely waiting for asymptotic floats to reach zero. Define a strict convergence threshold:

$$\epsilon = 10^{-4} \quad (0.0001\text{px})$$

```typescript
function stepSpring(state: SpringState, target: number, dt: number): boolean {
  const displacement = state.position - target;
  const springForce = -state.stiffness * displacement;
  const dampingForce = -state.damping * state.velocity;
  const acceleration = (springForce + dampingForce) / state.mass;

  state.velocity += acceleration * dt;
  state.position += state.velocity * dt;

  // Epsilon convergence check
  if (Math.abs(displacement) < 1e-4 && Math.abs(state.velocity) < 1e-4) {
    state.position = target;
    state.velocity = 0;
    return true; // Settled: cancel rAF loop immediately
  }
  return false; // In motion
}
```

---

## GPU Compositor Execution Rules

To achieve a solid 120Hz (ProMotion) frame rate, animation properties must be restricted strictly to the GPU Compositor thread:

| Property | Thread | Triggers Reflow/Layout? | Triggers Paint? | Allowed in Physics? |
| --- | --- | --- | --- | --- |
| `transform` (`translate3d`, `scale`) | Compositor | **NO** | **NO** | **YES** |
| `opacity` | Compositor | **NO** | **NO** | **YES** |
| `filter: blur(...)` | GPU | **NO** | Moderate | Caution (bounded layer only) |
| `top`, `left`, `right`, `bottom` | Main Thread | **YES** | **YES** | **BANNED** |
| `width`, `height` | Main Thread | **YES** | **YES** | **BANNED** (Use FLIP scale) |
| `margin`, `padding` | Main Thread | **YES** | **YES** | **BANNED** |

---

## Accessibility: Respecting `prefers-reduced-motion`

Every physics loop must inspect user accessibility preferences:

```typescript
const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

if (prefersReduced) {
  // Degrade immediately to instant state update or gentle opacity fade
  element.style.transform = `translate3d(${targetX}px, ${targetY}px, 0)`;
  element.style.opacity = targetOpacity.toString();
  return;
}
```
Spatial displacements, scales, and bounciness must collapse to zero motion when reduced motion is requested.
