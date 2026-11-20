#!/usr/bin/env python3
"""Verify one exported symbol of an installed TypeScript package with a selected compiler."""

import argparse
import json
from pathlib import Path
import re
import sys
import tempfile

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.python_api_evidence import read_bounded
from scripts.typescript_compiler_evidence import _paths, run_bounded

HELPER = Path(__file__).resolve().with_name("typescript_api_evidence.mjs")
SYMBOL_PATTERN = re.compile(r"[A-Za-z_$][A-Za-z0-9_$]*\Z")
PACKAGE_PATTERN = re.compile(r"(@[a-z0-9][a-z0-9._-]*/)?[a-z0-9][a-z0-9._-]*\Z")


def package_version(workspace, package):
    manifest = workspace / "node_modules" / Path(package) / "package.json"
    metadata = json.loads(read_bounded(manifest))
    version = metadata.get("version")
    if metadata.get("name") != package or not isinstance(version, str) or not version:
        raise ValueError("Installed package metadata does not identify the requested package")
    return version


def installed_api(workspace_arg, package, symbol, node, compiler, version):
    result = {"package": package, "symbol": symbol}
    if not workspace_arg.is_dir():
        return {**result, "status": "not_checked", "reason": "The selected workspace is unavailable"}
    try:
        workspace = workspace_arg.resolve(strict=True)
        result["version"] = package_version(workspace, package)
    except (OSError, ValueError, TypeError) as error:
        return {**result, "status": "inconclusive", "reason": str(error)}
    with tempfile.TemporaryDirectory(prefix="anti-slop-ts-api-") as directory:
        env = {"PATH": "/usr/bin:/bin", "HOME": directory, "TMPDIR": directory, "LANG": "C"}
        ran = run_bounded(
            [str(node), "--max-old-space-size=128", str(HELPER), str(compiler),
             str(workspace), package, symbol],
            Path(directory), env, timeout=15,
        )
    if ran["status"] != "completed" or ran["code"] != 0:
        return {**result, "status": "inconclusive", "reason": "The selected compiler did not return evidence"}
    try:
        evidence = json.loads(ran["output"])
    except ValueError:
        return {**result, "status": "inconclusive", "reason": "The selected compiler returned an unreadable result"}
    if evidence.get("compiler_version") != version:
        return {**result, "status": "inconclusive",
                "reason": "Compiler version does not match installed package metadata"}
    status = evidence.get("status")
    if status == "not_declared":
        return {**result, "status": "not_declared"}
    if status != "declared":
        return {**result, "status": "inconclusive",
                "reason": evidence.get("reason", "The selected compiler returned an unclassified outcome")}
    try:
        module = Path(evidence["path"]).relative_to(workspace).as_posix()
        span = {"path": module, "line": evidence["line"], "column": evidence["column"],
                "end_line": evidence["end_line"], "end_column": evidence["end_column"]}
    except (KeyError, TypeError, ValueError):
        return {**result, "status": "inconclusive",
                "reason": "The declaration lies outside the selected workspace"}
    return {**result, "status": "declared", "declaration_span": span,
            "provenance": {"installation": str(workspace), "module": module}}


def collect(workspace, package, symbol, node, tsc_js):
    compiler = {"toolchain": "typescript", "status": "not_checked", "path": str(tsc_js)}
    api = {"package": package, "symbol": symbol, "status": "not_checked"}
    if not PACKAGE_PATTERN.fullmatch(package) or not SYMBOL_PATTERN.fullmatch(symbol):
        return compiler, {**api, "status": "inconclusive",
                          "reason": "Package and symbol must be plain npm and identifier names"}
    try:
        node_path, compiler_path, version = _paths(node, tsc_js)
    except (OSError, UnicodeError, ValueError, AttributeError):
        return compiler, {**api, "reason": "Trusted installed Node and TypeScript compiler could not be verified"}
    compiler["version"] = version
    api = installed_api(workspace, package, symbol, node_path, compiler_path, version)
    if api["status"] != "not_checked":
        compiler["status"] = "passed"
    return compiler, api


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True,
                        help="Workspace whose node_modules holds the installed package")
    parser.add_argument("--package", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--node", type=Path, required=True, help="Trusted installed Node executable")
    parser.add_argument("--tsc-js", type=Path, required=True, help="Trusted installed TypeScript lib/tsc.js")
    args = parser.parse_args()
    compiler, api = collect(args.workspace, args.package, args.symbol, args.node, args.tsc_js)
    print(json.dumps({"compiler": compiler, "installed_api": api}, indent=2))
    return 0 if api["status"] == "declared" else 2


if __name__ == "__main__":
    sys.exit(main())
