# Zero-CLS Geometry Pre-Reservation Reference

> An interface that shifts during loading is an interface that stutters. Enforce Cumulative Layout Shift = 0.000 across all render lifecycles.

## The Mathematics of Layout Shift

Cumulative Layout Shift (CLS) measures visual instability during page load and dynamic rendering:

$$\text{Layout Shift Score} = \text{Impact Fraction} \times \text{Distance Fraction}$$

Where:
- **Impact Fraction:** The union of the visible areas of all unstable elements for the previous frame and the current frame, relative to the viewport.
- **Distance Fraction:** The greatest distance an unstable element has moved in the frame, divided by the viewport's largest dimension.

Any value $\text{CLS} > 0$ causes jarring visual stutter and causes mis-clicks (e.g., a user attempts to tap "Cancel", but an unsized image resolves and moves "Confirm" directly under their finger).

In Apple Craft & Design Engineering, the invariant is:

$$\text{Target CLS} = 0.000$$

---

## The Six Geometry Pre-Reservation Mechanisms

### 1. Pixel-Matched Skeletons (`pixel_matched_skeleton`)
A skeleton loader must not be an arbitrary generic gray rectangle. Its outer bounding box must identically match the resolved loaded content:
- Same `min-height` and `height`.
- Same padding, margin, border, and row gaps.
- Text skeletons must match the exact line-height and typography bounding boxes of the target text blocks.

```css
/* RESOLVED CONTAINER */
.product-card {
  display: grid;
  grid-template-rows: 240px 24px 18px 44px;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  min-height: 380px;
}

/* SKELETON LOADER (Identical outer geometry) */
.product-card-skeleton {
  display: grid;
  grid-template-rows: 240px 24px 18px 44px;
  gap: 12px;
  padding: 16px;
  border-radius: 12px;
  min-height: 380px;
}
```

### 2. Media Aspect Ratio Locks (`explicit_aspect_ratio`)
Every image, video, canvas, and iframe must have its aspect ratio pre-calculated and declared before the asset bytes arrive from the network:
```html
<!-- HTML intrinsic dimensions -->
<img src="avatar.jpg" width="80" height="80" alt="Avatar" loading="lazy" />

<!-- Or CSS aspect-ratio -->
<div class="media-container" style="aspect-ratio: 16 / 9; width: 100%;">
  <img src="hero.webp" class="cover-image" />
</div>
```

### 3. Reserved Layout Slots for Validation Errors (`reserved_error_track`)
A common source of layout shift in forms is the sudden appearance of inline error text when validation fails. If the error text is rendered into the flow without a reserved track, it pushes the inputs and buttons below it downward by 20–30px.

**Hardened Pattern:**
```css
.form-field-error-slot {
  min-height: 20px; /* Pre-allocated line track */
  font-size: 0.75rem;
  line-height: 1.25rem;
  color: var(--color-error);
  transition: opacity 150ms ease-out;
}
```
The error slot is permanently present in the layout flow. When valid, its text is empty or transparent; when an error occurs, the message fades in (`opacity: 1`) without changing the height of the form field.

### 4. Scrollbar Gutter Stabilization (`scrollbar_gutter_stable`)
When a document transitions from content that fits in the viewport to content that requires vertical scrolling, the appearance of the browser scrollbar reduces viewport width by 15–17px, causing an entire page-wide horizontal shift.

**Hardened Invariant:**
```css
html {
  scrollbar-gutter: stable;
}
```
This forces the layout engine to reserve space for the scrollbar regardless of whether content overflows, guaranteeing 0px horizontal jitter.

### 5. Font Metric Overrides (`font_metric_overrides`)
When custom webfonts load, the flash of unstyled text (FOUT) or flash of invisible text (FOIT) causes layout shift if the fallback system font has different ascent, descent, or line-gap metrics.

**Hardened Invariant:**
Use CSS `@font-face` metric overrides or `font-display: optional`:
```css
@font-face {
  font-family: 'Inter-Fallback';
  src: local('Arial');
  ascent-override: 90%;
  descent-override: 22%;
  line-gap-override: 0%;
  size-adjust: 107%;
}

@font-face {
  font-family: 'Inter';
  src: url('/fonts/Inter.woff2') format('woff2');
  font-display: optional; /* Zero shift guarantee */
}
```

### 6. Intrinsic Dimensions on Iconography & Badges
Badges, notification counts, and status pills must declare `min-width` and `tabular-nums` so numbers shifting from `1` to `99` do not jitter adjacent navigation buttons or headers:
```css
.notification-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 20px;
  height: 20px;
  font-variant-numeric: tabular-nums;
  padding: 0 4px;
}
```
