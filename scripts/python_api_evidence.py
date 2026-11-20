#!/usr/bin/env python3
"""Compile a Python file without running it and inspect a selected installed API."""

import argparse
import ast
import csv
import json
import re
import sys
from email.parser import BytesParser
from pathlib import Path

MAX_FILE_BYTES = 1024 * 1024


def read_bounded(path):
    if not path.is_file():
        raise ValueError("Expected a regular file")
    with path.open("rb") as reader:
        data = reader.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("File exceeds the 1 MiB inspection limit")
    return data


def compiler_evidence(source):
    compiler = {"toolchain": sys.implementation.name, "version": sys.version.split()[0], "path": str(source)}
    try:
        compile(read_bounded(source), str(source), "exec", dont_inherit=True)
    except SyntaxError as error:
        return {
            **compiler, "status": "diagnostic", "message": error.msg,
            "line": error.lineno, "column": error.offset,
            "end_line": getattr(error, "end_lineno", None), "end_column": getattr(error, "end_offset", None),
        }
    except (OSError, ValueError, RecursionError) as error:
        return {**compiler, "status": "not_checked", "reason": str(error)}
    return {**compiler, "status": "passed"}


def normalized_name(value):
    return re.sub(r"[-_.]+", "-", value).casefold()


def regular_child(root, relative):
    path = root / relative
    try:
        resolved = path.resolve(strict=True)
    except FileNotFoundError:
        return None
    if resolved != path or not resolved.is_file():
        raise ValueError("Installation evidence must be a regular file inside the selected site-packages")
    return resolved


def find_distribution(root, name):
    matches = []
    expected = normalized_name(name)
    for info in root.glob("*.dist-info"):
        dist_name, _, _ = info.name[:-10].rpartition("-")
        if normalized_name(dist_name) == expected:
            matches.append(info.name)
    if len(matches) != 1:
        raise ValueError("Distribution is missing or ambiguous in the selected installation")
    relative = matches[0]
    metadata = regular_child(root, relative + "/METADATA")
    ownership = regular_child(root, relative + "/RECORD")
    if not metadata or not ownership:
        raise ValueError("Installed distribution metadata or file ownership list is missing")
    headers = BytesParser().parsebytes(read_bounded(metadata), headersonly=True)
    version = headers.get("Version")
    if normalized_name(headers.get("Name", "")) != expected or not version:
        raise ValueError("Installed distribution metadata does not identify the requested package")
    rows = csv.reader(read_bounded(ownership).decode("utf-8").splitlines())
    return version, {row[0] for row in rows if row}


def module_candidates(module):
    stem = module.replace(".", "/")
    return [stem + ".pyi", stem + "/__init__.pyi", stem + ".py", stem + "/__init__.py"]


def find_module(root, owned, module):
    for candidate in module_candidates(module):
        if candidate in owned:
            path = regular_child(root, candidate)
            if path:
                return path
    raise ValueError("The installed distribution has no inspectable Python source or stub for the requested module")


def declared_symbol(tree, symbol):
    for stmt in tree.body:
        if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and stmt.name == symbol:
            return stmt
        if isinstance(stmt, ast.ImportFrom) and any(alias.name == symbol == alias.asname for alias in stmt.names):
            return stmt
        targets = []
        if isinstance(stmt, ast.AnnAssign):
            targets = [stmt.target]
        elif isinstance(stmt, ast.Assign):
            targets = stmt.targets
        if any(isinstance(target, ast.Name) and target.id == symbol for target in targets):
            return stmt
    return None


def installed_evidence(site, distribution, module, symbol):
    result = {"distribution": distribution, "module": module, "symbol": symbol}
    if not symbol.isidentifier() or not all(part.isidentifier() for part in module.split(".")):
        return {**result, "status": "inconclusive", "reason": "Module and symbol must be Python identifiers"}
    try:
        root = site.resolve(strict=True)
        result["version"], owned = find_distribution(root, distribution)
        path = find_module(root, owned, module)
        result["path"] = path.relative_to(root).as_posix()
        tree = ast.parse(read_bounded(path), filename=result["path"])
    except (OSError, ValueError, SyntaxError, RuntimeError, csv.Error) as error:
        return {**result, "status": "inconclusive", "reason": str(error)}

    declaration = declared_symbol(tree, symbol)
    if declaration:
        return {**result, "status": "declared", "line": declaration.lineno, "column": declaration.col_offset,
                "end_line": declaration.end_lineno, "end_column": declaration.end_col_offset}
    if path.suffix == ".pyi" and declared_symbol(tree, "__getattr__") is None:
        return {**result, "status": "not_declared", "reason": "No direct declaration in the installed stub"}
    return {**result, "status": "inconclusive", "reason": "No direct declaration; runtime or conditional exports may apply"}


def import_from_symbols(stmt):
    if not isinstance(stmt, ast.ImportFrom) or stmt.level != 0 or not stmt.module:
        return []
    return [(stmt, stmt.module, alias.name) for alias in stmt.names if alias.name != "*"]


def consumer_imports(source):
    tree = ast.parse(read_bounded(source), filename=str(source))
    return [entry for stmt in tree.body for entry in import_from_symbols(stmt)]


def consumer_import_evidence(source, site, distribution):
    result = {"distribution": distribution}
    if not site.is_dir():
        return {**result, "status": "not_checked", "reason": "The selected site-packages is unavailable"}
    try:
        imports = consumer_imports(source)
        root = site.resolve(strict=True)
        version, owned = find_distribution(root, distribution)
    except (OSError, ValueError, SyntaxError, RecursionError, csv.Error) as error:
        return {**result, "status": "inconclusive", "reason": str(error)}
    selected = [
        entry for entry in imports
        if any(candidate in owned for candidate in module_candidates(entry[1]))
    ]
    if len(selected) != 1:
        reason = ("The consumer has no explicit import from the selected distribution" if not selected
                  else "The consumer imports more than one symbol from the selected distribution")
        return {**result, "status": "inconclusive", "reason": reason, "version": version}
    stmt, module, symbol = selected[0]
    merged = dict(installed_evidence(site, distribution, module, symbol))
    module_path = merged.get("path")
    if "line" in merged:
        merged["declaration_span"] = {
            "path": merged.pop("path"), "line": merged.pop("line"), "column": merged.pop("column"),
            "end_line": merged.pop("end_line"), "end_column": merged.pop("end_column"),
        }
    merged["import_span"] = {
        "line": stmt.lineno, "column": stmt.col_offset,
        "end_line": stmt.end_lineno, "end_column": stmt.end_col_offset,
    }
    merged["provenance"] = {"installation": str(root), "module": module_path}
    return merged


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--site-packages", type=Path, required=True)
    parser.add_argument("--distribution", required=True)
    parser.add_argument("--module")
    parser.add_argument("--symbol")
    parser.add_argument("--consumer-import", action="store_true",
                        help="Derive the module and symbol from the consumer's own import")
    args = parser.parse_args()
    if args.consumer_import and (args.module or args.symbol):
        parser.error("--consumer-import derives the module and symbol from the consumer")
    if not args.consumer_import and not (args.module and args.symbol):
        parser.error("--module and --symbol are required unless --consumer-import is used")
    compiler = compiler_evidence(args.source)
    api = {"status": "not_checked"}
    if compiler["status"] == "passed":
        if args.consumer_import:
            api = consumer_import_evidence(args.source, args.site_packages, args.distribution)
        else:
            api = installed_evidence(args.site_packages, args.distribution, args.module, args.symbol)
    print(json.dumps({"compiler": compiler, "installed_api": api}, indent=2))
    if compiler["status"] == "diagnostic":
        return 1
    return 0 if api["status"] == "declared" else 2


if __name__ == "__main__":
    sys.exit(main())
