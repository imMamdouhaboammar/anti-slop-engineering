# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Validation and completeness regression tests for skills.sh repository configuration."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG_FILE = ROOT / "skills.sh.json"
SKILLS_DIR = ROOT / "skills"

ALLOWED_ROOT_KEYS = {"$schema", "schema", "notGrouped", "groupings", "paths"}
ALLOWED_GROUPING_KEYS = {"title", "description", "skills"}


class SkillsShConfigTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(CONFIG_FILE.is_file(), f"Expected config file at {CONFIG_FILE}")
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            self.config = json.load(f)

    def test_json_structure_and_allowed_fields(self):
        self.assertIsInstance(self.config, dict, "skills.sh.json must be a JSON object")
        self.assertTrue(
            set(self.config.keys()).issubset(ALLOWED_ROOT_KEYS),
            f"Unexpected keys in skills.sh.json: {set(self.config.keys()) - ALLOWED_ROOT_KEYS}",
        )
        self.assertEqual(
            self.config.get("$schema"),
            "https://skills.sh/schemas/skills.sh.schema.json",
            "Must use official schema URI",
        )
        self.assertEqual(
            self.config.get("notGrouped"),
            "bottom",
            "notGrouped must be set to 'bottom'",
        )
        self.assertIn("groupings", self.config, "Must contain 'groupings'")
        self.assertIsInstance(self.config["groupings"], list)
        self.assertGreaterEqual(len(self.config["groupings"]), 1)
        self.assertLessEqual(len(self.config["groupings"]), 50)

    def test_nonempty_unique_group_titles_and_descriptions(self):
        groupings = self.config["groupings"]
        seen_titles = set()
        for idx, group in enumerate(groupings):
            self.assertIsInstance(group, dict, f"Group #{idx} must be an object")
            self.assertTrue(
                set(group.keys()).issubset(ALLOWED_GROUPING_KEYS),
                f"Group #{idx} has unexpected keys: {set(group.keys()) - ALLOWED_GROUPING_KEYS}",
            )
            title = group.get("title")
            self.assertIsInstance(title, str, f"Group #{idx} title must be string")
            title_clean = title.strip()
            self.assertTrue(title_clean, f"Group #{idx} title must not be empty")
            self.assertLessEqual(len(title_clean), 120)
            self.assertNotIn(title_clean, seen_titles, f"Duplicate group title: {title_clean}")
            seen_titles.add(title_clean)

            if "description" in group:
                desc = group["description"]
                self.assertIsInstance(desc, str, f"Group #{idx} description must be string")
                desc_clean = desc.strip()
                self.assertTrue(desc_clean, f"Group #{idx} description must not be empty if present")
                self.assertLessEqual(len(desc_clean), 500)

    def test_zero_duplicate_skill_slugs_across_groups(self):
        groupings = self.config["groupings"]
        seen_slugs = set()
        for group in groupings:
            skills = group.get("skills")
            self.assertIsInstance(skills, list, f"Group '{group.get('title')}' skills must be a list")
            self.assertGreaterEqual(len(skills), 1)
            for slug in skills:
                self.assertIsInstance(slug, str)
                self.assertNotIn(
                    slug,
                    seen_slugs,
                    f"Duplicate skill slug '{slug}' across groupings",
                )
                seen_slugs.add(slug)

    def test_every_slug_maps_to_existing_skill_file(self):
        groupings = self.config["groupings"]
        for group in groupings:
            for slug in group["skills"]:
                skill_md = SKILLS_DIR / slug / "SKILL.md"
                self.assertTrue(
                    skill_md.is_file(),
                    f"Configured skill '{slug}' does not have corresponding {skill_md}",
                )

    def test_every_tracked_skill_is_covered_by_groups(self):
        discovered_skills = {
            p.parent.name
            for p in SKILLS_DIR.glob("*/SKILL.md")
            if p.is_file()
        }
        self.assertGreaterEqual(len(discovered_skills), 1, "Expected at least 1 skill in skills/")

        configured_skills = set()
        for group in self.config["groupings"]:
            for slug in group.get("skills", []):
                configured_skills.add(slug)

        missing = discovered_skills - configured_skills
        self.assertEqual(
            missing,
            set(),
            f"Tracked skills missing from skills.sh.json groupings: {sorted(missing)}",
        )

        extra = configured_skills - discovered_skills
        self.assertEqual(
            extra,
            set(),
            f"Configured skills in skills.sh.json not found under skills/*/SKILL.md: {sorted(extra)}",
        )


if __name__ == "__main__":
    unittest.main()
