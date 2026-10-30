# Solution: Google Site Reliability Engineering (SRE) Enforcement

## Problem Statement

AI coding agents often introduce subtle, systemic reliability hazards:
1. **Accidental Complexity (KISS failure):** Creating deeply nested control structures, monolithic functions (>80 lines), and superfluous pass-through wrapper chains that obscure failure semantics.
2. **Duplicated Invariants (DRY failure):** Copy-pasting validation checks, regular expressions, or error schemas across multiple endpoints, leading to divergent bug fixes and silent edge-case regressions.
3. **Speculative Over-Engineering (YAGNI failure):** Generating unused configuration knobs, dead parameter patterns (`_unused_param`, `future_kwargs`), placeholder comments (`TODO(future)`), and dead branches (`if False:`).
4. **Bandaid Engineering & Operational Toil (Scale failure):** Patching async race conditions with arbitrary `sleep()`, retrying network calls without exponential backoff and randomized full jitter (triggering retry storms and thundering herds), spawning unbounded promises/threads, and swallowing exceptions silently (`except: pass`).

## Implemented Architecture

We codified Google SRE discipline (Site Reliability Engineering Book Chapters 5 & 9) into the Anti-Slop Engineering framework through a dual static guard and educational playbook:

```
┌─────────────────────────────────────────────────────────────┐
│                 Anti-Slop Engineering CLI                   │
│          (bunx / npx anti-slop-engineering [cmd])           │
└──────────────────────────────┬──────────────────────────────┘
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    diff_guard.py (Triage)          sre_guard.py (SRE Engine)
    ├── Fast diff regex heuristics  ├── KISS: Nesting & Function Bloat
    ├── Test oracle integrity       ├── DRY: Sliding-window Hashing
    ├── Security & UI checks        ├── YAGNI: Speculative dead code
    └── SRE retry & bandaid hints   └── SCALE: Backoff, Jitter, Toil
```

### Components

1. **`scripts/sre_guard.py`:**
   - Zero-dependency Python 3.9+ static analysis engine.
   - **KISS:** Enforces `max_nesting <= 4` (with bracket-aware line analysis ignoring dictionary/parentheses formatting) and `max_function_lines <= 80`.
   - **DRY:** Detects duplicated code blocks (>=4 normalized lines) across non-test files using sliding-window SHA256 hashes.
   - **YAGNI:** Detects speculative placeholder comments, dead branches (`if False:`), and speculative parameters.
   - **Scale:** Blocks flat retries without exponential backoff/jitter, flags `sleep()` synchronization band-aids, detects unbounded concurrency mapping, blocks silent exception swallowing, and flags misleading static health checks.
2. **`bin/cli.js`:**
   - Universal command dispatcher for `sre` and `sre-guard` subcommands.
   - Deduplicated child process runner fulfilling DRY.
3. **`references/google-sre-discipline.md`:**
   - Comprehensive reference guide covering Simplicity, Single Source of Truth, Anti-Speculation, and Fixing Issues at Scale.
4. **`references/anti-pattern-catalog.md`:**
   - Added Section N: Google SRE Invariants (`SRE-01` through `SRE-12`).
5. **`SKILL.md` & `AGENTS.md`:**
   - Codified Operating Priority 13 and Agent Directive 14 mandating Google SRE discipline across all agent workflows.

## Verification & Proof

- 30/30 unit tests pass via `python3 -m unittest discover -s tests -v`.
- `make check` executes lint, test-verbose, diff_guard, and sre_guard cleanly with 0 SRE blockers and 0 reviews.
- Self-diff verification confirms zero regressions.
