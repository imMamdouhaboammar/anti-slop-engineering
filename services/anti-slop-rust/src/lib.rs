pub mod ladder_auditor;
pub mod model;
pub mod path_utils;
pub mod server;
pub mod shit_interceptor;

use model::AuditReport;
use std::sync::LazyLock;

pub(crate) static SHIT_INTERCEPTOR: LazyLock<shit_interceptor::ShitInterceptor> =
    LazyLock::new(shit_interceptor::ShitInterceptor::new);
pub(crate) static LADDER_AUDITOR: LazyLock<ladder_auditor::LadderAuditor> =
    LazyLock::new(ladder_auditor::LadderAuditor::new);

/// Run complete anti-slop triage across a unified git diff
pub fn triage_diff(
    diff_text: &str,
    allowed_files: Option<&[&str]>,
    read_only: bool,
) -> AuditReport {
    let mut findings = SHIT_INTERCEPTOR.audit_diff(diff_text, allowed_files, read_only);
    let mut current_file = String::new();
    let mut line_no = 0;
    let mut in_hunk = false;

    for line in diff_text.lines() {
        if line.starts_with("diff --git") {
            in_hunk = false;
            current_file.clear();
            continue;
        }
        if !in_hunk && line.starts_with("+++ b/") {
            current_file = line[6..].trim().to_string();
            continue;
        }
        if let Some(start) = shit_interceptor::extract_hunk_line(line) {
            in_hunk = true;
            line_no = start;
            continue;
        }
        if !in_hunk {
            continue;
        }
        if let Some(added) = line.strip_prefix('+') {
            for mut finding in LADDER_AUDITOR.audit_code(&current_file, added) {
                finding.line = line_no;
                findings.push(finding);
            }
            line_no += 1;
        } else if line.starts_with(' ') {
            line_no += 1;
        }
    }

    AuditReport::new("anti-slop-rust-triage", findings)
}

#[cfg(test)]
mod regression_tests {
    #[test]
    fn ladder_triage_reports_actual_new_file_line() {
        let diff = "diff --git a/src/app.js b/src/app.js\n--- a/src/app.js\n+++ b/src/app.js\n@@ -40,0 +41,2 @@\n+const x = 1;\n+const clone = JSON.parse(JSON.stringify(value));\n";
        let report = super::triage_diff(diff, None, false);
        assert!(report.findings.iter().any(|f| f.code == "BORING-KISS-03" && f.line == 42));
    }
}
