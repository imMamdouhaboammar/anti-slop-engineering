# AST & Type-Slop Taxonomies

A catalog of low-evidence, type-eroding, and algorithmic slop patterns in TypeScript/JavaScript codebases, paired with verified zero-slop remediation.

---

## 1. Evidence Fabrication & Type Laundering

### 1.1 `no-chained-type-assertions`
- **Severity**: Blocker
- **Mechanism**: Chaining `as unknown as Target` or `as any as Target`.
- **Anti-pattern**:
  ```ts
  // SLOP: Silencing compiler without validating structure
  const user = input as unknown as User;
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: Parse untrusted data at system boundary
  const user = UserSchema.parse(input);
  ```

### 1.2 `require-safety-comment-for-type-assertion`
- **Severity**: Review
- **Mechanism**: Performing an `as Target` assertion without nearby justification.
- **Anti-pattern**:
  ```ts
  // SLOP: Bare assertion without proof
  const id = value as AccountId;
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: Document the physical invariant
  // SAFETY: parseAccountId verified UUIDv4 format and org prefix before return.
  const id = value as AccountId;
  ```

### 1.3 `no-widen-then-assert`
- **Severity**: Blocker
- **Mechanism**: Widening a known value to `unknown` or `any`, only to assert it back downstream.
- **Anti-pattern**:
  ```ts
  // SLOP: Losing compile-time evidence
  const loaded: User = getUser();
  const cached: unknown = loaded;
  const user = cached as User;
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: Preserve explicit generic constraints or exact types
  const cached: User = getUser();
  ```

---

## 2. Algorithmic Complexity & Allocation Slop

### 2.1 `no-reduce-accumulator-copy`
- **Severity**: Blocker
- **Mechanism**: Copying the accumulator inside `.reduce()` callbacks via `acc.concat()`, `acc.slice()`, or `Object.assign({}, acc)`.
- **Impact**: Transforms linear $O(N)$ operations into quadratic $O(N^2)$ algorithmic bottlenecks.
- **Anti-pattern**:
  ```ts
  // SLOP: Allocating fresh arrays/objects on every item (O(N^2))
  const lookup = items.reduce((acc, item) => Object.assign({}, acc, { [item.id]: item }), {});
  const evens = items.reduce((acc, item) => item % 2 === 0 ? acc.concat([item]) : acc, []);
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: Mutate local accumulator in-place (O(N))
  const lookup = items.reduce((acc, item) => {
    acc[item.id] = item;
    return acc;
  }, {} as Record<string, Item>);

  const evens = items.reduce((acc, item) => {
    if (item % 2 === 0) acc.push(item);
    return acc;
  }, [] as number[]);
  ```

### 2.2 `no-array-filter-map`
- **Severity**: Review
- **Mechanism**: Chaining adjacent eager `.filter().map()` or `.map().filter()` calls.
- **Impact**: Allocates throwaway intermediate arrays in the heap.
- **Anti-pattern**:
  ```ts
  // SLOP: Intermediate array allocated between passes
  const emails = users.filter(u => u.active).map(u => u.email);
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: Lazy iterator helpers (zero intermediate array)
  const emails = users.values()
    .filter(u => u.active)
    .map(u => u.email)
    .toArray();

  // Alternatively: single flatMap
  const emails = users.flatMap(u => u.active ? [u.email] : []);
  ```

### 2.3 `no-conditional-empty-object-spread`
- **Severity**: Review
- **Mechanism**: Spreading conditional empty objects `...(c ? { x } : {})`.
- **Impact**: Generates disposable `{}` objects and deoptimizes V8 hidden classes.
- **Anti-pattern**:
  ```ts
  // SLOP: Polymorphic shape and heap churn
  const options = {
    retries: 3,
    ...(timeout !== undefined ? { timeout } : {}),
  };
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: Explicit conditional property assignment
  const options: RequestOptions = { retries: 3 };
  if (timeout !== undefined) options.timeout = timeout;
  ```

---

## 3. Test-Oracle Erosion & Meta-Naming Slop

### 3.1 `no-module-mocking`
- **Severity**: Blocker
- **Mechanism**: Invoking `vi.mock()` or `jest.mock()` to mock whole module files.
- **Impact**: Masks real breaking changes between modules; tests pass while production crashes.
- **Anti-pattern**:
  ```ts
  // SLOP: Mocking the module that contains the bugs
  vi.mock("./user-repository");
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: In-memory verified test double or dependency injection
  const fakeRepo = new InMemoryUserRepository();
  const service = new UserService(fakeRepo);
  ```

### 3.2 `no-shape-in-symbol-names`
- **Severity**: Review
- **Mechanism**: Appending `Shape` to locally declared types or interfaces.
- **Anti-pattern**:
  ```ts
  // SLOP: Meta-naming distraction
  interface UserProfileShape { id: string; }
  ```
- **Remediation**:
  ```ts
  // ZERO-SLOP: Clean domain modeling
  interface UserProfile { id: string; }
  ```

---

## 4. Effect Architecture Rules

### 4.1 `no-manual-tag-comparison`
- **Anti-pattern**:
  ```ts
  if (res._tag === "Ready") handleReady(res);
  ```
- **Remediation**:
  ```ts
  if (Predicate.isTagged("Ready")(res)) handleReady(res);
  // or Match:
  Match.value(res).pipe(
    Match.when({ _tag: "Ready" }, handleReady),
    Match.orElse(handleOther)
  );
  ```

### 4.2 `no-manual-effect-error-tag`
- **Anti-pattern**:
  ```ts
  program.pipe(
    Effect.catch((err) => err._tag === "NotFound" ? recover : Effect.fail(err))
  );
  ```
- **Remediation**:
  ```ts
  program.pipe(Effect.catchTag("NotFound", () => recover));
  ```
