use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::{is_doc_file, is_test_file};
use regex::Regex;

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

        for line in diff_text.lines() {
            if let Some(f) = extract_target_file(line) {
                current_file = f;
                line_no = 0;
                continue;
            }

            if let Some(l) = extract_hunk_line(line) {
                line_no = l;
                continue;
            }

            if let Some(f) = check_scope_creep(&current_file, line, line_no, allowed_files) {
                findings.push(f);
            }

            if let Some(f) = check_intent_violation(&current_file, line, line_no, read_only_intent) {
                findings.push(f);
            }

            let is_addition = line.starts_with('+') && !line.starts_with("+++");
            let is_ignored = is_doc_file(&current_file) || is_test_file(&current_file);

            if is_addition && !is_ignored {
                let code_content = line[1..].trim();
                let mut line_findings = self.audit_added_code(&current_file, line_no, code_content);
                findings.append(&mut line_findings);
            }

            if line.starts_with('+') || !line.starts_with('-') {
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

fn extract_target_file(line: &str) -> Option<String> {
    if line.starts_with("diff --git") {
        return line.split(" b/").nth(1).map(|t| t.trim().to_string());
    }
    if let Some(rest) = line.strip_prefix("+++ b/") {
        return Some(rest.trim().to_string());
    }
    None
}

fn extract_hunk_line(line: &str) -> Option<usize> {
    let start = line.strip_prefix("@@")?.split('+').nth(1)?;
    start.split(',').next()?.trim().parse().ok()
}

fn check_intent_violation(
    file: &str,
    line: &str,
    line_no: usize,
    read_only: bool,
) -> Option<Finding> {
    if !read_only || !line.starts_with('+') || line.starts_with("+++") {
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
    line: &str,
    line_no: usize,
    allowed_files: Option<&[&str]>,
) -> Option<Finding> {
    let allowed = allowed_files?;
    if file.is_empty() || allowed.is_empty() || !line.starts_with('+') || line.starts_with("+++") {
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
                "Scope creep: file '{}' modified outside allowed scope: {:?}",
                file, allowed
            ),
            suggestion: "Restrict edits strictly to designated files for this task.".to_string(),
        })
    } else {
        None
    }
}
