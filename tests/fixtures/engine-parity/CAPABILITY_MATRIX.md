# Engine Parity Capability Matrix

## Runtime ownership

| Runtime | Owned behavior | Portable behavior |
| --- | --- | --- |
| Node | CLI routing and installation, chooses native binaries when available | Python commands remain directly runnable. |
| Python | Portable Git checks, SRE and record checks, unified audit | Standard-library scripts exercise required behavior without native engines. |
| Rust | Structural triage, read-only intent and file scope checks | Python Diff Guard covers documented heuristic triage. Native-only options return a capability error when unavailable. |
| Go | Native SRE analysis, SLI reporting and optional serve/stream | Python SRE covers documented audit operations. Native-only daemon/stream requests require Go. |

[Tested capability and rule fixture](contracts.json)

The fixture identifies one canonical owner for the observed error-swallow, blind-sleep, flat-retry, deep-nesting, and unbounded-concurrency rules, and records alternate implementations with their actual IDs and severities. Different decisions are preserved by parity tests during migration. New shared-rule records must link to a fixture, declare one owner, and register each engine and emitted identifier once. Overlaps without independent evidence remain listed as current behavior in this matrix.

## `anti-slop-rust triage` ↔ `scripts/diff_guard.py`

| Contract / Behavior | `anti-slop-rust triage` | `scripts/diff_guard.py` | Classification |
| :--- | :--- | :--- | :--- |
| Clean diff (`0` changes vs `--base`) | Exits `0`, `summary.status == "PASSED"`, `total_findings == 0` | Exits `0`, `status == "no-heuristic-findings"`, `findings == []` | Shared |
| Invalid or missing Git `--base` ref | Exits non-zero, writes error to `stderr` | Exits `1`, emits error JSON (`--json`) or `ERROR:` | Shared |
| Swallowed exception (`except Exception: pass`, `catch (e) {}`) | Emits `STS-H02` (`Blocker`), exits `1` | Emits `ERROR_SWALLOW_CANDIDATE` (`review`), `status == "review-required"` | Shared detection (severity differs intentionally) |
| Deletion-only diff | Exits `0` (unless `--read-only` / scope violation) | Exits `0`, `summary.deleted_lines > 0` | Shared |
| Renamed file (`git mv`) | Parses diff without panic | Parses diff without crash | Shared |
| Whitespace & non-ASCII filenames | Parses diff without panic | Parses diff without crash | Shared |
| Scope creep (`--allowed`), read-only (`--read-only`), Ladder/Comment/Attention/Demock/StyleSeed/Tagore | Enforced (`STS-S01`, `STS-I01`, `BORING-*`, etc.) | Not implemented | Native-only (Rust) |
| Test-skipping blocker (`SKIPPED_TEST`), `LARGE_DIFF_REVIEW`, `TEST_CHANGE_REVIEW`, doc/UI copy checks | Not implemented (`--fail-on-blocker` not applicable) | Enforced (`--fail-on-blocker` exits `2` on `blocker`) | Fallback-only (Python) |
| Flat retry in counted loops (`SRE_SCALE_FLAT_RETRY`) | Not implemented | Enforced (`review`) | Fallback-only (Python) |

## `toil-guard audit` ↔ `scripts/sre_guard.py`

| Contract / Behavior | `toil-guard audit` | `scripts/sre_guard.py` | Classification |
| :--- | :--- | :--- | :--- |
| Clean repository (`0` changes vs `--base`) | Exits `0`, `sli.status == "PASSED"`, `sli.total_files == 0`, `findings == []` | Exits `0`, `summary.scanned_files == 0`, `findings == []` | Shared |
| Invalid or flag-like Git `--base` ref | Exits `1`, writes error to `stderr` | Exits `1`, emits error JSON or `ERROR:` | Shared |
| Missing or unreadable explicit file path | Exits `1`, writes error to `stderr` | Scans existing files only / ignores missing (`--files`) | Intentional difference |
| Swallowed exception (`except Exception: pass`, `catch (e) {}`) | Emits `SRE-SCALE-SWALLOW` (`BLOCKER`), `sli.status == "BLOCKED"`, exits `1` | Emits `SCALE_TOIL_ERROR_SWALLOW` (`blocker`), `--strict` exits `2` | Shared (exit code `1` vs `2` differs intentionally) |
| Blind sleep (`time.sleep(5)` / `time.Sleep(...)`) | Emits `SRE-SCALE-SLEEP` (`BLOCKER`), exits `1` | Emits `SCALE_TOIL_SLEEP_BAND_AID` (`review`) | Shared detection (severity differs intentionally) |
| Flat retry (counted loop with a fixed sleep) | Emits `SRE-SCALE-RETRY` (`REVIEW`) at the loop header | Emits `SCALE_UNBOUNDED_OR_FLAT_RETRY` (`blocker`), `--strict` exits `2` | Shared detection (severity differs intentionally) |
| Deep nesting (indentation depth 5+) | Emits `SRE-KISS-NESTING` (`BLOCKER`), exits `1` | Emits `KISS_DEEP_NESTING` (`review`) | Shared detection (severity differs intentionally) |
| Deletion-only diff | Exits `0`, `sli.status == "PASSED"` | Exits `0`, `summary.total_findings == 0` | Shared |
| Renamed, whitespace, & non-ASCII filenames | Handled without crash | Handled without crash | Shared |
| SLI error budget (`error_budget_left`), `serve` HTTP daemon, `stream` | Enforced | Not implemented | Native-only (Go) |
| `SCALE_MISLEADING_HEALTH_CHECK`, `in_active_diff` hunk annotation, active-diff `--strict` scoping | Not implemented | Enforced | Fallback-only (Python) |

## Recorded SRE-01 differences

Canonical owner: python-sre (`KISS_DEEP_NESTING`, review). Fallback: go-audit (`SRE-KISS-NESTING`, blocker). Both report the canonical fixture (`deep_nesting.diff`) at the same lines. Preserved differences, measured on disposable fixtures for this migration:

- Severity: the Python owner reports deep nesting as review evidence, per the catalog guidance for SRE-01 (escalate only for a demonstrated impact beyond readability); the Go audit escalates the identical lines to blocker. The divergence is recorded, not reconciled — changing either engine's severity is a separate decision.
- Detection agrees on the boundary: indentation depth 5 and deeper is flagged by both engines at the same lines; depth 4, shallow guard clauses, and multiline call continuations are flagged by neither.
- python-diff has no SRE-01 producer, so the unified audit never sees a cross-guard duplicate for this rule.

## Recorded SRE-08 differences

Canonical owner: python-sre (`SCALE_UNBOUNDED_OR_FLAT_RETRY`, blocker). Fallbacks: python-diff (`SRE_SCALE_FLAT_RETRY`, review) and go-audit (`SRE-SCALE-RETRY`, review). All three report the canonical fixture loop (`flat_retry.diff`) at its header line. Preserved differences, measured on disposable fixtures for this migration:

- Go flags a counted `for attempt in range(N)` header with no sleep at all when no `backoff` or `jitter` keyword appears within six lines; the Python guards require a fixed sleep inside the loop.
- Go flags exponential backoff written without the words `backoff` or `jitter` (for example `time.sleep(2 ** attempt)`); the Python guards treat a non-literal sleep argument as backoff-shaped and stay silent.
- The Python guards flag `while attempts <= N` counter loops with a fixed sleep; Go has no while-loop form and reports only the sleep itself (SRE-07).
- The unified audit suppresses the fallback entry when both Python guards report SRE-08 at the same file and line: the owner's entry is kept with its blocker severity and the suppressed fallback is recorded on it (`suppressed_duplicates`). The same owner-aware suppression applies to the error-swallow (OPS-01), blind-sleep (SRE-07), and unbounded-concurrency (SRE-09) pairs; findings at distinct locations and unmapped findings are never merged.

## Recorded SRE-09 differences

Canonical owner: python-sre (`SCALE_UNBOUNDED_CONCURRENCY`, review). Fallback: python-diff (`SRE_SCALE_UNBOUNDED_CONCURRENCY`, review). Both report the canonical fixture (`unbounded_concurrency.diff`) at line 5. Preserved differences, measured on disposable fixtures for this migration:

- No detection or severity divergence: both guards run the identical fan-out pattern (`Promise.all(... .map(...))`, `asyncio.gather(*...)`) and report review at the same line for Python and JavaScript fan-out. Ownership gives the combined audit one canonical entry per location; before this registration the combined audit emitted both entries at every shared location.
- Scope: python-diff skips this rule under `references/` paths; python-sre reports fan-out there, and its entry stands alone in the combined audit with no suppressed duplicate. Both guards stay silent on the same fan-out in a test path and on bounded fan-out (fixed argument lists with no splat or map).
- No Go or Rust producer is registered for SRE-09.

## Recorded SRE-05 differences

Canonical owner: python-sre (`YAGNI_DEAD_SPECULATIVE_FLAG`, blocker). Fallback: python-diff (`SRE_YAGNI_DEAD_FLAG`, blocker). Both report the canonical fixture (`dead_flag.diff`) at line 2. Preserved differences, measured on disposable fixtures for this registration:

- No detection or severity divergence on dead branches: both guards run the identical pattern (`if False:`, `if (false)`, `if (0)`) and report blocker at the same line. Ownership gives the combined audit one canonical entry per location; before this registration the combined audit emitted both entries (two blockers) at every shared location.
- Scope: both guards report dead branches under `references/` paths, and both stay silent on a live `if True:` branch.
- The Go producer registered for SRE-05 (`SRE-YAGNI-SPECULATIVE`, review) reports speculative comments (`TODO(future)`, `placeholder for future`, `not implemented yet`), not dead branches; it does not fire on the canonical fixture and shares no comparable location with the dead-flag pair, so it stays outside this ownership entry. The Python guards report the same comment surface under their own unregistered codes (`SRE_YAGNI_SPECULATIVE_CODE`, `YAGNI_SPECULATIVE_COMMENT`), which remain unmapped in the combined audit.
