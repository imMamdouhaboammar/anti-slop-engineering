# Playbook: Keyboard & Focus Mastery

## Objective
Deliver flawless keyboard and screen reader accessibility with high-contrast `:focus-visible` rings, dialog focus traps with restoration, roving tabindex for composite controls, and polite ARIA announcements.

---

## The 4-Step Keyboard Implementation Sequence

### Step 1: Replace Naked `outline: none` with `:focus-visible` Rings
Scan and eliminate all bare `outline: none` occurrences:
```css
/* BANNED */
*:focus {
  outline: none;
}

/* MANDATORY */
:focus:not(:focus-visible) {
  outline: none; /* Hide default outline for pointer/mouse users */
}

:focus-visible {
  outline: 2px solid #0071e3;
  outline-offset: 2px;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.25);
  border-radius: inherit;
}
```

### Step 2: Implement Dialog Focus Trap & Restoration
Wrap every modal, drawer, or sheet dialog with a trap:
1. When opened, lock `document.body.style.overflow = 'hidden'`.
2. Move focus to the first focusable child or close button.
3. Intercept `Tab` on the last child to loop back to the first child.
4. Intercept `Shift+Tab` on the first child to loop back to the last child.
5. On `Escape` key or dismiss, call `.focus()` on the trigger button that originally opened the dialog.

### Step 3: Implement Roving Tabindex on Composite Controls
For segmented tabs, toolbars, and carousels:
- Active element receives `tabIndex={0}`.
- All non-active siblings receive `tabIndex={-1}`.
- Listen for `ArrowRight`/`ArrowDown` (increment index) and `ArrowLeft`/`ArrowUp` (decrement index).
- Set DOM focus to the new active element immediately.

### Step 4: Add Polite ARIA Live Regions for State Changes
Provide screen readers with real-time feedback on dynamic changes:
```html
<div aria-live="polite" aria-atomic="true" class="sr-only">
  {statusAnnouncementText}
</div>
```
