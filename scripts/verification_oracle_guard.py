#!/usr/bin/env python3
"""Check Verification Oracle Architect records and test/source files for Contract-Verified In-Memory Fakes, Property-Based & Metamorphic Oracles, Seeded Deterministic Chaos Testing, and Red-Green Mutation Falsification."""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

VALID_DOMAIN_CATEGORIES = {
    "financial_ledger_and_payments",
    "parser_serializer_codec",
    "state_machine_and_workflow",
    "distributed_storage_and_sync",
    "authorization_and_policy_engine",
}
VALID_FAKE_MECHANICS = {
    "structured_clone_boundary_isolation",
    "unique_and_check_constraint_enforcement",
    "optimistic_concurrency_version_cas",
    "transactional_snapshot_rollback",
    "composite_tenant_isolation",
    "deterministic_cursor_pagination",
}
VALID_PROPERTY_FRAMEWORKS = {
    "fast-check",
    "hypothesis",
    "proptest",
    "rapid",
    "deterministic_seeded_property_engine",
}
VALID_INVARIANT_CATEGORIES = {
    "conservation_law",
    "roundtrip_invertibility",
    "idempotency_law",
    "metamorphic_relation",
    "state_machine_safety",
}
VALID_PRNG_ALGORITHMS = {
    "mulberry32",
    "xorshift32",
    "pcg32",
    "chacha8_rng",
}
VALID_CHAOS_FAULT_MODES = {
    "pre_commit_connection_drop",
    "post_commit_ack_drop",
    "transient_cas_version_conflict",
    "duplicate_out_of_order_delivery",
    "virtual_clock_lease_skew",
}
HEX_SEED_RE = re.compile(r"^0x[0-9a-fA-F]+$")
INFRA_ERROR_RE = re.compile(
    r"(?:ModuleNotFoundError:\s*No module named"
    r"|ImportError:\s*cannot import name"
    r"|SyntaxError:"
    r"|NameError:\s*name\s*['\"].*?['\"]\s*is not defined"
    r"|Cannot find module"
    r"|ERR_MODULE_NOT_FOUND"
    r"|undefined:\s*[a-zA-Z0-9_]+"
    r"|error\[E04(?:32|25)\]"
    r"|package\s+[a-zA-Z0-9_./]+\s+is not in std)",
    re.IGNORECASE,
)
ASSERTION_FAIL_RE = re.compile(
    r"(?:AssertionError"
    r"|FAIL:\s*test"
    r"|FAILED\s*\(failures="
    r"|ERR_ASSERTION"
    r"|expect\s*\([^)]*\)\s*\."
    r"|Expected:\s*.*\s*Received:"
    r"|assertion failed"
    r"|--- FAIL:)",
    re.IGNORECASE,
)
TEST_FILE_EXTENSIONS = {".py", ".ts", ".js", ".mjs", ".go", ".rs"}


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_target_system(record, require):
    target = record.get("target_system")
    require(isinstance(target, dict), "INVALID_TARGET_SYSTEM",
            "target_system must be a dictionary")
    if not isinstance(target, dict):
        return
    require(filled(target.get("module_under_test"), 10),
            "MISSING_MODULE_UNDER_TEST",
            "target_system.module_under_test must be at least 10 characters")
    require(choice(target.get("domain_category"), VALID_DOMAIN_CATEGORIES),
            "INVALID_DOMAIN_CATEGORY",
            "target_system.domain_category must be one of: %s"
            % ", ".join(sorted(VALID_DOMAIN_CATEGORIES)))
    require(target.get("module_mocking_banned") is True,
            "MODULE_MOCKING_NOT_BANNED",
            "target_system.module_mocking_banned must be true")


def check_verified_fakes(record, require):
    fakes = record.get("verified_in_memory_fakes")
    require(isinstance(fakes, dict), "INVALID_VERIFIED_IN_MEMORY_FAKES",
            "verified_in_memory_fakes must be a dictionary")
    if not isinstance(fakes, dict):
        return
    require(filled(fakes.get("port_interface"), 5),
            "MISSING_PORT_INTERFACE",
            "verified_in_memory_fakes.port_interface must name the domain Port")
    require(filled(fakes.get("fake_adapter_name"), 5),
            "MISSING_FAKE_ADAPTER_NAME",
            "verified_in_memory_fakes.fake_adapter_name must name the In-Memory Fake")
    require(filled(fakes.get("real_adapter_name"), 5),
            "MISSING_REAL_ADAPTER_NAME",
            "verified_in_memory_fakes.real_adapter_name must name the Real production adapter")
    require(filled(fakes.get("shared_contract_suite"), 10),
            "MISSING_SHARED_CONTRACT_SUITE",
            "verified_in_memory_fakes.shared_contract_suite must specify the shared contract suite")
    require(fakes.get("contract_parity_verified") is True,
            "CONTRACT_PARITY_NOT_VERIFIED",
            "verified_in_memory_fakes.contract_parity_verified must be true")

    mechanics = fakes.get("enforced_fake_mechanics")
    valid_list = (
        isinstance(mechanics, list)
        and len(mechanics) >= 3
        and all(isinstance(m, str) and m in VALID_FAKE_MECHANICS for m in mechanics)
    )
    require(valid_list, "INSUFFICIENT_ENFORCED_FAKE_MECHANICS",
            "verified_in_memory_fakes.enforced_fake_mechanics must list at least 3 valid mechanics")
    if isinstance(mechanics, list):
        require("transactional_snapshot_rollback" in mechanics
                and "structured_clone_boundary_isolation" in mechanics,
                "MISSING_CORE_FAKE_ISOLATION_OR_ROLLBACK",
                "enforced_fake_mechanics must include 'structured_clone_boundary_isolation' and 'transactional_snapshot_rollback'")


def check_property_oracles(record, require):
    prop = record.get("property_and_metamorphic_oracles")
    require(isinstance(prop, dict), "INVALID_PROPERTY_AND_METAMORPHIC_ORACLES",
            "property_and_metamorphic_oracles must be a dictionary")
    if not isinstance(prop, dict):
        return
    require(choice(prop.get("framework"), VALID_PROPERTY_FRAMEWORKS),
            "INVALID_PROPERTY_FRAMEWORK",
            "property_and_metamorphic_oracles.framework must be a supported property engine")
    runs = prop.get("generated_runs_per_property")
    require(isinstance(runs, int) and runs >= 100,
            "INSUFFICIENT_GENERATED_PROPERTY_RUNS",
            "property_and_metamorphic_oracles.generated_runs_per_property must be an integer >= 100")
    require(prop.get("shrinking_enabled") is True,
            "SHRINKING_NOT_ENABLED",
            "property_and_metamorphic_oracles.shrinking_enabled must be true")

    invariants = prop.get("invariants_verified")
    require(isinstance(invariants, list) and len(invariants) >= 2,
            "INSUFFICIENT_INVARIANTS_VERIFIED",
            "property_and_metamorphic_oracles.invariants_verified must contain at least 2 invariants")
    if not isinstance(invariants, list):
        return
    for idx, inv in enumerate(invariants):
        ok_item = (
            isinstance(inv, dict)
            and filled(inv.get("name"), 5)
            and choice(inv.get("category"), VALID_INVARIANT_CATEGORIES)
            and filled(inv.get("assertion_formula"), 15)
        )
        require(ok_item, "INVALID_PROPERTY_INVARIANT_%d" % idx,
                "invariants_verified[%d] must specify valid name, category, and assertion_formula" % idx)


def check_chaos_and_mutation(record, require):
    chaos = record.get("deterministic_chaos_testing")
    require(isinstance(chaos, dict), "INVALID_DETERMINISTIC_CHAOS_TESTING",
            "deterministic_chaos_testing must be a dictionary")
    if isinstance(chaos, dict):
        require(choice(chaos.get("seeded_prng_algorithm"), VALID_PRNG_ALGORITHMS),
                "INVALID_SEEDED_PRNG_ALGORITHM",
                "deterministic_chaos_testing.seeded_prng_algorithm must be a valid deterministic PRNG")
        seeds = chaos.get("reproduction_seeds")
        seeds_ok = (
            isinstance(seeds, list)
            and len(seeds) >= 2
            and all(isinstance(s, str) and bool(HEX_SEED_RE.match(s)) and 6 <= len(s) <= 18 for s in seeds)
        )
        require(seeds_ok, "INVALID_REPRODUCTION_SEEDS",
                "deterministic_chaos_testing.reproduction_seeds must contain at least 2 hex seeds (0x...)")
        require(chaos.get("virtual_clock_injected") is True,
                "VIRTUAL_CLOCK_NOT_INJECTED",
                "deterministic_chaos_testing.virtual_clock_injected must be true")
        require(chaos.get("zero_wall_clock_sleeps") is True,
                "WALL_CLOCK_SLEEPS_PRESENT",
                "deterministic_chaos_testing.zero_wall_clock_sleeps must be true")
        faults = chaos.get("injected_fault_modes")
        faults_ok = (
            isinstance(faults, list)
            and len(faults) >= 2
            and all(isinstance(f, str) and f in VALID_CHAOS_FAULT_MODES for f in faults)
            and "pre_commit_connection_drop" in faults
            and "post_commit_ack_drop" in faults
        )
        require(faults_ok, "MISSING_PRE_OR_POST_COMMIT_CHAOS_FAULTS",
                "injected_fault_modes must include both 'pre_commit_connection_drop' and 'post_commit_ack_drop'")
        require(chaos.get("idempotency_and_rollback_proven") is True,
                "IDEMPOTENCY_AND_ROLLBACK_NOT_PROVEN",
                "deterministic_chaos_testing.idempotency_and_rollback_proven must be true")

    mut = record.get("mutation_falsification")
    require(isinstance(mut, dict), "INVALID_MUTATION_FALSIFICATION",
            "mutation_falsification must be a dictionary")
    if isinstance(mut, dict):
        require(mut.get("red_green_falsification_verified") is True,
                "RED_GREEN_FALSIFICATION_NOT_VERIFIED",
                "mutation_falsification.red_green_falsification_verified must be true")
        require(filled(mut.get("mutated_production_invariant"), 20),
                "MISSING_MUTATED_PRODUCTION_INVARIANT",
                "mutation_falsification.mutated_production_invariant must describe the deliberate mutation")
        require(filled(mut.get("observed_red_failure_signal"), 20),
                "MISSING_OBSERVED_RED_FAILURE_SIGNAL",
                "mutation_falsification.observed_red_failure_signal must record the failing counterexample/seed")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(choice(action, {"proceed", "pause", "refuse"}), "INVALID_ACTION",
            "Verdict action must be proceed, pause, or refuse")
    require(filled(verdict.get("rationale"), 20),
            "MISSING_RATIONALE", "Verdict rationale must be at least 20 characters")
    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and bool(triggers) and all(filled(t) for t in triggers),
            "MISSING_REVISIT_TRIGGERS", "Verdict must declare at least one revisit trigger")
    return action


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    has_banned_mock = bool(
        re.search(
            r"\b(?:vi\.mock|jest\.mock|sinon\.stub|unittest\.mock\.patch|mock\.module)\s*\("
            r"|no-module-mocking",
            source_text,
        )
    )
    require(not has_banned_mock, "SOURCE_BANNED_MODULE_MOCK",
            "Detected banned module mocking (vi.mock/jest.mock/sinon.stub/unittest.mock.patch) or rule suppression; use a Contract-Verified In-Memory Fake")

    has_unseeded_random = bool(re.search(r"\b(?:Math\.random|random\.random)\s*\(", source_text))
    require(not has_unseeded_random, "SOURCE_UNSEEDED_RANDOM_IN_TEST",
            "Detected unseeded Math.random()/random.random(); use an explicit seeded PRNG (e.g. Mulberry32) for deterministic replay")

    has_wall_clock_sleep = bool(re.search(r"\b(?:setTimeout|time\.sleep)\s*\(", source_text))
    require(not has_wall_clock_sleep, "SOURCE_WALL_CLOCK_SLEEP_IN_TEST",
            "Detected wall-clock sleep (setTimeout/time.sleep); inject a DeterministicVirtualClock instead")

    has_tautological_assert = bool(
        re.search(r"expect\s*\(\s*true\s*\)\s*\.toBe\s*\(\s*true\s*\)|\.toBeDefined\s*\(\s*\)", source_text)
    )
    require(not has_tautological_assert, "SOURCE_TAUTOLOGICAL_OR_WEAK_ASSERTION",
            "Detected tautological or weak assertion (expect-true or toBeDefined); enforce concrete domain invariants")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_target_system(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_verified_fakes(record, require)
        check_property_oracles(record, require)
        check_chaos_and_mutation(record, require)

    if source_text is not None:
        findings.extend(scan_source_hazards(source_text))

    return {
        "record_status": "incomplete" if findings else "complete",
        "verdict_action": action,
        "machine_check_only": True,
        "findings": findings,
    }


def is_test_file(path_str: str) -> bool:
    normalized = path_str.replace("\\", "/")
    path = Path(normalized)
    if path.suffix.lower() not in TEST_FILE_EXTENSIONS:
        return False
    parts = path.parts
    if any(p in ("tests", "test", "spec", "__tests__") for p in parts[:-1]):
        return True
    stem = path.stem.lower()
    return stem.startswith("test_") or stem.endswith(("_test", ".test", ".spec"))


def find_repo_root(start_dir=None):
    cwd = start_dir or Path.cwd()
    try:
        res = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            return Path(res.stdout.strip()).resolve()
    except OSError as err:
        sys.stderr.write("[WARN] Unable to resolve git rev-parse: %s\n" % err)
    return cwd.resolve()


def detect_changed_test_files(repo_root: Path, base: str = "HEAD~1"):
    test_files = set()
    try:
        diff_res = subprocess.run(
            ["git", "-C", str(repo_root), "diff", "--name-only", "%s...HEAD" % base],
            capture_output=True,
            text=True,
            check=False,
        )
        if diff_res.returncode != 0:
            diff_res = subprocess.run(
                ["git", "-C", str(repo_root), "diff", "--name-only", base],
                capture_output=True,
                text=True,
                check=False,
            )
        if diff_res.returncode == 0:
            for line in diff_res.stdout.splitlines():
                line = line.strip()
                if line and is_test_file(line) and (repo_root / line).is_file():
                    test_files.add(line)

        status_res = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
        )
        if status_res.returncode == 0:
            for line in status_res.stdout.splitlines():
                if len(line) > 3:
                    file_path = line[3:].strip().split(" -> ")[-1]
                    if is_test_file(file_path) and (repo_root / file_path).is_file():
                        test_files.add(file_path)
    except OSError as err:
        sys.stderr.write("[WARN] Unable to detect changed test files: %s\n" % err)
    return sorted(test_files)


def detect_test_cmd(test_file: str, custom_cmd=None):
    if custom_cmd:
        if "{test_file}" in custom_cmd or "{file}" in custom_cmd:
            formatted = custom_cmd.replace("{test_file}", test_file).replace("{file}", test_file)
            return shlex.split(formatted)
        return shlex.split(custom_cmd) + [test_file]

    ext = Path(test_file).suffix.lower()
    if ext == ".py":
        return [sys.executable, "-m", "unittest", test_file]
    if ext in (".ts", ".js", ".mjs"):
        if shutil.which("bun"):
            return ["bun", "test", test_file]
        return ["npm", "test", "--", test_file]
    if ext == ".go":
        parent = str(Path(test_file).parent)
        return ["go", "test", "-v", "./%s" % parent if not parent.startswith(".") else parent]
    if ext == ".rs":
        return ["cargo", "test", "--test", Path(test_file).stem]
    return [sys.executable, "-m", "unittest", test_file]


def run_command_safe(cmd, cwd: Path, env=None, timeout: int = 30):
    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            env=env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration = round(time.time() - start, 3)
        return {
            "exit_code": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
            "timed_out": False,
            "error": None,
            "duration": duration,
        }
    except subprocess.TimeoutExpired as exc:
        duration = round(time.time() - start, 3)
        out = exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode(errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return {
            "exit_code": None,
            "stdout": out,
            "stderr": err,
            "timed_out": True,
            "error": "Timed out after %d seconds" % timeout,
            "duration": duration,
        }
    except FileNotFoundError as exc:
        return {
            "exit_code": 127,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
            "error": "Command not found: %s" % exc,
            "duration": 0.0,
        }
    except OSError as exc:
        return {
            "exit_code": 1,
            "stdout": "",
            "stderr": str(exc),
            "timed_out": False,
            "error": "Execution error: %s" % exc,
            "duration": 0.0,
        }


def extract_failure_snippet(output: str, max_lines: int = 3):
    lines = [ln.strip() for ln in output.splitlines() if ln.strip()]
    matched = []
    for line in reversed(lines):
        if any(token in line for token in ("Error:", "FAIL:", "FAILED", "AssertionError", "panicked", "assertion failed")):
            matched.append(line)
            if len(matched) >= max_lines:
                break
    if matched:
        return " | ".join(reversed(matched))
    return lines[-1] if lines else "Non-zero exit"


def classify_test_output(run_res):
    if run_res.get("timed_out"):
        return "timed_out", run_res.get("error") or "Execution timed out"

    exit_code = run_res.get("exit_code")
    stdout = run_res.get("stdout") or ""
    stderr = run_res.get("stderr") or ""
    combined = "%s\n%s" % (stdout, stderr)

    if exit_code == 127 or "command not found" in combined.lower():
        return "dependency_failure", "Test runner command or binary not available in environment"

    if exit_code == 0:
        return "passed", "Test completed with exit code 0"

    snippet = extract_failure_snippet(combined)
    if INFRA_ERROR_RE.search(combined):
        return "infrastructure_error", "Infrastructure / import failure: %s" % snippet

    if ASSERTION_FAIL_RE.search(combined):
        return "assertion_failure", "Assertion failure: %s" % snippet

    return "test_failure", "Test exited with code %s: %s" % (exit_code, snippet)


def _copy_test_tree(repo_root: Path, target_dir: Path, test_files):
    for t_rel in test_files:
        src = repo_root / t_rel
        dest = target_dir / t_rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            shutil.copy2(src, dest)

    for test_dir_name in ("tests", "test"):
        src_tests = repo_root / test_dir_name
        if src_tests.is_dir():
            for root, _, files in os.walk(src_tests):
                for f in files:
                    rel_p = Path(root, f).relative_to(repo_root)
                    target_p = target_dir / rel_p
                    if not target_p.exists():
                        target_p.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(repo_root / rel_p, target_p)


def _execute_test_isolated(test_file: str, cwd: Path, custom_cmd=None, timeout: int = 30):
    cmd = detect_test_cmd(test_file, custom_cmd)
    env = os.environ.copy()
    cur_pypath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(cwd) + (os.pathsep + cur_pypath if cur_pypath else "")
    res = run_command_safe(cmd, cwd=cwd, env=env, timeout=timeout)
    cls_type, reason = classify_test_output(res)
    res["classification"] = cls_type
    res["reason"] = reason
    res["command"] = cmd
    return res


def _evaluate_test_status(base_cls: str, curr_cls: str) -> str:
    if base_cls == "dependency_failure" or curr_cls == "dependency_failure":
        return "dependency_failure"
    if base_cls == "flaky_nondeterministic" or curr_cls == "flaky_nondeterministic":
        return "flaky_nondeterministic"
    if curr_cls != "passed":
        return "failed_on_current"
    if base_cls in ("assertion_failure", "test_failure"):
        return "verified"
    if base_cls == "passed":
        return "tautological"
    if base_cls == "infrastructure_error":
        return "inconclusive_infrastructure"
    return "inconclusive"


def _synthesize_proof_verdict(results, base_ref: str):
    statuses = [v["status"] for v in results.values()]
    if any(s == "dependency_failure" for s in statuses):
        return "dependency_failure", "pause", False, "Missing test runner or environment dependency prevented execution."
    if any(s == "failed_on_current" for s in statuses):
        return "failed_on_current", "refuse", False, "Test failed on current tree; fix is incomplete or test is broken."
    if any(s == "flaky_nondeterministic" for s in statuses):
        return "flaky_nondeterministic", "refuse", False, "Test exhibited non-deterministic flakiness across repeated runs."
    if any(s == "tautological" for s in statuses):
        return "tautological", "refuse", False, "Test passed on baseline '%s' without implementation changes; lacks red-state proof." % base_ref
    if all(s == "verified" for s in statuses):
        return "verified", "proceed", True, "Affirmative counterfactual red-state proof: tests failed on baseline and pass on current tree."
    if any(s == "verified" for s in statuses):
        return "verified", "proceed", True, "Partial affirmative proof: verified tests failed on baseline, other tests inconclusive."
    if all(s == "inconclusive_infrastructure" for s in statuses):
        return "inconclusive_infrastructure", "pause", False, "Tests failed on baseline due to missing imports/symbols; inconclusive (not fraud)."
    return "inconclusive", "pause", False, "Test outcomes could not establish conclusive red-green proof."


def run_counterfactual_proof(
    repo_root=None,
    base: str = "HEAD~1",
    test_files=None,
    test_cmd=None,
    timeout: int = 30,
    check_flaky: bool = False,
):
    root = find_repo_root(repo_root)
    resolved_tests = test_files or detect_changed_test_files(root, base=base)

    if not resolved_tests:
        return {
            "status": "no_tests_found",
            "verdict": "pause",
            "red_green_verified": False,
            "rationale": "No new or modified test files detected against baseline '%s'" % base,
            "base_ref": base,
            "test_files": [],
            "results": {},
        }

    temp_base = Path(tempfile.gettempdir())
    temp_worktree = temp_base / ("anti-slop-proof-%s-%d" % (os.getpid(), int(time.time() * 1000)))

    worktree_created = False
    try:
        wt_add = subprocess.run(
            ["git", "-C", str(root), "worktree", "add", "--detach", str(temp_worktree), base],
            capture_output=True,
            text=True,
            check=False,
        )
        if wt_add.returncode != 0:
            return {
                "status": "inconclusive_infrastructure",
                "verdict": "pause",
                "red_green_verified": False,
                "rationale": "Unable to establish isolated baseline worktree at '%s': %s" % (base, wt_add.stderr.strip()),
                "base_ref": base,
                "test_files": resolved_tests,
                "results": {},
            }
        worktree_created = True
        _copy_test_tree(root, temp_worktree, resolved_tests)

        per_test_results = {}
        for t_file in resolved_tests:
            base_run = _execute_test_isolated(t_file, cwd=temp_worktree, custom_cmd=test_cmd, timeout=timeout)
            curr_run = _execute_test_isolated(t_file, cwd=root, custom_cmd=test_cmd, timeout=timeout)

            if check_flaky:
                base_run2 = _execute_test_isolated(t_file, cwd=temp_worktree, custom_cmd=test_cmd, timeout=timeout)
                curr_run2 = _execute_test_isolated(t_file, cwd=root, custom_cmd=test_cmd, timeout=timeout)
                if base_run["classification"] != base_run2["classification"] or curr_run["classification"] != curr_run2["classification"]:
                    base_run["classification"] = "flaky_nondeterministic"
                    base_run["reason"] = "Test outcome varied across repeated executions"

            t_status = _evaluate_test_status(base_run["classification"], curr_run["classification"])
            per_test_results[t_file] = {
                "status": t_status,
                "baseline": base_run,
                "current": curr_run,
            }

        overall_status, overall_verdict, rg_verified, rationale = _synthesize_proof_verdict(per_test_results, base)
        return {
            "status": overall_status,
            "verdict": overall_verdict,
            "red_green_verified": rg_verified,
            "rationale": rationale,
            "base_ref": base,
            "test_files": resolved_tests,
            "results": per_test_results,
        }

    finally:
        if worktree_created:
            subprocess.run(
                ["git", "-C", str(root), "worktree", "remove", "--force", str(temp_worktree)],
                capture_output=True,
                text=True,
                check=False,
            )
        if temp_worktree.exists():
            shutil.rmtree(temp_worktree, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    audit_parser = subparsers.add_parser("audit", help="Audit Verification Oracle record and optional test source")
    audit_parser.add_argument("record", type=Path)
    audit_parser.add_argument("--source", type=Path, default=None,
                              help="Optional test/source file to scan for banned mocks, unseeded random, or weak assertions")
    audit_parser.add_argument("--counterfactual", action="store_true",
                              help="Also run isolated counterfactual red-state proof for newly added tests")
    audit_parser.add_argument("--base", default="HEAD~1", help="Baseline commit or ref (default: HEAD~1)")
    audit_parser.add_argument("--json", action="store_true")

    for cmd_alias in ("counterfactual", "proof"):
        cf_parser = subparsers.add_parser(cmd_alias, help="Run isolated counterfactual red-state proof for newly added tests")
        cf_parser.add_argument("--base", default="HEAD~1", help="Baseline commit or ref to compare against (default: HEAD~1)")
        cf_parser.add_argument("--tests", nargs="*", default=None, help="Explicit test files to verify")
        cf_parser.add_argument("--test-cmd", default=None, help="Custom test runner command template (e.g. 'python3 -m unittest {test_file}')")
        cf_parser.add_argument("--timeout", type=int, default=30, help="Per-test timeout in seconds (default: 30)")
        cf_parser.add_argument("--check-flaky", action="store_true", help="Check for non-deterministic flakiness across runs")
        cf_parser.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "audit":
        try:
            record = json.loads(args.record.read_text(encoding="utf-8"))
            if not isinstance(record, dict):
                raise ValueError("Record root must be a JSON object")
            source_text = args.source.read_text(encoding="utf-8") if args.source else None
            result = audit(record, source_text=source_text)
            if args.counterfactual:
                proof_res = run_counterfactual_proof(base=args.base)
                result["counterfactual_proof"] = proof_res
                if not proof_res.get("red_green_verified"):
                    result["record_status"] = "incomplete"
                    result["findings"].append({
                        "severity": "block" if proof_res.get("verdict") == "refuse" else "review",
                        "code": "COUNTERFACTUAL_RED_STATE_UNPROVEN",
                        "message": proof_res.get("rationale") or "Counterfactual red-state proof was not established",
                    })
        except (OSError, UnicodeError, ValueError) as error:
            print("Invalid Verification Oracle record: %s" % error, file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("Verification Oracle record: %s (%s)" % (result["record_status"], result["verdict_action"]))
            for item in result["findings"]:
                print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
            print("Structural audit only: Shared Contract Suites, Property Generators, and Deterministic Chaos seeds must be executed in the test runner.")

        return 2 if result["record_status"] == "incomplete" else 0

    if args.command in ("counterfactual", "proof"):
        result = run_counterfactual_proof(
            base=args.base,
            test_files=args.tests,
            test_cmd=args.test_cmd,
            timeout=args.timeout,
            check_flaky=args.check_flaky,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("🛡️  Anti-Slop Counterfactual Proof: %s (%s)" % (result["status"].upper(), result["verdict"]))
            print("Baseline: %s" % result["base_ref"])
            print("Rationale: %s" % result["rationale"])
            for t_path, t_info in result.get("results", {}).items():
                print("  - %s: %s" % (t_path, t_info["status"]))
                print("      baseline: %s (%s)" % (t_info["baseline"]["classification"], t_info["baseline"]["reason"]))
                print("      current:  %s (%s)" % (t_info["current"]["classification"], t_info["current"]["reason"]))

        if result["status"] == "verified":
            return 0
        if result["status"] in ("inconclusive_infrastructure", "dependency_failure", "no_tests_found"):
            return 1
        return 2


if __name__ == "__main__":
    sys.exit(main())
