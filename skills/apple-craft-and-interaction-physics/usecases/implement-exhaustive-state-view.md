# Use Case: Implement Exhaustive State View with Zero-CLS & Keyboard Mastery

## When to Use
Use when implementing or refactoring a production React, Vue, or web-standard view to ensure all 8 operational states are rendered, Cumulative Layout Shift is 0.000, and keyboard navigation is fully supported.

---

## 5-Step Implementation Checklist

1. **Discriminated Union State Machine:**
   - Define `type ViewState = ...` with tag `status`.
   - Implement `assertNever(state)` in the default branch.
   - Eliminate loose boolean flags (`isLoading`, `isError`).
2. **Zero-CLS Geometry Reservation:**
   - Create pixel-matched skeleton component with identical `min-height`, padding, and grid tracks.
   - Declare explicit `aspect-ratio` on all dynamic media containers.
   - Pre-reserve error slot height in CSS (`min-height: 20px`).
   - Add `scrollbar-gutter: stable` to container or document body.
3. **Optimistic Rollback & Draft Preservation:**
   - Capture `previousStateSnapshot` before updating the view.
   - If mutation fails, restore prior snapshot while keeping user's typed draft text in the input.
   - Render inline retry button inside the component.
4. **Keyboard & Focus Management:**
   - Ensure all clickable elements use semantic `<button>` or `<a>`.
   - Apply `:focus-visible` styling with 3:1 contrast, 2px stroke, and 2px offset.
   - For modal dialogs, implement focus trapping and restore focus to the trigger element on close.
   - For composite lists/tabs, implement Roving Tabindex with Arrow key navigation.
5. **Compositor & Physics Verification:**
   - Verify all transitions use `transform` and `opacity` only.
   - Ensure zero instances of `transition: all`.
   - Verify spring loops terminate with $\epsilon \le 10^{-4}$.
