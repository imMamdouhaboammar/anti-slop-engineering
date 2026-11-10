# Playbook: Zero-CLS Geometry Pre-Reservation

## Objective
Eliminate all visual jitter, content pops, and cumulative layout shift during data fetching, image loading, and form validation, achieving $\text{CLS} = 0.000$.

---

## The 4-Step Geometry Lock Process

### Step 1: Pre-Calculate Media Aspect Ratios
Never insert an image, canvas, or video without explicit geometry attributes:
```html
<!-- Pattern A: Intrinsic attributes -->
<img src="avatar.jpg" width="48" height="48" alt="Profile" />

<!-- Pattern B: CSS aspect-ratio container -->
<div class="card-cover-wrapper" style="aspect-ratio: 16 / 9; width: 100%;">
  <img src="banner.webp" class="cover-image" />
</div>
```

### Step 2: Build Pixel-Matched Skeleton Components
Ensure the skeleton component declares the exact CSS grid or flex dimensions as the resolved component:
```css
/* Card Container */
.feed-item,
.feed-item-skeleton {
  min-height: 120px;
  display: flex;
  gap: 16px;
  padding: 16px;
  border-bottom: 1px solid var(--border-color);
  box-sizing: border-box;
}

/* Skeleton Placeholder Blocks */
.skeleton-avatar {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  background: var(--skeleton-bg);
}

.skeleton-title {
  width: 60%;
  height: 20px;
  border-radius: 4px;
  background: var(--skeleton-bg);
}
```

### Step 3: Pre-Allocate Form Error Tracks
Forms must not expand vertically when validation errors appear:
```css
.field-container {
  display: flex;
  flex-direction: column;
}

.field-input {
  height: 44px; /* Minimum Apple touch target */
}

.field-error-slot {
  height: 20px; /* Fixed height reserved permanently */
  line-height: 20px;
  font-size: 0.75rem;
  color: var(--color-error);
  opacity: 0;
  transition: opacity 150ms ease-out;
}

.field-error-slot.has-error {
  opacity: 1;
}
```

### Step 4: Stabilize Viewport Scrollbars
Prevent layout shifts when pages grow taller than the window viewport:
```css
html {
  scrollbar-gutter: stable;
}
```
