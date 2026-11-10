# Keyboard & Focus Mastery Reference

> A world-class interface is effortlessly operable with one hand on a keyboard and fully transparent to a screen reader.

## The Core Laws of Keyboard & Focus Craft

AI code generators often treat keyboard accessibility as an afterthought—slapping `button { outline: none; }` to silence default browser styles, trapping keyboard users inside infinite tab loops, or letting focus wander aimlessly into hidden background DOM when modals open.

Apple HIG and WCAG 2.2 require complete keyboard parity, exquisite visual focus rings, and deterministic focus flow.

---

## 1. Focus Ring Discipline (WCAG 2.2 AA/AAA)

Default browser focus outlines can look inconsistent, but stripping them with `outline: none` or `outline: 0` is an instant accessibility violation that renders the interface unusable for millions of keyboard users.

### The Standard: `:focus-visible` with Offset
Never apply focus rings to mouse/pointer clicks; reserve prominent, high-contrast rings exclusively for keyboard navigation using `:focus-visible`:

```css
/* BANNED: The Silent Accessibility Erasure */
button:focus {
  outline: none;
}

/* MANDATORY: Apple HIG High-Contrast Focus Ring */
button:focus {
  outline: none; /* Only when accompanied by :focus-visible below */
}

button:focus-visible,
a:focus-visible,
input:focus-visible,
[tabindex]:focus-visible {
  outline: 2px solid var(--color-focus-ring, #0071e3);
  outline-offset: 2px;
  box-shadow: 0 0 0 4px rgba(0, 113, 227, 0.25);
  border-radius: inherit;
}
```

### Visual Specifications
- **Contrast Ratio:** The focus ring must have at least a **`3:1`** contrast ratio against both the inner button surface and the outer surrounding background.
- **Stroke Width:** Minimum **`2px`**.
- **Offset:** Minimum **`2px`** (`outline-offset: 2px`). This ensures the ring floats cleanly outside the element's border radius and is never clipped by `overflow: hidden` or adjacent elements.

---

## 2. Modal & Drawer Dialog Physics

Every slide-out sheet, drawer, and modal dialog must implement strict focus trapping, scroll locking, and deterministic focus restoration:

```typescript
export function useDialogFocusTrap(
  isOpen: boolean,
  dialogRef: React.RefObject<HTMLElement>,
  triggerRef: React.RefObject<HTMLElement>,
  onClose: () => void
) {
  useEffect(() => {
    if (!isOpen) return;

    const dialog = dialogRef.current;
    const trigger = triggerRef.current;
    if (!dialog) return;

    // 1. Lock document body scroll
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // 2. Query all focusable elements inside the dialog
    const focusableElements = dialog.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    // 3. Move initial focus into dialog
    firstElement?.focus();

    // 4. Trap Tab and Shift+Tab
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }

      if (e.key === 'Tab') {
        if (e.shiftKey) {
          if (document.activeElement === firstElement) {
            e.preventDefault();
            lastElement?.focus();
          }
        } else {
          if (document.activeElement === lastElement) {
            e.preventDefault();
            firstElement?.focus();
          }
        }
      }
    }

    dialog.addEventListener('keydown', handleKeyDown);

    return () => {
      dialog.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = originalOverflow;
      // 5. RESTORE FOCUS TO TRIGGER ELEMENT ON DISMISS
      trigger?.focus();
    };
  }, [isOpen, dialogRef, triggerRef, onClose]);
}
```

---

## 3. Roving Tabindex for Composite Widgets

For composite controls (segmented tab bars, toolbars, list boxes, menus), requiring the user to press `Tab` 20 times to bypass the controls is an anti-pattern. Implement **Roving Tabindex**:

- Only the currently selected/active item has `tabIndex={0}`.
- All other items have `tabIndex={-1}`.
- Navigating with `ArrowLeft`/`ArrowRight` (or `ArrowUp`/`ArrowDown`) updates the active item and moves DOM focus immediately.
- `Home` jumps to the first item; `End` jumps to the last item.
- Pressing `Tab` exits the entire composite widget in a single step.

```typescript
export function handleRovingKeyDown(
  e: React.KeyboardEvent,
  currentIndex: number,
  totalItems: number,
  onSelect: (index: number) => void
) {
  let nextIndex = currentIndex;

  if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
    e.preventDefault();
    nextIndex = (currentIndex + 1) % totalItems;
  } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
    e.preventDefault();
    nextIndex = (currentIndex - 1 + totalItems) % totalItems;
  } else if (e.key === 'Home') {
    e.preventDefault();
    nextIndex = 0;
  } else if (e.key === 'End') {
    e.preventDefault();
    nextIndex = totalItems - 1;
  }

  if (nextIndex !== currentIndex) {
    onSelect(nextIndex);
  }
}
```

---

## 4. Screen Reader Semantics & ARIA Live Regions

- **Dynamic State Announcements:** When an asynchronous mutation completes, or a cart updates, or an inline toast appears, announce the change quietly using an ARIA Live Region:
  ```html
  <div aria-live="polite" aria-atomic="true" class="sr-only">
    Cart updated: 3 items total
  </div>
  ```
- **Async Loading States:** Declare `aria-busy="true"` on containers while skeleton loaders are active:
  ```html
  <section aria-busy="true" aria-label="Loading account dashboard">
    <!-- Skeleton items -->
  </section>
  ```
- **Icon Buttons:** Any interactive element containing only an icon (e.g., SVG cross for close, magnifying glass for search) MUST declare an explicit accessible name:
  ```html
  <button type="button" aria-label="Dismiss notification" class="icon-btn">
    <svg aria-hidden="true" ...></svg>
  </button>
  ```
