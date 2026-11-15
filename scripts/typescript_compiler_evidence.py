#!/usr/bin/env python3
"""Probe an explicitly selected TypeScript compiler against two fixed fixtures."""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import tempfile

if sys.platform != "win32":
    import resource
from pathlib import Path

SANDBOX = Path("/usr/bin/sandbox-exec")
PROFILE = "(version 1)(allow default)(deny network*)"
CONTROL = "const count: number = 42;\n"
TYPE_ERROR = "const count: number = 'wrong';\n"


def parse_diagnostics(output):
    diagnostics = []
    for row in output.decode("utf-8", "replace").splitlines():
        location, delimiter, error = row.partition("): error ")
        path, opening, position = location.partition("(")
        line, comma, column = position.partition(",")
        code, colon, message = error.partition(": ")
        fields = (line, column, code[2:])
        if path != "fixture.ts" or not (delimiter and opening and comma and colon and code.startswith("TS")):
            continue
        if all(field.isascii() and field.isdecimal() and len(field) <= 6 for field in fields):
            diagnostics.append({"path": path, "line": int(line), "column": int(column),
                                "code": code, "message": message})
    return diagnostics


def run_bounded(command, cwd, env, timeout=8, limit=32768):
    if sys.platform == "win32":
        return {"status": "unavailable"}

    def limit_child():
        resource.setrlimit(resource.RLIMIT_FSIZE, (limit, limit))
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))

    with tempfile.TemporaryFile(dir=cwd) as output:
        try:
            child = subprocess.Popen(
                command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=output,
                stderr=subprocess.STDOUT, start_new_session=True, preexec_fn=limit_child,
            )
        except (OSError, subprocess.SubprocessError):
            return {"status": "unavailable"}
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                return {"status": "timeout"}
            finally:
                child.wait()
            return {"status": "timeout"}
        if output.tell() >= limit:
            return {"status": "output_limit"}
        output.seek(0)
        return {"status": "completed", "code": code, "output": output.read(limit)}


def _paths(node, compiler):
    node = node.resolve(strict=True)
    compiler = compiler.resolve(strict=True)
    if not node.is_file() or not os.access(node, os.X_OK):
        raise ValueError("Select a trusted installed Node executable")
    if not compiler.is_file() or compiler.name != "tsc.js" or compiler.parent.name != "lib":
        raise ValueError("Select lib/tsc.js of a trusted TypeScript installation")
    manifest = compiler.parents[1] / "package.json"
    if not manifest.is_file() or manifest.resolve() != manifest or manifest.stat().st_size > 65536:
        raise ValueError("Cannot verify TypeScript package metadata")
    metadata = json.loads(manifest.read_text(encoding="utf-8"))
    version = metadata.get("version")
    if metadata.get("name") != "typescript" or not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+(?:-[\w.-]+)?", version):
        raise ValueError("Cannot verify TypeScript package identity")
    return node, compiler, version


def _sandbox_probe(node, cwd, env):
    canary = "const net = require('node:net'); const attempt = net.createServer(); " \
             "attempt.on('error', err => process.exit(['EPERM', 'EACCES'].includes(err.code) ? 0 : 3)); " \
             "attempt.listen(0, '127.0.0.1', () => process.exit(2));"
    return run_bounded([str(SANDBOX), "-p", PROFILE, str(node), "-e", canary], cwd, env)


def _check_fixture(prefix, cwd, env, content):
    (cwd / "fixture.ts").write_text(content, encoding="utf-8")
    ran = run_bounded(prefix + ["--pretty", "false", "--noEmit", "--strict", "--noResolve",
                                "--lib", "es2020", "--typeRoots", "empty-types", "fixture.ts"], cwd, env)
    if ran["status"] != "completed":
        return {"status": "not_checked", "reason": ran["status"]}
    diagnostics = parse_diagnostics(ran["output"])
    if ran["code"] == 0 and not ran["output"]:
        return {"status": "passed"}
    if diagnostics and ran["code"] > 0:
        return {"status": "diagnostic", "exit_code": ran["code"], "diagnostics": diagnostics}
    return {"status": "not_checked", "reason": "Compiler returned an unclassified outcome"}


def expected_type_error(diagnostics):
    return any(
        item["path"] == "fixture.ts" and item["line"] == 1 and item["column"] == 7 and item["code"] == "TS2322"
        for item in diagnostics
    )


def collect(node, compiler):
    result = {"toolchain": "typescript", "status": "not_checked", "scope": "fixed fixture"}
    if sys.platform != "darwin" or not SANDBOX.is_file():
        return {**result, "reason": "Verified macOS network sandbox unavailable"}
    try:
        node, compiler, version = _paths(node, compiler)
    except (OSError, UnicodeError, ValueError, AttributeError):
        return {**result, "reason": "Trusted installed Node and TypeScript compiler could not be verified"}
    result["version"] = version
    with tempfile.TemporaryDirectory(prefix="anti-slop-ts-fixture-") as directory:
        cwd = Path(directory)
        (cwd / "empty-types").mkdir()
        env = {"PATH": "/usr/bin:/bin", "HOME": directory, "TMPDIR": directory, "LANG": "C"}
        probe = _sandbox_probe(node, cwd, env)
        if probe.get("code") != 0 or probe.get("output") != b"":
            return {**result, "reason": "Loopback network denial could not be verified"}
        prefix = [str(SANDBOX), "-p", PROFILE, str(node), "--max-old-space-size=128", str(compiler)]
        reported = run_bounded(prefix + ["--version"], cwd, env)
        if reported.get("code") != 0 or reported.get("output", b"").strip() != ("Version " + version).encode():
            return {**result, "reason": "Compiler version does not match installed package metadata"}
        result["network_isolation"] = "macOS sandbox; loopback bind denied"
        result["control"] = _check_fixture(prefix, cwd, env, CONTROL)
        result["type_error"] = _check_fixture(prefix, cwd, env, TYPE_ERROR)
    errors = result["type_error"].get("diagnostics", [])
    if result["control"]["status"] == "passed" and expected_type_error(errors):
        result["status"] = "passed"
    else:
        result["reason"] = "Fixed fixture did not reproduce the expected TypeScript control and diagnostic"
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=Path, required=True, help="Trusted installed Node executable")
    parser.add_argument("--tsc-js", type=Path, required=True, help="Trusted installed TypeScript lib/tsc.js")
    args = parser.parse_args()
    result = collect(args.node, args.tsc_js)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    sys.exit(main())
