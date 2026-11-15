use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::{
    extract_source_file, extract_target_file, is_doc_file, is_test_file,
};
use regex::Regex;

fn is_metadata_change_line(line: &str) -> bool {
    line.starts_with("old mode ")
        || line.starts_with("new mode ")
        || line.starts_with("deleted file mode ")
        || line.starts_with("new file mode ")
        || line.starts_with("similarity index ")
        || line.starts_with("rename from ")
        || line.starts_with("rename to ")
        || line.starts_with("copy from ")
        || line.starts_with("copy to ")
        || line.starts_with("Binary files ")
}

fn record_metadata_end(
    findings: &mut Vec<Finding>,
    file: &str,
    src_file: &str,
    had_metadata: bool,
    had_hunks: bool,
    allowed: Option<&[&str]>,
    read_only: bool,
) {
    if !had_metadata || had_hunks || file.is_empty() {
        return;
    }
    if let Some(f) = check_scope_creep(file, 1, allowed, true) {
        findings.push(f);
    }
    if !src_file.is_empty() && src_file != file {
        if let Some(f) = check_scope_creep(src_file, 1, allowed, true) {
            findings.push(f);
        }
    }
    if let Some(f) = check_intent_violation(file, 1, read_only, true) {
        findings.push(f);
    }
}

#[derive(Debug)]
pub struct ShitInterceptor {
    re_companion_hash: Regex,
    re_swallow_error: Regex,
    re_hypothetical_wrapper: Regex,
}

impl Default for ShitInterceptor {
    fn default() -> Self {
        Self::new()
    }
}

impl ShitInterceptor {
    pub fn new() -> Self {
        Self {
            re_companion_hash: Regex::new(
                r#"(?i)(createHash\(['"](?:sha256|md5|sha1)['"]\)|hashlib\.(?:sha256|md5|sha1)\()"#,
            )
            .unwrap(),
            re_swallow_error: Regex::new(
                r#"(?x)
                catch\s*\([^)]*\)\s*\{\s*\}|
                except(?:\s+Exception)?\s*:\s*pass
                "#,
            )
            .unwrap(),
            re_hypothetical_wrapper: Regex::new(
                r#"(?i)class\s+(?:Base|Abstract|Generic)\w+(?:Adapter|Provider|Factory|Service)\b"#,
            )
            .unwrap(),
        }
    }

    /// Audit a unified git diff for SHIT violations
    pub fn audit_diff(
        &self,
        diff_text: &str,
        allowed_files: Option<&[&str]>,
        read_only_intent: bool,
    ) -> Vec<Finding> {
        let mut findings = Vec::new();
        let mut current_file = String::new();
        let mut source_file = String::new();
        let mut line_no = 0;
        let mut in_hunk = false;
        let mut file_had_hunks = false;
        let mut file_had_metadata_change = false;

        for line in diff_text.lines() {
            if line.starts_with("diff --git") {
                record_metadata_end(
                    &mut findings,
                    &current_file,
                    &source_file,
                    file_had_metadata_change,
                    file_had_hunks,
                    allowed_files,
                    read_only_intent,
                );
                current_file = extract_target_file(line).unwrap_or_default();
                source_file = extract_source_file(line).unwrap_or_default();
                line_no = 0;
                in_hunk = false;
                file_had_hunks = false;
                file_had_metadata_change = false;
                continue;
            }
            if !in_hunk {
                if let Some(f) = extract_target_file(line) {
                    current_file = f;
                }
                if let Some(sf) = extract_source_file(line) {
                    source_file = sf;
                }
                if is_metadata_change_line(line) {
                    file_had_metadata_change = true;
                }
            }
            if let Some(l) = extract_hunk_line(line) {
                line_no = l;
                in_hunk = true;
                file_had_hunks = true;
                continue;
            }
            if !in_hunk {
                continue;
            }
            let is_change = line.starts_with('+') || line.starts_with('-');
            if let Some(f) = check_scope_creep(&current_file, line_no, allowed_files, is_change) {
                findings.push(f);
            }

            if let Some(f) = check_intent_violation(&current_file, line_no, read_only_intent, is_change) {
                findings.push(f);
            }

            let is_addition = line.starts_with('+') && !line.starts_with("+++");
            let is_ignored = is_doc_file(&current_file) || is_test_file(&current_file);

            if is_addition && !is_ignored {
                let code_content = line[1..].trim();
                let mut line_findings = self.audit_added_code(&current_file, line_no, code_content);
                findings.append(&mut line_findings);
            }

            if line.starts_with('+') || line.starts_with(' ') {
                line_no += 1;
            }
        }

        record_metadata_end(
            &mut findings,
            &current_file,
            &source_file,
            file_had_metadata_change,
            file_had_hunks,
            allowed_files,
            read_only_intent,
        );

        findings
    }

    fn audit_added_code(&self, file: &str, line_no: usize, code: &str) -> Vec<Finding> {
        let mut findings = Vec::new();

        if self.re_companion_hash.is_match(code)
            && (code.contains(".sha256") || code.contains(".md5") || code.contains("digest("))
        {
            findings.push(Self::hardening_review(
                file,
                line_no,
                "STS-H01",
                "Hypothetical hardening: companion hash/checksum generated without verified downstream consumer.",
                "Remove speculative checksum generation unless explicitly required by publishing contracts.",
            ));
        }

        if self.re_swallow_error.is_match(code) {
            findings.push(Self::hardening_blocker(
                file,
                line_no,
                "STS-H02",
                "Hypothetical hardening: swallowing error without logging or structured recovery.",
                "Handle errors explicitly or propagate them with actionable context.",
            ));
        }

        if self.re_hypothetical_wrapper.is_match(code) {
            findings.push(Self::hardening_review(
                file,
                line_no,
                "STS-H03",
                "Hypothetical abstraction: speculative Base/Abstract provider or factory detected.",
                "Prefer direct, cohesive implementation until multiple consumers emerge.",
            ));
        }

        findings
    }

    fn hardening_review(file: &str, line_no: usize, code: &str, msg: &str, suggestion: &str) -> Finding {
        Self::hardening_finding(file, line_no, Severity::Review, code, msg, suggestion)
    }

    fn hardening_blocker(file: &str, line_no: usize, code: &str, msg: &str, suggestion: &str) -> Finding {
        Self::hardening_finding(file, line_no, Severity::Blocker, code, msg, suggestion)
    }

    fn hardening_finding(
        file: &str,
        line_no: usize,
        severity: Severity,
        code: &str,
        msg: &str,
        suggestion: &str,
    ) -> Finding {
        Finding {
            file: file.to_string(),
            line: line_no,
            category: ViolationCategory::HypotheticalHardening,
            severity,
            code: code.to_string(),
            message: msg.to_string(),
            suggestion: suggestion.to_string(),
        }
    }
}

pub(crate) fn extract_hunk_line(line: &str) -> Option<usize> {
    let start = line.strip_prefix("@@")?.split('+').nth(1)?;
    start.split_whitespace().next()?.split(',').next()?.parse().ok()
}

fn check_intent_violation(
    file: &str,
    line_no: usize,
    read_only: bool,
    is_change: bool,
) -> Option<Finding> {
    if !read_only || !is_change {
        return None;
    }
    Some(Finding {
        file: file.to_string(),
        line: line_no,
        category: ViolationCategory::IntentViolation,
        severity: Severity::Blocker,
        code: "STS-I01".to_string(),
        message: "Intent violation: modification attempted while in read-only / review mode."
            .to_string(),
        suggestion: "Do not write or modify files during an audit or review turn.".to_string(),
    })
}

fn check_scope_creep(
    file: &str,
    line_no: usize,
    allowed_files: Option<&[&str]>,
    is_change: bool,
) -> Option<Finding> {
    let allowed = allowed_files?;
    if file.is_empty() || allowed.is_empty() || !is_change {
        return None;
    }
    let is_allowed = allowed.iter().any(|prefix| file.starts_with(prefix));
    if !is_allowed {
        Some(Finding {
            file: file.to_string(),
            line: line_no,
            category: ViolationCategory::ScopeCreep,
            severity: Severity::Blocker,
            code: "STS-S01".to_string(),
            message: format!(
                "Scope creep: file '{file}' modified outside allowed scope: {allowed:?}",
            ),
            suggestion: "Restrict edits strictly to designated files for this task.".to_string(),
        })
    } else {
        None
    }
}

#[cfg(test)]
mod review_regression_tests {
    use super::ShitInterceptor;

    #[test]
    fn deletion_only_changes_trigger_read_only_and_scope_checks() {
        let diff = "diff --git a/old.rs b/old.rs\n--- a/old.rs\n+++ b/old.rs\n@@ -1 +0,0 @@\n-let old = 1;\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings.iter().any(|f| f.code == "STS-S01"));
    }

    #[test]
    fn metadata_and_changed_lines_are_separated() {
        let diff = "diff --git a/a.rs b/a.rs\n--- a/a.rs\n+++ b/a.rs\n@@ -0,0 +1 @@\n+++not a header\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings.iter().any(|f| f.code == "STS-S01"));
    }

    #[test]
    fn non_hunk_mode_change_triggers_intent_and_scope_checks() {
        let diff = "diff --git a/script.sh b/script.sh\nold mode 100644\nnew mode 100755\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings.iter().any(|f| f.code == "STS-S01" && f.file == "script.sh"));
    }

    #[test]
    fn non_hunk_rename_triggers_scope_check_on_old_and_new_files() {
        let diff = "diff --git a/src/old.rs b/outside/new.rs\nsimilarity index 100%\nrename from src/old.rs\nrename to outside/new.rs\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), false);
        assert!(findings.iter().any(|f| f.code == "STS-S01" && f.file == "outside/new.rs"));
    }

    #[test]
    fn non_hunk_binary_diff_triggers_scope_and_intent_checks() {
        let diff = "diff --git a/outside/image.png b/outside/image.png\nBinary files a/outside/image.png and b/outside/image.png differ\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings.iter().any(|f| f.code == "STS-S01" && f.file == "outside/image.png"));
    }
}
