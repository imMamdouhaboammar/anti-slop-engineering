// SPDX-License-Identifier: MIT
// Example: Meta/Google Mechanical Sympathy — Allocation & P99 Micro-Benchmark Harness, O(1) Bounded Streaming, Zero-Allocation Hot Loop & Single-Roundtrip Batched I/O

export interface TenantConfig {
  readonly tenantId: string;
  readonly feeBasisPoints: number;
  readonly active: boolean;
}

export interface RawSettlementRecord {
  readonly id: string;
  readonly tenantId: string;
  readonly grossCents: number;
}

export interface BatchedSqlBulkExecutor {
  executeUnnestSettlementUpdate(
    ids: readonly string[],
    tenantIds: readonly string[],
    netCents: Int32Array,
    count: number
  ): Promise<void>;
}

export interface PipelinedCounterSink {
  flushTenantTotals(totalsByTenant: ReadonlyMap<string, number>): Promise<void>;
}

export interface MicroBenchmarkSummary {
  readonly iterations: number;
  readonly p50Ms: number;
  readonly p99Ms: number;
  readonly allocBytesPerOp: number;
}

export function indexActiveTenants(tenants: readonly TenantConfig[]): Map<string, number> {
  const feeBpsByTenant = new Map<string, number>();
  for (let i = 0; i < tenants.length; i++) {
    const t = tenants[i];
    if (t.active) {
      feeBpsByTenant.set(t.tenantId, t.feeBasisPoints);
    }
  }
  return feeBpsByTenant;
}

export class ReusableSettlementBatchBuffer {
  readonly ids: string[];
  readonly tenantIds: string[];
  readonly netCents: Int32Array;
  readonly totalsByTenant: Map<string, number>;
  readonly capacity: number;
  length = 0;

  constructor(capacity: number) {
    this.capacity = capacity;
    this.ids = new Array<string>(capacity);
    this.tenantIds = new Array<string>(capacity);
    this.netCents = new Int32Array(capacity);
    this.totalsByTenant = new Map<string, number>();
  }

  reset(): void {
    this.length = 0;
    this.totalsByTenant.clear();
  }

  pushRecord(id: string, tenantId: string, netAmountCents: number): boolean {
    const idx = this.length;
    this.ids[idx] = id;
    this.tenantIds[idx] = tenantId;
    this.netCents[idx] = netAmountCents;
    this.length = idx + 1;

    const prevTotal = this.totalsByTenant.get(tenantId) ?? 0;
    this.totalsByTenant.set(tenantId, prevTotal + netAmountCents);
    return this.length >= this.capacity;
  }
}

export function aggregateBatchZeroAlloc(
  records: readonly RawSettlementRecord[],
  feeBpsByTenant: ReadonlyMap<string, number>,
  scratchBuffer: ReusableSettlementBatchBuffer
): number {
  scratchBuffer.reset();

  for (let i = 0; i < records.length; i++) {
    const rec = records[i];
    const feeBps = feeBpsByTenant.get(rec.tenantId);
    if (feeBps === undefined) continue;

    const feeCents = Math.floor((rec.grossCents * feeBps) / 10_000);
    const netAmount = rec.grossCents - feeCents;
    scratchBuffer.pushRecord(rec.id, rec.tenantId, netAmount);
  }

  return scratchBuffer.length;
}

export async function processSettlementStreamBatched(
  chunks: AsyncIterable<readonly RawSettlementRecord[]>,
  tenants: readonly TenantConfig[],
  sqlExecutor: BatchedSqlBulkExecutor,
  counterSink: PipelinedCounterSink,
  batchCapacity = 1000
): Promise<{ readonly processedRows: number; readonly ioRoundtrips: number }> {
  const feeBpsByTenant = indexActiveTenants(tenants);
  const buffer = new ReusableSettlementBatchBuffer(batchCapacity);
  let processedRows = 0;
  let ioRoundtrips = 0;

  const flushBatch = async (): Promise<void> => {
    if (buffer.length === 0) return;
    await sqlExecutor.executeUnnestSettlementUpdate(
      buffer.ids,
      buffer.tenantIds,
      buffer.netCents,
      buffer.length
    );
    await counterSink.flushTenantTotals(buffer.totalsByTenant);
    processedRows += buffer.length;
    ioRoundtrips += 2;
    buffer.reset();
  };

  for await (const chunk of chunks) {
    for (let i = 0; i < chunk.length; i++) {
      const rec = chunk[i];
      const feeBps = feeBpsByTenant.get(rec.tenantId);
      if (feeBps === undefined) continue;

      const feeCents = Math.floor((rec.grossCents * feeBps) / 10_000);
      const isFull = buffer.pushRecord(rec.id, rec.tenantId, rec.grossCents - feeCents);
      if (isFull) {
        await flushBatch();
      }
    }
  }

  await flushBatch();
  return { processedRows, ioRoundtrips };
}

export function runPercentileAndAllocBenchmark(
  operation: () => void,
  nowNanoseconds: () => number,
  readHeapUsedBytes: () => number,
  warmupRuns = 50,
  sampleRuns = 200
): MicroBenchmarkSummary {
  for (let i = 0; i < warmupRuns; i++) {
    operation();
  }

  const latenciesMs = new Float64Array(sampleRuns);
  const heapStart = readHeapUsedBytes();

  for (let i = 0; i < sampleRuns; i++) {
    const t0 = nowNanoseconds();
    operation();
    const t1 = nowNanoseconds();
    latenciesMs[i] = (t1 - t0) / 1_000_000;
  }

  const heapEnd = readHeapUsedBytes();
  latenciesMs.sort();

  const p50Idx = Math.floor(sampleRuns * 0.5);
  const p99Idx = Math.floor(sampleRuns * 0.99);
  const totalBytes = Math.max(0, heapEnd - heapStart);

  return {
    iterations: sampleRuns,
    p50Ms: Number(latenciesMs[p50Idx].toFixed(4)),
    p99Ms: Number(latenciesMs[p99Idx].toFixed(4)),
    allocBytesPerOp: Math.round(totalBytes / sampleRuns),
  };
}
