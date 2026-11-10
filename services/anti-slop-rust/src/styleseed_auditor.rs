use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::is_test_file;
use regex::Regex;

#[derive(Debug)]
pub struct StyleSeedAuditor {
    inline_hex_re: Regex,
    ad_hoc_spatial_re: Regex,
    hardcoded_height_re: Regex,
}

impl Default for StyleSeedAuditor {
    fn default() -> Self {
        Self::new()
    }
}

impl StyleSeedAuditor {
    pub fn new() -> Self {
        Self {
            inline_hex_re: Regex::new(r"#([0-9a-fA-F]{6}|[0-9a-fA-F]{8}|[0-9a-fA-F]{3})\b").unwrap(),
            ad_hoc_spatial_re: Regex::new(r"\b(m|p|gap|space-[xy])-(\[[0-9]+(\.[0-9]+)?px\])").unwrap(),
            hardcoded_height_re: Regex::new(r"\bh-\[[0-9]+px\]").unwrap(),
        }
    }

    pub fn audit_line(&self, file: &str, line_no: usize, line: &str) -> Option<Finding> {
        if is_test_file(file) {
            return None;
        }

        let is_component_file = file.ends_with(".tsx")
            || file.ends_with(".jsx")
            || file.ends_with(".vue")
            || file.ends_with(".svelte")
            || file.ends_with(".css");

        if !is_component_file {
            return None;
        }

        let trimmed = line.trim();
        if trimmed.starts_with("//") || trimmed.starts_with("/*") || trimmed.starts_with('*') {
            return None;
        }

        // 1. Primitive color hex leakage
        if let Some(caps) = self.inline_hex_re.captures(trimmed) {
            if let Some(m) = caps.get(1) {
                let hex_val = m.as_str().to_lowercase();
                if hex_val != "000" && hex_val != "fff" && hex_val != "000000" && hex_val != "ffffff" {
                    return Some(Finding {
                        file: file.to_string(),
                        line: line_no,
                        category: ViolationCategory::StyleSeedViolation,
                        severity: Severity::Blocker,
                        code: "STYLESEED-001".to_string(),
                        message: format!("Direct primitive color hex '#{}' leaked into component code", m.as_str()),
                        suggestion: "Replace hardcoded hex with semantic design token (e.g., var(--fg-default) or var(--bg-surface))".to_string(),
                    });
                }
            }
        }

        // 2. Ad-hoc spatial slop
        if let Some(caps) = self.ad_hoc_spatial_re.captures(trimmed) {
            let matched_str = caps.get(0).map_or("", |m| m.as_str());
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::StyleSeedViolation,
                severity: Severity::Blocker,
                code: "STYLESEED-002".to_string(),
                message: format!("Ad-hoc spatial class '{matched_str}' violates 6-role spatial scale"),
                suggestion: "Replace arbitrary pixel class with canonical spatial role token (pageInset, sectionGap, stackGap, etc.)".to_string(),
            });
        }

        // 3. Hardcoded control height
        if let Some(caps) = self.hardcoded_height_re.captures(trimmed) {
            let matched_str = caps.get(0).map_or("", |m| m.as_str());
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::StyleSeedViolation,
                severity: Severity::Review,
                code: "STYLESEED-003".to_string(),
                message: format!("Hardcoded control height '{matched_str}' detected"),
                suggestion: "Bind control height to declared cognitive output grammar scale (e.g. 36px, 40px, 44px)".to_string(),
            });
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detects_primitive_color_leakage() {
        let auditor = StyleSeedAuditor::new();
        let res = auditor.audit_line("src/Button.tsx", 10, "const c = { bg: '#2563eb' };");
        assert!(res.is_some());
        let f = res.unwrap();
        assert_eq!(f.code, "STYLESEED-001");
        assert_eq!(f.severity, Severity::Blocker);
    }

    #[test]
    fn test_permits_primitive_in_test_file() {
        let auditor = StyleSeedAuditor::new();
        let res = auditor.audit_line("tests/Button.test.tsx", 10, "const c = { bg: '#2563eb' };");
        assert!(res.is_none());
    }

    #[test]
    fn test_detects_adhoc_spatial_class() {
        let auditor = StyleSeedAuditor::new();
        let res = auditor.audit_line("src/Card.tsx", 15, "<div className='p-[19px]'>hello</div>");
        assert!(res.is_some());
        let f = res.unwrap();
        assert_eq!(f.code, "STYLESEED-002");
    }
}
