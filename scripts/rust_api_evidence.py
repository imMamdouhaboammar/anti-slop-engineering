#!/usr/bin/env python3
"""Verify one public item of an installed Rust crate with a selected rustc."""

import argparse
import json
import os
from pathlib import Path
import re
import sys
import tempfile

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.python_api_evidence import read_bounded
from scripts.typescript_compiler_evidence import run_bounded

CRATE_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*\Z")
SYMBOL_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
VERSION_PATTERN = re.compile(r"rustc (\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?)")
ITEM_PATTERN = re.compile(
    r"^pub\s+(?:(?:async|const|unsafe)\s+)*(?:fn|struct|enum|trait|const|static|type)"
    r"\s+([A-Za-z_][A-Za-z0-9_]*)\b")
EDITIONS = {"2015", "2018", "2021", "2024"}


def _bounded_run(command, directory):
    env = {"PATH": "/usr/bin:/bin", "HOME": directory, "TMPDIR": directory, "LANG": "C"}
    # A rustup-managed rustc finds its toolchain through RUSTUP_HOME/CARGO_HOME
    # (or $HOME/.rustup); HOME above points into the run directory, so pass the
    # toolchain locations through explicitly. They name directories, not secrets.
    for name in ("RUSTUP_HOME", "CARGO_HOME"):
        if name in os.environ:
            env[name] = os.environ[name]
    if "RUSTUP_HOME" not in env and os.environ.get("HOME"):
        default = Path(os.environ["HOME"]) / ".rustup"
        if default.is_dir():
            env["RUSTUP_HOME"] = str(default)
    return run_bounded(command, Path(directory), env, timeout=15)


def rustc_identity(rustc_arg, directory):
    # Do not resolve symlinks: a rustup shim dispatches on its own file name,
    # so the selected path must be invoked exactly as selected.
    rustc = rustc_arg.absolute()
    if not rustc.is_file() or not os.access(rustc, os.X_OK):
        raise ValueError("Select a trusted installed rustc executable")
    ran = _bounded_run([str(rustc), "--version"], directory)
    if ran["status"] != "completed" or ran["code"] != 0:
        raise ValueError("The selected rustc did not return its version")
    match = VERSION_PATTERN.search(ran["output"].decode("utf-8", "replace"))
    if not match:
        raise ValueError("The selected rustc returned an unreadable version")
    return {"toolchain": "rustc", "version": match.group(1), "path": str(rustc)}


def _table_body(text, header):
    match = re.search(r"(?m)^\[" + re.escape(header) + r"\]\s*$", text)
    if not match:
        return None
    rest = text[match.end():]
    next_table = re.search(r"(?m)^\[", rest)
    return rest[:next_table.start()] if next_table else rest


def _string_field(body, field):
    match = re.search(r"(?m)^" + field + r"\s*=\s*\"([^\"]*)\"\s*$", body)
    return match.group(1) if match else None


def crate_metadata(root, crate):
    manifest_path = root / "Cargo.toml"
    text = read_bounded(manifest_path).decode("utf-8")
    package = _table_body(text, "package")
    if package is None:
        raise ValueError("Installed crate metadata has no [package] table")
    name = _string_field(package, "name")
    version = _string_field(package, "version")
    if name != crate or not version:
        raise ValueError("Installed crate metadata does not identify the requested crate")
    if (root / "build.rs").is_file():
        raise ValueError("The crate ships a build script; this receipt never runs build scripts")
    for header in ("dependencies", "dev-dependencies", "build-dependencies"):
        body = _table_body(text, header)
        if body and re.search(r"(?m)^[A-Za-z0-9_-]+\s*=", body):
            raise ValueError("The crate declares dependencies; this receipt never fetches them")
    lock_path = root / "Cargo.lock"
    if lock_path.is_file():
        lock = read_bounded(lock_path).decode("utf-8")
        for block in re.split(r"(?m)^\[\[package\]\]\s*$", lock)[1:]:
            if _string_field(block, "name") == crate and _string_field(block, "version") != version:
                raise ValueError("Cargo.lock disagrees with Cargo.toml for the requested crate")
    lib = _table_body(text, "lib")
    lib_path = _string_field(lib, "path") if lib else None
    edition = _string_field(package, "edition") or "2021"
    if edition not in EDITIONS:
        raise ValueError("Installed crate metadata declares an unsupported edition")
    return version, lib_path or "src/lib.rs", edition


def compile_lib(rustc_path, root, lib_relative, edition, directory):
    output = Path(directory) / "lib.rmeta"
    ran = _bounded_run(
        [rustc_path, "--edition", edition, "--crate-type", "lib", "--emit", "metadata",
         "-o", str(output), str(root / lib_relative)],
        directory,
    )
    if ran["status"] != "completed":
        return {"status": "not_checked", "reason": "The selected rustc did not return evidence"}
    text = ran["output"].decode("utf-8", "replace")
    if ran["code"] == 0:
        return {"status": "passed"}
    diagnostic = {"status": "diagnostic", "message": "rustc rejected the installed crate source"}
    for line in text.splitlines():
        if line.startswith("error"):
            diagnostic["message"] = line
            break
    location = re.search(r"--> [^:]+:(\d+):(\d+)", text)
    if location:
        diagnostic["line"] = int(location.group(1))
        diagnostic["column"] = int(location.group(2))
    return diagnostic


def _depths(lines):
    """Brace depth at the start of each line, skipping comments and literals."""
    depths = []
    depth = 0
    state = None
    for line in lines:
        depths.append(depth)
        index = 0
        while index < len(line):
            pair = line[index:index + 2]
            char = line[index]
            if state == "block":
                if pair == "*/":
                    state = None
                    index += 2
                    continue
            elif state in ("string", "char"):
                if char == "\\":
                    index += 2
                    continue
                if char == ('"' if state == "string" else "'"):
                    state = None
            elif pair == "//":
                break
            elif pair == "/*":
                state = "block"
                index += 2
                continue
            elif char == '"':
                state = "string"
            elif char == "'":
                state = "char"
            elif char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
            index += 1
    return depths


def find_declaration(lines, symbol):
    depths = _depths(lines)
    attributes = []
    for index, line in enumerate(lines):
        stripped = line.strip()
        if depths[index] == 0 and stripped.startswith("#["):
            attributes.append(stripped)
            continue
        match = ITEM_PATTERN.match(line) if depths[index] == 0 else None
        if match and match.group(1) == symbol:
            conditional = any(attr.startswith("#[cfg(") or attr.startswith("#[cfg_attr(")
                              for attr in attributes)
            end = index
            while end < len(lines) - 1 and "{" not in lines[end] and not lines[end].rstrip().endswith(";"):
                end += 1
            span = {"line": index + 1, "column": 0,
                    "end_line": end + 1, "end_column": len(lines[end].rstrip())}
            return ("conditional" if conditional else "declared"), span
        if stripped and not stripped.startswith("//"):
            attributes = []
    return None, None


def installed_api(installed_arg, crate, symbol, rustc_path):
    result = {"crate": crate, "symbol": symbol}
    if not installed_arg.is_dir():
        return {**result, "status": "not_checked",
                "reason": "The selected installed crate is unavailable"}
    try:
        root = installed_arg.resolve(strict=True)
        version, lib_relative, edition = crate_metadata(root, crate)
        result["version"] = version
        lib_path = root / lib_relative
        source = read_bounded(lib_path).decode("utf-8")
    except (OSError, ValueError, UnicodeDecodeError) as error:
        return {**result, "status": "inconclusive", "reason": str(error)}
    with tempfile.TemporaryDirectory(prefix="anti-slop-rust-api-") as directory:
        compiled = compile_lib(rustc_path, root, lib_relative, edition, directory)
    if compiled["status"] != "passed":
        return {**result, "status": "not_checked",
                "reason": "The installed crate source did not compile", "compiler": compiled}
    lines = source.splitlines()
    outcome, span = find_declaration(lines, symbol)
    if outcome == "declared":
        return {**result, "status": "declared",
                "declaration_span": {"path": lib_relative, **span},
                "provenance": {"installation": str(root), "module": lib_relative}}
    if outcome == "conditional":
        return {**result, "status": "inconclusive",
                "reason": "The declaration is conditionally compiled (cfg)"}
    if "pub use" in source or "include!" in source or "macro_rules!" in source:
        return {**result, "status": "inconclusive",
                "reason": "No direct declaration; re-exports, includes or macro-generated items may apply"}
    return {**result, "status": "not_declared",
            "reason": "No direct declaration in the installed crate source"}


def collect(installed, crate, symbol, rustc):
    compiler = {"toolchain": "rustc", "status": "not_checked", "path": str(rustc)}
    api = {"crate": crate, "symbol": symbol, "status": "not_checked"}
    if not CRATE_PATTERN.fullmatch(crate) or not SYMBOL_PATTERN.fullmatch(symbol):
        return compiler, {**api, "status": "inconclusive",
                          "reason": "Crate and symbol must be plain Rust names"}
    with tempfile.TemporaryDirectory(prefix="anti-slop-rust-api-") as directory:
        try:
            identity = rustc_identity(rustc, directory)
        except (OSError, ValueError) as error:
            return compiler, {**api, "reason": "Trusted installed rustc could not be verified: %s" % error}
    compiler.update(identity)
    api = installed_api(installed, crate, symbol, compiler["path"])
    nested = api.pop("compiler", None)
    if nested is not None:
        compiler.update(nested)
    elif api["status"] in ("declared", "not_declared", "inconclusive") and "version" in api:
        compiler["status"] = "passed"
    return compiler, api


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installed", type=Path, required=True,
                        help="Directory holding the installed crate (Cargo.toml and sources)")
    parser.add_argument("--crate", required=True)
    parser.add_argument("--symbol", required=True)
    parser.add_argument("--rustc", type=Path, required=True, help="Trusted installed rustc executable")
    args = parser.parse_args()
    compiler, api = collect(args.installed, args.crate, args.symbol, args.rustc)
    print(json.dumps({"compiler": compiler, "installed_api": api}, indent=2))
    if compiler["status"] == "diagnostic":
        return 1
    return 0 if api["status"] == "declared" else 2


if __name__ == "__main__":
    sys.exit(main())
