use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum Severity {
    Blocker,
    Review,
    Info,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum ViolationCategory {
    ScopeCreep,
    HypotheticalHardening,
    IntentViolation,
    TaskThrashing,
    LadderViolation,
    MissingBuiltIn,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Finding {
    pub file: String,
    pub line: usize,
    pub category: ViolationCategory,
    pub severity: Severity,
    pub code: String,
    pub message: String,
    pub suggestion: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditSummary {
    pub total_findings: usize,
    pub blockers: usize,
    pub reviews: usize,
    pub infos: usize,
    pub status: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AuditReport {
    pub engine: String,
    pub version: String,
    pub summary: AuditSummary,
    pub findings: Vec<Finding>,
}

impl AuditReport {
    pub fn new(engine: &str, findings: Vec<Finding>) -> Self {
        let blockers = findings.iter().filter(|f| f.severity == Severity::Blocker).count();
        let reviews = findings.iter().filter(|f| f.severity == Severity::Review).count();
        let infos = findings.iter().filter(|f| f.severity == Severity::Info).count();
        let status = if blockers > 0 {
            "BLOCKED".to_string()
        } else if reviews > 0 {
            "NEEDS_REVIEW".to_string()
        } else {
            "PASSED".to_string()
        };

        let summary = AuditSummary {
            total_findings: findings.len(),
            blockers,
            reviews,
            infos,
            status,
        };

        Self {
            engine: engine.to_string(),
            version: env!("CARGO_PKG_VERSION").to_string(),
            summary,
            findings,
        }
    }
}
