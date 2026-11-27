---
name: hooks-long-playbook
description: "Master architectural playbook for designing, implementing, and governing lifecycle hooks in developer tools, CLIs, agent runtimes, and enterprise products. Covers physical admission control vs. passive warnings, fail-closed security gates, sub-second latency budgeting, stdin/stdout JSON-RPC protocol contracts, session-start caching invariants, and battle-tested hook engine reference implementations across TypeScript/Bun, Python, Go, and Shell."
---

# Hooks Long Playbook (Architectural Design & Engineering Guide)

The **Hooks Long Playbook** is a comprehensive, production-grade engineering manual for software architects, tool builders, and CLI authors who need to design, embed, and govern lifecycle hooks in modern developer tools, agent runtimes, Git workflows, and enterprise platforms.

---

## 1. Core Philosophy & The Six Inviolable Hook Laws

A lifecycle hook is an extension point where an engine yields execution to external logic before, during, or after an operation. Poorly designed hooks cause silent bypasses, flakiness, performance degradation, and security holes.

Every robust hook implementation must strictly adhere to the **Six Inviolable Hook Laws**:

| Law | Axiom | Consequence of Violation |
| :--- | :--- | :--- |
| **1. The Admission Control Axiom** | *A pre-hook without physical deny authority is merely an unheeded suggestion.* | Passive console warnings are statistically ignored by LLMs and rushed developers (The Passive Advisory Trap). |
| **2. The Zero-Latency Budget** | *Inner-loop pre-hooks must execute in $< 200\text{ms}$ (local per-tool) and $< 2,000\text{ms}$ (Git pre-commit).* | Slow hooks incentivize developers to bypass them with `--no-verify`, destroying all quality guarantees. |
| **3. Scoped Isolation Invariant** | *Never inspect the entire workspace when an affected delta (`{staged_files}`, `target_files`, `ast_diff`) is available.* | Quadratic scale explosion: repos with 50,000 files grind to a halt on trivial 1-line edits. |
| **4. Explicit Fail-Closed / Fail-Open Boundary** | *Security, invariant, and integrity gates MUST fail-closed. Non-critical telemetry/metrics MUST fail-open with strict timeouts.* | Broken telemetry blocks core business flows; broken security gates silently allow malicious mutations. |
| **5. Stdio Protocol Purity** | *Machine communication (JSON-RPC) belongs on `stdout`. Human diagnostics, logs, and telemetry belong on `stderr`.* | Stray `console.log` statements corrupt JSON-RPC parsers, crashing LSP, MCP, and CLI tool streams. |
| **6. The Session Caching & Lifetime Invariant** | *If the host snapshots hook definitions at startup, hook definitions and target executables MUST remain immutable for the session duration.* | Mid-session script deletion or dynamic configuration shifts cause fatal execution deadlocks. |

---

## 2. Universal Lifecycle Event Taxonomy

When designing an extensible tool or runtime, map your execution lifecycle to standardized hook event phases:

```
[Session Initialization] ──► SessionStart / PreInit
                                    │
                                    ▼
[User Request / Turn]    ──► PreInvocation
                                    │
    ┌───────────────────────────────┴───────────────────────────────┐
    ▼                                                               ▼
[Tool / Command Call]                                        [Git Commit Flow]
    │                                                               │
    ├─► PreToolUse (Admission: Allow/Deny)                         ├─► PreCommit (Staged diff inspection)
    ├─► [Engine Execution]                                         ├─► CommitMsg (Conventional format)
    ├─► PostToolUse (Observation / Auditing)                       ├─► PrePush (Test & Preflight gates)
    └─► ToolError (Fallback / Telemetry)                           └─► PostCommit (Notification)
                                    │
                                    ▼
[Session Teardown]       ──► SessionEnd / Cleanup
```

### Event Matrix & Responsibilities

| Lifecycle Phase | Ideal Execution Model | Default Policy | Purpose & Practical Use-Case |
| :--- | :--- | :--- | :--- |
| `SessionStart` | Synchronous / Bounded ($< 500\text{ms}$) | Fail-Closed | Cache catalog, verify environment prerequisites, register invariant ledgers. |
| `PreInvocation` | Synchronous ($< 300\text{ms}$) | Fail-Open | Analyze user intent, inject autonomous skills/MCP capabilities into prompt. |
| `PreToolUse` | Synchronous ($< 200\text{ms}$) | **Fail-Closed** | Physical gatekeeper: reject unauthorized writes, check stale remote diffs. |
| `PostToolUse` | Asynchronous / Parallel | Fail-Open | Record audit trail, collect telemetry, trigger background diff analysis. |
| `PreCommit` | Parallel on `{staged_files}` ($< 2\text{s}$) | **Fail-Closed** | Scan for secrets, reject suppression comments (`@ts-ignore`), lint changed files. |
| `CommitMsg` | Synchronous ($< 100\text{ms}$) | **Fail-Closed** | Enforce Conventional Commits (`feat:`, `fix:`, scope length) on commit editmsg. |
| `PrePush` | Parallel ($< 30\text{s}$) | **Fail-Closed** | Execute unit tests and doctor preflight checks before remote transmission. |

---

## 3. Hook Engine Architecture for Products & CLIs

When building a CLI or developer platform that supports third-party or internal hooks (like `anti-slop-engineering`, ESLint, or Docker plugins), build a dedicated **Hook Dispatch Engine**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                          Hook Dispatcher                               │
│                                                                        │
│  1. Discovery: Load `hooks.json` or `.hooks.yaml`                     │
│  2. Matching: Filter hooks by event name & target tool/regex           │
│  3. Execution: Spawn child processes with isolated stdin/stdout        │
│  4. Timeout Guard: Enforce strict `AbortSignal` per hook (e.g. 5s)     │
│  5. Decision Aggregator: Aggregate Allow / Deny verdicts               │
└──────────────────┬──────────────────────────────────┬──────────────────┘
                   │                                  │
          stdin: JSON Payload                stdout: JSON Verdict
                   ▼                                  ▼
         ┌───────────────────┐              ┌───────────────────┐
         │ External Hook (TS)│              │External Hook (Py) │
         └───────────────────┘              └───────────────────┘
```

### Step 1: Configuration Schema Contract (`hooks.json`)

Standardize hook registration so external extensions and users configure hooks declaratively:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "version": "1.0.0",
  "hooks": {
    "PreToolUse": [
      {
        "name": "remote-diff-guard",
        "matcher": "edit_file|write_file",
        "command": "bun run ./hooks/remote-diff-guard.js",
        "timeout_ms": 3000,
        "on_failure": "deny",
        "environment": {
          "STRICT_MODE": "1"
        }
      }
    ],
    "PostToolUse": [
      {
        "name": "audit-logger",
        "matcher": ".*",
        "command": "python3 ./hooks/audit_logger.py",
        "timeout_ms": 1000,
        "on_failure": "ignore"
      }
    ]
  }
}
```

### Step 2: The Hook Communication Protocol (JSON over stdio)

To guarantee language-agnostic interoperability (allowing hooks in Bun, Node, Python, Go, Rust, or Bash):
1. **Host sends execution context via `stdin` as UTF-8 JSON**:
   ```json
   {
     "hook_event": "PreToolUse",
     "session_id": "1c412e63-abaf-474a-9de0-6e117c382188",
     "tool_name": "write_file",
     "tool_input": {
       "Path": "/app/src/index.ts",
       "Content": "const x = 1;"
     },
     "workspace_root": "/Users/user/project",
     "timestamp": "2026-11-27T20:20:00Z"
   }
   ```

2. **Hook replies via `stdout` as UTF-8 JSON**:
   ```json
   {
     "decision": "allow",
     "explanation": "No anti-slop violations detected."
   }
   ```
   Or if denying execution:
   ```json
   {
     "decision": "deny",
     "explanation": "Blocked: File contains unpulled changes on GitHub (HEAD..@{u}). Reconcile with 'git pull --rebase' before editing.",
     "remediation_hint": "git pull --rebase"
   }
   ```

3. **Stderr is reserved for human telemetry**:
   Diagnostics printed to `stderr` are logged in debug mode without corrupting the parser.

---

## 4. Physical Gatekeeping vs. The Passive Advisory Trap

### The Problem: Why Advisory Warnings Fail
AI coding agents and hurried engineers routinely ignore warnings printed to stdout or logs. If an agent executes `write_file` and a hook merely logs:
`"⚠️ Warning: Do not use @ts-ignore"`
The LLM reads the warning as conversational background and continues generating code.

### The Solution: Deterministic Physical Admission Control
A production gatekeeper MUST intercept the execution pipeline:

```
[Agent emits ToolCall]
          │
          ▼
┌──────────────────────────────────────┐
│ Hook Engine evaluates PreToolUse     │
└──────────────────┬───────────────────┘
                   │
         Does hook return "deny"?
        ┌──────────┴──────────┐
      YES                     NO
        │                      │
        ▼                      ▼
┌────────────────────────┐  ┌────────────────────────┐
│ Physically ABORT Tool  │  │ Execute Tool           │
│ Return structured error│  │ Return Tool output     │
│ to Agent with hint     │  └────────────────────────┘
└────────────────────────┘
```

#### Antigravity / Agent Admission Rules:
- Return `{"decision": "deny", "explanation": "..."}` to immediately reject the tool call.
- The engine must NEVER invoke the underlying tool handler when a hook denies.
- The explanation must include a concrete, deterministic remediation action.

#### Git / CLI Admission Rules:
- Exit with non-zero status (`exit 1`) to abort commits, pushes, or tool invocations.
- Cleanly restore any temporary files or lockfiles before exiting.

---

## 5. Performance, Latency Budgeting & Scoped Isolation

Hooks placed in inner loops (such as `PreToolUse` on every file edit, or `pre-commit` on every git save) become unbearable if they run slow tests or scan entire repositories.

### The Scoped Delta Pattern (`{staged_files}`)

Never execute full-repo scanners on local hooks:

```yaml
# ❌ SLOW: Scans 20,000 files on every 1-line commit (takes 25s)
pre-commit:
  commands:
    lint:
      run: npm run lint

# ✅ FAST: Scans only modified files in parallel (takes 0.4s)
pre-commit:
  parallel: true
  commands:
    lint-staged:
      glob: "*.{ts,tsx,js,jsx}"
      run: bunx oxlint -c .oxlintrc.json --deny-warnings {staged_files}
    typecheck-backend:
      glob: "src/**/*.{ts,tsx}"
      run: bunx tsc --noEmit
```

### Latency Budgeting Guidelines

1. **Sub-200ms per PreToolUse**:
   - Use compiled native runtimes (Bun, Node v22, Rust, Go) or fast Python scripts without heavy imports (avoid importing `pandas` or `torch` in a hook!).
2. **Sub-2000ms per Pre-Commit**:
   - Run independent hooks in parallel (`parallel: true`).
   - Isolate file categories using globs so Python linters never run when editing TypeScript files.
3. **Bounded Timeouts**:
   - Always wrap hook child processes with hard timeouts (e.g. 3,000ms). If a hook hangs, kill the process with `SIGKILL` and handle according to the `on_failure` policy (`deny` for security, `ignore` for metrics).

---

## 6. Security, Isolation & Sandboxing

Because hooks execute arbitrary commands on developer machines and CI servers, enforce strict security hygiene:

1. **Banish Shell Argument Injection**:
   - **Never** interpolate file paths or untrusted parameters directly into shell strings:
     ```javascript
     // ❌ CRITICAL VULNERABILITY: Shell Injection via filename
     execSync(`python3 guard.py ${filePath}`);
     ```
   - **Always** pass arguments as discrete arrays or pipe payloads via `stdin`:
     ```javascript
     // ✅ SECURE: Passed via stdin or argument array
     spawn("python3", ["guard.py"], { stdio: ["pipe", "pipe", "inherit"] });
     ```

2. **Symlink Traversal Prevention**:
   - Before executing a hook located at a relative path, resolve its canonical real path (`fs.realpathSync()`). Reject hooks that resolve outside the repository or workspace boundary unless explicitly authorized.

3. **Credential Scrubbing on Hook Errors**:
   - Scrub sensitive patterns (API keys, authorization headers, passwords) from hook error outputs before returning them to the agent or terminal.

---

## 7. The Session Caching & Lifetime Invariant

Host environments (such as Antigravity, IDE extensions, or long-running daemons) load `.agents/hooks.json` or plugin manifests into memory at **Session Boot**:

### The Pitfall:
If you modify `hooks.json` or delete a referenced hook script (e.g. `/tmp/my_hook.py`) while a session is running:
1. The host continues to call the cached hook path.
2. The missing script produces `ENOENT` / Exit Code 2.
3. Every subsequent file modification fails with a host-level deadlock.

### Architectural Invariants:
1. **Fresh Session Verification**: Always verify hook changes in a freshly initialized session.
2. **Atomic Script Lifecycle**: Never delete or replace hook scripts in transient `/tmp` directories while an active session holds references to them. Keep hook scripts inside the repository's tracked directory structure.
3. **No-Op Fallback Resiliency**: If a hook script is missing or encounters internal crashes, write defensive error handlers that log diagnostic output and provide clear recovery instructions.

---

## 8. Language & Runtime Selection Matrix (Agent Decision Tree)

When an agent or engineer is tasked with implementing a new hook, choosing the wrong runtime causes cold-start lag, dependency hell, or distribution failures. Use this deterministic decision framework to select the optimal language for the hook's purpose.

### Performance & Distribution Benchmark

| Criterion | 🦀 Rust | 🐹 Go (Golang) | 🧅 Bun (TypeScript) | 🐍 Python (Stdlib Only) |
| :--- | :--- | :--- | :--- | :--- |
| **Cold Start Latency** | **Fastest** ($< 2\text{ms}$) | **Ultra-Fast** ($1 - 5\text{ms}$) | **Very Fast** ($5 - 15\text{ms}$) | **Moderate** ($30 - 80\text{ms}$) |
| **Distribution** | Single static binary | Single static binary (`CGO=0`) | Requires Bun or `bun build --compile` | Pre-installed on Unix/macOS |
| **Memory Footprint** | Minimal ($< 5\text{MB}$) | Low ($5 - 15\text{MB}$) | Moderate ($20 - 40\text{MB}$) | Moderate ($30 - 60\text{MB}$) |
| **Development Velocity** | Moderate | High | **Highest** (Native TS) | High |
| **JSON & AST Strength** | Unrivaled AST (`oxc`/`syn`) | Great JSON & concurrency | **Native JSON & Web APIs** | Clean `json`/`ast` stdlib |

### Logical Agent Selection Rules

Follow these four rules in order when deciding which language to write a hook in:

1. **Choose `Bun (TypeScript)` for Agent & IDE Lifecycle Hooks (`PreInvocation`, `PreToolUse`, `PostToolUse`):**
   - **Why:** Agent hooks primarily parse JSON-RPC payloads over `stdin`/`stdout`, inspect prompt text or file diffs, and interact with TypeScript/JavaScript ecosystems. Bun provides $<15\text{ms}$ startup, native TypeScript execution without a build step, and rapid iteration.
   - **Examples:** `capability-preflight.js`, `remote-diff-guard.js`, `hook_dispatch.mjs`.

2. **Choose `Go (Golang)` for Distributable Git Hook Runners & CLI Plugin Dispatchers:**
   - **Why:** When building a hook orchestrator or CLI tool distributed to many developers across macOS, Linux, and Windows, Go compiles to a zero-dependency single binary with $1-5\text{ms}$ startup and native Goroutines to fan out parallel checks (`pre-commit`).
   - **Examples:** `Lefthook`, `toil-guard`, CLI hook engines.

3. **Choose `Rust` for Deep AST Parsing, Security Scanners & High-Throughput Rules:**
   - **Why:** If the hook must parse full Abstract Syntax Trees (ASTs) across hundreds of files, verify cryptographic signatures, or scan large diffs under strict $<50\text{ms}$ budgets without memory spikes, Rust is mandatory.
   - **Examples:** `oxlint`, `ruff`, `anti-slop-rust`.

4. **Choose `Python (Standard Library >= 3.9 ONLY)` for Universal Zero-Install Fallbacks:**
   - **Why:** When a hook must run out-of-the-box on any developer machine or CI runner without requiring Bun, Go, or Rust toolchains to be installed.
   - **Strict Condition:** Use **only** Python standard library modules (`sys`, `json`, `re`, `subprocess`, `pathlib`). **Never** require `pip install` or virtual environments (`venv`) inside a hook—third-party imports and venv activation blow past the $200\text{ms}$ latency budget.
   - **Examples:** `diff_guard.py`, `sre_guard.py`, `repo_fortress_guard.py`.

```
[New Hook Task]
      │
      ├─► Is it an Agent / MCP / IDE JSON-RPC hook? ───────────► Bun (TypeScript)
      ├─► Is it a distributable Git/CLI hook orchestrator? ────► Go (Static Binary)
      ├─► Does it require deep AST parsing / heavy scanning? ──► Rust
      └─► Must it run anywhere with zero extra installs? ──────► Python (Stdlib Only)
```

---

## 9. Reference Implementations

The `hooks-long-playbook` includes two complete, production-ready reference implementations:

### 1. TypeScript / Bun Pluggable Hook Engine (`examples/hook-engine.ts`)
A zero-dependency, type-safe hook runner supporting parallel dispatch, bounded timeouts, stdio JSON-RPC, and physical allow/deny decisions.

### 2. Python Robust Hook Engine (`examples/hook_engine.py`)
A standard-library (>=3.9) hook runner with subprocess timeout guards, credential scrubbing, and structured JSON output.

### 3. Universal Drop-in Git Hooks (`references/templates/lefthook.yml`)
The battle-tested pre-commit and commit-msg configuration providing sub-2s execution, anti-suppression diff checks, secret leak detection, and conventional commits enforcement.

---

## 10. Verification & Self-Audit Checklist

Before shipping any tool or product that exposes hooks, verify:

- [ ] **Authority Test**: Does the hook physically halt execution when an invariant fails?
- [ ] **Latency Benchmark**: Does the pre-tool hook complete in $< 200\text{ms}$?
- [ ] **Delta Scope Check**: Does the hook only process changed files/entities rather than whole disk?
- [ ] **Stdio Isolation**: Is JSON-RPC machine data strictly on `stdout` and logs on `stderr`?
- [ ] **Timeout Resilience**: Does a hanging hook cleanly terminate at its timeout without locking the host?
- [ ] **Session Caching Awareness**: Are hook scripts stored in stable, tracked repository paths?
- [ ] **Shell Injection Free**: Are arguments passed via `stdin` or argv arrays without string interpolation?
