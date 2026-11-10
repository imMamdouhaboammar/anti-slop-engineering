# Playbook: Microsoft Research & AWS Deterministic Simulation (DST)

A playbook for building and operating deterministic simulation test harnesses for distributed and concurrent software.

## Philosophy: Hermetic World Containment

In traditional systems, code calls external ambient resources:
```
System Code ──> Date.now() / System.currentTimeMillis() (Wall Clock)
System Code ──> Math.random() / crypto.randomBytes() (Ambient Entropy)
System Code ──> net.Socket / fetch() (Host Network)
System Code ──> fs.writeFile() (Host Filesystem)
```
This architecture makes deterministic simulation impossible.

In Microsoft Research (Coyote) and AWS/FoundationDB DST, all ambient dependencies are encapsulated behind deterministic runtime interfaces:

```
                  ┌───────────────────────────────┐
                  │    Simulated Actor / Node     │
                  └───────────────┬───────────────┘
                                  │
    ┌─────────────────────────────┼─────────────────────────────┐
    ▼                             ▼                             ▼
Virtual Clock               Seeded PRNG                  Virtual Network
(Discrete Event Tick)     (Mulberry32/PCG32)           (In-Memory Fault Seam)
```

## Step-by-Step Implementation

### Step 1: Build the Deterministic Virtual Clock
1. Maintain an event priority queue ordered by `(scheduledTimestamp, priority)`.
2. Do not use real physical time; virtual time advances instantaneously to the timestamp of the next event in the queue.
3. Every timeout or delayed message schedules a future event at `currentTime + delayMs`.

### Step 2: Wire the Seeded PRNG
1. Accept a single 64-bit integer or hex seed (`seed: 0xCAFE_BABE`).
2. Derive all subsystem seeds deterministically from the root seed.
3. Ban all calls to `Math.random()`, `crypto.randomUUID()`, or standard library unseeded entropy.

### Step 3: Implement the Fault Injection Seam
Inject faults during message routing and storage operations:
- **Packet Drop:** Generate random float $r \in [0, 1)$. If $r < p_{\text{drop}}$, discard the packet without scheduling delivery.
- **Clock Skew:** Offset message timestamps by an injected drift value $\Delta \in [-\Delta_{\text{max}}, +\Delta_{\text{max}}]$.
- **Message Reordering:** Add a random jitter delay to message delivery events so messages arrive out of sequence.
- **Network Partition:** Maintain a partition graph. If nodes $A$ and $B$ are partitioned, discard all packets between them until the partition is healed at a predetermined virtual timestamp.
- **Node Crash & Recovery:** Abruptly terminate the in-memory state of an actor; schedule a restart event 500 virtual milliseconds later to test replay from the write-ahead log.

### Step 4: Verify Invariants at Every Step
After every discrete event step, run safety assertions:
- **Leader Election:** At most one leader exists per term across the entire cluster.
- **Data Integrity:** Committed state machine transitions are never rolled back or overwritten.
- **Memory Safety:** In-memory queue sizes remain strictly bounded.

### Step 5: Triage and Minimal Repro
When an invariant fails:
1. Note the seed and step count.
2. Re-run the simulation with identical seed; verify the failure reproduces at the exact same step.
3. Bisect or shrink the event sequence to identify the minimal causal interleaving.
