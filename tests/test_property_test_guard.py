# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Tests for deterministic seed control in property tests and fuzzers."""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPT_PATH = ROOT / "scripts" / "property_test_guard.py"

from scripts.property_test_guard import (
    Mulberry32,
    SplitMix64,
    SeedContext,
    generate_seed,
    parse_seed,
    scan_source_for_unseeded_generators,
)


class PropertyTestSeedEngineTests(unittest.TestCase):
    def test_parse_valid_integer_seed(self):
        seed_int, seed_hex = parse_seed(123456789)
        self.assertEqual(seed_int, 123456789)
        self.assertEqual(seed_hex, "0x00000000075bcd15")

    def test_parse_valid_hex_seed(self):
        seed_int, seed_hex = parse_seed("0xCAFE_BABE")
        self.assertEqual(seed_int, 0xCAFEBABE)
        self.assertEqual(seed_hex, "0x00000000cafebabe")

    def test_parse_invalid_seed_raises(self):
        with self.assertRaises(ValueError):
            parse_seed(-1)
        with self.assertRaises(ValueError):
            parse_seed(2**64)
        with self.assertRaises(ValueError):
            parse_seed("not_a_seed")

    def test_generate_seed_returns_bounded_uint64_and_hex(self):
        seed_int, seed_hex = generate_seed()
        self.assertIsInstance(seed_int, int)
        self.assertGreaterEqual(seed_int, 0)
        self.assertLess(seed_int, 2**64)
        self.assertTrue(seed_hex.startswith("0x"))
        self.assertEqual(len(seed_hex), 18)

    def test_mulberry32_prng_deterministic_sequence(self):
        prng1 = Mulberry32(0xDEADBEEF)
        seq1 = [prng1.next_uint32() for _ in range(100)]

        prng2 = Mulberry32(0xDEADBEEF)
        seq2 = [prng2.next_uint32() for _ in range(100)]
        self.assertEqual(seq1, seq2)

        prng3 = Mulberry32(0xCAFEBABE)
        seq3 = [prng3.next_uint32() for _ in range(100)]
        self.assertNotEqual(seq1, seq3)

    def test_splitmix64_prng_deterministic_sequence(self):
        prng1 = SplitMix64(0x12345678_9ABCDEF0)
        seq1 = [prng1.next_uint64() for _ in range(50)]

        prng2 = SplitMix64(0x12345678_9ABCDEF0)
        seq2 = [prng2.next_uint64() for _ in range(50)]
        self.assertEqual(seq1, seq2)

    def test_seed_context_injects_and_restores_env(self):
        old_val = os.environ.get("ANTI_SLOP_SEED")
        with SeedContext(0xABCD) as ctx:
            self.assertEqual(ctx["seed_int"], 0xABCD)
            self.assertEqual(os.environ.get("ANTI_SLOP_SEED"), ctx["seed_hex"])
        self.assertEqual(os.environ.get("ANTI_SLOP_SEED"), old_val)


class PropertyTestSourceScannerTests(unittest.TestCase):
    def test_source_scanner_detects_unseeded_math_random(self):
        code = "const val = Math.random();\n"
        findings = scan_source_for_unseeded_generators(code, "test_file.ts")
        codes = [f["code"] for f in findings]
        self.assertIn("UNSEEDED_MATH_RANDOM", codes)

    def test_source_scanner_detects_unseeded_python_random(self):
        code = "import random\nx = random.randint(1, 100)\n"
        findings = scan_source_for_unseeded_generators(code, "test_file.py")
        codes = [f["code"] for f in findings]
        self.assertIn("UNSEEDED_PYTHON_RANDOM", codes)

    def test_source_scanner_detects_unseeded_fast_check(self):
        code = "fc.assert(fc.property(fc.integer(), (n) => n === n));\n"
        findings = scan_source_for_unseeded_generators(code, "test_pbt.ts")
        codes = [f["code"] for f in findings]
        self.assertIn("UNSEEDED_FAST_CHECK_PROPERTY", codes)

    def test_source_scanner_accepts_clean_seeded_property_test(self):
        code = (
            "import { Mulberry32 } from './prng';\n"
            "const seed = process.env.SEED ? parseInt(process.env.SEED, 16) : 0xCAFEBABE;\n"
            "fc.assert(fc.property(fc.integer(), (n) => n === n), { seed });\n"
        )
        findings = scan_source_for_unseeded_generators(code, "test_pbt.ts")
        self.assertEqual(findings, [])


class PropertyTestGuardCLITests(unittest.TestCase):
    def test_cli_generate_seed_json(self):
        res = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "generate-seed", "--json"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertIn("seed", data)
        self.assertIn("seed_hex", data)
        self.assertTrue(data["seed_hex"].startswith("0x"))

    def test_cli_scan_source_clean_and_violating(self):
        with tempfile.TemporaryDirectory() as td:
            violating = pathlib.Path(td) / "bad.ts"
            violating.write_text("const x = Math.random();\n")
            res_bad = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "scan", "--source", str(violating), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_bad.returncode, 2)
            data_bad = json.loads(res_bad.stdout)
            self.assertGreaterEqual(len(data_bad["findings"]), 1)

            clean = pathlib.Path(td) / "good.ts"
            clean.write_text("// deterministic\nconst x = 42;\n")
            res_good = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "scan", "--source", str(clean), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_good.returncode, 0)
            data_good = json.loads(res_good.stdout)
            self.assertEqual(len(data_good["findings"]), 0)

    def test_cli_run_command_with_seed_injection(self):
        cmd = f'{sys.executable} -c "import os; print(os.environ.get(\'ANTI_SLOP_SEED\'))"'
        res = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "run", "--seed", "0xABCD", "--command", cmd],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0)
        self.assertIn("0x000000000000abcd", res.stdout)


if __name__ == "__main__":
    unittest.main()
