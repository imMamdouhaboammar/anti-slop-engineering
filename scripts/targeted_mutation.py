#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Mutate changed Python conditions or Boolean returns and run a trusted unittest file in disposable copies.

A test file whose own line declares `# targeted-mutation: external-action` is
excluded before any execution: neither the baseline nor any mutant runs, and
the report records the exclusion outside the score denominator.
"""

import argparse
import ast
from itertools import accumulate
import json
import os
from pathlib import Path
import random
import shutil
import sys
import tempfile

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.git_changeset import collect_changes, git, repository_root
from scripts.verification_oracle_guard import (
    _copy_snapshot_files,
    _execute_test_isolated,
    _regular_relative_file,
)

MAX_MUTANTS = 4
TEST_TIMEOUT = 10
NEGATE_CONDITION = "negate_condition"
FLIP_BOOLEAN_RETURN = "flip_boolean_return"
EXTERNAL_ACTION_MARKER = "# targeted-mutation: external-action"


def external_action_line(test_source):
    for number, line in enumerate(test_source.decode("utf-8").splitlines(), start=1):
        if line.strip() == EXTERNAL_ACTION_MARKER:
            return number
    return None


def changed_expressions(source, function_name, hunks, operator):
    tree = ast.parse(source.decode("utf-8"))
    functions = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name]
    if len(functions) != 1:
        raise ValueError(f"Expected one top-level function named {function_name!r}")
    statements = functions[0].body
    if operator == NEGATE_CONDITION:
        expressions = (statement.test for statement in statements if isinstance(statement, ast.If))
    else:
        expressions = (
            statement.value for statement in statements
            if isinstance(statement, ast.Return) and isinstance(statement.value, ast.Constant)
            and type(statement.value.value) is bool
        )
    return [
        node for node in expressions if any(
            hunk["new_count"] and hunk["new_start"] <= node.end_lineno
            and node.lineno < hunk["new_start"] + hunk["new_count"]
            for hunk in hunks
        )
    ]


def mutate_expression(source, node, offsets, operator):
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    if operator == NEGATE_CONDITION:
        replacement = b"not (" + source[start:end] + b")"
    else:
        replacement = b"False" if node.value else b"True"
    return source[:start] + replacement + source[end:]


def run_snapshot_test(snapshot, work, test_file, source_file, replacement=None):
    work.mkdir()
    checkout = work / "repo"
    shutil.copytree(snapshot, checkout)
    if replacement is not None:
        (checkout / source_file).write_bytes(replacement)
    return _execute_test_isolated(test_file, checkout, timeout=TEST_TIMEOUT)


def score_mutants(report, candidates, snapshot, workspace, source_file, test_file, source, baseline_cases, operator):
    offsets = list(accumulate(map(len, source.splitlines(keepends=True)), initial=0))
    for number, expression in enumerate(candidates):
        mutant = mutate_expression(source, expression, offsets, operator)
        status = "inconclusive"
        try:
            compile(mutant, source_file, "exec")
        except (SyntaxError, ValueError):
            observation, status = "invalid_source", "invalid"
        else:
            result, cases = run_snapshot_test(
                snapshot, workspace / f"run-{number}", test_file, source_file, mutant,
            )
            observation = result["classification"]
            if cases.keys() == baseline_cases.keys():
                if observation == "assertion_failure":
                    status = "killed"
                elif observation == "passed":
                    status = "survived"
        report["results"].append({
            "operator": operator,
            "line": expression.lineno,
            "end_line": expression.end_lineno,
            "status": status,
            "observation": observation,
        })
        report["score"]["evaluated"] += int(status in {"killed", "survived"})
        report["score"]["killed"] += int(status == "killed")
    if report["score"]["evaluated"]:
        report["status"] = "evaluated"


def run_targeted_mutation(root, source_file, function_name, test_file, base, seed, operator=NEGATE_CONDITION):
    if operator not in {NEGATE_CONDITION, FLIP_BOOLEAN_RETURN}:
        raise ValueError(f"Unsupported mutation operator: {operator!r}")
    tracked = {os.fsdecode(item) for item in git(root, "ls-files", "--cached", "-z").split(b"\0") if item}
    for name, directory in ((source_file, "scripts"), (test_file, "tests")):
        path = Path(name)
        if (path.suffix != ".py" or not path.parts or path.parts[0] != directory
                or name not in tracked or not _regular_relative_file(root, name)):
            raise ValueError(f"Expected a tracked regular Python file under {directory}/: {name!r}")

    source = (root / source_file).read_bytes()
    test_source = (root / test_file).read_bytes()
    changes = collect_changes(root, base)
    hunks = next((entry["hunks"] for entry in changes["files"]
                  if entry["new_path"] and entry["new_path"]["text"] == source_file and not entry["binary"]), ())
    candidates = changed_expressions(source, function_name, hunks, operator)
    random.Random(seed).shuffle(candidates)
    report = {
        "status": "no_mutants" if not candidates else "inconclusive",
        "source": source_file, "function": function_name, "test": test_file, "seed": seed,
        "base": changes["base"], "eligible": len(candidates), "baseline": "not_run",
        "results": [], "score": {"killed": 0, "evaluated": 0}, "exclusion": None,
    }
    if not candidates:
        return report
    marker_line = external_action_line(test_source)
    if marker_line is not None:
        report["status"] = "excluded"
        report["exclusion"] = {"marker": "external-action", "line": marker_line}
        return report

    with tempfile.TemporaryDirectory(prefix="anti-slop-targeted-mutation-") as work:
        workspace = Path(work)
        snapshot = workspace / "snapshot"
        _copy_snapshot_files(root, snapshot, tracked)
        if (snapshot / source_file).read_bytes() != source or (snapshot / test_file).read_bytes() != test_source:
            raise ValueError("The selected source or test changed during snapshot creation")
        baseline, cases = run_snapshot_test(snapshot, workspace / "baseline", test_file, source_file)
        report["baseline"] = baseline["classification"]
        if baseline["classification"] == "passed":
            score_mutants(report, candidates[:MAX_MUTANTS], snapshot, workspace, source_file, test_file, source, cases, operator)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Tracked Python source under scripts/")
    parser.add_argument("--function", required=True, help="Top-level function containing the changed expression")
    parser.add_argument("--test", required=True, help="Tracked offline unittest file under tests/")
    parser.add_argument("--base", default="HEAD", help="Git commit used to select changed lines")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--operator", choices=(NEGATE_CONDITION, FLIP_BOOLEAN_RETURN), default=NEGATE_CONDITION)
    args = parser.parse_args()
    try:
        report = run_targeted_mutation(
            Path(repository_root(Path.cwd())).resolve(),
            args.source, args.function, args.test, args.base, args.seed, args.operator,
        )
    except (OSError, RuntimeError, SyntaxError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "evaluated" else 2


if __name__ == "__main__":
    sys.exit(main())
