# Anti-Slop Engineering Rules for Antigravity

> Operating rules, architectural invariants, and behavioral guidelines enforced by the Anti-Slop Engineering Plugin.

## 1. Autonomous Preflight & Tool Routing (Gate 0)
- **Zero User-Prompt Requirement**: Never wait for the user to @mention tools or ask permission to use anti-slop capabilities. Infer domain intent automatically.
- **State Selection Briefly**: State the selected tools/guards in 1 concise line before execution, then proceed directly to technical action.
- **Dedicated MCP & CLI Integration**: Prefer native `anti_slop_*` MCP tools and the `anti-slop-engineering` CLI over ad-hoc scripts.

## 2. GitHub-First Remote Diff Guard (GitHub >> Local >> GitHub)
- **Never Edit Blindly**: Before modifying files in any repository tracking a remote, verify remote status.
- **Hard Block on Stale Files**: If remote contains newer unpulled commits (`HEAD..@{u}`), reconcile with `git pull --rebase` before modifying code.
- **Local Diff Verification**: Always inspect `git diff` and run local guards before pushing.

## 3. The Google Site Reliability Engineering (SRE) Mandate
- **KISS (Simplicity)**: Maintain control flow nesting depth <= 4 levels. Decompose functions > 80 lines into cohesive, single-responsibility units. Ban unnecessary wrapper layers.
- **DRY (Single Source of Truth)**: Consolidate duplicate code blocks (>= 4 lines) and duplicate validation schemas into canonical modules.
- **YAGNI (Zero Speculative Complexity)**: Ban speculative parameters (`_unused_param`, `future_kwargs`), dead branches (`if False:`), and placeholder comments (`TODO(future)`).
- **Fix Issues at Scale (Toil Elimination)**: Never use flat retries or blind `sleep()` synchronization band-aids; implement exponential backoff with full jitter. Bound concurrency with pools or semaphores. Ban silent exception swallowing (`except Exception: pass`). Enforce idempotency on all state mutations.

## 4. Clean-Room Senior Dev Ladder & SHIT Interceptors
- Intercept the four SHIT hazards before writing code:
  - **S**cope creep: Reject unrequested features, premature optimizations, and unrequested abstraction layers.
  - **H**ypothetical hardening: Do not add defense against scenarios that cannot occur in the current architecture.
  - **I**ntent violation: Solve the underlying user problem, not just the literal symptom.
  - **T**ask thrashing: Maintain focus on the discrete next action; avoid hopping between unrelated files.
- Climb the Senior Dev Ladder: Verify necessity -> Reuse codebase helpers -> Prioritize standard library built-ins -> Prefer native platform features -> Use existing dependencies -> Emit minimal sufficient code.
- **Name the Built-in**: Never hand-roll primitives provided by runtime/platform (`crypto.randomUUID()`, `URLSearchParams`, `structuredClone()`, etc.).

## 5. Type-Level & AST Slop Gate
- Eliminate chained type assertions (`as unknown as T`).
- Eliminate ungrounded assertions (`as T` without nearby `// SAFETY:` invariant justification).
- Eliminate quadratic reducer accumulator copies (`acc = { ...acc, [k]: v }` inside `.reduce()`).
- Eliminate conditional empty spreads (`...(condition ? { key: value } : {})`).
- Eliminate test-oracle erosion via module mocking (`vi.mock()`, `jest.mock()`); prefer dependency injection and real lightweight doubles.

## 6. Comment Budget & Obviousness Mandate (Zero-Obviousness & CCR Invariant)
- Enforce Comment-to-Code Ratio ($\text{CCR} \le 0.35$).
- Ban syntax play-by-play narration comments (`// increment i`, `// return result`, `// loop through items`).
- Protect formal contracts: `// SAFETY:` invariants, JSDoc/TSDoc docstrings, Rust `///` doc comments, and license headers are strictly preserved.

## 7. Apple Craft, Interaction Physics & WCAG 2.2 Contrast
- Enforce Exhaustive UI State Matrices: `loading_skeleton`, `empty`, `partial_error`, `offline`, and `optimistic_rollback` via Discriminated Unions.
- Zero Cumulative Layout Shift ($CLS = 0.000$): Pre-reserve geometry for skeletons, images, dynamic error slots, and specify `scrollbar-gutter: stable`.
- Interruptible Physics: Compositor-only transforms (`transform`, `opacity`), cancellation on user interruption, and epsilon-terminated `requestAnimationFrame` ($\epsilon \le 10^{-4}$).
- Accessible Contrast: Normal text must meet $\ge 4.5:1$ contrast ratio; large text must meet $\ge 3:1$ against backgrounds under WCAG 2.2 AA.

## 8. Zero-Trust & 10M Concurrent Scale (Paranoid Principal)
- Parse, never validate: All external untrusted inputs must pass through schema boundaries (Zod/ArkType/Valibot).
- Distributed Idempotency: All state-changing mutations must support `Idempotency-Key` headers backed by atomic store operations.
- Constant-Time Cryptography: Token and signature comparisons must use `crypto.timingSafeEqual()`.
- RFC 9457 Problem Details: All error payloads must return machine-readable problem details (`type`, `title`, `status`, `detail`, `instance`).

## 9. Mandela Test-Oracle Elimination
- Hunt down the 8 Mandela Leakage Patterns:
  1. Tautological assertions (`expect(true).toBe(true)`).
  2. Swallowed assertion errors (`try { expect(...) } catch {}`).
  3. Circular mock confirmation (mocks verifying mocks).
  4. Benchmark leakage in training/eval sets.
  5. Frame-injected evals.
  6. Empty assertions.
  7. Unasserted side effects.
  8. Self-grading verification loops.

## 10. Musk 5-Step Reduction & Add-Back Ledger
- Question every requirement (who said it, why is it needed).
- Delete unnecessary code, dependencies, and steps before attempting to optimize.
- Simplify and optimize only what remains.
- Accelerate cycle times.
- Automate repetitive toil.
- Maintain Add-Back rate target between 10% and 25% in `.anti-slop/add-back-ledger.jsonl`.

## 11. NVIDIA Re0 Context Reset & Cold-Read Shower Test
- Keep agent state notes dense and bounded ($\le 1,500$ tokens).
- Maintain 4 canonical sections: `OBJECTIVE`, `PROVEN_INVARIANTS`, `NEGATIVE_CORPUS`, `NEXT_SINGLE_ACTION`.
- The Shower Test: Any fresh agent or human reading the state note in isolation must be able to understand the entire context and immediately execute the next action without guessing.

## 12. Upstream Invariant Backpropagation
- Never merely patch downstream symptoms.
- Downstream code failures, test rejections, and slop findings must be backpropagated to upstream rules (`rules/AGENTS.md`, `.anti-slop/invariant-ledger.json`).
