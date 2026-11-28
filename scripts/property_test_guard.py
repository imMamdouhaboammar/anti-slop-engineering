#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Deterministic seed control and source scanner for property tests and fuzzers."""

import argparse
import ast
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

JS_EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"}
JS_TOKENS = re.compile(
    r"//[^\n]*|/\*[\s\S]*?\*/|"
    r"""'(?:\\[\s\S]|[^'\\])*'|"(?:\\[\s\S]|[^"\\])*"|"""
    r"\.\.\.|[\w$]+|\S"
)
TEMPLATE_CONTROL = re.compile(r"\\[\s\S]|\x60|\$\{")
BRACKETS = {"(": ")", "[": "]", "{": "}"}
PYTHON_GENERATORS = {"randint", "random", "choice", "randrange", "sample", "shuffle"}
PYTHON_RANDOM_RE = re.compile(
    r"\brandom\s*\.\s*(?:" + "|".join(sorted(PYTHON_GENERATORS)) + r")\s*\("
)


class Mulberry32:
    """32-bit deterministic PRNG with state cycle of 2^32."""

    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFF

    def next_uint32(self) -> int:
        self.state = (self.state + 0x6D2B79F5) & 0xFFFFFFFF
        z = self.state
        z = ((z ^ (z >> 15)) * (z | 1)) & 0xFFFFFFFF
        z = (z ^ (z + (((z ^ (z >> 7)) * (z | 61)) & 0xFFFFFFFF))) & 0xFFFFFFFF
        return (z ^ (z >> 14)) & 0xFFFFFFFF


class SplitMix64:
    """64-bit deterministic PRNG for high-entropy seed expansion."""

    def __init__(self, seed: int):
        self.state = seed & 0xFFFFFFFFFFFFFFFF

    def next_uint64(self) -> int:
        self.state = (self.state + 0x9E3779B97F4A7C15) & 0xFFFFFFFFFFFFFFFF
        z = self.state
        z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & 0xFFFFFFFFFFFFFFFF
        z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & 0xFFFFFFFFFFFFFFFF
        return (z ^ (z >> 31)) & 0xFFFFFFFFFFFFFFFF


def parse_seed(val: Union[int, str]) -> Tuple[int, str]:
    """Parse integer or hex string seed into bounded uint64 and formatted hex."""
    if isinstance(val, int):
        seed_int = val
    elif isinstance(val, str):
        cleaned = val.strip().replace("_", "")
        try:
            seed_int = int(cleaned, 16) if cleaned.lower().startswith("0x") else int(cleaned, 10)
        except ValueError as err:
            raise ValueError(f"Invalid seed representation: {val!r}") from err
    else:
        raise ValueError(f"Seed must be int or str, got {type(val).__name__}")

    if not (0 <= seed_int < (1 << 64)):
        raise ValueError(f"Seed must be between 0 and 2^64-1, got {val!r}")

    return seed_int, f"0x{seed_int:016x}"


def generate_seed() -> Tuple[int, str]:
    """Generate a high-entropy 64-bit seed using OS entropy."""
    seed_int = int.from_bytes(os.urandom(8), byteorder="big")
    return seed_int, f"0x{seed_int:016x}"


class SeedContext:
    """Context manager setting ANTI_SLOP_SEED in environment during test runs."""

    def __init__(self, seed: Union[int, str]):
        self.seed_int, self.seed_hex = parse_seed(seed)
        self.prev_seed: Optional[str] = None

    def __enter__(self) -> Dict[str, Any]:
        self.prev_seed = os.environ.get("ANTI_SLOP_SEED")
        os.environ["ANTI_SLOP_SEED"] = self.seed_hex
        return {"seed_int": self.seed_int, "seed_hex": self.seed_hex}

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if self.prev_seed is None:
            os.environ.pop("ANTI_SLOP_SEED", None)
        else:
            os.environ["ANTI_SLOP_SEED"] = self.prev_seed


def _python_call_name(call: ast.Call) -> str:
    target = call.func
    if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) and target.value.id == "random":
        return target.attr
    return ""


def _explicit_python_seed(call: ast.Call) -> bool:
    argument = next(
        iter(call.args),
        next((option.value for option in call.keywords if option.arg == "a"), None),
    )
    return argument is not None and not (
        isinstance(argument, ast.Constant) and argument.value is None
    ) and not isinstance(argument, ast.Starred)


def _python_calls(node: ast.AST, scopes: List[List[ast.stmt]]) -> Iterator[ast.Call]:
    pending = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            scopes.append(current.body)
            body = set(current.body)
            pending.extend(child for child in ast.iter_child_nodes(current) if child not in body)
        elif isinstance(current, ast.Lambda):
            scopes.append([ast.Expr(value=current.body)])
            pending.append(current.args)
        else:
            if isinstance(current, ast.Call):
                yield current
            pending.extend(ast.iter_child_nodes(current))


def _python_scope_has_unseeded_draw(
    statements: List[ast.stmt], scopes: List[List[ast.stmt]]
) -> bool:
    seeded = False
    pending = list(reversed(statements))
    while pending:
        statement = pending.pop()
        nodes = [statement]
        if isinstance(statement, ast.ClassDef):
            nodes = statement.decorator_list + statement.bases + statement.keywords
            pending.extend(reversed(statement.body))
        calls = sorted(
            (call for node in nodes for call in _python_calls(node, scopes)),
            key=lambda call: (call.end_lineno, call.end_col_offset),
        )
        for call in calls:
            name = _python_call_name(call)
            if name == "seed":
                if not _explicit_python_seed(call):
                    seeded = False
                elif isinstance(statement, ast.Expr) and statement.value is call:
                    seeded = True
            if name in PYTHON_GENERATORS and not seeded:
                return True
    return False


def _has_unseeded_python_draw(source: str) -> bool:
    try:
        module = ast.parse(source)
    except (SyntaxError, RecursionError):
        return bool(PYTHON_RANDOM_RE.search(source))

    scopes = [module.body]
    while scopes:
        if _python_scope_has_unseeded_draw(scopes.pop(), scopes):
            return True
    return False


def _js_tokens(source: str) -> Iterator[str]:
    position = 0
    template_depths: List[int] = []
    in_text = False
    while position < len(source):
        pattern = TEMPLATE_CONTROL if in_text else JS_TOKENS
        match = pattern.search(source, position)
        if match is None:
            return
        token = match[0]
        position = match.end()
        if in_text:
            if token == "`":
                template_depths.pop()
                in_text = False
                yield ")"
            elif token == "${":
                in_text = False
                yield "("
        elif token == "`":
            template_depths.append(0)
            in_text = True
            yield "("
        elif not token.startswith(("//", "/*")):
            if template_depths and token == "{":
                template_depths[-1] += 1
            elif template_depths and token == "}":
                if template_depths[-1] == 0:
                    in_text = True
                    yield ")"
                    continue
                template_depths[-1] -= 1
            yield token


def _top_level_tokens(tokens: List[str], start: int) -> Iterator[int]:
    closing = []
    for index in range(start, len(tokens)):
        token = tokens[index]
        if not closing:
            if token in BRACKETS.values():
                return
            yield index
        if token in BRACKETS:
            closing.append(BRACKETS[token])
        elif closing and token == closing[-1]:
            closing.pop()


def _fast_check_seed_option(tokens: List[str], start: int) -> bool:
    argument_start = next(
        (index + 1 for index in _top_level_tokens(tokens, start) if tokens[index] == ","),
        None,
    )
    if argument_start is None or tokens[argument_start : argument_start + 1] != ["{"]:
        return False

    seeded = False
    for index in _top_level_tokens(tokens, argument_start + 1):
        if tokens[index - 1] not in ("{", ","):
            continue
        if tokens[index] in ("...", "["):
            seeded = False
        elif tokens[index : index + 2] in (["seed", ","], ["seed", "}"]):
            seeded = True
        elif tokens[index] in ("seed", "'seed'", '"seed"') and tokens[index + 1 : index + 2] == [":"]:
            seeded = tokens[index + 2 : index + 3] not in (["undefined"], ["void"], [])
    return seeded


def scan_source_for_unseeded_generators(source: str, file_path: str = "") -> List[Dict[str, Any]]:
    """Check direct module calls and inline fast-check option objects."""
    findings: List[Dict[str, Any]] = []
    suffix = Path(file_path).suffix.lower()
    tokens = list(_js_tokens(source)) if suffix != ".py" else []

    for index, token in enumerate(tokens):
        if token == "Math" and tokens[index + 1 : index + 4] == [".", "random", "("]:
            findings.append({
                "code": "UNSEEDED_MATH_RANDOM",
                "file": file_path,
                "severity": "block",
                "message": "Math.random() call found without deterministic PRNG seed.",
            })

    if suffix not in JS_EXTENSIONS and _has_unseeded_python_draw(source):
        findings.append({
            "code": "UNSEEDED_PYTHON_RANDOM",
            "file": file_path,
            "severity": "block",
            "message": "Python random module generator found without explicit deterministic seed.",
        })

    for index, token in enumerate(tokens):
        if token == "fc" and tokens[index + 1 : index + 4] == [".", "assert", "("]:
            if not _fast_check_seed_option(tokens, index + 4):
                findings.append({
                    "code": "UNSEEDED_FAST_CHECK_PROPERTY",
                    "file": file_path,
                    "severity": "block",
                    "message": "fast-check fc.assert(...) without explicit seed configuration.",
                })

    return findings


def _handle_generate_seed(as_json: bool) -> int:
    seed_int, seed_hex = generate_seed()
    if as_json:
        print(json.dumps({"seed": seed_int, "seed_hex": seed_hex}))
    else:
        print(f"Seed: {seed_hex} ({seed_int})")
    return 0


def _handle_scan(source_path: str, as_json: bool) -> int:
    path = Path(source_path)
    if not path.is_file():
        err_msg = f"File not found: {source_path}"
        if as_json:
            print(json.dumps({"error": err_msg, "findings": []}))
        else:
            print(f"Error: {err_msg}", file=sys.stderr)
        return 1

    content = path.read_text(encoding="utf-8", errors="replace")
    findings = scan_source_for_unseeded_generators(content, str(path))
    if as_json:
        print(json.dumps({"findings": findings}))
    else:
        for f in findings:
            print(f"[{f['severity'].upper()}] {f['code']}: {f['message']}")
    return 2 if findings else 0


def _cli_seed_context(value: str) -> SeedContext:
    try:
        return SeedContext(value)
    except ValueError as err:
        raise argparse.ArgumentTypeError(str(err)) from err


def _handle_run(seed: SeedContext, command: str) -> int:
    cmd_parts = shlex.split(command)
    with seed:
        proc = subprocess.run(cmd_parts)
        return proc.returncode


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="subcommand")

    gen_p = subparsers.add_parser("generate-seed")
    gen_p.add_argument("--json", action="store_true", help="Output as JSON")

    scan_p = subparsers.add_parser("scan")
    scan_p.add_argument("--source", required=True, help="Source file to scan")
    scan_p.add_argument("--json", action="store_true", help="Output as JSON")

    run_p = subparsers.add_parser("run")
    run_p.add_argument("--seed", required=True, type=_cli_seed_context, help="Seed integer or hex")
    run_p.add_argument("--command", required=True, help="Command to execute")

    args = parser.parse_args()

    if args.subcommand == "generate-seed":
        return _handle_generate_seed(args.json)
    if args.subcommand == "scan":
        return _handle_scan(args.source, args.json)
    if args.subcommand == "run":
        return _handle_run(args.seed, args.command)

    parser.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
