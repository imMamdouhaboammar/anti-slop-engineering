# Usecase: Build a Deterministic Simulator (DST)

Step-by-step workflow for implementing a hermetic Discrete Event Simulator with virtual time and seeded fault injection.

## When to Use
- Testing distributed consensus algorithms (Raft, Paxos, 2PC).
- Validating asynchronous actor systems, job orchestrators, or message queues.
- Verifying fault recovery against network partitions, message reordering, and clock drift.

## Workflow

### 1. Define the Virtual Clock Interface
Replace all system time lookups with an injected clock:
```typescript
export interface VirtualClock {
  now(): number;
  schedule(delayMs: number, priority: number, fn: () => void): number;
}
```

### 2. Instantiate the Seeded PRNG
Initialize a deterministic generator with an explicit 64-bit root seed:
```typescript
const prng = new Mulberry32PRNG(0xCAFE_BABE);
```

### 3. Wire the In-Memory Network Fabric
Route all inter-node communication through a simulated network layer that can:
- Drop packets based on a configured drop rate.
- Delay packets to simulate latency jitter and out-of-order delivery.
- Partition nodes by blocking message delivery between selected subsets.

### 4. Execute the Simulation Loop
Run the discrete event queue until completion or a fixed virtual time horizon:
```typescript
const clock = new DeterministicVirtualClock();
const network = new DeterministicNetworkSimulator(clock, prng, {
  dropProbability: 0.05,
  reorderProbability: 0.1,
});

// Run 10,000 virtual milliseconds of distributed traffic
clock.runUntil(10000);
```

### 5. Assert Invariants
After simulation steps, verify:
- Consistency invariants across all node states.
- Zero unhandled exceptions or deadlocks.
- Bounded queue lengths and message buffers.

### 6. Verify Reproducibility
Record the execution trace. Run the simulation a second time with the exact same seed; verify the trace matches line-by-line.
