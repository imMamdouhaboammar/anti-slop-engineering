use crate::model::{Finding, Severity, ViolationCategory};
use crate::path_utils::{
    is_doc_file, is_git_file_header, is_relative_git_path, is_test_file, scope_matches, DiffPaths,
};
use regex::Regex;

fn is_transfer(line: &str) -> bool {
    ["rename from ", "rename to ", "copy from ", "copy to "]
        .iter()
        .any(|prefix| line.starts_with(prefix))
}

fn is_metadata_change(line: &str) -> bool {
    line == "GIT binary patch"
        || [
            "old mode ",
            "new mode ",
            "deleted file mode ",
            "new file mode ",
            "Binary files ",
        ]
        .iter()
        .any(|prefix| line.starts_with(prefix))
}

#[derive(Default)]
struct MetadataChange {
    changed: bool,
    transfer: bool,
    line_checked: bool,
}

impl MetadataChange {
    fn record(
        &self,
        findings: &mut Vec<Finding>,
        paths: &DiffPaths,
        allowed: Option<&[&str]>,
        read_only: bool,
    ) {
        if (self.changed || self.transfer) && !self.line_checked {
            record_line_policy(findings, paths.target(), 1, allowed, read_only, true);
        }
        if self.transfer && paths.source() != paths.target() {
            findings.extend(check_scope_creep(paths.source(), 1, allowed, true));
        }
    }
}

fn record_line_policy(
    findings: &mut Vec<Finding>,
    file: &str,
    line: usize,
    allowed: Option<&[&str]>,
    read_only: bool,
    changed: bool,
) {
    findings.extend(check_scope_creep(file, line, allowed, changed));
    findings.extend(check_intent_violation(file, line, read_only, changed));
}

#[derive(Debug)]
pub struct ShitInterceptor {
    re_companion_hash: Regex,
    re_swallow_error: Regex,
    re_hypothetical_wrapper: Regex,
    re_py_except: Regex,
    re_catch_open: Regex,
    re_ignore_reason: Regex,
}

struct HunkLine {
    line_no: usize,
    kind: u8,
    text: String,
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
            re_py_except: Regex::new(r#"^(\s*)except\b[^:]*:\s*$"#).unwrap(),
            re_catch_open: Regex::new(r#"catch\s*\([^)]*\)\s*\{"#).unwrap(),
            re_ignore_reason: Regex::new(
                r#"(?i)\b(?:expected|intentional|deliberate|by design|safe to ignore|fallback|no-?op)\b"#,
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
        let mut paths = DiffPaths::default();
        let mut line_no = 0;
        let mut in_hunk = false;
        let mut metadata = MetadataChange::default();
        let mut hunk: Vec<HunkLine> = Vec::new();
        let mut hunk_file = String::new();

        for line in diff_text.lines() {
            if is_git_file_header(line) {
                self.flush_hunk(&mut findings, &hunk_file, &hunk);
                hunk = Vec::new();
                metadata.record(&mut findings, &paths, allowed_files, read_only_intent);
                paths.update(line);
                line_no = 0;
                in_hunk = false;
                metadata = MetadataChange::default();
                continue;
            }
            if !in_hunk {
                paths.update(line);
                metadata.changed |= is_metadata_change(line);
                metadata.transfer |= is_transfer(line);
            }
            if let Some(l) = extract_hunk_line(line) {
                self.flush_hunk(&mut findings, &hunk_file, &hunk);
                hunk = Vec::new();
                hunk_file = paths.target().to_string();
                line_no = l;
                in_hunk = true;
                continue;
            }
            if !in_hunk {
                continue;
            }
            let current_file = paths.target();
            let is_change = line.starts_with('+') || line.starts_with('-');
            metadata.line_checked |= is_change;
            record_line_policy(
                &mut findings,
                current_file,
                line_no,
                allowed_files,
                read_only_intent,
                is_change,
            );

            let is_addition = line.starts_with('+') && !line.starts_with("+++");
            let is_ignored = is_doc_file(current_file) || is_test_file(current_file);

            if is_addition && !is_ignored {
                let code_content = line[1..].trim();
                let mut line_findings = self.audit_added_code(current_file, line_no, code_content);
                findings.append(&mut line_findings);
            }

            if line.starts_with('+') || line.starts_with(' ') || line.starts_with('-') {
                hunk.push(HunkLine {
                    line_no,
                    kind: line.as_bytes()[0],
                    text: line[1..].to_string(),
                });
            }

            if line.starts_with('+') || line.starts_with(' ') {
                line_no += 1;
            }
        }

        self.flush_hunk(&mut findings, &hunk_file, &hunk);
        metadata.record(&mut findings, &paths, allowed_files, read_only_intent);

        findings
    }

    fn flush_hunk(&self, findings: &mut Vec<Finding>, file: &str, hunk: &[HunkLine]) {
        if hunk.is_empty() || file.is_empty() {
            return;
        }
        for finding in self.audit_hunk_multiline(file, hunk) {
            let duplicate = findings.iter().any(|existing| {
                existing.code == finding.code
                    && existing.file == finding.file
                    && existing.line == finding.line
            });
            if !duplicate {
                findings.push(finding);
            }
        }
    }

    /// Detect empty error handlers that a formatter split across lines,
    /// which the per-line swallow regex in audit_added_code cannot see.
    fn audit_hunk_multiline(&self, file: &str, hunk: &[HunkLine]) -> Vec<Finding> {
        if is_doc_file(file) || is_test_file(file) {
            return Vec::new();
        }
        let (code, comments) = hunk_code_views(file, hunk);
        if file.ends_with(".py") {
            return self.python_hunk_swallows(file, hunk, &code, &comments);
        }
        let mut findings = Vec::new();
        for (idx, hl) in hunk.iter().enumerate() {
            if hl.kind != b'+' {
                continue;
            }
            let Some(m) = self.re_catch_open.find(&code[idx]) else {
                continue;
            };
            let brace_char = code[idx][..m.end() - 1].chars().count();
            if brace_block_is_empty(hunk, &code, &comments, idx, brace_char, &self.re_ignore_reason)
            {
                findings.push(swallow_finding(file, hl.line_no));
            }
        }
        findings
    }

    fn python_hunk_swallows(
        &self,
        file: &str,
        hunk: &[HunkLine],
        code: &[String],
        comments: &[Vec<(usize, String)>],
    ) -> Vec<Finding> {
        let mut findings = Vec::new();
        for (idx, hl) in hunk.iter().enumerate() {
            if hl.kind == b'-' {
                continue;
            }
            let Some(caps) = self.re_py_except.captures(&code[idx]) else {
                continue;
            };
            if let Some(line) = self.python_suite_swallow(hunk, code, comments, idx, caps[1].len()) {
                findings.push(swallow_finding(file, line));
            }
        }
        findings
    }

    /// Returns the line to flag when the except suite after hunk index
    /// `idx` contains only no-op statements. A suite counts as closed
    /// only when a dedented line appears inside the hunk; a hunk that
    /// ends mid-suite stays unflagged because the suite may continue
    /// past the diff.
    fn python_suite_swallow(
        &self,
        hunk: &[HunkLine],
        code: &[String],
        comments: &[Vec<(usize, String)>],
        idx: usize,
        indent: usize,
    ) -> Option<usize> {
        let mut noop = false;
        let mut first_added_noop = None;
        let mut reason = has_ignore_reason(&comments[idx], &self.re_ignore_reason);
        for (j, hl) in hunk.iter().enumerate().skip(idx + 1) {
            if hl.kind == b'-' {
                continue;
            }
            let trimmed = code[j].trim();
            if trimmed.is_empty() {
                reason |= has_ignore_reason(&comments[j], &self.re_ignore_reason);
                continue;
            }
            if indent_width(&code[j]) <= indent {
                if noop && !reason {
                    return if hunk[idx].kind == b'+' {
                        Some(hunk[idx].line_no)
                    } else {
                        first_added_noop
                    };
                }
                return None;
            }
            reason |= has_ignore_reason(&comments[j], &self.re_ignore_reason);
            if trimmed == "pass" || trimmed == "..." {
                noop = true;
                if hl.kind == b'+' && first_added_noop.is_none() {
                    first_added_noop = Some(hl.line_no);
                }
            } else {
                return None;
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

        if self.re_swallow_error.is_match(code) {
            findings.push(swallow_finding(file, line_no));
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

pub(crate) fn swallow_finding(file: &str, line_no: usize) -> Finding {
    ShitInterceptor::hardening_blocker(
                file,
                line_no,
                "STS-H02",
                "Hypothetical hardening: swallowing error without logging or structured recovery.",
                "Handle errors explicitly or propagate them with actionable context.",
    )
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
        file: if file.is_empty() { "unknown" } else { file }.to_owned(),
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
        is_relative_git_path(file) && allowed.iter().any(|scope| scope_matches(file, scope));
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

fn indent_width(code_line: &str) -> usize {
    code_line
        .chars()
        .take_while(|c| *c == ' ' || *c == '\t')
        .count()
}

fn has_ignore_reason(comments: &[(usize, String)], re_ignore_reason: &Regex) -> bool {
    comments
        .iter()
        .any(|(_, text)| re_ignore_reason.is_match(text))
}

/// Reports whether the brace block opening at `brace_char` in
/// code[start] contains no code before its matching close brace and no
/// documented ignore reason in its comments.
fn brace_block_is_empty(
    hunk: &[HunkLine],
    code: &[String],
    comments: &[Vec<(usize, String)>],
    start: usize,
    brace_char: usize,
    re_ignore_reason: &Regex,
) -> bool {
    let mut depth = 0usize;
    let mut empty = true;
    for (i, hl) in hunk.iter().enumerate().skip(start) {
        if hl.kind == b'-' {
            continue;
        }
        let min_col = if i == start { brace_char } else { 0 };
        let mut max_col = usize::MAX;
        let mut closed = false;
        for (j, c) in code[i].chars().enumerate() {
            if i == start && j < brace_char {
                continue;
            }
            match c {
                '{' => depth += 1,
                '}' => {
                    depth -= 1;
                    if depth == 0 {
                        max_col = j;
                        closed = true;
                        break;
                    }
                }
                _ => {
                    if depth > 0 && !c.is_whitespace() {
                        empty = false;
                    }
                }
            }
        }
        if comments[i]
            .iter()
            .any(|(col, text)| *col >= min_col && *col < max_col && re_ignore_reason.is_match(text))
        {
            return false;
        }
        if closed {
            return empty;
        }
    }
    false
}

/// Builds per-line code views for a hunk: string and comment content is
/// blanked out, and the comment text of each line is returned alongside.
/// Multiline literals (Python triple quotes, JS template literals, C
/// block comments) are tracked across the hunk's context and added
/// lines so handler-shaped text inside them is never treated as code.
/// Deleted lines belong to the old file and contribute empty views.
fn hunk_code_views(file: &str, hunk: &[HunkLine]) -> (Vec<String>, Vec<Vec<(usize, String)>>) {
    let mut code = Vec::with_capacity(hunk.len());
    let mut comments = Vec::with_capacity(hunk.len());
    if file.ends_with(".py") {
        code_views_python(hunk, &mut code, &mut comments);
    } else {
        code_views_clike(file, hunk, &mut code, &mut comments);
    }
    (code, comments)
}

fn code_views_python(
    hunk: &[HunkLine],
    code: &mut Vec<String>,
    comments: &mut Vec<Vec<(usize, String)>>,
) {
    let mut triple: Option<[char; 3]> = None;
    for hl in hunk {
        if hl.kind == b'-' {
            code.push(String::new());
            comments.push(Vec::new());
            continue;
        }
        let chars: Vec<char> = hl.text.chars().collect();
        let mut out = String::new();
        let mut line_comments = Vec::new();
        let mut j = 0;
        while j < chars.len() {
            if let Some(t) = triple {
                if chars[j..].starts_with(&t) {
                    out.push_str("   ");
                    j += 3;
                    triple = None;
                } else {
                    out.push(' ');
                    j += 1;
                }
                continue;
            }
            if j + 2 < chars.len()
                && ((chars[j] == '"' && chars[j + 1] == '"' && chars[j + 2] == '"')
                    || (chars[j] == '\'' && chars[j + 1] == '\'' && chars[j + 2] == '\''))
            {
                triple = Some([chars[j]; 3]);
                out.push_str("   ");
                j += 3;
                continue;
            }
            match chars[j] {
                '#' => {
                    line_comments.push((out.chars().count(), chars[j..].iter().collect()));
                    break;
                }
                '"' | '\'' => {
                    let quote = chars[j];
                    j += 1;
                    while j < chars.len() {
                        if chars[j] == '\\' {
                            j += 2;
                            continue;
                        }
                        let done = chars[j] == quote;
                        j += 1;
                        if done {
                            break;
                        }
                    }
                    out.push(' ');
                }
                c => {
                    out.push(c);
                    j += 1;
                }
            }
        }
        code.push(out);
        comments.push(line_comments);
    }
}

fn code_views_clike(
    file: &str,
    hunk: &[HunkLine],
    code: &mut Vec<String>,
    comments: &mut Vec<Vec<(usize, String)>>,
) {
    let templates = [".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"]
        .iter()
        .any(|ext| file.ends_with(ext));
    let mut in_block_comment = false;
    let mut in_template = false;
    let mut template_expr_depth = 0usize;
    for hl in hunk {
        if hl.kind == b'-' {
            code.push(String::new());
            comments.push(Vec::new());
            continue;
        }
        let chars: Vec<char> = hl.text.chars().collect();
        let mut out = String::new();
        let mut line_comments = Vec::new();
        let mut block_buf = String::new();
        let mut block_col = 0usize;
        let mut j = 0;
        while j < chars.len() {
            if in_block_comment {
                if chars[j] == '*' && j + 1 < chars.len() && chars[j + 1] == '/' {
                    in_block_comment = false;
                    block_buf.push_str("*/");
                    line_comments.push((block_col, std::mem::take(&mut block_buf)));
                    out.push_str("  ");
                    j += 2;
                } else {
                    block_buf.push(chars[j]);
                    out.push(' ');
                    j += 1;
                }
                continue;
            }
            if in_template && template_expr_depth == 0 {
                match chars[j] {
                    '\\' => {
                        out.push_str("  ");
                        j += 2;
                    }
                    '`' => {
                        in_template = false;
                        out.push(' ');
                        j += 1;
                    }
                    '$' if j + 1 < chars.len() && chars[j + 1] == '{' => {
                        template_expr_depth = 1;
                        out.push_str("  ");
                        j += 2;
                    }
                    _ => {
                        out.push(' ');
                        j += 1;
                    }
                }
                continue;
            }
            match chars[j] {
                '/' if j + 1 < chars.len() && chars[j + 1] == '/' => {
                    line_comments.push((out.chars().count(), chars[j..].iter().collect()));
                    break;
                }
                '/' if j + 1 < chars.len() && chars[j + 1] == '*' => {
                    in_block_comment = true;
                    block_col = out.chars().count();
                    block_buf.push_str("/*");
                    out.push_str("  ");
                    j += 2;
                }
                '`' if templates => {
                    in_template = true;
                    out.push(' ');
                    j += 1;
                }
                '"' | '\'' => {
                    let quote = chars[j];
                    j += 1;
                    while j < chars.len() {
                        if chars[j] == '\\' {
                            j += 2;
                            continue;
                        }
                        let done = chars[j] == quote;
                        j += 1;
                        if done {
                            break;
                        }
                    }
                    out.push(' ');
                }
                c => {
                    if in_template {
                        if c == '{' {
                            template_expr_depth += 1;
                        } else if c == '}' {
                            template_expr_depth -= 1;
                        }
                    }
                    out.push(c);
                    j += 1;
                }
            }
        }
        if in_block_comment {
            line_comments.push((block_col, block_buf));
        }
        code.push(out);
        comments.push(line_comments);
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
    fn non_hunk_mode_change_triggers_intent_and_scope_checks() {
        let diff = "diff --git a/script.sh b/script.sh\nold mode 100644\nnew mode 100755\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "script.sh"));
    }

    #[test]
    fn non_hunk_rename_triggers_scope_check_on_old_and_new_files() {
        let diff = "diff --git a/src/old.rs b/outside/new.rs\nsimilarity index 100%\nrename from src/old.rs\nrename to outside/new.rs\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "outside/new.rs"));
    }

    #[test]
    fn non_hunk_binary_diff_triggers_scope_and_intent_checks() {
        let diff = "diff --git a/outside/image.png b/outside/image.png\nBinary files a/outside/image.png and b/outside/image.png differ\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings.iter().any(|f| f.code == "STS-I01"));
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "outside/image.png"));
    }

    #[test]
    fn metadata_path_errors_keep_the_policy_active() {
        let diff = "diff --git b/src/x.rs\nold mode 100644\nnew mode 100755\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        for code in ["STS-S01", "STS-I01"] {
            assert!(findings
                .iter()
                .any(|f| f.code == code && f.file == "unknown"));
        }
    }

    #[test]
    fn metadata_binary_patch_without_hunks_is_a_change() {
        let diff = "diff --git a/data.bin b/data.bin\nindex aabbcc..ddeeff 100644\nGIT binary patch\nliteral 1\nA\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        for code in ["STS-S01", "STS-I01"] {
            assert!(findings
                .iter()
                .any(|f| f.code == code && f.file == "data.bin"));
        }
    }

    #[test]
    fn metadata_rename_with_hunks_checks_both_paths_without_duplicate_intent() {
        let diff = "diff --git a/archive/old.rs b/src/new.rs\nsimilarity index 90%\nrename from archive/old.rs\nrename to src/new.rs\n--- a/archive/old.rs\n+++ b/src/new.rs\n@@ -1,2 +1 @@\n context\n-removed\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), true);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "archive/old.rs"));
        assert_eq!(findings.iter().filter(|f| f.code == "STS-I01").count(), 1);
    }

    #[test]
    fn metadata_bare_file_header_is_inert() {
        let diff = "diff --git a/data.bin b/data.bin\n";
        assert!(ShitInterceptor::new()
            .audit_diff(diff, Some(&["src/"]), true)
            .is_empty());
    }

    #[test]
    fn malformed_metadata_boundary_does_not_reuse_prior_path() {
        let diff = "diff --git a/src/first.rs b/src/first.rs\n@@ -0,0 +1 @@\n+first\ndiff --git\nold mode 100644\nnew mode 100755\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), false);
        assert_eq!(
            findings
                .iter()
                .filter(|f| f.code == "STS-S01" && f.file == "unknown")
                .count(),
            1
        );
    }

    #[test]
    fn quoted_paths_are_unquoted_and_audited() {
        let diff = "diff --git \"a/src/my file.rs\" \"b/src/my file.rs\"\n--- \"a/src/my file.rs\"\n+++ \"b/src/my file.rs\"\n@@ -1 +1,2 @@\n let a = 1;\n+let b = 2;\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["other/"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "src/my file.rs"));
    }

    #[test]
    fn quoted_escaped_octal_paths_are_unquoted_and_audited() {
        let diff = "diff --git \"a/src/\\303\\251.rs\" \"b/src/\\303\\251.rs\"\n--- \"a/src/\\303\\251.rs\"\n+++ \"b/src/\\303\\251.rs\"\n@@ -1 +1,2 @@\n let a = 1;\n+let b = 2;\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["other/"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "src/é.rs"));
    }

    #[test]
    fn unparseable_path_with_allowed_scope_flags_scope_creep() {
        let diff = "@@ -1 +1,2 @@\n+change\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "unknown"));
    }

    #[test]
    fn git_path_keeps_literal_filename_characters() {
        for (operand, file) in [
            (r#""src/has\"quote.rs""#, "src/has\"quote.rs"),
            (r#""src/has\tab.rs""#, "src/has\tab.rs"),
            (r#""space\\file.rs""#, r"space\file.rs"),
            ("space/file.rs  \t", "space/file.rs  "),
        ] {
            let target = if let Some(quoted) = operand.strip_prefix('"') {
                format!("\"b/{quoted}")
            } else {
                format!("b/{operand}")
            };
            let diff = format!("--- /dev/null\n+++ {target}\n@@ -0,0 +1 @@\n+line\n");
            let findings = ShitInterceptor::new().audit_diff(&diff, Some(&["other/"]), false);
            assert_eq!(findings[0].file, file);
        }
    }

    #[test]
    fn git_path_rejects_malformed_or_undecodable_targets() {
        for header in [
            "diff --git b/src/file.rs",
            "diff --git a/src/file.rs b/src/file.rs\n+++ invalid",
            r#"+++ "b/src/invalid\377.rs""#,
            r#"+++ "b/src/invalid\q.rs""#,
            r#"+++ "b/src/invalid\000.rs""#,
        ] {
            let diff = format!("{header}\n@@ -0,0 +1 @@\n+line\n");
            let findings = ShitInterceptor::new().audit_diff(&diff, Some(&["src/"]), false);
            assert!(
                findings
                    .iter()
                    .any(|f| f.code == "STS-S01" && f.file == "unknown"),
                "{header}"
            );
        }
    }

    #[test]
    fn git_path_deletion_uses_the_complete_source() {
        let diff = "diff --git a/archive b/src/file.rs b/archive b/src/file.rs\n--- a/archive b/src/file.rs\t\n+++ /dev/null\n@@ -1 +0,0 @@\n-line\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "archive b/src/file.rs"));
    }

    #[test]
    fn git_path_rename_metadata_keeps_real_prefix() {
        let diff = "diff --git a/a/old.rs b/b/new.rs\nrename from a/old.rs\nrename to b/new.rs\n@@ -0,0 +1 @@\n+line\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["other/"]), false);
        assert!(findings
            .iter()
            .any(|f| f.code == "STS-S01" && f.file == "b/new.rs"));
    }

    #[test]
    fn malformed_file_boundary_does_not_reuse_prior_path() {
        let diff = "diff --git a/src/first.rs b/src/first.rs\n@@ -0,0 +1 @@\n+first\ndiff --git\n@@ -0,0 +1 @@\n+second\n";
        let findings = ShitInterceptor::new().audit_diff(diff, Some(&["src/"]), false);
        assert_eq!(
            findings
                .iter()
                .filter(|f| f.code == "STS-S01" && f.file == "unknown")
                .count(),
            1
        );
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
