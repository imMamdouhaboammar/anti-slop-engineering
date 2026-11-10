# Type Slop Remediation Playbook

A structured execution playbook for diagnosing, isolating, and eliminating type-level and AST slop from TypeScript and JavaScript codebases.

---

## Step 1: Pre-Commit Diff Triage

Before committing changes, execute the zero-dependency AST Guard:

```bash
bunx anti-slop-engineering ast --base HEAD --json
```

- If `verdict == "FAIL"`: Blocker findings exist (e.g. chained casts, reducer copies, module mocks). Halting commit is mandatory.
- If `verdict == "REVIEW"`: Actionable improvements identified (e.g. eager `.filter().map()` chains, missing `// SAFETY:` comments).

---

## Step 2: Eliminating Chained Type Assertions

1. Identify the unparsed boundary where external input enters the application.
2. Replace `as unknown as T` with a runtime schema validator:
   ```ts
   // Before
   export function parsePayload(data: unknown): UserPayload {
     return data as unknown as UserPayload;
   }

   // After
   import { z } from "zod";

   const UserPayloadSchema = z.object({
     id: z.string().uuid(),
     role: z.enum(["admin", "member", "guest"]),
   });

   export function parsePayload(data: unknown): UserPayload {
     return UserPayloadSchema.parse(data);
   }
   ```

---

## Step 3: Fixing Quadratic Reducer Copies

Search for accumulator copies within `.reduce()`:
- `Object.assign({}, acc, ...)`
- `acc.concat(...)`
- `acc.slice()`

Replace with direct mutations on the fresh local accumulator:
```ts
// Before
const index = items.reduce((acc, item) => ({ ...acc, [item.id]: item }), {});

// After
const index = items.reduce((acc, item) => {
  acc[item.id] = item;
  return acc;
}, {} as Record<string, Item>);
```

---

## Step 4: Adopting Lazy Iterator Pipelines

Replace eager consecutive `.filter().map()` chains with native JS iterator helpers:
```ts
// Before: Allocates intermediate array
const activeTitles = posts.filter(p => p.published).map(p => p.title);

// After: Zero intermediate allocation
const activeTitles = posts.values()
  .filter(p => p.published)
  .map(p => p.title)
  .toArray();
```

---

## Step 5: Replacing Module Mocks with In-Memory Doubles

When testing services that depend on external systems:
1. Define a narrow TypeScript interface for the dependency.
2. Implement an in-memory test fake.
3. Inject the fake in tests instead of calling `vi.mock()`.

```ts
// Before (Fragile Oracle)
vi.mock("../db/user-store");

// After (High-Fidelity Contract)
class InMemoryUserStore implements UserStore {
  private users = new Map<string, User>();
  async findById(id: string) { return this.users.get(id) ?? null; }
  async save(user: User) { this.users.set(user.id, user); }
}

const fakeStore = new InMemoryUserStore();
const service = new UserService(fakeStore);
```
