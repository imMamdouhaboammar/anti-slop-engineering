# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import unittest
from scripts.comment_budget_guard import (
    audit_diff_comments,
    is_exempt_file,
    is_protected_comment,
    is_syntax_narration,
)


class TestCommentBudgetGuard(unittest.TestCase):
    def test_exempt_file_extensions(self):
        self.assertTrue(is_exempt_file("README.md"))
        self.assertTrue(is_exempt_file("config.yaml"))
        self.assertTrue(is_exempt_file("schema.sql"))
        self.assertTrue(is_exempt_file("package.json"))
        self.assertFalse(is_exempt_file("src/engine.py"))
        self.assertFalse(is_exempt_file("src/service.ts"))

    def test_protected_safety_and_doc_comments(self):
        self.assertTrue(is_protected_comment("// SAFETY: index is bounded by slice length"))
        self.assertTrue(is_protected_comment("/// Formats the given input"))
        self.assertTrue(is_protected_comment("/** Multi-line docstring */"))
        self.assertTrue(is_protected_comment("# SPDX-License-Identifier: MIT"))
        self.assertFalse(is_protected_comment("// increment the counter"))

    def test_detects_syntax_narration_slop(self):
        self.assertTrue(is_syntax_narration("// increment count"))
        self.assertTrue(is_syntax_narration("// return result"))
        self.assertTrue(is_syntax_narration("# check if user is none"))
        self.assertTrue(is_syntax_narration("// initialize variable x"))
        self.assertTrue(is_syntax_narration("// loop through items"))
        self.assertFalse(is_syntax_narration("// Compute FFT spectrum over sliding window"))

    def test_diff_with_syntax_narration_flags_blocker(self):
        diff = """diff --git a/src/calc.ts b/src/calc.ts
--- a/src/calc.ts
+++ b/src/calc.ts
@@ -10,6 +10,12 @@
+  // increment count
+  count += 1;
+  // check if count is valid
+  if (count > 0) {
+    // return result
+    return count;
+  }
"""
        record = audit_diff_comments(diff, density_threshold=0.35, min_comment_floor=2)
        self.assertEqual(record["code"], "ERR_SYNTAX_NARRATION_SLOP")
        blockers = [f for f in record["findings"] if f["severity"] == "blocker"]
        self.assertGreaterEqual(len(blockers), 2)

    def test_diff_with_clean_code_and_safety_comments_passes(self):
        diff = """diff --git a/src/buffer.rs b/src/buffer.rs
--- a/src/buffer.rs
+++ b/src/buffer.rs
@@ -1,5 +1,12 @@
+pub fn read_exact(buf: &[u8], len: usize) -> Option<&[u8]> {
+    // SAFETY: caller guarantees len does not exceed buffer capacity
+    if len <= buf.len() {
+        Some(&buf[..len])
+    } else {
+        None
+    }
+}
"""
        record = audit_diff_comments(diff, density_threshold=0.35, min_comment_floor=20)
        self.assertEqual(record["code"], "NO_COMMENT_FINDINGS")
        self.assertEqual(len(record["findings"]), 0)


if __name__ == "__main__":
    unittest.main()
