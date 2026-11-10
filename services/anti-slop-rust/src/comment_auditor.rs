// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::is_doc_file;
use regex::Regex;

#[derive(Debug)]
pub struct CommentAuditor {
    re_syntax_narration: Vec<Regex>,
    re_protected: Vec<Regex>,
}

impl Default for CommentAuditor {
    fn default() -> Self {
        Self::new()
    }
}

impl CommentAuditor {
    pub fn new() -> Self {
        Self {
            re_syntax_narration: vec![
                Regex::new(r#"(?i)^\s*(?://|#)\s*(?:increment|decrement)\s+\w+"#).unwrap(),
                Regex::new(r#"(?i)^\s*(?://|#)\s*return\s+(?:the\s+)?(?:result|value|response|data|true|false|null|none)\b"#).unwrap(),
                Regex::new(r#"(?i)^\s*(?://|#)\s*check\s+if\s+(?:\w+\s+)?(?:is\s+)?(?:null|none|empty|valid|defined|exists)\b"#).unwrap(),
                Regex::new(r#"(?i)^\s*(?://|#)\s*(?:initialize|declare|assign)\s+(?:variable|state|object|array|counter|constant)\b"#).unwrap(),
                Regex::new(r#"(?i)^\s*(?://|#)\s*(?:loop|iterate)\s+(?:through|over)\s+(?:all\s+)?(?:items|elements|list|array)\b"#).unwrap(),
                Regex::new(r#"(?i)^\s*(?://|#)\s*parse\s+(?:the\s+)?(?:json|string|input|data)\b"#).unwrap(),
                Regex::new(r#"(?i)^\s*(?://|#)\s*call\s+(?:\w+\s+)?(?:function|method|api)\b"#).unwrap(),
                Regex::new(r#"(?i)^\s*(?://|#)\s*print\s+(?:the\s+)?(?:message|error|output|log)\b"#).unwrap(),
            ],
            re_protected: vec![
                Regex::new(r#"(?i)//\s*SAFETY:"#).unwrap(),
                Regex::new(r#"(?i)//\s*SPDX-License-Identifier:"#).unwrap(),
                Regex::new(r#"(?i)//\s*Copyright\s+\(c\)"#).unwrap(),
                Regex::new(r#"(?i)#\s*SPDX-License-Identifier:"#).unwrap(),
                Regex::new(r#"(?i)#\s*Copyright\s+\(c\)"#).unwrap(),
                Regex::new(r#"^\s*///"#).unwrap(),
                Regex::new(r#"^\s*/\*\*"#).unwrap(),
                Regex::new(r#"^\s*\*"#).unwrap(),
            ],
        }
    }

    pub fn is_exempt(&self, file: &str) -> bool {
        if is_doc_file(file) {
            return true;
        }
        let lower = file.to_lowercase();
        lower.ends_with(".yaml")
            || lower.ends_with(".yml")
            || lower.ends_with(".json")
            || lower.ends_with(".toml")
            || lower.ends_with(".sql")
            || lower.ends_with(".lock")
    }

    pub fn is_protected(&self, line: &str) -> bool {
        self.re_protected.iter().any(|r| r.is_match(line))
    }

    pub fn audit_line(&self, file: &str, line_no: usize, line: &str) -> Option<Finding> {
        if self.is_exempt(file) || self.is_protected(line) {
            return None;
        }

        for r in &self.re_syntax_narration {
            if r.is_match(line) {
                return Some(Finding {
                    file: file.to_string(),
                    line: line_no,
                    category: ViolationCategory::CommentSlop,
                    severity: Severity::Blocker,
                    code: "COMMENT-NARRATION-01".to_string(),
                    message: "Trivial syntax play-by-play comment detected (Zero-Obviousness & Anti-Truism Doctrine)".to_string(),
                    suggestion: "Remove tautological comment; let clean code speak for itself.".to_string(),
                });
            }
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detects_narration() {
        let auditor = CommentAuditor::new();
        assert!(auditor.audit_line("src/main.rs", 10, "// increment counter").is_some());
        assert!(auditor.audit_line("src/main.rs", 11, "// return result").is_some());
        assert!(auditor.audit_line("src/main.rs", 12, "// SAFETY: bounded slice").is_none());
        assert!(auditor.audit_line("docs/guide.md", 5, "// increment counter").is_none());
    }
}
