#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from asset_provenance_guard import (
    calculate_sha256,
    evaluate_asset_provenance,
    load_asset_ledger,
    save_asset_ledger,
)


class AssetProvenanceGuardTests(unittest.TestCase):
    def test_calculate_sha256(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"test data 123")
            f_path = Path(f.name)
        try:
            sha = calculate_sha256(f_path)
            self.assertEqual(len(sha), 64)
            self.assertEqual(sha, "cfd1939e8cb0b3a3670c73642debb427d00ea1397da81b689a16e94da0cc90bc")
        finally:
            f_path.unlink()

    def test_clean_asset_and_ledger_passes(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            asset_dir = Path(tmp_dir) / "assets"
            asset_dir.mkdir()
            asset_file = asset_dir / "model.gltf"
            asset_file.write_bytes(b'{"asset": {"version": "2.0"}}')
            sha = calculate_sha256(asset_file)

            ledger_file = Path(tmp_dir) / "asset-ledger.jsonl"
            ledger_file.write_text(json.dumps({
                "path": "model.gltf",
                "sha256": sha,
                "source_url": "https://polyhaven.com/a/sample",
                "license": "CC0",
                "attribution": "Poly Haven"
            }) + "\n", encoding="utf-8")

            report = evaluate_asset_provenance(asset_dir, ledger_file)
            self.assertEqual(report["verdict"], "PROCEED")
            self.assertEqual(report["verified_clean_assets_count"], 1)
            self.assertEqual(report["unverified_assets_count"], 0)

    def test_missing_provenance_record_rejects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            asset_dir = Path(tmp_dir) / "assets"
            asset_dir.mkdir()
            asset_file = asset_dir / "untracked.png"
            asset_file.write_bytes(b"\x89PNG\r\n\x1a\n")

            ledger_file = Path(tmp_dir) / "empty-ledger.jsonl"
            ledger_file.write_text("", encoding="utf-8")

            report = evaluate_asset_provenance(asset_dir, ledger_file)
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "MISSING_PROVENANCE_RECORD" for f in report["findings"]))

    def test_unapproved_license_rejects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            asset_dir = Path(tmp_dir) / "assets"
            asset_dir.mkdir()
            asset_file = asset_dir / "pirated.mp3"
            asset_file.write_bytes(b"ID3\x03\x00\x00\x00")
            sha = calculate_sha256(asset_file)

            ledger_file = Path(tmp_dir) / "asset-ledger.jsonl"
            ledger_file.write_text(json.dumps({
                "path": "pirated.mp3",
                "sha256": sha,
                "source_url": "https://unknown.site/audio.mp3",
                "license": "ALL_RIGHTS_RESERVED",
                "attribution": "Commercial Artist"
            }) + "\n", encoding="utf-8")

            report = evaluate_asset_provenance(asset_dir, ledger_file)
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "UNAPPROVED_LICENSE" for f in report["findings"]))

    def test_sha256_hash_mismatch_rejects(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            asset_dir = Path(tmp_dir) / "assets"
            asset_dir.mkdir()
            asset_file = asset_dir / "tampered.svg"
            asset_file.write_bytes(b"<svg></svg>")

            ledger_file = Path(tmp_dir) / "asset-ledger.jsonl"
            ledger_file.write_text(json.dumps({
                "path": "tampered.svg",
                "sha256": "0000000000000000000000000000000000000000000000000000000000000000",
                "source_url": "https://iconify.design",
                "license": "MIT",
                "attribution": "Iconify"
            }) + "\n", encoding="utf-8")

            report = evaluate_asset_provenance(asset_dir, ledger_file)
            self.assertEqual(report["verdict"], "REJECT")
            self.assertTrue(any(f["class"] == "HASH_MISMATCH" for f in report["findings"]))

    def test_cli_selftest(self):
        cmd = [sys.executable, str(SCRIPTS_DIR / "asset_provenance_guard.py"), "--selftest"]
        res = subprocess.run(cmd, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        self.assertIn("PASS", res.stdout)


if __name__ == "__main__":
    unittest.main()
