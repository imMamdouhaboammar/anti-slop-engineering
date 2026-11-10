// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::is_doc_file;
use regex::Regex;

pub struct TagoreAuditor {
    re_inflation: Regex,
    re_copula: Regex,
    re_participle: Regex,
    re_hype: Regex,
    re_sycophancy: Regex,
}

impl Default for TagoreAuditor {
    fn default() -> Self {
        Self::new()
    }
}

impl TagoreAuditor {
    pub fn new() -> Self {
        Self {
            re_inflation: Regex::new(
                r#"(?i)\b(?:stands?|serves?)\s+as\s+(?:an?\s+)?(?:enduring\s+)?(?:testament|beacon|reminder)\b|\b(?:pivotal|vital|groundbreaking)\s+(?:moment|role|milestone|shift)\b|\bunderscores?\s+(?:the\s+)?importance\b|\bevolving\s+landscape\b"#,
            )
            .unwrap(),
            re_copula: Regex::new(
                r#"(?i)\b(?:serves?\s+as|stands?\s+as|functions?\s+as)\s+(?:an?\s+)?(?:robust|comprehensive|vital|powerful)\b|\b(?:boasts?|features?)\s+(?:an?\s+)?(?:impressive|unmatched)\b"#,
            )
            .unwrap(),
            re_participle: Regex::new(
                r#"(?i)(?:,\s*(?:highlighting|underscoring|emphasizing|ensuring|reflecting|fostering|enhancing|facilitating)\s+[^,\n]+){2,}"#,
            )
            .unwrap(),
            re_hype: Regex::new(
                r#"(?i)\b(?:groundbreaking|game-changer|revolutionary|unparalleled|seamlessly|best-in-class|unlock(?:ing)?\s+the\s+power)\b"#,
            )
            .unwrap(),
            re_sycophancy: Regex::new(
                r#"(?i)\b(?:great\s+question!?|excellent\s+point!?|that'?s\s+a\s+fantastic\s+idea!?)\b"#,
            )
            .unwrap(),
        }
    }

    pub fn audit_line(&self, file: &str, line_no: usize, line: &str) -> Option<Finding> {
        // Only audit documentation, markdown, or text files
        if !is_doc_file(file) && !file.ends_with(".md") && !file.ends_with(".txt") {
            return None;
        }

        if self.re_inflation.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::TagoreDiscourseViolation,
                severity: Severity::Blocker,
                code: "TAGORE-INFLATION-01".to_string(),
                message: "Significance inflation detected: AI puffery elevates routine engineering into historic milestone.".to_string(),
                suggestion: "State the technical change directly without inflation or legacy claims.".to_string(),
            });
        }

        if self.re_copula.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::TagoreDiscourseViolation,
                severity: Severity::Blocker,
                code: "TAGORE-COPULA-02".to_string(),
                message: "Copula avoidance: Elaborate verb substitution avoiding simple 'is', 'are', or 'has'.".to_string(),
                suggestion: "Use simple copula verbs ('is', 'are', 'has', 'contains').".to_string(),
            });
        }

        if self.re_participle.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::TagoreDiscourseViolation,
                severity: Severity::Review,
                code: "TAGORE-PARTICIPLE-03".to_string(),
                message: "Superficial participle (-ing) chaining: trailing participles tacked on for fake depth.".to_string(),
                suggestion: "Break into declarative sentences with active subjects and empirical specifics.".to_string(),
            });
        }

        if self.re_hype.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::TagoreDiscourseViolation,
                severity: Severity::Review,
                code: "TAGORE-HYPE-04".to_string(),
                message: "Promotional marketing buzzword inappropriate for engineering discourse.".to_string(),
                suggestion: "Use restrained, precise technical terminology.".to_string(),
            });
        }

        if self.re_sycophancy.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::TagoreDiscourseViolation,
                severity: Severity::Blocker,
                code: "TAGORE-SYCOPHANCY-05".to_string(),
                message: "Sycophantic conversational cheerleading token detected.".to_string(),
                suggestion: "Address technical substance directly without cheerleading or servile flattery.".to_string(),
            });
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detects_significance_inflation() {
        let auditor = TagoreAuditor::new();
        assert!(auditor.audit_line("docs/architecture.md", 10, "This PR serves as an enduring testament to our platform").is_some());
        assert!(auditor.audit_line("README.md", 5, "Marking a pivotal milestone in software development").is_some());
        assert!(auditor.audit_line("src/lib.rs", 10, "serves as an enduring testament").is_none());
    }

    #[test]
    fn test_detects_copula_avoidance() {
        let auditor = TagoreAuditor::new();
        assert!(auditor.audit_line("docs/architecture.md", 10, "The module serves as a robust engine").is_some());
        assert!(auditor.audit_line("README.md", 15, "The service boasts an unmatched cache").is_some());
        assert!(auditor.audit_line("docs/architecture.md", 20, "The module is a cache engine").is_none());
    }

    #[test]
    fn test_detects_promotional_hype() {
        let auditor = TagoreAuditor::new();
        assert!(auditor.audit_line("docs/architecture.md", 10, "Our groundbreaking solution seamlessly integrates").is_some());
        assert!(auditor.audit_line("docs/architecture.md", 20, "The function handles HTTP requests").is_none());
    }
}
