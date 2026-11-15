#!/usr/bin/env python3
"""Replay static guards on bounded, generated Git fixtures."""

import argparse
import json
import os
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
GUARDS = ("diff_guard", "sre_guard")
WORKLOADS = ((3, 3), (100, 100))
CHILD_TIMEOUT_SECONDS = 8


def _environment(root, git):
    env = {
        "HOME": str(root), "XDG_CONFIG_HOME": str(root), "PATH": str(git.parent),
        "LANG": "C", "LC_ALL": "C",
        "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_ALLOW_PROTOCOL": "",
    }
    if os.name == "nt" and "SystemRoot" in os.environ:
        env["SystemRoot"] = os.environ["SystemRoot"]
    return env


def _run(command, cwd, env):
    return subprocess.run(
        command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=CHILD_TIMEOUT_SECONDS, check=False,
    )


def _write_fixture(repo, count, lines, git, env):
    args = [str(git), "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
            "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false"]
    paths = [repo / ("file_%03d.py" % i) for i in range(count)]
    for path in paths:
        path.write_text("initial = 1\n", encoding="utf-8")
    commands = (["init", "-q", "--template="], ["add", "--", "."], ["commit", "-qm", "fixture"])
    for command in commands:
        if _run(args + command, repo, env).returncode != 0:
            raise ValueError("Failed to create the temporary Git fixture")
    for index, path in enumerate(paths):
        contents = "".join("value_%03d_%03d = %d\n" % (index, row, row + index) for row in range(lines))
        path.write_text(contents, encoding="utf-8")


def _guard(repo, env, name, base):
    command = [sys.executable, "-I", "-S", str(SCRIPTS / (name + ".py")), "--repo", str(repo),
               "--base", base, "--json"]
    start = time.monotonic()
    try:
        ran = _run(command, repo, env)
        elapsed = time.monotonic() - start
        report = json.loads(ran.stdout)
    except subprocess.TimeoutExpired:
        return {"status": "inconclusive", "reason": "timeout"}
    except (OSError, ValueError) as error:
        return {"status": "inconclusive", "reason": type(error).__name__}
    if not isinstance(report, dict):
        return {"status": "inconclusive", "reason": "Invalid guard report"}
    if base != "HEAD" and ran.returncode == 1 and report.get("error"):
        return {"status": "expected_error", "exit_code": 1}
    summary = report.get("summary")
    if ran.returncode or not isinstance(summary, dict) or not isinstance(report.get("findings"), list):
        return {"status": "inconclusive", "exit_code": ran.returncode, "reason": "Unexpected guard outcome"}
    scanned = summary.get("changed_files" if name == "diff_guard" else "scanned_files")
    return {"status": "completed", "exit_code": ran.returncode, "scanned_files": scanned, "elapsed": elapsed}


def _measure(repo, env, name, samples, expected_files):
    elapsed = []
    for _ in range(samples):
        result = _guard(repo, env, name, "HEAD")
        if result["status"] != "completed":
            return result
        if result["scanned_files"] != expected_files:
            return {"status": "inconclusive", "reason": "Guard scan scope differed from the fixture"}
        elapsed.append(result["elapsed"])
    return {
        "status": "completed", "exit_code": 0, "scanned_files": expected_files,
        "elapsed_seconds": {"median": round(statistics.median(elapsed), 6), "max": round(max(elapsed), 6)},
    }


def _benchmark(root, git, version, env, samples):
    report = {
        "status": "completed", "samples": samples, "workloads": [],
        "environment": {"git": version, "platform": platform.system() + " " + platform.machine(),
                        "python": platform.python_version()},
    }
    for number, (count, lines) in enumerate(WORKLOADS):
        repo = root / ("workload-%d" % number)
        repo.mkdir()
        _write_fixture(repo, count, lines, git, env)
        measurements = {name: _measure(repo, env, name, samples, count) for name in GUARDS}
        invalid = {name: _guard(repo, env, name, "unavailable-fixture-base") for name in GUARDS}
        if any(item["status"] != "completed" for item in measurements.values()) or any(
            item["status"] != "expected_error" for item in invalid.values()
        ):
            report["status"] = "inconclusive"
        report["workloads"].append({
            "fixture_files": count, "fixture_added_lines": count * lines,
            "guards": measurements, "invalid_base": invalid,
        })
    return report


def _collect_report(samples):
    executable = shutil.which("git")
    if executable is None:
        return {"status": "inconclusive", "reason": "Git is unavailable"}
    try:
        git = Path(executable).absolute()
        with tempfile.TemporaryDirectory(prefix="anti-slop-static-benchmark-") as directory:
            root = Path(directory).resolve()
            env = _environment(root, git)
            version = _run([str(git), "--version"], root, env)
            if version.returncode != 0:
                return {"status": "inconclusive", "reason": "Git version is unavailable"}
            return _benchmark(root, git, version.stdout.decode("utf-8", "replace").strip(), env, samples)
    except subprocess.TimeoutExpired:
        return {"status": "inconclusive", "reason": "Git fixture setup timed out"}
    except (OSError, ValueError) as error:
        return {"status": "inconclusive", "reason": str(error)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", type=int, choices=range(1, 6), default=5)
    args = parser.parse_args()
    report = _collect_report(args.samples)
    print(json.dumps(report, indent=2))
    sys.exit(0 if report["status"] == "completed" else 2)
