# Clean-Room Reconnaissance & Architectural Synthesis

This document records the clean-room reverse-engineering analysis of four reference systems in accordance with the `/rea` protocol:
1. **Ponytail** (`DietrichGebert/ponytail`)
2. **Stop That Shit** (`lennney/stop-that-shit`)
3. **Ponytail Lite** (`ilindaniel/ponytail-lite`)
4. **Boring Engineering** (`alvindemesadev/boring-engineering`)

No code from any reference repository is copied or decompiled. Only functional mechanisms, behavioural taxonomies, and architectural design patterns are synthesized into native high-performance microservices.

---

## 1. Functional Taxonomy & Core Invariants

### 1.1 Stop That Shit (The SHIT Taxonomy)
- **S — Scope Creep:** Modifying modules, configuration files, or infrastructure unrelated to the primary issue or explicit task contract.
- **H — Hypothetical Hardening & Unread Hashes:** Emitting companion checksum files (`.sha256`, `.md5`) with zero downstream readers, defensive compatibility wrappers for imaginary future consumers, and swallowing errors without diagnostics.
- **I — Intent Violation:** Executing state-mutating file edits or system changes during read-only review, audit, or diagnostic tasks.
- **T — Task Thrashing:** Repetitive re-reading, circular diff generation, or continuous multi-agent spawning without changing program state or progressing acceptance criteria.

### 1.2 Ponytail & Ponytail Lite (The Senior Engineer Ladder)
- **Core Principle:** The best code is the code you never wrote. Write only what the task requires without sacrificing correctness, security, or validation.
- **Decision Ladder:**
  1. *Existence Check:* Does this feature/file strictly need to exist?
  2. *Codebase Reuse:* Does an existing function, helper, or component in the repository already solve this?
  3. *Standard Library First:* Does the standard library or platform runtime provide a built-in method?
  4. *Native Platform Feature:* Does the browser or OS runtime natively support the affordance (e.g. HTML5 `<input type="date">`)?
  5. *Installed Dependency:* Does an existing pinned dependency provide the utility before adding new dependencies?
  6. *Single-Expression / Direct Expression:* Can this be written simply and directly without ceremony?
  7. *Minimal Sufficient Implementation:* Write only the necessary, tested code.

### 1.3 Boring Engineering (Practical Decision System)
- **YAGNI Filter:** Strict binary gate—if not explicitly required by the active task, do not build it.
- **KISS Standard ("Name the Built-In"):** Prior to authoring custom parsing, formatting, validation, or retry logic, the agent must identify the runtime built-in. Hand-rolling standard primitives is classified as an anti-pattern.
- **Practical DRY 3-Point Abstraction Barrier:**
  A shared abstraction is permitted if and only if:
  1. The duplicate logic appears in >=2 real, existing call sites (not speculative).
  2. All call sites would require identical modifications if the underlying logic evolved.
  3. The abstraction can be accurately named without coordinating conjunctions (`and`, `or`).

---

## 2. Microservice Architecture Mapping

```
                                +-----------------------------+
                                |      CLI & Agent Entry      |
                                |       (bin/cli.js)          |
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
      |   - Rule-based diff checks   |                    | • Prometheus /metrics Server |
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

### 2.1 Rust Microservice (`services/anti-slop-rust`)
- **Focus:** Regex-based diff triage for scope, speculative hardening, and read-only intent, plus simple built-in replacement checks.
- **Key Modules:**
  - `src/shit_interceptor.rs`: Scope creep detection, unread checksum/hash generation checks, speculative try-catch error swallowing, and file boundary guards.
  - `src/ladder_auditor.rs`: Regex-based built-in replacement suggestions and conjunction naming hints.
  - `src/server.rs`: Lightweight HTTP microservice (`axum` + `tokio`) exposing `/health`, `/v1/triage`, `/v1/shit-check`, and `/v1/ladder-audit`.
  - `src/main.rs`: High-performance CLI interface powered by `clap`.

### 2.2 Go Microservice (`services/toil-guard-go`)
- **Focus:** Concurrent repository-wide stream analysis, Google SRE metric verification (KISS, DRY, YAGNI, Scale), automated toil detection, and SLI/SLO budget verification.
- **Key Modules:**
  - `pkg/sre/complexity.go`: Control flow nesting level (<=4) and function length (<=80 lines) verification.
  - `pkg/sre/dry.go`: Sliding-window token hash scanner across files.
  - `pkg/sre/toil.go`: SRE anti-pattern heuristics (blind sleep synchronization, fixed retry loops, and silent error swallowing).
  - `pkg/sre/sli.go`: Error budget calculation and slop index scoring.
  - `pkg/server/server.go`: Production Go HTTP microservice with graceful shutdown, `/healthz`, `/metrics`, and `/v1/audit`.
  - `cmd/toil-guard/main.go`: Multi-subcommand CLI runner (`audit`, `stream`, `serve`).
