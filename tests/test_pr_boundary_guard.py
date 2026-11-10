# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import unittest
from scripts.pr_boundary_guard import (
    count_emojis,
    count_code_references,
    parse_markdown_sections,
    audit_pr_boundary,
)


class TestPrBoundaryGuard(unittest.TestCase):
    def test_count_emojis_unicode_and_shortcodes(self):
        text = "Hello world! 🚀 Fix issue #123 with :sparkles: and 🛡️ and :+1:."
        count = count_emojis(text)
        self.assertGreaterEqual(count, 4)

    def test_count_code_references(self):
        text = "Modified `foo.py`, called `calculate_metrics()`, and updated path `src/utils/math.ts`."
        refs = count_code_references(text)
        self.assertGreaterEqual(refs, 3)

    def test_parse_markdown_sections_and_checkboxes(self):
        md = """## Type of Change
- [ ] Bugfix
- [x] Feature
- [ ] Breaking change

## Verification
- [x] Unit tests passed
"""
        sections = parse_markdown_sections(md)
        self.assertEqual(len(sections), 2)
        self.assertEqual(sections[0]["title"], "Type of Change")
        self.assertEqual(len(sections[0]["checkboxes"]), 3)
        self.assertFalse(sections[0]["checkboxes"][0]["checked"])
        self.assertTrue(sections[0]["checkboxes"][1]["checked"])

    def test_radio_button_violation_when_multiple_checked(self):
        template = """## Type of Change
- [ ] Bugfix
- [ ] Feature
- [ ] Documentation
"""
        body = """## Type of Change
- [x] Bugfix
- [x] Feature
- [ ] Documentation
"""
        record = audit_pr_boundary(
            pr_body=body,
            template_content=template,
        )
        violations = [f for f in record["findings"] if f["rule"] == "RADIO_BUTTON_TEMPLATE_VIOLATION"]
        self.assertEqual(len(violations), 1)
        self.assertIn("mutually exclusive", violations[0]["message"])

    def test_hallucinated_extra_sections_detected(self):
        template = """## Description
Explain changes here.

## Testing
Test checklist.
"""
        body = """## Description
Clean description.

## Testing
All tests pass.

## AI Rationale
Hallucinated reasoning.

## Comprehensive Impact Analysis
Extra unnecessary section.

## Future Recommendations
Another hallucinated section.
"""
        record = audit_pr_boundary(
            pr_body=body,
            template_content=template,
        )
        hallucinations = [f for f in record["findings"] if f["rule"] == "HALLUCINATED_EXTRA_SECTIONS"]
        self.assertEqual(len(hallucinations), 1)

    def test_clean_pr_passes_without_findings(self):
        template = """## Type of Change
- [ ] Bugfix
- [ ] Feature

## Summary
Brief explanation.
"""
        body = """## Type of Change
- [ ] Bugfix
- [x] Feature

## Summary
Refactor core mathematical calculation for cleaner separation.
"""
        record = audit_pr_boundary(
            pr_title="feat(engine): refactor core calculation",
            pr_body=body,
            template_content=template,
            require_conventional=True,
            blocked_source_branches=[],
        )
        self.assertEqual(record["code"], "NO_PR_BOUNDARY_FINDINGS")
        self.assertEqual(len(record["findings"]), 0)

    def test_blocked_source_branch_flags_review(self):
        record = audit_pr_boundary(
            pr_title="feat: update feature",
            blocked_source_branches=["main", "master"],
        )
        # In current repo, we are on branch 'main'
        branch_findings = [f for f in record["findings"] if f["rule"] == "BLOCKED_SOURCE_BRANCH"]
        self.assertEqual(len(branch_findings), 1)
        self.assertEqual(branch_findings[0]["severity"], "review")


if __name__ == "__main__":
    unittest.main()
