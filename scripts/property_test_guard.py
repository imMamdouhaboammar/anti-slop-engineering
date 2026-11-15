#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Deterministic seed control and source scanner for property tests and fuzzers."""

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

MATH_RANDOM_RE = re.compile(r"\bMath\.random\s*\(")
FC_ASSERT_RE = re.compile(r"\bfc\.assert\s*\(")

PYTHON_RANDOM_PATTERNS = (
    "random.randint(",
    "random.randint (",
    "random.random(",
    "random.random (",
    "random.choice(",
    "random.choice (",
    "random.randrange(",
    "random.randrange (",
    "random.sample(",
    "random.sample (",
    "random.shuffle(",
    "random.shuffle (",
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
            if cleaned.lower().startswith("0x"):
                seed_int = int(cleaned, 16)
            else:
                seed_int = int(cleaned, 10)
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


def _check_fc_assert_seeded(source: str, match_pos: int) -> bool:
    """Inspect fc.assert block starting at match_pos to verify seed option."""
    window = source[match_pos : match_pos + 500]
    semi_idx = window.find(";")
    if semi_idx != -1:
        window = window[:semi_idx]
    return bool(re.search(r"\bseed\b", window))


def scan_source_for_unseeded_generators(source: str, file_path: str = "") -> List[Dict[str, Any]]:
    """Scan source code for unseeded random generators or unconfigured PBT runners."""
    findings: List[Dict[str, Any]] = []

    for match in MATH_RANDOM_RE.finditer(source):
        findings.append({
            "code": "UNSEEDED_MATH_RANDOM",
            "file": file_path,
            "severity": "block",
            "message": "Math.random() call found without deterministic PRNG seed.",
        })

    for pat in PYTHON_RANDOM_PATTERNS:
        if pat in source:
            findings.append({
                "code": "UNSEEDED_PYTHON_RANDOM",
                "file": file_path,
                "severity": "block",
                "message": "Python random module generator found without explicit deterministic seed.",
            })
            break

    for match in FC_ASSERT_RE.finditer(source):
        if not _check_fc_assert_seeded(source, match.start()):
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


def _handle_run(seed_val: str, command: str) -> int:
    cmd_parts = shlex.split(command)
    with SeedContext(seed_val):
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
    run_p.add_argument("--seed", required=True, help="Seed integer or hex")
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
