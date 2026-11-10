// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::is_doc_file;
use regex::Regex;

#[derive(Debug)]
pub struct AttentionAuditor {
    re_opener_wrappers: Regex,
    re_closer_offers: Regex,
}

impl Default for AttentionAuditor {
    fn default() -> Self {
        Self::new()
    }
}

impl AttentionAuditor {
    pub fn new() -> Self {
        Self {
            re_opener_wrappers: Regex::new(
                r#"(?i)^\s*(?:\*\*)*(?:here'?s|here is|sure|certainly|below is|i'?ve\s+(?:drafted|written|put together)|the following table outlines|in this section we will)\b"#,
            )
            .unwrap(),
            re_closer_offers: Regex::new(
                r#"(?i)\b(?:hope this helps|let me know if you|feel free to (?:adjust|tweak|use)|does this work for you)\b"#,
            )
            .unwrap(),
        }
    }

    pub fn audit_line(&self, file: &str, line_no: usize, line: &str) -> Option<Finding> {
        // Only audit documentation, markdown, or text files
        if !is_doc_file(file) && !file.ends_with(".md") && !file.ends_with(".txt") {
            return None;
        }

        if self.re_opener_wrappers.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::AttentionSlop,
                severity: Severity::Blocker,
                code: "ATTENTION-WRAPPER-01".to_string(),
                message: "Conversational opener wrapper detected in documentation/deliverable (The Direct Payload Invariant)".to_string(),
                suggestion: "Strip preamble; transition directly from header to technical payload.".to_string(),
            });
        }

        if self.re_closer_offers.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::AttentionSlop,
                severity: Severity::Blocker,
                code: "ATTENTION-CLOSER-02".to_string(),
                message: "Conversational closer offer detected in documentation/deliverable (Deliverable Purity)".to_string(),
                suggestion: "Remove 'Hope this helps!' / closer fluff; deliver raw artifact only.".to_string(),
            });
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detects_opener_wrapper() {
        let auditor = AttentionAuditor::new();
        assert!(auditor.audit_line("docs/guide.md", 10, "Here is the configuration you need:").is_some());
        assert!(auditor.audit_line("README.md", 5, "In this section we will explore features").is_some());
        assert!(auditor.audit_line("README.md", 15, "Hope this helps!").is_some());
        assert!(auditor.audit_line("src/main.rs", 10, "Here is the configuration:").is_none());
        assert!(auditor.audit_line("docs/guide.md", 20, "## Configuration").is_none());
    }
}
