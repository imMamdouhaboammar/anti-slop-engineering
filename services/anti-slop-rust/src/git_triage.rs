use crate::model::AuditReport;
use crate::path_utils::{is_doc_file, is_git_file_header, is_test_file, DiffPaths};
use crate::shit_interceptor::swallow_finding;
use oxc::allocator::Allocator;
use oxc::ast::ast::{CatchClause, Comment};
use oxc::ast_visit::{walk, Visit};
use oxc::parser::Parser;
use oxc::span::SourceType;
use std::collections::{BTreeMap, BTreeSet};
use std::io::{self, Read, Write};
use std::process::{Command, Stdio};

const MAX_FILE_BYTES: usize = 2 * 1024 * 1024;
const MAX_SOURCE_BYTES: usize = 32 * 1024 * 1024;
const MAX_SOURCE_FILES: usize = 1024;

pub fn triage_git(base: &str, read_only: bool) -> io::Result<AuditReport> {
    let revision = Command::new("git")
        .args(["rev-parse", "--verify", "--end-of-options", base])
        .output()?;
    let base_oid = String::from_utf8_lossy(&revision.stdout);
    if !revision.status.success() || !object_id(base_oid.trim()) {
        return Err(io::Error::other(format!(
            "Git base could not be resolved: {base}"
        )));
    }

    let output = Command::new("git")
        .args([
            "-c",
            "diff.suppressBlankEmpty=false",
            "diff",
            "--full-index",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            "--no-relative",
            "--src-prefix=a/",
            "--dst-prefix=b/",
            "--output-indicator-new=+",
            "--output-indicator-old=-",
            "--output-indicator-context= ",
            base_oid.trim(),
            "--",
        ])
        .output()?;
    if !output.status.success() {
        return Err(io::Error::other(format!(
            "git diff {base} failed: {}",
            String::from_utf8_lossy(&output.stderr)
        )));
    }

    let diff = String::from_utf8_lossy(&output.stdout);
    let mut report = crate::triage_diff(&diff, None, read_only);
    let parsed = parse_changed_sources(&diff);
    report
        .findings
        .retain(|finding| finding.code != "STS-H02" || !parsed.contains_key(&finding.file));
    report
        .findings
        .extend(parsed.into_iter().flat_map(|(path, lines)| {
            lines
                .into_iter()
                .map(move |line| swallow_finding(&path, line))
        }));
    Ok(AuditReport::new(&report.engine, report.findings))
}

fn parse_changed_sources(diff: &str) -> BTreeMap<String, BTreeSet<usize>> {
    let mut file = Vec::new();
    let mut results = BTreeMap::new();
    let mut budget = SourceBudget {
        bytes: MAX_SOURCE_BYTES,
        files: MAX_SOURCE_FILES,
    };
    for line in diff
        .split_inclusive('\n')
        .chain(std::iter::once("diff --git"))
    {
        if is_git_file_header(line) {
            if budget.files == 0 || budget.bytes == 0 {
                break;
            }
            if let Some((path, lines)) = parse_changed_source(&file, &mut budget) {
                results.insert(path, lines);
            }
            file.clear();
        }
        file.push(line);
    }
    results
}

struct SourceBudget {
    bytes: usize,
    files: usize,
}

fn parse_changed_source(
    file: &[&str],
    budget: &mut SourceBudget,
) -> Option<(String, BTreeSet<usize>)> {
    let first_hunk = file.iter().position(|line| line.starts_with("@@ "))?;
    let (headers, patch) = file.split_at(first_hunk);
    let mut paths = DiffPaths::default();
    let mut index = None;
    let mut mode = None;
    for header in headers.iter().map(|line| line.trim_end_matches('\n')) {
        paths.update(header);
        if let Some(value) = header.strip_prefix("index ") {
            let mut fields = value.split_ascii_whitespace();
            index = fields.next()?.split_once("..");
            mode = fields.next().or(mode);
        } else if let Some(value) = header
            .strip_prefix("new mode ")
            .or_else(|| header.strip_prefix("new file mode "))
        {
            mode = Some(value);
        }
    }
    let path = paths.target();
    let source_type = SourceType::from_path(path).ok()?;
    if is_doc_file(path) || is_test_file(path) || !matches!(mode, Some("100644" | "100755")) {
        return None;
    }
    let (old, new) = index?;
    if !object_id(old) || !object_id(new) || new.bytes().all(|byte| byte == b'0') {
        return None;
    }

    budget.files -= 1;
    let old_text = read_old_blob(old, budget)?;
    let source = apply_hunks(&old_text, patch, budget.bytes.min(MAX_FILE_BYTES))?;
    budget.bytes -= source.text.len();
    if !matches_post_image(&source.text, new)? {
        return None;
    }
    let lines = changed_empty_catches(&source, source_type)?;
    Some((path.to_owned(), lines))
}

fn object_id(text: &str) -> bool {
    matches!(text.len(), 40 | 64) && text.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn read_old_blob(oid: &str, budget: &mut SourceBudget) -> Option<String> {
    if oid.bytes().all(|byte| byte == b'0') {
        return Some(String::new());
    }
    let mut child = Command::new("git")
        .args(["cat-file", "blob", oid])
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .ok()?;
    let limit = budget.bytes.min(MAX_FILE_BYTES);
    let mut data = Vec::new();
    let result = child
        .stdout
        .take()?
        .take((limit + 1) as u64)
        .read_to_end(&mut data);
    budget.bytes = budget.bytes.saturating_sub(data.len());
    if result.is_err() || data.len() > limit {
        let _ = child.kill();
    }
    if !child.wait().ok()?.success() || result.is_err() || data.len() > limit {
        return None;
    }
    String::from_utf8(data).ok()
}

fn matches_post_image(text: &str, expected: &str) -> Option<bool> {
    let mut child = Command::new("git")
        .args(["hash-object", "--stdin"])
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::null())
        .spawn()
        .ok()?;
    let result = child.stdin.take()?.write_all(text.as_bytes());
    let output = child.wait_with_output().ok()?;
    Some(
        result.is_ok()
            && output.status.success()
            && String::from_utf8_lossy(&output.stdout).trim_end() == expected,
    )
}

struct PostImage {
    text: String,
    additions: Vec<usize>,
    deletions: Vec<usize>,
}

fn apply_hunks(old: &str, patch: &[&str], max_bytes: usize) -> Option<PostImage> {
    let mut remaining = old.split_inclusive('\n');
    let mut old_offset = 0;
    let mut new_offset = 0usize;
    let mut source = PostImage {
        text: String::new(),
        additions: Vec::new(),
        deletions: Vec::new(),
    };
    let mut lines = patch.iter().copied().peekable();
    while let Some(header) = lines.next() {
        let (start, count) = hunk_range(header, '-')?;
        let (new_start, new_count) = hunk_range(header, '+')?;
        let gap = start.checked_sub(old_offset)?;
        for _ in 0..gap {
            append(&mut source.text, remaining.next()?, max_bytes)?;
        }
        if new_offset.checked_add(gap)? != new_start {
            return None;
        }
        let counts = apply_hunk(
            &mut source,
            &mut remaining,
            &mut lines,
            new_start,
            max_bytes,
        )?;
        if counts != (count, new_count) {
            return None;
        }
        old_offset = start.checked_add(count)?;
        new_offset = new_start.checked_add(new_count)?;
    }
    for line in remaining {
        append(&mut source.text, line, max_bytes)?;
    }
    Some(source)
}

fn apply_hunk<'a>(
    source: &mut PostImage,
    remaining: &mut impl Iterator<Item = &'a str>,
    lines: &mut std::iter::Peekable<impl Iterator<Item = &'a str>>,
    mut new_offset: usize,
    max_bytes: usize,
) -> Option<(usize, usize)> {
    let start = new_offset;
    let mut old_count = 0;
    while let Some(line) = lines.next_if(|line| !line.starts_with("@@ ")) {
        let (&kind, content) = line.as_bytes().split_first()?;
        let content = without_no_newline_marker(std::str::from_utf8(content).ok()?, lines);
        if kind == b'-' || kind == b' ' {
            if remaining.next()? != content {
                return None;
            }
            old_count += 1;
        }
        match kind {
            b'-' => {
                if source.deletions.last() != Some(&new_offset) {
                    source.deletions.push(new_offset);
                }
            }
            b'+' | b' ' => {
                append(&mut source.text, content, max_bytes)?;
                new_offset += 1;
                if kind == b'+' {
                    source.additions.push(new_offset);
                }
            }
            _ => return None,
        }
    }
    Some((old_count, new_offset - start))
}

fn without_no_newline_marker<'a>(
    line: &'a str,
    lines: &mut std::iter::Peekable<impl Iterator<Item = &'a str>>,
) -> &'a str {
    if lines.next_if(|line| line.starts_with("\\ ")).is_some() {
        line.strip_suffix('\n').unwrap_or(line)
    } else {
        line
    }
}

fn append(out: &mut String, text: &str, max_bytes: usize) -> Option<()> {
    if out.len() + text.len() > max_bytes {
        return None;
    }
    out.push_str(text);
    Some(())
}

fn hunk_range(header: &str, side: char) -> Option<(usize, usize)> {
    let header = header.strip_prefix("@@ ")?;
    let mut ranges = header.split_ascii_whitespace();
    let range = if side == '+' {
        ranges.nth(1)?
    } else {
        ranges.next()?
    };
    let range = range.strip_prefix(side)?;
    let (start, count) = range.split_once(',').unwrap_or((range, "1"));
    let count: usize = count.parse().ok()?;
    let start: usize = start.parse().ok()?;
    let offset = if count == 0 {
        start
    } else {
        start.checked_sub(1)?
    };
    Some((offset, count))
}

fn changed_empty_catches(source: &PostImage, source_type: SourceType) -> Option<BTreeSet<usize>> {
    let allocator = Allocator::default();
    let parsed = Parser::new(&allocator, &source.text, source_type).parse();
    if !parsed.diagnostics.is_empty() {
        return None;
    }
    let mut visitor = EmptyCatchVisitor {
        source,
        comments: &parsed.program.comments,
        line_breaks: source
            .text
            .match_indices('\n')
            .map(|(offset, _)| offset)
            .collect(),
        findings: BTreeSet::new(),
    };
    visitor.visit_program(&parsed.program);
    Some(visitor.findings)
}

struct EmptyCatchVisitor<'a> {
    source: &'a PostImage,
    comments: &'a [Comment],
    line_breaks: Vec<usize>,
    findings: BTreeSet<usize>,
}

impl EmptyCatchVisitor<'_> {
    fn line(&self, offset: u32) -> usize {
        self.line_breaks
            .partition_point(|&newline| newline < offset as usize)
            + 1
    }

    fn overlaps_change(&self, first: usize, last: usize) -> bool {
        let candidate = self.source.additions.partition_point(|&line| line < first);
        let addition = self
            .source
            .additions
            .get(candidate)
            .is_some_and(|&line| line <= last);
        let candidate = self
            .source
            .deletions
            .partition_point(|&anchor| anchor < first);
        let deletion = self
            .source
            .deletions
            .get(candidate)
            .is_some_and(|&anchor| anchor < last);
        addition || deletion
    }

    fn contains_comment(&self, catch: &CatchClause<'_>) -> bool {
        let first = self
            .comments
            .partition_point(|comment| comment.span.start < catch.body.span.start);
        self.comments
            .get(first)
            .is_some_and(|comment| comment.span.end < catch.body.span.end)
    }
}

impl<'a> Visit<'a> for EmptyCatchVisitor<'_> {
    fn visit_catch_clause(&mut self, catch: &CatchClause<'a>) {
        let first = self.line(catch.span.start);
        let last = self.line(catch.span.end.saturating_sub(1));
        if catch.body.body.is_empty()
            && self.overlaps_change(first, last)
            && !self.contains_comment(catch)
        {
            self.findings.insert(first);
        }
        walk::walk_catch_clause(self, catch);
    }
}
