// SPDX-License-Identifier: MIT
// Example: Expand -> Migrate -> Contract Dual-Write Repository, Keyset Backfill & Stripe-Style Wire Adapter

import { z } from "zod";

// --- 1. Tolerant Reader Boundary Schema (Accepts Version N and Version N-1 Payloads) ---
export const UpsertUserWireSchema = z
  .object({
    id: z.string().uuid(),
    givenName: z.string().trim().min(1).max(120).optional(),
    familyName: z.string().trim().min(1).max(120).optional(),
    // Retained for backward compatibility: Version N server accepts Version N-1 requests
    fullName: z.string().trim().min(1).max(240).optional(),
  })
  .strict()
  .refine(
    (payload) => Boolean((payload.givenName && payload.familyName) || payload.fullName),
    { message: "Wire contract requires either (givenName + familyName) or legacy fullName" }
  );

export type UpsertUserWireInput = z.infer<typeof UpsertUserWireSchema>;

export interface CanonicalUserRecord {
  id: string;
  givenName: string;
  familyName: string;
  /** @deprecated Populated via dual-write during Phase 1 & Phase 2 until Phase 3 contraction */
  fullName: string;
}

// --- 2. Bidirectional Wire Normalizer (Upcaster & Downcaster) ---
export function normalizeUserInput(raw: unknown): CanonicalUserRecord {
  const parsed = UpsertUserWireSchema.parse(raw);

  if (parsed.givenName && parsed.familyName) {
    return {
      id: parsed.id,
      givenName: parsed.givenName,
      familyName: parsed.familyName,
      fullName: `${parsed.givenName} ${parsed.familyName}`,
    };
  }

  const parts = (parsed.fullName ?? "").split(/\s+/);
  const givenName = parts[0] || "Unknown";
  const familyName = parts.slice(1).join(" ") || "Unknown";

  return {
    id: parsed.id,
    givenName,
    familyName,
    fullName: parsed.fullName ?? `${givenName} ${familyName}`,
  };
}

// Conservative Writer: Emits both new fields (for N) and legacy field (for N-1 forward compatibility)
export function serializeUserResponse(record: CanonicalUserRecord, apiVersion = "2026-11-10") {
  if (apiVersion < "2026-11-10") {
    return {
      id: record.id,
      fullName: record.fullName || `${record.givenName} ${record.familyName}`,
    };
  }
  return {
    id: record.id,
    givenName: record.givenName,
    familyName: record.familyName,
    fullName: record.fullName || `${record.givenName} ${record.familyName}`,
  };
}

// --- 3. Database Adapter Seam & Out-of-Band Keyset Backfill ---
export interface MigrationDatabasePort {
  upsertDualWrite(record: CanonicalUserRecord, signal: AbortSignal): Promise<void>;
  fetchUnmigratedBatch(afterId: string, limit: number, signal: AbortSignal): Promise<Array<{ id: string; full_name: string }>>;
  applyBackfillBatch(updates: readonly CanonicalUserRecord[], signal: AbortSignal): Promise<number>;
  getReplicationLagMs(signal: AbortSignal): Promise<number>;
}

export interface BackfillOptions {
  batchSize?: number;
  baseDelayMs?: number;
  maxReplicationLagMs?: number;
}

export async function runThrottledKeysetBackfill(
  db: MigrationDatabasePort,
  options: BackfillOptions = {}
): Promise<{ totalMigrated: number; batchesProcessed: number }> {
  const batchSize = Math.min(options.batchSize ?? 1000, 5000);
  const baseDelayMs = Math.max(options.baseDelayMs ?? 100, 10);
  const maxLagMs = options.maxReplicationLagMs ?? 2000;

  let cursorId = "00000000-0000-0000-0000-000000000000";
  let totalMigrated = 0;
  let batchesProcessed = 0;

  while (true) {
    const lagMs = await db.getReplicationLagMs(AbortSignal.timeout(2000));
    if (lagMs > maxLagMs) {
      const pauseMs = baseDelayMs * 4 + Math.floor(Math.random() * baseDelayMs);
      await new Promise((resolve) => setTimeout(resolve, pauseMs));
      continue;
    }

    const rows = await db.fetchUnmigratedBatch(cursorId, batchSize, AbortSignal.timeout(5000));
    if (rows.length === 0) {
      break;
    }

    const updates = rows.map((row) =>
      normalizeUserInput({ id: row.id, fullName: row.full_name })
    );

    const updatedCount = await db.applyBackfillBatch(updates, AbortSignal.timeout(5000));
    totalMigrated += updatedCount;
    batchesProcessed += 1;
    cursorId = rows[rows.length - 1]!.id;

    const jitteredSleep = baseDelayMs + Math.floor(Math.random() * baseDelayMs);
    await new Promise((resolve) => setTimeout(resolve, jitteredSleep));
  }

  return { totalMigrated, batchesProcessed };
}
