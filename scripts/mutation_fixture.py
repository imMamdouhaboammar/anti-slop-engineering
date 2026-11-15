#!/usr/bin/env python3
"""Run a fixed mutation-testing fixture in bounded Python children."""

import argparse
import ast
import json
import random
import subprocess
import sys
import tempfile
from pathlib import Path

SOURCE = "def select(enabled):\n    if enabled:\n        return 4\n    return 0\n"
CASES = ("condition", "return", "invalid_ast", "unavailable", "timeout")
CHILD_TIMEOUT = 1


def _child(case):
    tree = ast.parse(SOURCE)
    branch = tree.body[0].body[0]
    if case == "condition":
        branch.test = ast.UnaryOp(op=ast.Not(), operand=branch.test)
    elif case == "return":
        tree.body[0].body[1].value = ast.Constant(value=2)
    elif case == "invalid_ast":
        tree.body[0].body[1].value = ast.Pass()
    elif case == "unavailable":
        return 4
    elif case == "timeout":
        try:
            sys.stdin.read()
        except OSError:
            return 4
        return 4

    try:
        program = compile(ast.fix_missing_locations(tree), "<built-in fixture>", "exec")
    except (SyntaxError, TypeError, ValueError):
        return 3
    globals_scope = {}
    exec(program, globals_scope)  # The program originates only from SOURCE above.
    return 0 if globals_scope["select"](True) == 4 else 1


def _run_case(case, cwd):
    script = Path(__file__).resolve()
    stdin = subprocess.PIPE if case == "timeout" else subprocess.DEVNULL
    try:
        with subprocess.Popen(
            [sys.executable, "-I", "-S", str(script), "--worker", case],
            cwd=cwd, stdin=stdin, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        ) as child:
            try:
                code = child.wait(timeout=CHILD_TIMEOUT)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
                return "timed_out"
    except OSError:
        return "unavailable"
    return {0: "passed", 1: "failed", 3: "invalid"}.get(code, "unavailable")


def evaluate(seed, runner):
    baseline = runner("baseline")
    report = {
        "seed": seed, "baseline": baseline, "results": [],
        "score": {"killed": 0, "evaluated": 0}, "status": "inconclusive",
    }
    if baseline != "passed":
        return report

    cases = list(CASES)
    random.Random(seed).shuffle(cases)
    statuses = {"passed": "survived", "failed": "killed", "invalid": "invalid"}
    for case in cases:
        result = runner(case)
        state = statuses.get(result, "inconclusive")
        report["results"].append({"mutant": case, "status": state, "observation": result})
        if state in {"killed", "survived"}:
            report["score"]["evaluated"] += 1
        if state == "killed":
            report["score"]["killed"] += 1
    report["status"] = "fixture_evaluated"
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--worker", choices=("baseline",) + CASES, help=argparse.SUPPRESS)
    options = parser.parse_args()
    if options.worker:
        return _child(options.worker)

    with tempfile.TemporaryDirectory(prefix="anti-slop-mutation-fixture-") as work:
        report = evaluate(options.seed, lambda case: _run_case(case, work))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "fixture_evaluated" else 2


if __name__ == "__main__":
    sys.exit(main())
