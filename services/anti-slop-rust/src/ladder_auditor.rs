use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::{is_doc_file, is_test_file};
use regex::Regex;

pub struct LadderAuditor {
    re_handrolled_uuid: Regex,
    re_handrolled_query_parser: Regex,
    re_handrolled_clone: Regex,
    re_conjunction_naming: Regex,
}

impl Default for LadderAuditor {
    fn default() -> Self {
        Self::new()
    }
}

impl LadderAuditor {
    pub fn new() -> Self {
        Self {
            re_handrolled_uuid: Regex::new(
                r#"(?i)Math\.random\(\)\.toString\(36\)|[a-z0-9]+-[a-z0-9]+-4[a-z0-9]+-[a-z0-9]+"#,
            )
            .unwrap(),
            re_handrolled_query_parser: Regex::new(
                r#"(?i)\.split\(['"]&['"]\)\.map\(|\.split\(['"]\?['"]\)\[1\]"#,
            )
            .unwrap(),
            re_handrolled_clone: Regex::new(
                r#"JSON\.parse\(JSON\.stringify\("#,
            )
            .unwrap(),
            re_conjunction_naming: Regex::new(
                r#"(?:class|interface|type|fn|function|struct|enum)\s+[A-Za-z0-9_]*[a-z0-9](?:And|Or)[A-Z]"#,
            )
            .unwrap(),
        }
    }

    /// Audit code additions for Senior Dev Ladder & Built-in compliance
    pub fn audit_code(&self, file_path: &str, content: &str) -> Vec<Finding> {
        let mut findings = Vec::new();

        if is_doc_file(file_path) || is_test_file(file_path) {
            return findings;
        }

        for (idx, line) in content.lines().enumerate() {
            let line_no = idx + 1;
            let trimmed = line.trim();
            self.audit_line(file_path, line_no, trimmed, &mut findings);
        }

        findings
    }

    fn audit_line(&self, file: &str, line_no: usize, line: &str, out: &mut Vec<Finding>) {
        if self.re_handrolled_uuid.is_match(line) && line.contains("Math.random") {
            out.push(Self::built_in(
                file,
                line_no,
                "BORING-KISS-01",
                "Hand-rolled UUID generator detected when standard built-in exists.",
                "Name the built-in: use crypto.randomUUID() instead of hand-rolled math random strings.",
            ));
        }

        if self.re_handrolled_query_parser.is_match(line) {
            out.push(Self::built_in(
                file,
                line_no,
                "BORING-KISS-02",
                "Hand-rolled URL query parser detected when platform built-in exists.",
                "Name the built-in: use new URLSearchParams(query) instead of manual string splitting.",
            ));
        }

        if self.re_handrolled_clone.is_match(line) {
            out.push(Self::built_in(
                file,
                line_no,
                "BORING-KISS-03",
                "JSON serialization used for cloning when native structuredClone exists.",
                "Name the built-in: use native structuredClone(value) to preserve types safely.",
            ));
        }

        if self.re_conjunction_naming.is_match(line) {
            out.push(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::LadderViolation,
                severity: Severity::Review,
                code: "BORING-DRY-01".to_string(),
                message: "Symbol name contains conjunction ('And' / 'Or'), indicating mixed responsibilities.".to_string(),
                suggestion: "Practical DRY rule 3: Abstractions must be nameable without 'and' or 'or'. Decompose into single-purpose components.".to_string(),
            });
        }
    }

    fn built_in(file: &str, line_no: usize, code: &str, msg: &str, suggestion: &str) -> Finding {
        Finding {
            file: file.to_string(),
            line: line_no,
            category: ViolationCategory::MissingBuiltIn,
            severity: Severity::Review,
            code: code.to_string(),
            message: msg.to_string(),
            suggestion: suggestion.to_string(),
        }
    }
}
