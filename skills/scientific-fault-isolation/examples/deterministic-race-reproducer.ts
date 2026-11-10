// SPDX-License-Identifier: MIT
// Example: Surgical Fault Isolation — Deterministic Rendezvous Barrier, Seeded PRNG, Frozen Clock & Race Fix

export interface ClockPort {
  nowMs(): number;
}

export class FrozenClock implements ClockPort {
  constructor(private currentMs: number) {}
  nowMs(): number {
    return this.currentMs;
  }
  advanceMs(deltaMs: number): void {
    this.currentMs += deltaMs;
  }
}

export class SeededPrng {
  private state: number;
  constructor(seed: number) {
    this.state = seed >>> 0 || 0xdeadbeef;
  }
  nextFloat(): number {
    let x = this.state;
    x ^= x << 13;
    x ^= x >>> 17;
    x ^= x << 5;
    this.state = x >>> 0;
    return this.state / 0x100000000;
  }
}

export class DeterministicRendezvousBarrier {
  private arrived = 0;
  private release!: () => void;
  private readonly gate: Promise<void>;

  constructor(private readonly parties: number) {
    this.gate = new Promise<void>((resolve) => {
      this.release = resolve;
    });
  }

  async arriveAndWait(): Promise<void> {
    this.arrived += 1;
    if (this.arrived >= this.parties) {
      this.release();
    }
    await this.gate;
  }
}

export interface CouponRecord {
  code: string;
  remainingUses: number;
  version: number;
  expiresAtMs: number;
}

export interface CouponStorePort {
  readCoupon(code: string): Promise<CouponRecord | null>;
  compareAndSwapCoupon(code: string, expectedVersion: number, nextRemainingUses: number): Promise<boolean>;
  unsafeWriteCoupon(code: string, nextRemainingUses: number): Promise<void>;
}

// --- 1. In-Memory Store Instrumented with Optional Deterministic Read Barrier ---
export class BarrierInstrumentedCouponStore implements CouponStorePort {
  private readonly rows = new Map<string, CouponRecord>();

  constructor(
    initial: readonly CouponRecord[],
    private readonly readBarrier?: DeterministicRendezvousBarrier
  ) {
    for (const item of initial) {
      this.rows.set(item.code, { ...item });
    }
  }

  private commitRow(row: CouponRecord, nextRemainingUses: number): void {
    this.rows.set(row.code, { ...row, remainingUses: nextRemainingUses, version: row.version + 1 });
  }

  async readCoupon(code: string): Promise<CouponRecord | null> {
    const row = this.rows.get(code);
    const snapshot = row ? { ...row } : null;
    if (this.readBarrier) {
      await this.readBarrier.arriveAndWait();
    }
    return snapshot;
  }

  async unsafeWriteCoupon(code: string, nextRemainingUses: number): Promise<void> {
    const row = this.rows.get(code);
    if (row) this.commitRow(row, nextRemainingUses);
  }

  async compareAndSwapCoupon(
    code: string,
    expectedVersion: number,
    nextRemainingUses: number
  ): Promise<boolean> {
    const row = this.rows.get(code);
    if (!row || row.version !== expectedVersion) {
      return false;
    }
    this.commitRow(row, nextRemainingUses);
    return true;
  }
}

function validateEligibleCoupon(
  coupon: CouponRecord | null,
  clock: ClockPort
): { ok: true; coupon: CouponRecord } | { ok: false; reason: string } {
  if (!coupon) return { ok: false, reason: "NOT_FOUND" };
  if (clock.nowMs() >= coupon.expiresAtMs) return { ok: false, reason: "EXPIRED" };
  if (coupon.remainingUses <= 0) return { ok: false, reason: "DEPLETED" };
  return { ok: true, coupon };
}

// --- 2. Vulnerable Implementation (Exposes Confirmed Hypothesis H1: TOCTOU Read-Modify-Write) ---
export async function redeemCouponBuggy(store: CouponStorePort, clock: ClockPort, code: string) {
  const check = validateEligibleCoupon(await store.readCoupon(code), clock);
  if (!check.ok) return { redeemed: false, reason: check.reason };
  await store.unsafeWriteCoupon(code, check.coupon.remainingUses - 1);
  return { redeemed: true };
}

// --- 3. Surgical Fix (Enforces Optimistic Concurrency Control / Atomic CAS at Data Boundary) ---
export async function redeemCouponSurgical(store: CouponStorePort, clock: ClockPort, code: string) {
  const eligible = validateEligibleCoupon(await store.readCoupon(code), clock);
  if (!eligible.ok) return { redeemed: false, reason: eligible.reason };
  const committed = await store.compareAndSwapCoupon(
    code,
    eligible.coupon.version,
    eligible.coupon.remainingUses - 1
  );
  if (!committed) {
    return { redeemed: false, reason: "CONCURRENT_MODIFICATION_CONFLICT" };
  }
  return { redeemed: true };
}

// --- 4. Deterministic Red-Green Harness (Zero sleep() Calls) ---
export async function verifyDeterministicRaceIsolation(): Promise<{
  buggyAllowedCount: number;
  surgicalAllowedCount: number;
}> {
  const frozenClock = new FrozenClock(Date.parse("2026-11-10T12:00:00.000Z"));
  const initialCoupon: CouponRecord = {
    code: "BLACKFRIDAY_SINGLE_USE",
    remainingUses: 1,
    version: 1,
    expiresAtMs: Date.parse("2026-11-10T12:00:01.000Z"),
  };

  const runConcurrentPair = async (
    fn: (store: CouponStorePort, clock: ClockPort, code: string) => Promise<{ redeemed: boolean }>
  ): Promise<number> => {
    const barrier = new DeterministicRendezvousBarrier(2);
    const store = new BarrierInstrumentedCouponStore([initialCoupon], barrier);
    const outcomes = await Promise.all([
      fn(store, frozenClock, initialCoupon.code),
      fn(store, frozenClock, initialCoupon.code),
    ]);
    return outcomes.filter((r) => r.redeemed).length;
  };

  return {
    buggyAllowedCount: await runConcurrentPair(redeemCouponBuggy),
    surgicalAllowedCount: await runConcurrentPair(redeemCouponSurgical),
  };
}
