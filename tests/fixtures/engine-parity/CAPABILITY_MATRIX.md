# Engine Parity Capability Matrix

## Runtime ownership

| Runtime | Owned behavior | Portable behavior |
| --- | --- | --- |
| Node | CLI routing and installation, chooses native binaries when available | Python commands remain directly runnable. |
| Python | Portable Git checks, SRE and record checks, unified audit | Standard-library scripts exercise required behavior without native engines. |
| Rust | Structural triage, read-only intent and file scope checks | Python Diff Guard covers documented heuristic triage. Native-only options return a capability error when unavailable. |
| Go | Native SRE analysis, SLI reporting and optional serve/stream | Python SRE covers documented audit operations. Native-only daemon/stream requests require Go. |

[Tested capability and rule fixture](contracts.json)

The fixture identifies one canonical owner for the observed error-swallow and blind-sleep rules, and records alternate implementations with their actual IDs and severities. Different decisions are preserved by parity tests during migration. New shared-rule records must link to a fixture, declare one owner, and register each engine and emitted identifier once. Overlaps without independent evidence remain listed as current behavior in this matrix.

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

## `toil-guard audit` ↔ `scripts/sre_guard.py`

| Contract / Behavior | `toil-guard audit` | `scripts/sre_guard.py` | Classification |
| :--- | :--- | :--- | :--- |
| Clean repository (`0` changes vs `--base`) | Exits `0`, `sli.status == "PASSED"`, `sli.total_files == 0`, `findings == []` | Exits `0`, `summary.scanned_files == 0`, `findings == []` | Shared |
| Invalid or flag-like Git `--base` ref | Exits `1`, writes error to `stderr` | Exits `1`, emits error JSON or `ERROR:` | Shared |
| Missing or unreadable explicit file path | Exits `1`, writes error to `stderr` | Scans existing files only / ignores missing (`--files`) | Intentional difference |
| Swallowed exception (`except Exception: pass`, `catch (e) {}`) | Emits `SRE-SCALE-SWALLOW` (`BLOCKER`), `sli.status == "BLOCKED"`, exits `1` | Emits `SCALE_TOIL_ERROR_SWALLOW` (`blocker`), `--strict` exits `2` | Shared (exit code `1` vs `2` differs intentionally) |
| Blind sleep (`time.sleep(5)` / `time.Sleep(...)`) | Emits `SRE-SCALE-SLEEP` (`BLOCKER`), exits `1` | Emits `SCALE_TOIL_SLEEP_BAND_AID` (`review`) | Shared detection (severity differs intentionally) |
| Deletion-only diff | Exits `0`, `sli.status == "PASSED"` | Exits `0`, `summary.total_findings == 0` | Shared |
| Renamed, whitespace, & non-ASCII filenames | Handled without crash | Handled without crash | Shared |
| SLI error budget (`error_budget_left`), `serve` HTTP daemon, `stream` | Enforced | Not implemented | Native-only (Go) |
| `SCALE_MISLEADING_HEALTH_CHECK`, `in_active_diff` hunk annotation, active-diff `--strict` scoping | Not implemented | Enforced | Fallback-only (Python) |
