# Playbook: State-Machine Modeling & Structure-Aware Fuzzing

Playbook for modeling robust state machines and constructing structure-aware fuzzing harnesses for untrusted input boundaries.

## Pillar 1: State-Machine Formal Modeling

### Step 1: Map the Complete State Transition Matrix
Before writing code, construct the 2D matrix mapping every state and event combination:
1. Define every legitimate state as a distinct type in a tagged union.
2. Define every event as a typed payload.
3. For every cell `(State, Event)`, explicitly declare either a valid transition to `NextState` with side effects or a strict invalid transition rejection.

### Step 2: Enforce Type-Level Elimination of Impossible States
Ban loose boolean flags:
- Prohibit interfaces with multiple independent status flags (`isConnecting`, `isConnected`, `isError`).
- Mandate tagged unions where properties specific to a state exist ONLY in that variant (e.g. `votesAcquired` exists only in `Candidate`, `heartbeatTick` exists only in `Leader`).

### Step 3: Author Generative Model-Based Test Suites
Using `fast-check` or `Hypothesis`:
1. Define commands representing valid API actions.
2. Initialize both the real system and a simple, canonical reference model.
3. Generate arbitrary sequences of 100 to 1,000 commands.
4. Execute each command against both the real system and the reference model; assert strict state equivalence at every step.

---

## Pillar 2: Structure-Aware Fuzzing on Parsers

### Step 1: Identify Untrusted Boundaries
Identify all points of entry:
- JSON/YAML/Protobuf deserializers.
- Custom binary packet or RPC frame decoders.
- URL and query string parsers.
- Authentication token and certificate unpackers.

### Step 2: Build the Grammar-Aware Generator
Do not use dumb bit-flippers. Construct a recursive arbitrary generator matching the input grammar:
- Generate valid tokens, arrays, objects, and nested structures.
- Mutate syntax slightly: inject null bytes, Unicode surrogates, max integer values, empty collections, and extreme nesting depths.

### Step 3: Assert the Four Invariants
Execute the fuzz harness over $\ge 5,000$ iterations and assert:
1. **Crash Freedom:** The parser never throws uncaught panics, unhandled promise rejections, or segfaults. All invalid inputs produce structured error results.
2. **Recursion Bounds:** Inputs exceeding `MAX_DEPTH` (e.g. 16 levels) are rejected cleanly before triggering call stack exhaustion.
3. **Payload Bounds:** Inputs exceeding `MAX_BYTES` (e.g. 1MB) are rejected immediately at the boundary.
4. **Idempotence / Canonicalization:** Parsing and re-serializing a valid payload yields an identical, normalized structure.
