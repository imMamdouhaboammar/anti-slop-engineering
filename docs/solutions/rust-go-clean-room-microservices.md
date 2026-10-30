# Solution: Clean-Room Rust & Go Microservices for Anti-Slop Engineering

## Problem
AI coding agents frequently suffer from four distinct failure modes:
1. **Scope Creep & Boundary Violation:** Arbitrarily rewriting adjacent modules or config files when tasked with a targeted bugfix.
2. **Hypothetical Hardening & Companion Hashes:** Authoring unread `.sha256` or `.md5` companion files, speculative compatibility factories, or swallowing errors.
3. **Intent Violations:** Mutating repository state when read-only review, audit, or diagnostic intent was specified.
4. **Task Thrashing & Over-Engineering:** Re-reading the same files, generating redundant classes instead of naming platform built-ins, and ignoring Google SRE simplicity, single source of truth, and toil elimination invariants.

Existing solutions in the ecosystem like Ponytail, Stop-That-Shit, Ponytail-Lite, and Boring-Engineering provide valuable philosophical concepts (the lazy senior dev, the SHIT taxonomy, boring engineering decision ladders), but often exist as isolated plugins or prompt-only files.

## Architecture & Clean-Room Implementation
We synthesized these core mechanisms using the clean-room `/rea` (Reverse Engineer Anything) methodology without copying code or inheriting plugin baggage:

```
                            +-----------------------------+
                            |       CLI & Agent Entry     |
                            |         (bin/cli.js)        |
                            +--------------+--------------+
                                           |
                 +-------------------------+-------------------------+
                 |                                                   |
                 v                                                   v
  +------------------------------+                    +------------------------------+
  |      Rust Engine / Daemon    |                    |       Go Engine / Daemon     |
  |   (services/anti-slop-rust)  |                    |    (services/toil-guard-go)  |
  +------------------------------+                    +------------------------------+
  | • SHIT Boundary Interceptor  |                    | • Google SRE Stream Analyzer |
  |   - Scope Creep Detector     |                    | • Concurrency & Toil Guard   |
  |   - Hypothetical Hardening   |                    | • Sliding-Window DRY Scanner |
  |   - Intent Violation Gate    |                    | • SLI/SLO Error Budget Engine|
  |   - Task Thrashing Watcher   |                    | • Prometheus /metrics Server |
  | • Senior Dev Ladder Auditor  |                    | • HTTP REST Service (/v1/..) |
  | • Axum REST Server (/v1/..)  |                    +------------------------------+
  +------------------------------+                                   |
                 |                                                   |
                 +-------------------------+-------------------------+
                                           |
                                           v
                            +-----------------------------+
                            | Zero-Dependency Python Core |
                            | (scripts/diff_guard.py &    |
                            |  scripts/sre_guard.py)      |
                            +-----------------------------+
```

### 1. Rust Microservice Engine (`services/anti-slop-rust`)
- **Technology Stack:** Rust (2021 edition), `clap` (derive CLI), `serde` / `serde_json`, `regex`, `tokio`, and `axum`.
- **SHIT Interceptor (`src/shit_interceptor.rs`):**
  - `STS-S01`: Enforces strict file boundaries and catches unrequested path mutations.
  - `STS-I01`: Flags any diff additions when read-only intent is active.
  - `STS-H01`: Catches unread companion hash creation (`createHash('sha256')`, companion `.sha256` files).
  - `STS-H02`: Detects silent error swallowing (`catch (e) {}`, `except Exception: pass`).
  - `STS-H03`: Flags speculative multi-tier `Base*` and `Abstract*` adapter hierarchies.
- **Ladder Auditor (`src/ladder_auditor.rs`):**
  - `BORING-KISS-01`: Flags hand-rolled math-random UUIDs in favor of `crypto.randomUUID()`.
  - `BORING-KISS-02`: Flags hand-rolled query string splitters in favor of `new URLSearchParams()`.
  - `BORING-KISS-03`: Flags `JSON.parse(JSON.stringify())` in favor of `structuredClone()`.
  - `BORING-DRY-01`: Flags class/function names with conjunctions (`And` / `Or`) indicating mixed responsibilities.
- **Axum Microservice Daemon (`src/server.rs`):**
  - Exposes `/health`, `/v1/triage`, `/v1/shit-check`, and `/v1/ladder-audit`.

### 2. Go SRE Microservice Engine (`services/toil-guard-go`)
- **Technology Stack:** Go 100% standard library (`net/http`, `context`, `sync`, `os/exec`, `regexp`, `encoding/json`).
- **KISS Complexity Analyzer (`pkg/sre/complexity.go`):**
  - Flags nesting depth > 4 levels (`SRE-KISS-NESTING`).
  - Flags function length > 80 lines (`SRE-KISS-FUNC-LEN`).
- **Sliding-Window DRY Token Scanner (`pkg/sre/dry.go`):**
  - Rolling window of size >= 4 lines across all files detecting exact duplicate logic.
- **Toil & Scale Detector (`pkg/sre/toil.go`):**
  - Flags blind sleep synchronization (`SRE-SCALE-SLEEP`).
  - Flags fixed retry loops without exponential backoff and jitter (`SRE-SCALE-RETRY`).
  - Flags silent error swallowing (`SRE-SCALE-SWALLOW`).
  - Flags speculative placeholder comments (`SRE-YAGNI-SPECULATIVE`).
- **SLI / SLO Error Budget Engine (`pkg/sre/sli.go`):**
  - Generates slop index and calculates remaining error budget.
- **Microservice Daemon (`pkg/server/server.go`):**
  - Exposes `/healthz`, Prometheus `/metrics`, `/v1/audit`, and `/v1/sli-budget`.

### 3. Unified Orchestration (`bin/cli.js` & `Makefile`)
- Polyglot execution with automatic fallbacks:
  - `bunx anti-slop-engineering rust triage`
  - `bunx anti-slop-engineering toil audit`
  - `bunx anti-slop-engineering serve-rust --port 9091`
  - `bunx anti-slop-engineering serve-go --port 9092`
  - Falls back gracefully to standard library Python guards if native binaries have not been compiled.

## Verification
- **Python Test Suite:** 30 unit tests passing (`python3 -m unittest discover -s tests -v`).
- **Rust Test Suite:** 7 unit tests passing (`cargo test` in `services/anti-slop-rust`).
- **Go Test Suite:** 7 unit tests passing (`go test -v ./...` in `services/toil-guard-go`).
- **Total Test Suite:** 44 verified automated unit tests passing across all three runtimes.
- **Self-Diff Verification:** Zero blockers on self-scan (`python3 scripts/diff_guard.py --base HEAD` and `python3 scripts/sre_guard.py --base HEAD`).
