#!/usr/bin/env python3
"""Check Verification Oracle Architect records and test/source files for Contract-Verified In-Memory Fakes, Property-Based & Metamorphic Oracles, Seeded Deterministic Chaos Testing, and Red-Green Mutation Falsification."""

import argparse
import importlib.util
import inspect
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET
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
    r"|Expected:\s*.*\s*Received:"
    r"|assertion failed"
    r"|--- FAIL:)",
    re.IGNORECASE,
)
TEST_FILE_EXTENSIONS = {".py", ".ts", ".js", ".mjs", ".go", ".rs"}

GO_TEST_NAMES = """
package main

import (
	"encoding/json"
	"go/ast"
	"go/parser"
	"go/token"
	"os"
	"strings"
	"unicode"
	"unicode/utf8"
)

func main() {
	file, err := parser.ParseFile(token.NewFileSet(), os.Args[2], nil, parser.SkipObjectResolution)
	if err != nil {
		os.Exit(1)
	}
	names := []string{}
	for _, declaration := range file.Decls {
		fn, ok := declaration.(*ast.FuncDecl)
		if !ok || fn.Recv != nil {
			continue
		}
		name := fn.Name.Name
		if name == "TestMain" || !(strings.HasPrefix(name, "Test") || strings.HasPrefix(name, "Example")) {
			continue
		}
		suffix := strings.TrimPrefix(strings.TrimPrefix(name, "Test"), "Example")
		first, _ := utf8.DecodeRuneInString(suffix)
		if !unicode.IsLower(first) {
			names = append(names, name)
		}
	}
	if err := json.NewEncoder(os.Stdout).Encode(names); err != nil {
		os.Exit(1)
	}
}
"""

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
    cwd = Path(start_dir or Path.cwd())
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


def _git_paths(repo_root: Path, *args):
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        capture_output=True,
        check=True,
    )
    return (os.fsdecode(path) for path in result.stdout.split(b"\0") if path)


def _regular_relative_file(repo_root: Path, name: str):
    path = Path(name)
    source = repo_root / path
    if path.is_absolute() or ".." in path.parts or path.as_posix() != name:
        return False
    return source.is_file() and source.resolve() == source


def detect_changed_test_files(repo_root: Path, base: str = "HEAD~1"):
    tracked = _git_paths(repo_root, "diff", "--name-only", "-z", base, "--")
    untracked = _git_paths(repo_root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(
        name for name in set(tracked).union(untracked)
        if is_test_file(name) and _regular_relative_file(repo_root, name)
    )


def detect_test_cmd(test_file: str, custom_cmd=None):
    if custom_cmd:
        argv = shlex.split(custom_cmd)
        if any("{test_file}" in arg or "{file}" in arg for arg in argv):
            return [arg.replace("{test_file}", test_file).replace("{file}", test_file) for arg in argv]
        return argv + [test_file]

    ext = Path(test_file).suffix.lower()
    if ext == ".py":
        return [sys.executable, str(Path(__file__).resolve()), "_unittest_selected", test_file]
    if ext in (".ts", ".js", ".mjs"):
        if shutil.which("bun"):
            return ["bun", "test", "./" + test_file]
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
        if re.search(r"^Ran 0 tests? in ", combined, re.MULTILINE):
            return "no_tests_ran", "The runner exited without executing a test"
        return "passed", "Test completed with exit code 0"

    snippet = extract_failure_snippet(combined)
    if INFRA_ERROR_RE.search(combined):
        return "infrastructure_error", "Infrastructure / import failure: %s" % snippet

    if ASSERTION_FAIL_RE.search(combined):
        return "assertion_failure", "Assertion failure: %s" % snippet

    return "test_failure", "Test exited with code %s: %s" % (exit_code, snippet)


def _copy_snapshot_files(repo_root: Path, target_dir: Path, paths):
    for name in set(paths):
        if not _regular_relative_file(repo_root, name):
            continue
        target = target_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(repo_root / name, target)


def _resolve_baseline(root: Path, base: str):
    return subprocess.run(
        ["git", "-C", str(root), "rev-parse", "--verify", "--end-of-options", base + "^{commit}"],
        capture_output=True, check=True, text=True,
    ).stdout.strip()


def _baseline_entries(root: Path, commit: str):
    tree = subprocess.run(
        ["git", "-C", str(root), "ls-tree", "-rz", "--full-tree", commit],
        capture_output=True, check=True,
    )
    for entry in tree.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.split()
        path = Path(os.fsdecode(raw_path))
        if kind != b"blob" or mode not in (b"100644", b"100755") or path.is_absolute() or ".." in path.parts:
            continue
        yield path, mode, oid


def _write_baseline_blob(objects, destination: Path, mode, oid):
    header = objects.readline().split()
    if len(header) != 3 or header[:2] != [oid, b"blob"]:
        raise ValueError("Unable to read a regular file from the baseline commit")
    remaining = int(header[2])
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("wb") as output:
        while remaining:
            chunk = objects.read(min(remaining, 64 * 1024))
            if not chunk:
                raise ValueError("Incomplete baseline blob")
            output.write(chunk)
            remaining -= len(chunk)
    if objects.read(1) != b"\n":
        raise ValueError("Incomplete baseline blob separator")
    destination.chmod(int(mode, 8) & 0o777)


def _create_baseline(root: Path, target: Path, commit: str):
    entries = list(_baseline_entries(root, commit))
    with tempfile.TemporaryFile() as objects:
        subprocess.run(
            ["git", "-C", str(root), "cat-file", "--batch"],
            input=b"".join(oid + b"\n" for _, _, oid in entries),
            stdout=objects, stderr=subprocess.PIPE, check=True,
        )
        objects.seek(0)
        for path, mode, oid in entries:
            _write_baseline_blob(objects, target / path, mode, oid)


def _go_test_command(cwd: Path, test_file: str, env, timeout):
    path = Path(test_file)
    package = cwd / path.parent
    listing_cmd = ["go", "list", "-json", "."]
    listing = run_command_safe(listing_cmd, package, env=env, timeout=timeout)
    names = set()
    if listing["exit_code"] != 0:
        return package, listing_cmd, listing, names
    try:
        metadata = json.loads(listing["stdout"])
    except ValueError:
        return package, listing_cmd, listing, names
    if path.name not in metadata.get("TestGoFiles", []) + metadata.get("XTestGoFiles", []):
        return package, listing_cmd, listing, names

    helper = cwd.parent / "test_names.go"
    helper.write_text(GO_TEST_NAMES, encoding="utf-8")
    names_cmd = ["go", "run", str(helper), "--", "./" + path.name]
    parsed = run_command_safe(names_cmd, package, env=env, timeout=timeout)
    if parsed["exit_code"] != 0:
        return package, names_cmd, parsed, names
    try:
        names = set(json.loads(parsed["stdout"]))
    except (TypeError, ValueError):
        return package, names_cmd, parsed, names
    if not names:
        return package, names_cmd, parsed, names
    selected = "^(" + "|".join(sorted(re.escape(name) for name in names)) + ")$"
    return package, ["go", "test", "-json", "-count=1", "-run", selected, "."], None, names


def _go_test_evidence(result, selected):
    cases = {}
    named_failure = False
    for line in result["stdout"].splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            return None, {}
        name = event.get("Test")
        action = event.get("Action")
        if name and name.split("/", 1)[0] not in selected:
            return None, {}
        if name and action in ("pass", "fail", "skip"):
            cases[name] = action
        if action == "output":
            output = event.get("Output", "")
            if output.startswith(("panic:", "fatal error:")):
                return "test_failure", cases
            named_failure |= bool(name and output.strip().startswith("--- FAIL:"))
    if result["exit_code"] == 0 and "pass" in cases.values():
        return "passed", cases
    if result["exit_code"] == 1 and named_failure and "fail" in cases.values():
        return "assertion_failure", cases
    if not any(value in ("pass", "fail") for value in cases.values()):
        return None, cases
    return "test_failure", cases


def _bun_test_evidence(report: Path, cwd: Path, test_file: str, exit_code):
    try:
        root = ET.parse(report).getroot()
    except (OSError, ET.ParseError):
        return None, {}
    cases = {}
    failed = []
    for suite in root.findall("testsuite"):
        for case in suite.findall("testcase"):
            filename = case.get("file") or suite.get("file")
            if not filename or (cwd / filename).resolve() != (cwd / test_file).resolve():
                return None, {}
            name = (case.get("classname"), case.get("name"))
            if not name[1] or name in cases:
                return None, {}
            failure = case.find("failure")
            if failure is not None:
                failed.append(failure.get("type"))
                cases[name] = "fail"
            elif case.find("error") is not None:
                return "test_failure", cases
            elif case.find("skipped") is not None:
                cases[name] = "skip"
            else:
                cases[name] = "pass"
    if root.get("failures") != str(len(failed)) or root.get("errors", "0") != "0":
        return "test_failure", cases
    if exit_code == 0 and not failed and "pass" in cases.values():
        return "passed", cases
    if exit_code == 1 and failed and all(kind == "AssertionError" for kind in failed):
        return "assertion_failure", cases
    if not any(value in ("pass", "fail") for value in cases.values()):
        return None, cases
    return "test_failure", cases


def _unittest_cases(suite):
    pending = [iter(suite)]
    while pending:
        item = next(pending[-1], None)
        if item is None:
            pending.pop()
        elif isinstance(item, unittest.TestSuite):
            if len(pending) >= 100:
                raise ValueError("Unittest suite nesting exceeds 100")
            pending.append(iter(item))
        else:
            yield item


def _run_unittest_selected(filename: Path, report: Path):
    sys.argv[:] = [str(filename)]
    name = filename.stem
    parent = filename.parent
    while (parent / "__init__.py").is_file():
        name = parent.name + "." + name
        parent = parent.parent
    sys.path.insert(0, str(parent))
    spec = importlib.util.spec_from_file_location(name, filename)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)

    suite = unittest.defaultTestLoader.loadTestsFromModule(module)
    selected = list(_unittest_cases(suite))
    for case in selected:
        method = getattr(case, getattr(case, "_testMethodName", ""), None)
        origin = inspect.getsourcefile(inspect.unwrap(method)) if inspect.ismethod(method) else None
        if not origin or Path(origin).resolve() != filename:
            print("Unittest did not establish the selected test file", file=sys.stderr)
            return 1
    if len({case.id() for case in selected}) != len(selected):
        print("Unittest reported duplicate selected test identities", file=sys.stderr)
        return 1

    outcome = unittest.TextTestRunner(verbosity=2).run(suite)
    failures = {getattr(test, "test_case", test).id() for test, _ in outcome.failures}
    skipped = {
        getattr(test, "test_case", test).id()
        for test, _ in outcome.skipped + outcome.expectedFailures
    }
    completed_all = outcome.testsRun == len(selected)
    cases = {
        test.id(): "fail" if test.id() in failures else "pass"
        for test in selected if completed_all and test.id() not in skipped
    }
    report.write_text(json.dumps({
        "cases": cases, "errors": len(outcome.errors),
        "unexpected_successes": len(outcome.unexpectedSuccesses),
    }), encoding="utf-8")
    return 0 if outcome.wasSuccessful() else 1


def _python_test_evidence(report: Path, exit_code):
    try:
        payload = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, {}
    cases = payload["cases"]
    if payload["errors"] or payload["unexpected_successes"]:
        return "test_failure", cases
    if exit_code == 0 and "pass" in cases.values():
        return "passed", cases
    if exit_code == 1 and "fail" in cases.values():
        return "assertion_failure", cases
    return None, cases


def _execute_test_isolated(test_file: str, cwd: Path, custom_cmd=None, timeout: int = 30):
    cmd = detect_test_cmd(test_file, custom_cmd)
    env = os.environ.copy()
    env["PYTHONPATH"] = str(cwd)
    ext = Path(test_file).suffix.lower()
    native_go = not custom_cmd and ext == ".go"
    native_bun = not custom_cmd and cmd[:2] == ["bun", "test"]
    native_python = not custom_cmd and ext == ".py"
    report = cwd.parent / "results"
    run = None
    run_cwd = cwd
    if native_go:
        run_cwd, cmd, run, selected = _go_test_command(cwd, test_file, env, timeout)
    if native_bun:
        cmd += ["--reporter=junit", "--reporter-outfile=" + str(report)]
    if native_python:
        cmd += [str(report)]
    if run is None:
        run = run_command_safe(cmd, cwd=run_cwd, env=env, timeout=timeout)
    classification, reason = classify_test_output(run)
    cases = {}
    if classification not in ("timed_out", "dependency_failure", "infrastructure_error"):
        evidence = None
        if native_go and cmd[:2] == ["go", "test"]:
            evidence, cases = _go_test_evidence(run, selected)
        elif native_bun:
            evidence, cases = _bun_test_evidence(report, cwd, test_file, run["exit_code"])
        elif native_python:
            evidence, cases = _python_test_evidence(report, run["exit_code"])
        if evidence is None:
            classification = "unattributed"
            reason = "The runner did not establish execution of the selected test"
        elif evidence != classification:
            classification = evidence
            reason = "The selected runner reported %s" % evidence
    run.update(classification=classification, reason=reason, command=cmd)
    return run, cases



def _evaluate_test_status(base_cls: str, curr_cls: str) -> str:
    if base_cls == "dependency_failure" or curr_cls == "dependency_failure":
        return "dependency_failure"
    if base_cls == "flaky_nondeterministic" or curr_cls == "flaky_nondeterministic":
        return "flaky_nondeterministic"
    if curr_cls in ("no_tests_ran", "infrastructure_error"):
        return "inconclusive_infrastructure"
    if "unattributed" in (base_cls, curr_cls) or curr_cls == "timed_out":
        return "inconclusive"
    if curr_cls != "passed":
        return "failed_on_current"
    if base_cls == "assertion_failure":
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
    if all(s == "inconclusive_infrastructure" for s in statuses):
        return "inconclusive_infrastructure", "pause", False, "The runner could not evaluate a test because required code or fixtures were missing, or no test ran."
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
    resolved_tests = []
    try:
        commit = _resolve_baseline(root, base)
        resolved_tests = test_files or detect_changed_test_files(root, base=commit)
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
        for name in resolved_tests:
            if not _regular_relative_file(root, name):
                raise ValueError("Test is missing or is not a regular repository-relative file: %r" % name)
        with tempfile.TemporaryDirectory(prefix="anti-slop-proof-") as temp_dir:
            baseline = Path(temp_dir) / "baseline"
            current = Path(temp_dir) / "current"
            baseline.mkdir()
            current.mkdir()
            _create_baseline(root, baseline, commit)
            _copy_snapshot_files(root, baseline, resolved_tests)
            current_paths = _git_paths(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
            _copy_snapshot_files(root, current, set(current_paths).union(resolved_tests))
            results = _run_proof_tests(resolved_tests, baseline, current, test_cmd, timeout, check_flaky)
    except (OSError, RuntimeError, ValueError, subprocess.CalledProcessError) as exc:
        return {
            "status": "inconclusive_infrastructure",
            "verdict": "pause",
            "red_green_verified": False,
            "rationale": "Unable to run proof at baseline '%s': %s" % (base, exc),
            "base_ref": base,
            "test_files": resolved_tests,
            "results": {},
        }
    status, verdict, verified, rationale = _synthesize_proof_verdict(results, base)
    return {
        "status": status,
        "verdict": verdict,
        "red_green_verified": verified,
        "rationale": rationale,
        "base_ref": base,
        "test_files": resolved_tests,
        "results": results,
    }


def _run_proof_test(test_file, snapshot, test_cmd, timeout):
    with tempfile.TemporaryDirectory(prefix="run-", dir=snapshot.parent) as temp_dir:
        checkout = Path(temp_dir) / "checkout"
        shutil.copytree(snapshot, checkout)
        return _execute_test_isolated(test_file, checkout, custom_cmd=test_cmd, timeout=timeout)


def _proof_test_status(baseline, current):
    base_run, baseline_cases = baseline
    current_run, current_cases = current
    status = _evaluate_test_status(base_run["classification"], current_run["classification"])
    if status == "verified" and baseline_cases:
        if any(
            state == "fail" and current_cases.get(name) != "pass"
            for name, state in baseline_cases.items()
        ):
            base_run["classification"] = "unattributed"
            base_run["reason"] = "A failing baseline test did not pass in the current snapshot"
            return "inconclusive"
    return status


def _run_proof_tests(test_files, baseline: Path, current: Path, test_cmd, timeout: int, check_flaky: bool):
    per_test_results = {}
    for test_file in test_files:
        base_result = _run_proof_test(test_file, baseline, test_cmd, timeout)
        current_result = _run_proof_test(test_file, current, test_cmd, timeout)
        status = _proof_test_status(base_result, current_result)
        base_run = base_result[0]
        current_run = current_result[0]
        if check_flaky:
            base_repeat = _run_proof_test(test_file, baseline, test_cmd, timeout)
            current_repeat = _run_proof_test(test_file, current, test_cmd, timeout)
            repeat_status = _proof_test_status(base_repeat, current_repeat)
            if (
                base_result[1] != base_repeat[1]
                or current_result[1] != current_repeat[1]
                or status != repeat_status
                or base_run["classification"] != base_repeat[0]["classification"]
                or current_run["classification"] != current_repeat[0]["classification"]
            ):
                base_run["classification"] = "flaky_nondeterministic"
                base_run["reason"] = "Test outcome varied across repeated executions"
                status = "flaky_nondeterministic"

        per_test_results[test_file] = {
            "status": status,
            "baseline": base_run,
            "current": current_run,
        }

    return per_test_results



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
    if len(sys.argv) == 4 and sys.argv[1] == "_unittest_selected":
        sys.exit(_run_unittest_selected(Path(sys.argv[2]).resolve(), Path(sys.argv[3])))
    sys.exit(main())
