pub mod ladder_auditor;
pub mod model;
pub mod path_utils;
pub mod server;
pub mod shit_interceptor;

use model::AuditReport;

/// Run complete anti-slop triage across a unified git diff
pub fn triage_diff(
    diff_text: &str,
    allowed_files: Option<&[&str]>,
    read_only: bool,
) -> AuditReport {
    let interceptor = shit_interceptor::ShitInterceptor::new();
    let auditor = ladder_auditor::LadderAuditor::new();

    let mut findings = interceptor.audit_diff(diff_text, allowed_files, read_only);

    let mut current_file = "diff_patch".to_string();
    let mut added_lines = Vec::new();

    for line in diff_text.lines() {
        if line.starts_with("+++ b/") {
            if !added_lines.is_empty() {
                let code = added_lines.join("\n");
                findings.extend(auditor.audit_code(&current_file, &code));
                added_lines.clear();
            }
            current_file = line[6..].trim().to_string();
        } else if line.starts_with('+') && !line.starts_with("+++") {
            added_lines.push(&line[1..]);
        }
    }

    if !added_lines.is_empty() {
        let code = added_lines.join("\n");
        findings.extend(auditor.audit_code(&current_file, &code));
    }

    AuditReport::new("anti-slop-rust-triage", findings)
}
