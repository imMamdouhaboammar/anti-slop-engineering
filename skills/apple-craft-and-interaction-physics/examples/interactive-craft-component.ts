// Apple HIG Craft & Interaction Physics Reference Implementation
// Implements: Exhaustive State Matrix, Zero CLS, Interruptible Spring Physics, and Keyboard/Focus Mastery

export interface FeedItem {
  id: string;
  title: string;
  summary: string;
  imageUrl: string;
  author: string;
}

// 1. Exhaustive UI State Matrix (Discriminated Union)
export type FeedViewState =
  | { status: 'loading_skeleton'; rowCount: number }
  | { status: 'empty'; guidanceTitle: string; callToAction: () => void }
  | { status: 'loaded_fresh'; items: readonly FeedItem[]; updatedAt: number }
  | { status: 'revalidating_stale'; items: readonly FeedItem[]; isBackground: true }
  | { status: 'partial_error'; items: readonly FeedItem[]; failedSection: string; onRetrySection: () => void }
  | { status: 'offline'; items: readonly FeedItem[] | null; pendingDrafts: number }
  | { status: 'optimistic_rollback'; draftContent: string; rollbackReason: string; onRetry: () => void }
  | { status: 'terminal_error'; incidentId: string; message: string; onRecover: () => void };

export function assertNever(variant: never): never {
  throw new Error(`Unreachable UI State Matrix variant: ${JSON.stringify(variant)}`);
}

// 2. Interruptible Spring Physics Engine with Velocity Inheritance
export interface SpringConfig {
  stiffness: number; // k
  damping: number;   // c
  mass: number;      // m
}

export const APPLE_SPRING_DEFAULT: SpringConfig = {
  stiffness: 220,
  damping: 26,
  mass: 1.0,
};

export class InterruptibleSpring {
  private currentX = 0;
  private currentVelocity = 0;
  private targetX = 0;
  private rafId: number | null = null;
  private isSettled = true;

  constructor(
    private readonly config: SpringConfig = APPLE_SPRING_DEFAULT,
    private readonly onUpdate: (x: number) => void = () => {},
    private readonly onSettled: () => void = () => {}
  ) {}

  public interrupt(): void {
    if (this.rafId !== null) {
      cancelAnimationFrame(this.rafId);
      this.rafId = null;
    }
    this.isSettled = false;
  }

  public retarget(newTarget: number, initialVelocity?: number): void {
    this.interrupt();
    this.targetX = newTarget;

    // Inherit continuous velocity if supplied, otherwise retain moving velocity
    if (typeof initialVelocity === 'number') {
      this.currentVelocity = initialVelocity;
    }

    const prefersReducedMotion =
      typeof window !== 'undefined' &&
      window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;

    if (prefersReducedMotion) {
      this.currentX = newTarget;
      this.currentVelocity = 0;
      this.isSettled = true;
      this.onUpdate(this.currentX);
      this.onSettled();
      return;
    }

    let lastTimestamp = performance.now();

    const tick = (now: number) => {
      const dt = Math.min((now - lastTimestamp) / 1000, 0.032); // Clamp to prevent spring explosion
      lastTimestamp = now;

      const displacement = this.currentX - this.targetX;
      const springForce = -this.config.stiffness * displacement;
      const dampingForce = -this.config.damping * this.currentVelocity;
      const acceleration = (springForce + dampingForce) / this.config.mass;

      this.currentVelocity += acceleration * dt;
      this.currentX += this.currentVelocity * dt;

      // Epsilon convergence check: cancel when close and slow
      if (Math.abs(displacement) < 1e-4 && Math.abs(this.currentVelocity) < 1e-4) {
        this.currentX = this.targetX;
        this.currentVelocity = 0;
        this.isSettled = true;
        this.onUpdate(this.currentX);
        this.onSettled();
        this.rafId = null;
        return;
      }

      this.onUpdate(this.currentX);
      this.rafId = requestAnimationFrame(tick);
    };

    this.rafId = requestAnimationFrame(tick);
  }

  public getPosition(): number {
    return this.currentX;
  }

  public getVelocity(): number {
    return this.currentVelocity;
  }

  public dispose(): void {
    this.interrupt();
  }
}

// 3. Keyboard & Focus Dialog Trap with Deterministic Restoration
export class ModalDialogManager {
  private activeDialog: HTMLElement | null = null;
  private previousActiveElement: HTMLElement | null = null;
  private boundKeyDown: ((e: KeyboardEvent) => void) | null = null;
  private originalBodyOverflow = '';

  public open(dialog: HTMLElement, trigger: HTMLElement, onClose: () => void): void {
    this.close(); // Clean prior if open

    this.activeDialog = dialog;
    this.previousActiveElement = trigger;
    this.originalBodyOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';

    // Verify a11y attributes
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');

    const focusables = dialog.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusables[0];
    const last = focusables[focusables.length - 1];

    first?.focus();

    this.boundKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === 'Tab') {
        if (e.shiftKey) {
          if (document.activeElement === first) {
            e.preventDefault();
            last?.focus();
          }
        } else {
          if (document.activeElement === last) {
            e.preventDefault();
            first?.focus();
          }
        }
      }
    };

    dialog.addEventListener('keydown', this.boundKeyDown);
  }

  public close(): void {
    if (this.activeDialog && this.boundKeyDown) {
      this.activeDialog.removeEventListener('keydown', this.boundKeyDown);
      document.body.style.overflow = this.originalBodyOverflow;
      this.activeDialog = null;
      this.boundKeyDown = null;

      // Deterministic focus restoration
      if (this.previousActiveElement) {
        this.previousActiveElement.focus();
        this.previousActiveElement = null;
      }
    }
  }
}

// 4. Roving Tabindex Manager for Segmented Controls
export class RovingTabindexController {
  constructor(
    private readonly items: HTMLElement[],
    private activeIndex = 0
  ) {
    this.updateTabindices();
  }

  public handleKeyDown(e: KeyboardEvent, onActivate: (index: number) => void): void {
    const total = this.items.length;
    let nextIndex = this.activeIndex;

    if (e.key === 'ArrowRight' || e.key === 'ArrowDown') {
      e.preventDefault();
      nextIndex = (this.activeIndex + 1) % total;
    } else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') {
      e.preventDefault();
      nextIndex = (this.activeIndex - 1 + total) % total;
    } else if (e.key === 'Home') {
      e.preventDefault();
      nextIndex = 0;
    } else if (e.key === 'End') {
      e.preventDefault();
      nextIndex = total - 1;
    }

    if (nextIndex !== this.activeIndex) {
      this.activeIndex = nextIndex;
      this.updateTabindices();
      this.items[nextIndex].focus();
      onActivate(nextIndex);
    }
  }

  private updateTabindices(): void {
    this.items.forEach((item, index) => {
      item.tabIndex = index === this.activeIndex ? 0 : -1;
    });
  }
}
