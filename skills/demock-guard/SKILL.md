---
name: demock-guard
description: Detect and eliminate test doubles on production paths, silent dummy fallbacks (e.g. SQLite fallbacks in Supabase apps), fail-open authorization gates, and placeholder stubs.
license: MIT
metadata:
  version: "1.7.0"
  parent: anti-slop-engineering
---

# Demock & Silent-Fallback Guard

> Eliminate phantom mocks on live paths, silent exception swallowing with dummy data, and fake persistence fallbacks.

## Why This Skill Is Needed & Target State

AI code generators often insert silent fallbacks to make a broken system appear to work:
1. Falling back to local SQLite or in-memory dictionaries when a database connection fails (hiding outages and creating data split-brain).
2. Catch blocks that swallow exceptions and return dummy empty arrays or mock objects (`catch { return [{ id: 1, name: "Sample" }]; }`).
3. Instantiating `Mock*` or `Fake*` doubles in non-test runtime modules.
4. Security/auth checks that return `true` when credentials or tokens are missing.

The target state is fail-closed, honest engineering: production paths either execute their real dependencies or surface explicit, actionable failures with exact RFC 9457 error contracts.

## Invariant Rules

1. **Fail-Closed by Default:** External dependency outages must never be silently masked with dummy fallback objects. Fail closed or degrade gracefully with visible caller-facing status.
2. **Zero Test Doubles in Runtime:** `Mock*`, `MagicMock`, `Fake*`, and test framework doubles are strictly banned in production files.
3. **No Auth Bypass:** Missing credentials must return 401/403 or throw `AuthenticationError`, never return `true`.

## CLI Usage

```bash
# Scan git diff against base commit
bunx anti-slop-engineering demock --base HEAD

# Scan specific files or directories with JSON output
bunx anti-slop-engineering demock src/ --json --strict
```
