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

    def test_cli_scan_accepts_explicit_python_seed(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td) / "property.py"
            source.write_text(
                "import random\n"
                "random.seed(42)\n"
                "assert 0 <= random.randrange(10) < 10\n"
            )
            res = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "scan", "--source", str(source), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertEqual(json.loads(res.stdout)["findings"], [])

    def test_cli_scan_flags_python_seed_after_first_draw_or_seeded_from_entropy(self):
        for seed_call in ["random.seed(42)", "random.seed()", "random.seed(None)"]:
            with self.subTest(seed_call=seed_call), tempfile.TemporaryDirectory() as td:
                source = pathlib.Path(td) / "property.py"
                source.write_text(f"import random\nrandom.randrange(10)\n{seed_call}\n")
                if seed_call != "random.seed(42)":
                    source.write_text(f"import random\n{seed_call}\nrandom.randrange(10)\n")
                res = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), "scan", "--source", str(source), "--json"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
                self.assertEqual(
                    [entry["code"] for entry in json.loads(res.stdout)["findings"]],
                    ["UNSEEDED_PYTHON_RANDOM"],
                )

    def test_cli_scan_requires_seed_in_fast_check_options(self):
        examples = (
            "fc.assert(fc.property(fc.string(), (seed) => seed.length >= 0));",
            "fc.assert(fc.property(fc.string(), (value) => value.length >= 0), "
            "{ reporter: () => { const seed = 42; } });",
            "fc.assert(fc.property(fc.string(), (value) => value.length >= 0), "
            "{ /* seed: 42 */ numRuns: 2 });",
        )
        for snippet in examples:
            with self.subTest(snippet=snippet), tempfile.TemporaryDirectory() as td:
                source = pathlib.Path(td) / "property.ts"
                source.write_text(snippet)
                res = subprocess.run(
                    [sys.executable, str(SCRIPT_PATH), "scan", "--source", str(source), "--json"],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
                self.assertEqual(
                    [entry["code"] for entry in json.loads(res.stdout)["findings"]],
                    ["UNSEEDED_FAST_CHECK_PROPERTY"],
                )

    def test_source_examples_in_strings_and_comments_do_not_report_draws(self):
        for suffix, snippet in (
            (".py", '# random.randrange(10)\nexample = "random.random()"\n'),
            (".ts", '// fc.assert(fc.property(example))\nconst example = "Math.random()";'),
        ):
            with self.subTest(suffix=suffix):
                self.assertEqual(scan_source_for_unseeded_generators(snippet, "example" + suffix), [])

    def test_deep_python_expression_finishes_source_scan(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td) / "property.py"
            source.write_text(
                "import random\n"
                "random.seed(1)\n"
                + "+".join(["random.random()", *["1"] * 1500])
                + "\n"
            )
            res = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "scan", "--source", str(source), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertEqual(json.loads(res.stdout)["findings"], [])

    def test_python_draw_in_deferred_function_requires_its_own_provable_seed(self):
        source = (
            "import random\n"
            "random.seed(1)\n"
            "def draw():\n"
            "    return random.random()\n"
            "random.seed(None)\n"
            "draw()\n"
        )
        findings = scan_source_for_unseeded_generators(source, "property.py")
        self.assertEqual([entry["code"] for entry in findings], ["UNSEEDED_PYTHON_RANDOM"])

    def test_python_draw_with_explicit_seed_in_same_function_is_accepted(self):
        source = (
            "import random\n"
            "def draw():\n"
            "    random.seed(1)\n"
            "    return random.random()\n"
            "draw()\n"
        )
        self.assertEqual(scan_source_for_unseeded_generators(source, "property.py"), [])

    def test_explicit_entropy_values_do_not_supply_a_fast_check_seed(self):
        for entropy in ("undefined", "void 0"):
            with self.subTest(entropy=entropy):
                source = (
                    "fc.assert(fc.property(fc.integer(), Number.isInteger), "
                    f"{{ seed: {entropy} }});"
                )
                findings = scan_source_for_unseeded_generators(source, "property.ts")
                self.assertEqual(
                    [entry["code"] for entry in findings],
                    ["UNSEEDED_FAST_CHECK_PROPERTY"],
                )

    def test_fast_check_seed_from_next_call_does_not_cover_previous_call(self):
        source = (
            "fc.assert(fc.property(fc.integer(), (n) => Number.isInteger(n)))\n"
            "fc.assert(fc.property(fc.integer(), (n) => Number.isInteger(n)), { seed: 42 })"
        )
        findings = scan_source_for_unseeded_generators(source, "property.ts")
        self.assertEqual([entry["code"] for entry in findings], ["UNSEEDED_FAST_CHECK_PROPERTY"])

    def test_cli_scan_accepts_seed_option_after_callback_with_statements(self):
        with tempfile.TemporaryDirectory() as td:
            source = pathlib.Path(td) / "property.ts"
            source.write_text(
                "fc.assert(fc.property(fc.integer(), (n) => {\n"
                "  const square = n * n;\n"
                "  return square >= 0;\n"
                "}), { numRuns: 100, 'seed': 42 });\n"
            )
            res = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "scan", "--source", str(source), "--json"],
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
            self.assertEqual(json.loads(res.stdout)["findings"], [])

    def test_cli_reports_invalid_seed_as_usage_error_without_launching_command(self):
        res = subprocess.run(
            [
                sys.executable, str(SCRIPT_PATH), "run", "--seed", "not_a_seed",
                "--command", f'{sys.executable} -c "print(42)"',
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 2, res.stdout + res.stderr)
        self.assertIn("Invalid seed", res.stderr)
        self.assertNotIn("Traceback", res.stderr)
        self.assertEqual(res.stdout, "")

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
