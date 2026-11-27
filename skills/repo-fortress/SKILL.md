---
name: repo-fortress
description: "Universal zero-tolerance repository fortification, anti-suppression gating, static-analysis hardening, and automated release engine. Use whenever auditing, hardening, or cleaning up a polyglot codebase, setting up sub-2-second git hooks (Lefthook), enforcing strict commitlint conventions, configuring zero-tolerance anti-suppression CI/CD pipelines (GitHub Actions), eliminating thousands of linter/type errors without cheating (no @ts-ignore, no eslint-disable, no as unknown as, no silent catch), or building multi-arch production Docker images with automated SemVer (Release Please). Applicable to TypeScript, Bun, Node, Python, Rust, Go, and Monorepos."
---

# Repo Fortress (Universal Repository Fortification & Quality Convergence)

Repo Fortress is a sovereign, zero-tolerance engineering framework designed to harden any software repository into an unassailable quality fortress. It eliminates the root causes of static analysis failures, enforces compile-time and runtime soundness, and erects a three-tier defense shield that physically prevents AI coding agents and human contributors from bypassing quality gates.

---

## When to Activate This Skill

- **Repository Hardening & Convergence**: Bringing 500 to 5,000+ linter and type errors down to absolute zero (`0 errors, 0 warnings`) across a polyglot codebase without regressions.
- **Setting Up Git Quality Gates**: Installing lightning-fast (<2s) pre-commit hooks (`lefthook`), commit message standards (`commitlint`), and secret leak blockers.
- **Configuring Zero-Tolerance CI/CD**: Erecting GitHub Actions pipelines featuring an autonomous `anti-suppression-guard` that physically blocks PRs introducing suppression comments or type laundering.
- **Automated SemVer & Release Pipeline**: Scaffolding Google `release-please` for monorepos/standalone repos linked to multi-architecture production Docker builds with supply-chain provenance attestations.
- **Eliminating AI Cheating**: Auditing and cleansing existing codebases of `@ts-ignore`, `eslint-disable`, `oxlint-disable`, `# noqa`, `as unknown as`, and silent `catch {}` blocks.

---

## The Five Anti-Cheating Invariants (ZERO TOLERANCE)

AI coding agents habitually bypass linters and type-checkers when faced with massive error volumes. Repo Fortress enforces five inviolable laws:

| Invariant | Prohibited Anti-Pattern | Mandatory Remediation Protocol |
| :--- | :--- | :--- |
| **1. Anti-Suppression** | `// eslint-disable`, `// oxlint-disable`, `@ts-ignore`, `@ts-expect-error`, `# noqa`, `# type: ignore` | Solve the underlying type or logic violation. If a rule produces false positives due to modern runtime upgrades (e.g. React 19 JSX Transform), perform **Framework Alignment** at the config level, never inline suppressions. |
| **2. Zero Type-Laundering** | `as unknown as T`, non-null assertions (`!`), raw `as ConcreteType` | Implement runtime schema validation, discriminated unions, user-defined type guards (`is`), or narrow port interfaces. |
| **3. Zero Silent Catches** | `catch {}`, `.catch(() => {})`, `except Exception: pass` | Type the caught error, log with structured context (with credential scrubbing), or rethrow cleanly. If fire-and-forget is required, log safely before `void`. |
| **4. Strictness Directionality** | Disabling rules, weakening tsconfig flags, adding source dirs to ignore lists | Linter and compiler configurations may ONLY be made **stricter**, never looser. Only generated build artifacts (`dist/`, `node_modules/`, `.data/`) belong in ignore files. |
| **5. Root-Cause Logic Fixes** | Blindly prefixing unused variables with `_` to silence linters | Investigate the variable. If it reveals dead code, delete it; if it reveals an unawaited side effect or an unwired parameter, wire it into domain logic. |

---

## The Three-Tier Enforcement Architecture

Repo Fortress establishes three independent, complementary defense tiers:

```
[Developer / Agent Workspace]
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│ TIER 1: Local Lightning Hooks (Lefthook + Commitlint)       │
│ • Runs in < 2 seconds on {staged_files} only                │
│ • Anti-Suppression Diff Guard on staged changes             │
│ • Pre-commit fast lint (Oxlint / Ruff) + Secret leak regex   │
│ • Commit-msg Conventional Commits validation                │
│ • Pre-push fast unit tests & CLI preflight diagnostics      │
└─────────────────────────────────────────────────────────────┘
        │ git push
        ▼
┌─────────────────────────────────────────────────────────────┐
│ TIER 2: Remote CI Quality Gate (GitHub Actions)             │
│ • Dedicated anti-suppression-guard diffing BASE_SHA vs HEAD │
│ • Parallel multi-language matrix jobs (TS, Python, Docker) │
│ • Strict zero-warnings policy across 100% of the repository │
│ • Security audit & static dependency vulnerability scan     │
└─────────────────────────────────────────────────────────────┘
        │ merge to main
        ▼
┌─────────────────────────────────────────────────────────────┐
│ TIER 3: Release & Delivery Shield (Release Please + GHCR)   │
│ • Conventional Commits parse → Automated SemVer & Changelog │
│ • Multi-stage, multi-arch Docker build (amd64 + arm64)      │
│ • Smart cross-compilation (--platform=$BUILDPLATFORM for UI)│
│ • Non-root execution + tini PID 1 graceful shutdown         │
│ • GitHub Actions supply-chain provenance attestation        │
└─────────────────────────────────────────────────────────────┘
```

---

## The 4-Phase Convergence Playbook

When tasked with fortifying a repository or resolving hundreds/thousands of static analysis violations, execute this disciplined 4-phase playbook:

### Phase 1: Repository Baseline Audit & Inventory
1. Inspect the root manifests, workspaces, package managers, and toolchains (`package.json`, `tsconfig.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Dockerfile`).
2. Run baseline checks without modifying files and record exact metrics:
   - Total linter errors & warnings.
   - Total TypeScript/compiler errors.
   - Dead code and unused exports (e.g. via `knip` or equivalent).
   - Existing inline suppression count (`grep -r "disable\|ignore\|noqa"`).
   - Test suite pass/fail counts.

### Phase 2: Compiler & Linter Hardening + Framework Alignment
1. **Enable Maximum Strictness**:
   - TypeScript: `"strict": true`, `"noUncheckedIndexedAccess": true`, `"noImplicitReturns": true`, `"noFallthroughCasesInSwitch": true`, `"noImplicitOverride": true`, `"noUnusedLocals": true`, `"noUnusedParameters": true`.
   - Python: Enable Ruff rules `E, F, W, B` (bugbear), `S` (bandit security), `UP` (pyupgrade), `SIM` (simplify), `RUF`. Run `mypy --strict`.
   - Linters (Oxlint / ESLint / Clippy / Golangci-lint): Enable `typescript`, `unicorn`, `import`, `promise`, `jsx-a11y`, `pedantic`, and `perf` categories.
2. **Framework Alignment vs Rule Weakening**:
   - Distinguish legacy false positives from genuine bugs. For instance:
     - Disabling `react/react-in-jsx-scope` in React 19 / modern JSX runtime is **Framework Alignment** (not weakening).
     - Disabling `no-floating-promises` or `no-explicit-any` is **Weakening** (strictly prohibited).

### Phase 3: Module-by-Module Root-Cause Remediation
Remediate violations in isolated, domain-specific batches following this strict priority hierarchy:

#### Priority P0: Async & Runtime Correctness
- **Floating Promises (`no-floating-promises`)**: Always `await` asynchronous calls where execution order or resource cleanup matters (sockets, DB writes, SSE broadcasts). Where fire-and-forget background execution is genuine, attach `.catch((err) => ...)` with credential scrubbing, and apply `void` *only* after rejection is handled.
- **Unnecessary Awaits (`await-thenable`)**: Strip redundant `await` from synchronous calls after verifying the callee signature.
- **Unsafe String Interpolation (`no-base-to-string`)**: Fix `${unknownOrObject}` interpolations using structured formatters (`err instanceof Error ? err.message : String(...)`).

#### Priority P1: Type Soundness & Structural Boundaries
- **Unsafe Casts (`no-unsafe-type-assertion`)**: Replace `as ConcreteType` with lightweight runtime type guards (`isType`), Zod/ArkType schema decoders, or discriminated unions.
- **Potentially Undefined Accesses**: For array/record lookups under `noUncheckedIndexedAccess`, use genuine bounds checks and deterministic fallbacks—never non-null assertions (`!`).
- **Test Fixtures & Mocks**: Replace partial mock casts (`as unknown as TargetPort`) with typed factory helpers, narrow port interfaces, or `satisfies`.

#### Priority P2: Dead Code & Asset Optimization
- **Knip Triage**: Cross-check unused exports against CLI entrypoints, dynamic imports, and framework routes before pruning.
- **Bundle Optimization**: Configure manual Rollup/Vite chunks to resolve vendor bloat warnings cleanly.

### Phase 4: Mandatory 0-Warning Verification Gate
Execute the entire verification matrix. Declare completion **only** when all commands return Exit Code 0:
1. Strict Linter across all workspaces (`0 errors, 0 warnings`).
2. Strict Type-Checking across all workspaces (`0 errors`).
3. Complete Test Suite passing (`0 failures`).
4. Production Build passing with zero chunk warnings.
5. Repository Preflight/Doctor diagnostics green.
6. Clean Git Diff (`git diff --check` returns 0).

---

## Universal Project Templates & Scaffolding

Repo Fortress includes drop-in templates for all three tiers:

### Tier 1: Local Pre-Commit & Commitlint (`lefthook.yml`)
Place in repository root:
```yaml
min_version: 1.7.0
no_tty: true

commit-msg:
  commands:
    commitlint:
      run: bunx commitlint --edit {1} # or npx commitlint

pre-commit:
  parallel: true
  commands:
    anti-suppression:
      exclude: "(^tests/|\\.md$|^lefthook\\.yml$|^\\.github/workflows/)"
      run: |
        VIOLATIONS=$(git diff --cached -U0 -- {staged_files} | grep -E '^\+.*(oxlint-disable|eslint-disable|@ts-ignore|@ts-expect-error|# noqa|# type:\s*ignore|as unknown as)' || true)
        if [ -n "$VIOLATIONS" ]; then
          echo "❌ Blocked: Forbidden lint/type suppression or 'as unknown as' detected:"
          echo "$VIOLATIONS"
          exit 1
        fi

    secrets-check:
      exclude: "(\\.env\\.example$|\\.lock$)"
      run: |
        LEAKS=$(git diff --cached -U0 -- {staged_files} | grep -E '^\+.*(AIza[0-9A-Za-z-_]{35}|sk-[A-Za-z0-9]{20,}|ghp_[A-Za-z0-9]{36})' || true)
        if [ -n "$LEAKS" ]; then
          echo "❌ Blocked: Potential hardcoded API secret detected in staged changes!"
          exit 1
        fi

    lint-staged:
      glob: "*.{ts,tsx,js,jsx,mjs,cjs}"
      run: bunx oxlint -c .oxlintrc.json --deny-warnings {staged_files}

    typecheck:
      glob: "**/*.{ts,tsx}"
      run: bunx tsc --noEmit

pre-push:
  parallel: true
  commands:
    tests:
      run: bun test # or npm test / pytest / cargo test
```

### Tier 2: Remote CI Quality Gate (`.github/workflows/lint-gate.yml`)
```yaml
name: Strict Quality Gate
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

concurrency:
  group: lint-gate-${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: true

jobs:
  anti-suppression-guard:
    name: Anti-Suppression Diff Guard
    runs-on: ubuntu-latest
    if: github.event_name == 'pull_request'
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Scan PR diff for forbidden suppressions
        run: |
          BASE_SHA="${{ github.event.pull_request.base.sha }}"
          HEAD_SHA="${{ github.event.pull_request.head.sha }}"
          FORBIDDEN_PATTERN='^\+.*(oxlint-disable|eslint-disable|@ts-ignore|@ts-expect-error|# noqa|# type:\s*ignore|as unknown as)'
          VIOLATIONS=$(git diff -U0 "$BASE_SHA" "$HEAD_SHA" -- \
            ':!.github/workflows/lint-gate.yml' \
            ':!*.md' \
            ':!tests/**' | grep -E "$FORBIDDEN_PATTERN" || true)
          if [ -n "$VIOLATIONS" ]; then
            echo "::error::Forbidden suppression or type-laundering detected in PR diff:"
            echo "$VIOLATIONS"
            exit 1
          fi
          echo "Clean diff — zero forbidden suppressions introduced."

  polyglot-gate:
    name: Multi-Stack Parallel Gate
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      # Language setup steps (Bun, Python uv, Rust, Go)
      # Run linters with --deny-warnings, typecheck, tests, and build
```

### Tier 3: Release Please & Supply-Chain Containerization
- `release-please-config.json` + `.release-please-manifest.json` for SemVer tracking.
- `.github/workflows/release-please.yml` combining changelog generation and multi-arch Docker image publishing to `ghcr.io` with `actions/attest-build-provenance`.

---

## Sovereign CLI Automation Helper

Repo Fortress includes an autonomous zero-dependency Python script to inspect any project and scaffold the three-tier quality shield in seconds:

```bash
# Run from repository root
python3 ~/.agents/skills/repo-fortress/scripts/init_fortress.py --all
```

Flags supported:
- `--hooks`: Scaffold `lefthook.yml` and `commitlint.config.mjs`.
- `--ci`: Scaffold `.github/workflows/lint-gate.yml` tailored to detected stacks.
- `--release`: Scaffold `release-please` manifests and workflow.
- `--docker`: Scaffold production multi-stage multi-arch `Dockerfile` and `docker-compose.yml`.
- `--all`: Scaffold the complete 3-Tier quality fortress.
- `--dry-run`: Preview generated files without writing.
