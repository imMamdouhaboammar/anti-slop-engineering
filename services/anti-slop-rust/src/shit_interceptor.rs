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

        let process_file_hunks = |file: &str, lines: &[(usize, char, String)]| -> Vec<Finding> {
            if file.is_empty() || is_doc_file(file) || is_test_file(file) {
                return Vec::new();
            }
            let mut lexical = HunkLexicalContext::default();
            let code: Vec<_> = lines
                .iter()
                .map(|(_, prefix, raw)| {
                    if *prefix == '-' {
                        ""
                    } else {
                        lexical.source_before_comment(raw, file)
                    }
                })
                .collect();
            let mut findings = Vec::new();
            for (i, &(line, prefix, ref raw)) in lines.iter().enumerate() {
                if prefix == '-' {
                    continue;
                }
                let added = prefix == '+';
                if added {
                    findings.extend(self.audit_added_code(file, line, raw.trim()));
                }
                let single_line = added
                    && !has_ignore_reason(raw, code[i])
                    && self
                        .re_swallow_error
                        .find(code[i].trim())
                        .is_some_and(|matched| {
                            !is_inside_string_literal(code[i].trim(), matched.start())
                        });
                let end = self.empty_handler_end(i, lines, &code);
                let changed_handler = end
                    .is_some_and(|end| lines[i..=end].iter().any(|(_, prefix, _)| *prefix != ' '));
                if single_line || changed_handler {
                    findings.push(Self::hardening_blocker(
                        file,
                        line,
                        "STS-H02",
                        "Hypothetical hardening: swallowing error without logging or structured recovery.",
                        "Handle errors explicitly or propagate them with actionable context.",
                    ));
                }
            }
            findings
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

            let is_hunk_content = line.starts_with(['+', '-', ' ']);

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

    fn empty_handler_end(
        &self,
        start: usize,
        lines: &[(usize, char, String)],
        code: &[&str],
    ) -> Option<usize> {
        let header = code[start].trim();
        if self.re_go_if_err_nil.is_match(header) || self.re_catch_block.is_match(header) {
            return Self::empty_brace_block_end(start, lines, code);
        }
        self.re_py_except
            .is_match(header)
            .then(|| Self::empty_python_suite_end(start, lines, code))
            .flatten()
    }

    fn empty_brace_block_end(
        start: usize,
        lines: &[(usize, char, String)],
        code: &[&str],
    ) -> Option<usize> {
        let mut opened = false;
        for i in start..(start + 25).min(lines.len()) {
            let (_, prefix, ref raw) = lines[i];
            if prefix == '-' || (i > start && code[i].trim().is_empty() && !opened) {
                continue;
            }
            let body = code[i].trim();
            if has_ignore_reason(raw, code[i]) {
                return None;
            }
            if !opened {
                if i > start && !body.starts_with('{') {
                    return None;
                }
                let Some((_, after_open)) = body.rsplit_once('{') else {
                    continue;
                };
                opened = true;
                if after_open.trim_start().starts_with('}') {
                    return Some(i);
                }
                if !after_open.trim().is_empty() {
                    return None;
                }
            } else if body.starts_with('}') {
                return Some(i);
            } else if !body.is_empty() {
                return None;
            }
        }
        None
    }

    fn empty_python_suite_end(
        start: usize,
        lines: &[(usize, char, String)],
        code: &[&str],
    ) -> Option<usize> {
        let initial_indent = code[start].len() - code[start].trim_start().len();
        let mut found_noop = false;
        let mut end = start;
        for i in (start + 1)..(start + 20).min(lines.len()) {
            let (_, prefix, ref raw) = lines[i];
            let indent = raw.len() - raw.trim_start().len();
            if prefix == '-' {
                if indent > initial_indent && !raw.trim().is_empty() {
                    end = i;
                }
                continue;
            }

            let body = code[i].trim();
            if indent <= initial_indent && !body.is_empty() {
                return found_noop.then_some(end);
            }
            if indent > initial_indent && has_ignore_reason(raw, code[i]) {
                return None;
            }
            match body {
                "pass" | "..." => {
                    found_noop = true;
                    end = i;
                }
                "" => (),
                _ => return None,
            }
        }
        None
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

#[derive(Clone, Copy)]
enum LexicalSpan {
    BlockComment,
    String(&'static str),
    Template,
}

impl LexicalSpan {
    fn end_in(self, text: &str) -> Option<(usize, bool)> {
        match self {
            Self::BlockComment => text.find("*/").map(|offset| (offset + 2, false)),
            Self::String("\x60") => text.find('\x60').map(|offset| (offset + 1, false)),
            Self::String(delimiter) => unescaped_boundary(text, delimiter, false),
            Self::Template => unescaped_boundary(text, "\x60", true),
        }
    }
}

fn unescaped_boundary(text: &str, delimiter: &str, template: bool) -> Option<(usize, bool)> {
    let mut chars = text.char_indices();
    while let Some((offset, c)) = chars.next() {
        if c == '\\' {
            chars.next();
            continue;
        }
        if text[offset..].starts_with(delimiter) {
            return Some((offset + delimiter.len(), false));
        }
        if template && text[offset..].starts_with("\x24{") {
            return Some((offset + 2, true));
        }
    }
    None
}

#[derive(Default)]
struct HunkLexicalContext {
    span: Option<LexicalSpan>,
    template_interpolation_seen: bool,
}

impl HunkLexicalContext {
    fn source_before_comment<'a>(&mut self, line: &'a str, file: &str) -> &'a str {
        let mut pos = 0;
        let mut output_start = 0;
        if let Some(active) = self.span {
            let Some((end, interpolation)) = active.end_in(line) else {
                return "";
            };
            pos = end;
            output_start = pos;
            self.span = None;
            self.template_interpolation_seen |= interpolation;
        }

        let python = file.ends_with(".py");
        let go = file.ends_with(".go");
        let javascript = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"]
            .iter()
            .any(|extension| file.ends_with(extension));
        let mut short_quote = None;
        let mut chars = line[pos..].char_indices();
        while let Some((i, c)) = chars.next() {
            if let Some(quote) = short_quote {
                if c == '\\' {
                    chars.next();
                } else if c == quote {
                    short_quote = None;
                }
                continue;
            }

            let remaining = &line[pos + i..];
            if (python && c == '#') || (!python && remaining.starts_with("//")) {
                return &line[output_start..pos + i];
            }

            let (active, open) = if python && remaining.starts_with("\"\"\"") {
                (LexicalSpan::String("\"\"\""), 3)
            } else if python && remaining.starts_with("'''") {
                (LexicalSpan::String("'''"), 3)
            } else if go && c == '\x60' {
                (LexicalSpan::String("\x60"), 1)
            } else if javascript && !self.template_interpolation_seen && c == '\x60' {
                (LexicalSpan::Template, 1)
            } else if !python && remaining.starts_with("/*") {
                (LexicalSpan::BlockComment, 2)
            } else {
                if matches!(c, '"' | '\'' | '\x60') {
                    short_quote = Some(c);
                }
                continue;
            };
            if let Some((end, interpolation)) = active.end_in(&remaining[open..]) {
                // Interpolation admits code, nested literals, and unmatched braces
                // outside the hunk. Keep the existing line-level fallback there.
                self.template_interpolation_seen |= interpolation;
                let after = i + open + end;
                if matches!(active, LexicalSpan::BlockComment) {
                    if line[output_start..pos + i].trim().is_empty() {
                        output_start = pos + after;
                    } else if line[pos + after..].trim().is_empty() {
                        return &line[output_start..pos + i];
                    }
                }
                while chars.clone().next().is_some_and(|(next, _)| next < after) {
                    chars.next();
                }
            } else {
                self.span = Some(active);
                return match active {
                    LexicalSpan::BlockComment => &line[output_start..pos + i],
                    LexicalSpan::String(_) | LexicalSpan::Template => &line[output_start..],
                };
            }
        }
        &line[output_start..]
    }
}

fn has_ignore_reason(raw: &str, code: &str) -> bool {
    if !raw.starts_with(code) {
        return false;
    }
    let comment = raw[code.len()..].trim_start();
    ["//", "/*", "#"]
        .iter()
        .any(|marker| comment.starts_with(marker))
        && has_documented_reason(comment)
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
