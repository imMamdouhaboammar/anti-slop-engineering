#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Tests for lazy searchable anti-pattern catalog lookup and indexing."""

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = ROOT_DIR / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import catalog_lookup
from catalog_lookup import (
    format_catalog_entry,
    get_catalog_index,
    lookup_catalog_entry,
    search_catalog,
)


class CatalogLookupTests(unittest.TestCase):
    def test_catalog_index_completeness_and_uniqueness(self):
        """Catalog index contains all 217 patterns with unique IDs and valid skills."""
        index = get_catalog_index()
        self.assertEqual(len(index), 217, f"Expected exactly 217 catalog patterns, got {len(index)}")

        ids = list(index.keys())
        self.assertEqual(len(ids), len(set(ids)), "Catalog IDs must be completely unique with zero duplicates")

        for cat_id, entry in index.items():
            self.assertEqual(entry["id"], cat_id)
            self.assertTrue(entry["title"], f"Pattern {cat_id} missing title")
            self.assertTrue(entry["description"], f"Pattern {cat_id} missing description")
            self.assertTrue(entry["category_code"], f"Pattern {cat_id} missing category_code")
            self.assertTrue(entry["category_name"], f"Pattern {cat_id} missing category_name")
            self.assertTrue(entry["skill"], f"Pattern {cat_id} missing skill")
            skill_file = ROOT_DIR / entry["skill_path"]
            self.assertTrue(skill_file.is_file(), f"Skill file for {cat_id} does not exist: {skill_file}")

    def test_exact_lookup_case_insensitive(self):
        """Exact lookup resolves ID regardless of casing or formatting."""
        queries = ["SIM-08", "sim-08", "Sim-08", "REQ-01", "req-01", "SRE-01", "SEC-05"]
        for q in queries:
            result = lookup_catalog_entry(q)
            self.assertTrue(result["found"], f"Failed to find entry for {q}")
            self.assertEqual(result["id"], q.upper())
            self.assertTrue(len(result["title"]) > 0)
            self.assertTrue(len(result["description"]) > 0)

    def test_lookup_unmatched_id(self):
        """Unmatched ID returns found=False with actionable remediation advice."""
        result = lookup_catalog_entry("UNKNOWN-999")
        self.assertFalse(result["found"])
        self.assertIn("not found", result["message"].lower())
        self.assertTrue(len(result["available_categories"]) >= 14)

    def test_keyword_search(self):
        """Keyword search finds relevant entries across titles, descriptions, and IDs."""
        results = search_catalog("injection", limit=5)
        self.assertTrue(len(results) > 0)
        matched_ids = [r["id"] for r in results]
        self.assertIn("SEC-05", matched_ids)

        # Search for SRE retry
        retry_results = search_catalog("retry", limit=5)
        self.assertTrue(any("SRE" in r["id"] for r in retry_results))

    def test_format_catalog_entry_direct_payload(self):
        """Formatted catalog entry adheres to Direct Payload Invariant with zero fluff."""
        entry = lookup_catalog_entry("SIM-08")
        text = format_catalog_entry(entry)
        self.assertIn("SIM-08", text)
        self.assertIn("Dense clever one-liners", text)
        self.assertIn("anti-slop-engineering", text)
        self.assertNotIn("Here is", text)
        self.assertNotIn("Hope this helps", text)

    def test_cli_catalog_lookup(self):
        """CLI invocation of catalog_lookup supports exact ID lookup and search."""
        script = str(SCRIPTS_DIR / "catalog_lookup.py")
        res = subprocess.run([sys.executable, script, "SIM-08", "--json"], capture_output=True, text=True)
        self.assertEqual(res.returncode, 0)
        data = json.loads(res.stdout)
        self.assertTrue(data["found"])
        self.assertEqual(data["id"], "SIM-08")
        self.assertEqual(data["skill"], "anti-slop-engineering")

        res_search = subprocess.run([sys.executable, script, "--search", "injection", "--json"], capture_output=True, text=True)
        self.assertEqual(res_search.returncode, 0)
        search_data = json.loads(res_search.stdout)
        self.assertTrue(len(search_data["results"]) > 0)


if __name__ == "__main__":
    unittest.main()
