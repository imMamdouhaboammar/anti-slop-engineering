#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Mutate changed Python conditions and run a trusted unittest file in disposable copies."""

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


def changed_conditions(source, function_name, hunks):
    tree = ast.parse(source.decode("utf-8"))
    functions = [node for node in tree.body
                 if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name]
    if len(functions) != 1:
        raise ValueError(f"Expected one top-level function named {function_name!r}")
    return [
        statement.test
        for statement in functions[0].body
        if isinstance(statement, ast.If) and any(
            hunk["new_count"] and hunk["new_start"] <= statement.test.end_lineno
            and statement.test.lineno < hunk["new_start"] + hunk["new_count"]
            for hunk in hunks
        )
    ]


def negate_condition(source, node, offsets):
    start = offsets[node.lineno - 1] + node.col_offset
    end = offsets[node.end_lineno - 1] + node.end_col_offset
    return source[:start] + b"not (" + source[start:end] + b")" + source[end:]


def run_snapshot_test(snapshot, work, test_file, source_file, replacement=None):
    work.mkdir()
    checkout = work / "repo"
    shutil.copytree(snapshot, checkout)
    if replacement is not None:
        (checkout / source_file).write_bytes(replacement)
    return _execute_test_isolated(test_file, checkout, timeout=TEST_TIMEOUT)


def score_mutants(report, candidates, snapshot, workspace, source_file, test_file, source, baseline_cases):
    offsets = list(accumulate(map(len, source.splitlines(keepends=True)), initial=0))
    for number, condition in enumerate(candidates):
        mutant = negate_condition(source, condition, offsets)
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
            "operator": "negate_condition",
            "line": condition.lineno,
            "end_line": condition.end_lineno,
            "status": status,
            "observation": observation,
        })
        report["score"]["evaluated"] += int(status in {"killed", "survived"})
        report["score"]["killed"] += int(status == "killed")
    if report["score"]["evaluated"]:
        report["status"] = "evaluated"


def run_targeted_mutation(root, source_file, function_name, test_file, base, seed):
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
    candidates = changed_conditions(source, function_name, hunks)
    random.Random(seed).shuffle(candidates)
    report = {
        "status": "no_mutants" if not candidates else "inconclusive",
        "source": source_file, "function": function_name, "test": test_file, "seed": seed,
        "base": changes["base"], "eligible": len(candidates), "baseline": "not_run",
        "results": [], "score": {"killed": 0, "evaluated": 0},
    }
    if not candidates:
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
            score_mutants(report, candidates[:MAX_MUTANTS], snapshot, workspace, source_file, test_file, source, cases)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Tracked Python source under scripts/")
    parser.add_argument("--function", required=True, help="Top-level function with direct if statements")
    parser.add_argument("--test", required=True, help="Tracked offline unittest file under tests/")
    parser.add_argument("--base", default="HEAD", help="Git commit used to select changed lines")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    try:
        report = run_targeted_mutation(
            Path(repository_root(Path.cwd())).resolve(),
            args.source, args.function, args.test, args.base, args.seed,
        )
    except (OSError, RuntimeError, SyntaxError, ValueError) as error:
        parser.error(str(error))
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "evaluated" else 2


if __name__ == "__main__":
    sys.exit(main())
