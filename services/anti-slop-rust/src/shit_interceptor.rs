use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::{is_doc_file, is_test_file};
use regex::Regex;

#[derive(Debug)]
pub struct ShitInterceptor {
    re_companion_hash: Regex,
    re_swallow_error: Regex,
    re_hypothetical_wrapper: Regex,
    re_go_if_err_nil: Regex,
    re_catch_block: Regex,
    re_py_except: Regex,
}

impl Default for ShitInterceptor {
    fn default() -> Self {
        Self::new()
    }
}

impl ShitInterceptor {
    pub fn new() -> Self {
        Self {
            re_companion_hash: compile_regex(
                r#"(?i)(createHash\(['"](?:sha256|md5|sha1)['"]\)|hashlib\.(?:sha256|md5|sha1)\()"#,
            ),
            re_swallow_error: compile_regex(
                r#"(?x)
                catch\s*(?:\([^)]*\))?\s*\{\s*\}|
                except(?:\s+[^:]*)?:\s*(?:pass|\.\.\.)|
                if\s+(?:.+;\s*)?err\s*!=\s*nil\s*\{\s*\}
                "#,
            ),
            re_hypothetical_wrapper: compile_regex(
                r#"(?i)class\s+(?:Base|Abstract|Generic)\w+(?:Adapter|Provider|Factory|Service)\b"#,
            ),
            re_go_if_err_nil: compile_regex(
                r#"^(?:if\s+(?:.+;\s*)?err\s*!=\s*nil|if\s+err\s*!=\s*nil)\s*\{?$"#,
            ),
            re_catch_block: compile_regex(r#"^(?:\}\s*)?catch\s*(?:\([^)]*\))?\s*\{?$"#),
            re_py_except: compile_regex(r#"^except(?:\s+[^:]*)?:$"#),
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
        let mut hunk_lines: Vec<(usize, char, String)> = Vec::new();

        let process_file_hunks = |file: &str, h_lines: &[(usize, char, String)]| -> Vec<Finding> {
            if file.is_empty() || is_doc_file(file) || is_test_file(file) {
                return Vec::new();
            }
            let mut f_findings = Vec::new();
            for i in 0..h_lines.len() {
                let (l_no, prefix, ref line_text) = h_lines[i];
                if prefix != '+' {
                    continue;
                }
                let code_content = line_text.trim();
                let mut line_findings = self.audit_added_code(file, l_no, code_content);
                if !line_findings.iter().any(|f| f.code == "STS-H02")
                    && self.is_multiline_swallowed_error(i, h_lines)
                {
                    line_findings.push(Self::hardening_blocker(
                        file,
                        l_no,
                        "STS-H02",
                        "Hypothetical hardening: swallowing error without logging or structured recovery.",
                        "Handle errors explicitly or propagate them with actionable context.",
                    ));
                }
                f_findings.append(&mut line_findings);
            }
            f_findings
        };

        for line in diff_text.lines() {
            if line.starts_with("diff --git") {
                findings.extend(process_file_hunks(&current_file, &hunk_lines));
                hunk_lines.clear();
                current_file = extract_target_file(line).unwrap_or_default();
                line_no = 0;
                in_hunk = false;
                continue;
            }
            if !in_hunk {
                if let Some(f) = extract_target_file(line) {
                    findings.extend(process_file_hunks(&current_file, &hunk_lines));
                    hunk_lines.clear();
                    current_file = f;
                    continue;
                }
            }
            if let Some(l) = extract_hunk_line(line) {
                findings.extend(process_file_hunks(&current_file, &hunk_lines));
                hunk_lines.clear();
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

            let is_hunk_content = (line.starts_with('+') && !line.starts_with("+++"))
                || (line.starts_with('-') && !line.starts_with("---"))
                || line.starts_with(' ');

            if is_hunk_content {
                let prefix = line.chars().next().unwrap_or(' ');
                let text = line.get(1..).unwrap_or("");
                hunk_lines.push((line_no, prefix, text.to_string()));
            }

            if line.starts_with('+') || line.starts_with(' ') {
                line_no += 1;
            }
        }

        findings.extend(process_file_hunks(&current_file, &hunk_lines));

        findings
    }

    fn is_multiline_swallowed_error(
        &self,
        start_idx: usize,
        lines: &[(usize, char, String)],
    ) -> bool {
        let (_, _, ref first_text) = lines[start_idx];
        let code = first_text.trim();

        if is_comment_or_doc_line(code) || is_inside_string_literal(code, 0) {
            return false;
        }

        if self.re_go_if_err_nil.is_match(code) || self.re_catch_block.is_match(code) {
            return self.is_swallowed_brace_block(start_idx, lines);
        }

        if self.re_py_except.is_match(code) {
            return self.is_swallowed_python_except(start_idx, lines);
        }

        false
    }

    fn is_swallowed_brace_block(&self, start_idx: usize, lines: &[(usize, char, String)]) -> bool {
        let limit = (start_idx + 25).min(lines.len());
        let mut depth = 0;
        let mut has_documented = false;

        for j in start_idx..limit {
            let Some((_, line)) = get_active_hunk_line(lines, j) else {
                continue;
            };
            if depth == 0 {
                let Some((_, after_open)) = line.split_once('{') else {
                    continue;
                };
                depth = 1;
                if !after_open.trim().is_empty() {
                    return after_open.trim_start().starts_with('}');
                }
                continue;
            }

            let (is_comment, is_doc) = check_comment_doc(line);
            if is_comment {
                has_documented |= is_doc;
                continue;
            }

            for c in line.chars() {
                match c {
                    '{' => depth += 1,
                    '}' => {
                        depth -= 1;
                        if depth == 0 {
                            return !has_documented;
                        }
                    }
                    c if c.is_whitespace() => (),
                    _ => return false,
                }
            }
        }
        false
    }

    fn is_swallowed_python_except(
        &self,
        start_idx: usize,
        lines: &[(usize, char, String)],
    ) -> bool {
        let limit = (start_idx + 20).min(lines.len());
        let mut has_statements = false;
        let mut has_documented = false;
        let mut only_pass_or_ellipsis = false;

        let (_, _, ref base_text) = lines[start_idx];
        let base_indent = base_text.len() - base_text.trim_start().len();

        for j in (start_idx + 1)..limit {
            let Some((raw, line)) = get_active_hunk_line(lines, j) else {
                continue;
            };

            let indent = raw.len() - raw.trim_start().len();
            if indent <= base_indent {
                break;
            }

            let (is_comment, is_doc) = check_comment_doc(line);
            if is_comment {
                if is_doc {
                    has_documented = true;
                }
                continue;
            }

            if line == "pass" || line == "..." {
                only_pass_or_ellipsis = true;
            } else {
                has_statements = true;
            }
        }

        only_pass_or_ellipsis && !has_statements && !has_documented
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

        if let Some(loc) = self.re_swallow_error.find(code) {
            if !is_comment_or_doc_line(code) && !is_inside_string_literal(code, loc.start()) {
                findings.push(Self::hardening_blocker(
                    file,
                    line_no,
                    "STS-H02",
                    "Hypothetical hardening: swallowing error without logging or structured recovery.",
                    "Handle errors explicitly or propagate them with actionable context.",
                ));
            }
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

fn compile_regex(pat: &str) -> Regex {
    match Regex::new(pat) {
        Ok(r) => r,
        Err(e) => panic!("invalid static regex pattern: {e}"),
    }
}

fn get_active_hunk_line(lines: &[(usize, char, String)], idx: usize) -> Option<(&str, &str)> {
    let (_, prefix, ref text) = lines[idx];
    if prefix == '-' {
        return None;
    }
    let trimmed = text.trim();
    if trimmed.is_empty() {
        return None;
    }
    Some((text.as_str(), trimmed))
}

fn check_comment_doc(line: &str) -> (bool, bool) {
    if is_comment_or_doc_line(line) {
        return (true, has_documented_reason(line));
    }
    (false, false)
}

fn is_comment_or_doc_line(line: &str) -> bool {
    let t = line.trim_start();
    t.starts_with("//")
        || t.starts_with("/*")
        || t.starts_with('*')
        || t.starts_with('#')
        || t.starts_with("\"\"\"")
        || t.starts_with("'''")
}

fn has_documented_reason(text: &str) -> bool {
    let lower = text.to_lowercase();
    let reasons = [
        "ignore",
        "intentional",
        "expected",
        "deliberate",
        "by design",
        "suppress",
        "safe to ignore",
        "noop",
        "no-op",
        "skip",
        "fallback",
    ];
    reasons.iter().any(|r| lower.contains(r))
}

fn is_inside_string_literal(line: &str, target_idx: usize) -> bool {
    let mut in_double = false;
    let mut in_single = false;
    let mut in_backtick = false;
    let mut escaped = false;

    for (i, c) in line.char_indices() {
        if i >= target_idx {
            break;
        }
        if escaped {
            escaped = false;
            continue;
        }
        if c == '\\' {
            escaped = true;
            continue;
        }
        match c {
            '"' if !in_single && !in_backtick => in_double = !in_double,
            '\'' if !in_double && !in_backtick => in_single = !in_single,
            '`' if !in_double && !in_single => in_backtick = !in_backtick,
            _ => {}
        }
    }
    in_double || in_single || in_backtick
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
        let diff =
            "diff --git a/a.rs b/a.rs\n--- a/a.rs\n+++ b/a.rs\n@@ -0,0 +1 @@\n+++not a header\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings.iter().any(|f| f.code == "STS-S01"));
    }
}
