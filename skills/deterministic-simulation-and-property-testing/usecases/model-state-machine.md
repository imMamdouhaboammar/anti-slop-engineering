# Usecase: Model State Machines & Prevent Impossible States

Step-by-step workflow for formal state-machine modeling and compile-time impossible state elimination.

## When to Use
- Managing complex lifecycles (payments, order processing, authentication, network connections).
- Refactoring loose boolean flags into deterministic finite state machines.
- Validating state transitions against invalid concurrent events.

## Workflow

### 1. Identify Valid States & Unique Payloads
Define each state as a distinct type variant in a tagged union:
```typescript
export type AuthState =
  | { readonly kind: "Unauthenticated" }
  | { readonly kind: "Authenticating"; readonly challengeId: string; readonly expiresAt: number }
  | { readonly kind: "Authenticated"; readonly sessionToken: string; readonly user: UserProfile }
  | { readonly kind: "Locked"; readonly reason: string; readonly lockedUntil: number };
```

### 2. Define Explicit Transition Function
Implement a pure, total transition function mapping `(State, Event) -> (NextState, SideEffects)`:
```typescript
export function handleAuthEvent(state: AuthState, event: AuthEvent): { next: AuthState; effects: Effect[] } {
  switch (state.kind) {
    case "Unauthenticated":
      if (event.kind === "StartLogin") {
        return {
          next: { kind: "Authenticating", challengeId: event.challengeId, expiresAt: Date.now() + 60000 },
          effects: [sendChallengeEffect(event.challengeId)],
        };
      }
      return { next: state, effects: [] };
    // Handle remaining states exhaustively
  }
}
```

### 3. Author Generative Model-Based Test
Generate random sequences of valid and invalid events:
```typescript
test("state machine handles random event sequences without violating security invariants", () => {
  fc.assert(
    fc.property(fc.array(arbAuthEvent, { minLength: 10, maxLength: 100 }), (events) => {
      let state: AuthState = { kind: "Unauthenticated" };
      for (const event of events) {
        const { next } = handleAuthEvent(state, event);
        // Safety invariant: Never transition to Authenticated without a valid session token
        if (next.kind === "Authenticated") {
          expect(next.sessionToken).toBeTruthy();
        }
        state = next;
      }
    }),
    { numRuns: 2000 }
  );
});
```
