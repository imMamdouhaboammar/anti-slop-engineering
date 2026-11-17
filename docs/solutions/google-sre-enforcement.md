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

## Enforcement tiers

| Capability | Activation | Evidence and limits |
| --- | --- | --- |
| Tier 1, local static review | Run `python3 scripts/diff_guard.py --base <ref> --json` and `python3 scripts/sre_guard.py --base <ref> --json` in a checkout. Git and Python 3.9+ are required. | Looks for supported patterns and emits findings and scope limits. The scripts require no Python packages, compiler, service, or registry. A report applies to the files it scanned. Inspect the Diff Guard untracked-file notice before relying on coverage. |
| Tier 1, CI gate | Set `--fail-on-blocker` for Diff Guard and `--strict` for SRE Guard, or configure the repository CI audit gate. | Diff Guard exits 2 on any blocker. SRE Guard `--strict` exits 2 on active-diff blockers in Git diff mode (pre-existing out-of-diff findings remain non-blocking) and on any blocker with `--files`. Both scripts exit 1 on a failed Git inspection. Default scans return zero when they completed, including findings. An unavailable revision is an error. Unified audit applies a 60-second timeout per child and records a timed-out guard as incomplete/error. Full audit has no measured total latency bound. |
| Tier 2, dynamic evidence | Enable a provider or local verifier explicitly. Provider policy must identify the permitted actions, inputs, isolation, output location, and wall/CPU budgets. | Availability depends on a tested provider and environment. Post-action, commit-boundary, and advisory checks provide evidence at their own boundaries. Only a verified pre-action hook that can deny the action constitutes prevention. Record actual execution and diagnostics even when the expected toolchain binary exists. |

Tier 1 can run by itself in an offline checkout. Keep Tier 2 disabled unless its adapter and permissions are verified for the selected environment. A running service, compiler adapter, hook, or sandbox cannot stand in for an unavailable Tier 1 result. Preserve actual execution states. An unavailable provider, timeout, failed isolation probe, or missing dependency is inconclusive for intended dynamic behavior. Keep any runtime artifact in a disposable directory, record bounded diagnostics and provenance, and leave network access and telemetry disabled unless explicitly enabled by the operator. Where a provider supports test-only access, verify the restrictions before invoking the test.

For a Tier 2 runtime fixture, record the isolation probe, elapsed time, dependency-call count, and recovery result. The opt-in Go lookup fixture in [#81](https://github.com/imMamdouhaboammar/anti-slop-engineering/issues/81) tracks the native implementation.

### Measured Tier 1 cost

Wall time includes Python startup, Git queries and JSON formatting. The test used five serial runs per cell, an Apple M4 arm64 Mac, Python 3.14.6, the repository's release commit `5af649d`, and network-denied execution. The fixtures started with tracked regular Python files of one line each and replaced them with per-file numeric assignments. Larger projects and real code can differ.

| Fixture | Diff Guard median / max | SRE Guard median / max |
| --- | ---: | ---: |
| 3 changed files, 9 added lines | 0.291 s / 0.356 s | 0.269 s / 0.322 s |
| 100 changed files, 10,000 added lines | 0.552 s / 0.575 s | 0.395 s / 0.437 s |

Both guards returned zero in those runs. Replacing the base with an unavailable revision made both return 1. A separate loopback-bind canary was denied under the same network profile. The table is a measurement, with no cross-host latency commitment.

Reproduce the workloads and verify the invalid-revision behavior from a repository checkout.

```bash
python3 -I -S scripts/benchmark_static_guards.py --samples 5
python3 -m unittest discover -s tests -p test_audit_runner_failures.py -v
```

The benchmark generates two disposable Git repositories, runs the fixed Python guards with Git system and user configuration disabled, and emits JSON with interpreter, Git, host, scan counts, elapsed time and invalid-revision outcomes. Each child has an eight-second measurement deadline, and a timeout, failed Git fixture or unexpected guard result makes the benchmark inconclusive. The benchmark needs only Git and Python. The failure suite runs the audit coordinator with fixed failing and timing-out child fixtures.

For a network-denied reproduction on macOS, wrap the benchmark with `sandbox-exec -p '(version 1)(allow default)(deny network*)' ...`. The benchmark's raw timings vary between hosts and run conditions.
