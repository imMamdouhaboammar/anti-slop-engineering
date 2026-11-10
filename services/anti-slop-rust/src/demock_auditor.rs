use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::is_test_file;
use regex::Regex;

#[derive(Debug)]
pub struct DemockAuditor {
    test_double_re: Regex,
    sqlite_fallback_re: Regex,
    unimplemented_re: Regex,
}

impl Default for DemockAuditor {
    fn default() -> Self {
        Self::new()
    }
}

impl DemockAuditor {
    pub fn new() -> Self {
        Self {
            test_double_re: Regex::new(r"\b(MagicMock|AsyncMock|new\s+FakeDatabase|new\s+DummyStorage)\b").unwrap(),
            sqlite_fallback_re: Regex::new(r"(?i)(fallback\s+to\s+sqlite|local_sqlite_fallback|new\s+LocalSqliteDb)").unwrap(),
            unimplemented_re: Regex::new(r"\b(raise\s+NotImplementedError|todo!\s*\(|unimplemented!\s*\()").unwrap(),
        }
    }

    pub fn audit_line(&self, file: &str, line_no: usize, line: &str) -> Option<Finding> {
        if is_test_file(file) {
            return None;
        }

        if self.test_double_re.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::DemockViolation,
                severity: Severity::Blocker,
                code: "DEMOCK-001".to_string(),
                message: "Test double or mock instantiated in production path".to_string(),
                suggestion: "Remove mock object from runtime code; inject real dependency via constructor".to_string(),
            });
        }

        if self.sqlite_fallback_re.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::DemockViolation,
                severity: Severity::Blocker,
                code: "DEMOCK-002".to_string(),
                message: "Forbidden silent SQLite fallback detected in database layer".to_string(),
                suggestion: "Fail closed on database connectivity errors; do not fallback to local SQLite".to_string(),
            });
        }

        if self.unimplemented_re.is_match(line) {
            return Some(Finding {
                file: file.to_string(),
                line: line_no,
                category: ViolationCategory::DemockViolation,
                severity: Severity::Review,
                code: "DEMOCK-003".to_string(),
                message: "Unimplemented placeholder on production path".to_string(),
                suggestion: "Implement full logic or isolate from active export".to_string(),
            });
        }

        None
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_detects_mock_in_production() {
        let auditor = DemockAuditor::new();
        let res = auditor.audit_line("src/service.py", 10, "client = MagicMock()");
        assert!(res.is_some());
        let finding = res.unwrap();
        assert_eq!(finding.category, ViolationCategory::DemockViolation);
        assert_eq!(finding.severity, Severity::Blocker);
    }

    #[test]
    fn test_permits_mock_in_test_file() {
        let auditor = DemockAuditor::new();
        let res = auditor.audit_line("tests/test_service.py", 10, "client = MagicMock()");
        assert!(res.is_none());
    }

    #[test]
    fn test_detects_sqlite_fallback() {
        let auditor = DemockAuditor::new();
        let res = auditor.audit_line("src/db.ts", 42, "const db = new LocalSqliteDb(); // fallback to sqlite");
        assert!(res.is_some());
        let finding = res.unwrap();
        assert_eq!(finding.severity, Severity::Blocker);
    }
}
