/**
 * Deterministic Simulation and Property Testing Reference Implementation
 *
 * Demonstrates:
 * 1. Seeded Discrete Event Simulation (DST) with Virtual Clock, packet drops, clock skew, and reordering.
 * 2. Property-Based Testing with deterministic generation and automatic shrinking.
 * 3. State-Machine Modeling with impossible states made unrepresentable in the type system.
 * 4. Structure-Aware Fuzzing against an untrusted parser boundary with memory and recursion bounds.
 */

// ============================================================================
// 1. Seeded PRNG & Deterministic Virtual Clock (Discrete Event Simulation)
// ============================================================================

export class Mulberry32PRNG {
  private state: number;

  constructor(seed: number) {
    this.state = seed >>> 0;
  }

  public nextUint32(): number {
    let t = (this.state += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return (t ^ (t >>> 14)) >>> 0;
  }

  public nextFloat(): number {
    return this.nextUint32() / 4294967296.0;
  }

  public nextInt(min: number, max: number): number {
    return Math.floor(this.nextFloat() * (max - min + 1)) + min;
  }

  public choice<T>(items: readonly T[]): T {
    if (items.length === 0) throw new Error("Cannot choose from empty list");
    return items[this.nextInt(0, items.length - 1)];
  }
}

export interface ScheduledEvent {
  id: number;
  timeMs: number;
  priority: number;
  execute: () => void;
}

export class DeterministicVirtualClock {
  private currentTimeMs = 0;
  private nextEventId = 1;
  private queue: ScheduledEvent[] = [];

  public now(): number {
    return this.currentTimeMs;
  }

  public schedule(delayMs: number, priority: number, execute: () => void): number {
    const id = this.nextEventId++;
    const timeMs = this.currentTimeMs + Math.max(0, delayMs);
    this.queue.push({ id, timeMs, priority, execute });
    this.queue.sort((a, b) => (a.timeMs !== b.timeMs ? a.timeMs - b.timeMs : a.priority - b.priority));
    return id;
  }

  public step(): boolean {
    const event = this.queue.shift();
    if (!event) return false;
    this.currentTimeMs = event.timeMs;
    event.execute();
    return true;
  }

  public runUntil(maxTimeMs: number): void {
    while (this.queue.length > 0 && this.queue[0].timeMs <= maxTimeMs) {
      this.step();
    }
  }

  public pendingEventsCount(): number {
    return this.queue.length;
  }
}

// ============================================================================
// 2. Simulated Network with Fault Injection (Drops, Skew, Reordering)
// ============================================================================

export interface NetworkPacket<T> {
  senderId: string;
  recipientId: string;
  payload: T;
  sequenceNumber: number;
}

export class DeterministicNetworkSimulator<T> {
  private dropProbability: number;
  private reorderProbability: number;
  private maxClockSkewMs: number;
  private partitions = new Set<string>(); // "A:B" means partitioned

  constructor(
    private clock: DeterministicVirtualClock,
    private prng: Mulberry32PRNG,
    options: {
      dropProbability?: number;
      reorderProbability?: number;
      maxClockSkewMs?: number;
    } = {}
  ) {
    this.dropProbability = options.dropProbability ?? 0.05;
    this.reorderProbability = options.reorderProbability ?? 0.1;
    this.maxClockSkewMs = options.maxClockSkewMs ?? 200;
  }

  public setPartition(nodeA: string, nodeB: string, enabled: boolean): void {
    const key = [nodeA, nodeB].sort().join(":");
    if (enabled) {
      this.partitions.add(key);
    } else {
      this.partitions.delete(key);
    }
  }

  public send(packet: NetworkPacket<T>, deliver: (p: NetworkPacket<T>) => void): void {
    const partitionKey = [packet.senderId, packet.recipientId].sort().join(":");
    if (this.partitions.has(partitionKey)) {
      return; // Partition: packet dropped silently
    }

    if (this.prng.nextFloat() < this.dropProbability) {
      return; // Fault injection: packet drop
    }

    let delay = this.prng.nextInt(10, 50);
    if (this.prng.nextFloat() < this.reorderProbability) {
      delay += this.prng.nextInt(60, 200); // Fault injection: reorder delay
    }

    const clockSkew = this.prng.nextInt(-this.maxClockSkewMs, this.maxClockSkewMs);
    const effectiveDelay = Math.max(1, delay + clockSkew);

    this.clock.schedule(effectiveDelay, packet.sequenceNumber, () => {
      deliver(packet);
    });
  }
}

// ============================================================================
// 3. State-Machine Modeling (Impossible States Unrepresentable via Type System)
// ============================================================================

export type RaftState =
  | { readonly kind: "Follower"; readonly term: number; readonly votedFor: string | null }
  | { readonly kind: "Candidate"; readonly term: number; readonly votesAcquired: ReadonlySet<string> }
  | { readonly kind: "Leader"; readonly term: number; readonly heartbeatTick: number }
  | { readonly kind: "Terminated"; readonly term: number; readonly reason: string };

export type RaftEvent =
  | { readonly type: "ElectionTimeout"; readonly candidateId: string }
  | { readonly type: "VoteReceived"; readonly fromNode: string; readonly voteGranted: boolean }
  | { readonly type: "HigherTermDiscovered"; readonly higherTerm: number }
  | { readonly type: "HeartbeatTick" }
  | { readonly type: "Shutdown"; readonly reason: string };

export interface TransitionResult {
  readonly nextState: RaftState;
  readonly sideEffects: readonly string[];
}

export function transition(currentState: RaftState, event: RaftEvent, clusterSize: number): TransitionResult {
  // Global invariant: HigherTermDiscovered forces immediate step-down to Follower from any state
  if (event.type === "HigherTermDiscovered") {
    if (event.higherTerm > currentState.term) {
      return {
        nextState: { kind: "Follower", term: event.higherTerm, votedFor: null },
        sideEffects: ["PersistTerm", "ResetElectionTimer"],
      };
    }
    return { nextState: currentState, sideEffects: [] };
  }

  if (event.type === "Shutdown") {
    return {
      nextState: { kind: "Terminated", term: currentState.term, reason: event.reason },
      sideEffects: ["CancelTimers", "CloseSockets"],
    };
  }

  switch (currentState.kind) {
    case "Follower": {
      if (event.type === "ElectionTimeout") {
        const nextTerm = currentState.term + 1;
        const votes = new Set<string>([event.candidateId]);
        return {
          nextState: { kind: "Candidate", term: nextTerm, votesAcquired: votes },
          sideEffects: ["BroadcastRequestVote", "ResetElectionTimer"],
        };
      }
      return { nextState: currentState, sideEffects: [] };
    }

    case "Candidate": {
      if (event.type === "VoteReceived" && event.voteGranted) {
        const updatedVotes = new Set(currentState.votesAcquired).add(event.fromNode);
        const quorumNeeded = Math.floor(clusterSize / 2) + 1;
        if (updatedVotes.size >= quorumNeeded) {
          return {
            nextState: { kind: "Leader", term: currentState.term, heartbeatTick: 0 },
            sideEffects: ["BroadcastAppendEntriesHeartbeat", "AcquireLeaderLease"],
          };
        }
        return {
          nextState: { kind: "Candidate", term: currentState.term, votesAcquired: updatedVotes },
          sideEffects: [],
        };
      }
      if (event.type === "ElectionTimeout") {
        const nextTerm = currentState.term + 1;
        return {
          nextState: { kind: "Candidate", term: nextTerm, votesAcquired: new Set([event.candidateId]) },
          sideEffects: ["BroadcastRequestVote", "ResetElectionTimer"],
        };
      }
      return { nextState: currentState, sideEffects: [] };
    }

    case "Leader": {
      if (event.type === "HeartbeatTick") {
        return {
          nextState: { kind: "Leader", term: currentState.term, heartbeatTick: currentState.heartbeatTick + 1 },
          sideEffects: ["BroadcastAppendEntriesHeartbeat"],
        };
      }
      return { nextState: currentState, sideEffects: [] };
    }

    case "Terminated":
      return { nextState: currentState, sideEffects: [] };
  }
}

// ============================================================================
// 4. Property-Based Testing with Automatic Shrinking
// ============================================================================

export interface Arbitrary<T> {
  generate(prng: Mulberry32PRNG): T;
  shrink(value: T): Iterable<T>;
}

export const ArbInt = (min: number, max: number): Arbitrary<number> => ({
  generate: (prng) => prng.nextInt(min, max),
  shrink: function* (value: number) {
    if (value === 0) return;
    const target = 0;
    const half = Math.trunc((value - target) / 2);
    if (half !== 0) yield value - half;
    yield target;
  },
});

export const ArbAsciiString = (minLength: number, maxLength: number): Arbitrary<string> => ({
  generate: (prng) => {
    const len = prng.nextInt(minLength, maxLength);
    let str = "";
    for (let i = 0; i < len; i++) {
      str += String.fromCharCode(prng.nextInt(32, 126));
    }
    return str;
  },
  shrink: function* (value: string) {
    if (value.length > minLength) {
      yield value.slice(0, Math.floor(value.length / 2));
      yield value.slice(0, value.length - 1);
    }
  },
});

export function assertProperty<T>(
  arbitrary: Arbitrary<T>,
  predicate: (val: T) => boolean,
  options: { runs: number; seed: number }
): { passed: boolean; counterexample?: T; runsCompleted: number } {
  const prng = new Mulberry32PRNG(options.seed);
  for (let run = 1; run <= options.runs; run++) {
    const sample = arbitrary.generate(prng);
    if (!predicate(sample)) {
      // Automatic shrinking loop to minimal failing counterexample
      let smallest = sample;
      let shrank = true;
      while (shrank) {
        shrank = false;
        for (const candidate of arbitrary.shrink(smallest)) {
          if (!predicate(candidate)) {
            smallest = candidate;
            shrank = true;
            break;
          }
        }
      }
      return { passed: false, counterexample: smallest, runsCompleted: run };
    }
  }
  return { passed: true, runsCompleted: options.runs };
}

// ============================================================================
// 5. Structure-Aware Fuzzing on Parsers & Deserializers
// ============================================================================

export interface UntrustedPayload {
  command: "READ" | "WRITE" | "DELETE" | "PING";
  key: string;
  value?: string;
  metadata?: Record<string, string>;
  nestedDepth?: number;
}

export function parseUntrustedPayload(raw: string, maxBytes = 65536, maxDepth = 8): UntrustedPayload {
  if (raw.length > maxBytes) {
    throw new Error("Payload exceeds byte limit");
  }
  const parsed: unknown = JSON.parse(raw);
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Malformed JSON: root must be an object");
  }

  const record = parsed as Record<string, unknown>;
  const cmd = record.command;
  if (cmd !== "READ" && cmd !== "WRITE" && cmd !== "DELETE" && cmd !== "PING") {
    throw new Error(`Invalid command: ${String(cmd)}`);
  }

  if (typeof record.key !== "string" || record.key.length === 0 || record.key.length > 256) {
    throw new Error("Invalid or missing key");
  }

  if (record.metadata !== undefined) {
    if (!record.metadata || typeof record.metadata !== "object" || Array.isArray(record.metadata)) {
      throw new Error("Invalid metadata: must be an object");
    }
  }

  // Validate depth to eliminate recursive allocation bombs
  function checkDepth(obj: unknown, currentDepth: number): void {
    if (currentDepth > maxDepth) throw new Error("Recursion depth exceeded");
    if (obj && typeof obj === "object") {
      for (const val of Object.values(obj)) {
        checkDepth(val, currentDepth + 1);
      }
    }
  }
  checkDepth(parsed, 1);

  return parsed as UntrustedPayload;
}

export function structureAwareFuzzHarness(prng: Mulberry32PRNG, iterations: number): { crashes: number; rejections: number } {
  const commands = ["READ", "WRITE", "DELETE", "PING", "CORRUPT", "", null, 42];
  let crashes = 0;
  let rejections = 0;

  for (let i = 0; i < iterations; i++) {
    const rawObj: Record<string, unknown> = {
      command: prng.choice(commands),
      key: prng.nextFloat() < 0.2 ? 12345 : prng.choice(["normal_key", "x".repeat(300), ""]),
    };

    if (prng.nextFloat() < 0.3) {
      // Mutate structure with deep nesting
      let nested: Record<string, unknown> = {};
      const depth = prng.nextInt(1, 15);
      for (let d = 0; d < depth; d++) {
        nested = { child: nested };
      }
      rawObj.metadata = nested;
    }

    const payloadString = JSON.stringify(rawObj);

    try {
      parseUntrustedPayload(payloadString, 65536, 8);
    } catch (err: unknown) {
      if (err instanceof Error) {
        rejections++; // Valid error rejection
      } else {
        crashes++; // Non-standard throw or fatal crash
      }
    }
  }

  return { crashes, rejections };
}
