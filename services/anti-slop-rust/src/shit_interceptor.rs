use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::{is_doc_file, is_relative_git_path, is_test_file, path_matches_scope};
use regex::Regex;

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
        let mut line_no = 0;
        let mut in_hunk = false;

        for line in diff_text.lines() {
            if line.starts_with("diff --git") {
                current_file = extract_target_file(line).unwrap_or_default();
                line_no = 0;
                in_hunk = false;
                continue;
            }
            if !in_hunk {
                if let Some(f) = extract_target_file(line) {
                    current_file = f;
                    continue;
                }
            }
            if let Some(l) = extract_hunk_line(line) {
                line_no = l;
                in_hunk = true;
                continue;
            }
            if !in_hunk {
                continue;
            }
            let is_change = line.starts_with('+') || line.starts_with('-');
            if let Some(f) = check_scope_creep(&current_file, line_no, allowed_files, is_change) {
                findings.push(f);
            }

            if let Some(f) =
                check_intent_violation(&current_file, line_no, read_only_intent, is_change)
            {
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

    fn hardening_review(
        file: &str,
        line_no: usize,
        code: &str,
        msg: &str,
        suggestion: &str,
    ) -> Finding {
        Self::hardening_finding(file, line_no, Severity::Review, code, msg, suggestion)
    }

    fn hardening_blocker(
        file: &str,
        line_no: usize,
        code: &str,
        msg: &str,
        suggestion: &str,
    ) -> Finding {
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

fn extract_target_file(line: &str) -> Option<String> {
    if line.starts_with("diff --git") {
        return line.split(" b/").nth(1).map(|t| t.trim().to_string());
    }
    if let Some(rest) = line.strip_prefix("+++ b/") {
        return Some(rest.trim().to_string());
    }
    None
}

pub(crate) fn extract_hunk_line(line: &str) -> Option<usize> {
    let start = line.strip_prefix("@@")?.split('+').nth(1)?;
    start
        .split_whitespace()
        .next()?
        .split(',')
        .next()?
        .parse()
        .ok()
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
    if allowed.is_empty() || !is_change {
        return None;
    }
    let is_allowed =
        is_relative_git_path(file) && allowed.iter().any(|scope| path_matches_scope(file, scope));

    if !is_allowed {
        Some(Finding {
            file: if file.is_empty() { "unknown" } else { file }.to_owned(),
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
        let diff =
            "diff --git a/a.rs b/a.rs\n--- a/a.rs\n+++ b/a.rs\n@@ -0,0 +1 @@\n+++not a header\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings.iter().any(|f| f.code == "STS-S01"));
    }

    #[test]
    fn prefix_collision_does_not_permit_unauthorized_files() {
        let diff = "diff --git a/src/auth_bypass.rs b/src/auth_bypass.rs\n--- a/src/auth_bypass.rs\n+++ b/src/auth_bypass.rs\n@@ -1 +1,2 @@\n let a = 1;\n+let b = 2;\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/auth"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "src/auth_bypass.rs"));
    }

    #[test]
    fn path_traversal_is_normalized_and_blocked() {
        let diff = "diff --git a/src/auth/../../.github/workflows/ci.yml b/src/auth/../../.github/workflows/ci.yml\n--- a/src/auth/../../.github/workflows/ci.yml\n+++ b/src/auth/../../.github/workflows/ci.yml\n@@ -1 +1,2 @@\n name: CI\n+run: echo pwned\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/auth"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "src/auth/../../.github/workflows/ci.yml"));
    }

    #[test]
    fn component_boundary_permits_valid_subpath() {
        let diff = "diff --git a/src/auth/login.rs b/src/auth/login.rs\n--- a/src/auth/login.rs\n+++ b/src/auth/login.rs\n@@ -1 +1,2 @@\n let a = 1;\n+let b = 2;\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/auth"]), false);
        assert!(!findings.iter().any(|f| f.code == "STS-S01"));
    }

    #[test]
    fn scope_policy_rejects_untrusted_path_components() {
        for path in [
            "src/tmp/../auth/a.rs",
            "src/auth/./a.rs",
            "/src/auth/a.rs",
            r"src\auth\a.rs",
            "C:/src/auth/a.rs",
        ] {
            let diff = format!(
                "diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -0,0 +1 @@\n+line\n"
            );
            let findings = ShitInterceptor::new().audit_diff(&diff, Some(&["src/auth/"]), false);
            assert!(findings.iter().any(|f| f.code == "STS-S01"), "{path:?}");
        }
    }

    #[test]
    fn scope_policy_rejects_unusable_allowlist_entries() {
        let diff = "diff --git a/src/auth/a.rs b/src/auth/a.rs\n--- a/src/auth/a.rs\n+++ b/src/auth/a.rs\n@@ -0,0 +1 @@\n+line\n";
        for scope in ["", ".", "/", "/src/auth/", "src/tmp/../auth/", r"src\auth\"] {
            let findings = ShitInterceptor::new().audit_diff(diff, Some(&[scope]), false);
            assert!(findings.iter().any(|f| f.code == "STS-S01"), "{scope:?}");
        }
    }

    #[test]
    fn scope_policy_directory_suffix_requires_a_child_path() {
        let diff = "diff --git a/src/auth b/src/auth\n--- a/src/auth\n+++ b/src/auth\n@@ -0,0 +1 @@\n+line\n";
        let interceptor = ShitInterceptor::new();
        let directory = interceptor.audit_diff(diff, Some(&["src/auth/"]), false);
        let bare = interceptor.audit_diff(diff, Some(&["src/auth"]), false);
        assert!(directory.iter().any(|f| f.code == "STS-S01"));
        assert!(bare.is_empty());
    }
}
