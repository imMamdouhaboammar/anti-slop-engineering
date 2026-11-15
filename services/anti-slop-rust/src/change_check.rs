use anti_slop_rust::model::{AuditReport, Finding, Severity, ViolationCategory};
use serde::Deserialize;
use std::io::{self, Read};

#[derive(Deserialize)]
#[serde(rename_all = "lowercase")]
enum Snapshot {
    Worktree,
    Index,
    Commit,
}

#[derive(Deserialize)]
struct ChangeSet {
    version: u32,
    snapshot: Snapshot,
    base: String,
    target: Option<String>,
    files: Vec<FileChange>,
    untracked: Vec<GitPath>,
}

#[derive(Deserialize)]
struct FileChange {
    status: char,
    old_path: Option<GitPath>,
    new_path: Option<GitPath>,
    old_mode: Option<String>,
    new_mode: Option<String>,
    score: Option<u8>,
    added: Option<usize>,
    deleted: Option<usize>,
    binary: bool,
    hunks: Vec<Hunk>,
}

#[derive(Deserialize)]
struct Hunk {
    old_start: usize,
    old_count: usize,
    new_start: usize,
    new_count: usize,
}

#[derive(Deserialize, PartialEq)]
struct GitPath {
    text: Option<String>,
    raw_hex: Option<String>,
}

impl GitPath {
    fn validate(&self) -> io::Result<()> {
        let encoded = self.text.is_none()
            && self.raw_hex.as_deref().is_some_and(|raw| {
                !raw.is_empty() && raw.len() % 2 == 0 && raw.bytes().all(|b| b.is_ascii_hexdigit())
            });
        if encoded
            || (self.raw_hex.is_none() && self.text.as_deref().is_some_and(is_relative_git_path))
        {
            return Ok(());
        }
        Err(invalid("Invalid repository-relative change-set path"))
    }

    fn label(&self) -> &str {
        self.text.as_deref().unwrap_or("unknown")
    }
}

impl ChangeSet {
    fn validate(&self) -> io::Result<()> {
        if self.version != 1 {
            return Err(invalid(format!(
                "Unsupported change-set version {}",
                self.version
            )));
        }
        if !is_commit_oid(&self.base) {
            return Err(invalid("Invalid change-set base commit OID"));
        }
        if matches!(self.snapshot, Snapshot::Commit) != self.target.is_some()
            || self
                .target
                .as_deref()
                .is_some_and(|target| !is_commit_oid(target))
        {
            return Err(invalid("Invalid change-set target commit OID"));
        }
        if !matches!(self.snapshot, Snapshot::Worktree) && !self.untracked.is_empty() {
            return Err(invalid("Untracked paths require a worktree change set"));
        }
        for file in &self.files {
            file.validate()?;
        }
        self.untracked.iter().try_for_each(GitPath::validate)
    }
}

impl FileChange {
    fn validate(&self) -> io::Result<()> {
        let correct_paths = match self.status {
            'A' => self.old_path.is_none() && self.new_path.is_some(),
            'D' => self.old_path.is_some() && self.new_path.is_none(),
            'C' | 'R' => {
                self.old_path.is_some() && self.new_path.is_some() && self.old_path != self.new_path
            }
            'M' | 'T' | 'U' | 'X' | 'B' => {
                self.old_path.is_some() && self.old_path == self.new_path
            }
            _ => false,
        };
        if !correct_paths {
            return Err(invalid("Change-set operation has invalid old/new paths"));
        }
        if self.score.is_some_and(|score| score > 100)
            || [&self.old_mode, &self.new_mode]
                .into_iter()
                .flatten()
                .any(|mode| {
                    mode.len() != 6 || !mode.bytes().all(|byte| (b'0'..=b'7').contains(&byte))
                })
        {
            return Err(invalid("Invalid change-set Git mode or score"));
        }
        for path in [&self.old_path, &self.new_path].into_iter().flatten() {
            path.validate()?;
        }
        if self.binary && (self.added.is_some() || self.deleted.is_some() || !self.hunks.is_empty())
            || !self.binary && (self.added.is_none() || self.deleted.is_none())
        {
            return Err(invalid("Invalid change-set file counts"));
        }
        for hunk in &self.hunks {
            validate_range(hunk.old_start, hunk.old_count)?;
            validate_range(hunk.new_start, hunk.new_count)?;
        }
        Ok(())
    }

    fn path(&self) -> &GitPath {
        self.new_path
            .as_ref()
            .or(self.old_path.as_ref())
            .expect("validated file change has a path")
    }
}

fn validate_range(start: usize, count: usize) -> io::Result<()> {
    if (start == 0 && count > 0) || start.checked_add(count).is_none() {
        return Err(invalid("Invalid change-set hunk range"));
    }
    Ok(())
}

fn is_commit_oid(oid: &str) -> bool {
    matches!(oid.len(), 40 | 64) && oid.bytes().all(|byte| byte.is_ascii_hexdigit())
}

fn is_relative_git_path(path: &str) -> bool {
    let driven = path.as_bytes().get(1) == Some(&b':') && path.as_bytes()[0].is_ascii_alphabetic();
    !driven && !path.contains('\0') && path.split('/').all(|part| !matches!(part, "" | "." | ".."))
}

fn scope_matches(path: &str, scope: &str) -> bool {
    let prefix = scope.strip_suffix('/').unwrap_or(scope);
    is_relative_git_path(prefix)
        && ((path == prefix && !scope.ends_with('/'))
            || path
                .strip_prefix(prefix)
                .is_some_and(|rest| rest.starts_with('/')))
}

pub(crate) fn audit(
    source: impl Read,
    allowed: Option<&[&str]>,
    read_only: bool,
    include_untracked: bool,
) -> io::Result<AuditReport> {
    let changes: ChangeSet =
        serde_json::from_reader(source).map_err(|err| invalid(err.to_string()))?;
    changes.validate()?;
    let mut findings = Vec::new();
    for file in &changes.files {
        let path = file.path();
        findings.extend(intent_finding(path, read_only));
        findings.extend(scope_finding(path, allowed));
        if let Some(old) = &file.old_path {
            if old != path {
                findings.extend(scope_finding(old, allowed));
            }
        }
    }
    if include_untracked {
        for path in &changes.untracked {
            findings.extend(intent_finding(path, read_only));
            findings.extend(scope_finding(path, allowed));
        }
    }
    Ok(AuditReport::new("anti-slop-rust-changeset", findings))
}

fn intent_finding(path: &GitPath, read_only: bool) -> Option<Finding> {
    read_only.then(|| Finding {
        file: path.label().to_owned(),
        line: 1,
        category: ViolationCategory::IntentViolation,
        severity: Severity::Blocker,
        code: "STS-I01".to_owned(),
        message: "Intent violation: change recorded while in read-only / review mode.".to_owned(),
        suggestion: "Do not write or modify files during an audit or review turn.".to_owned(),
    })
}

fn scope_finding(path: &GitPath, allowed: Option<&[&str]>) -> Option<Finding> {
    let scope = allowed.filter(|allowed| !allowed.is_empty())?;
    if path
        .text
        .as_deref()
        .is_some_and(|text| scope.iter().any(|entry| scope_matches(text, entry)))
    {
        return None;
    }
    let message = if path.text.is_some() {
        format!(
            "Scope creep: file '{}' changed outside allowed scope.",
            path.label()
        )
    } else {
        "Scope creep: non-UTF-8 change-set path cannot be checked within allowed scope.".to_owned()
    };
    Some(Finding {
        file: path.label().to_owned(),
        line: 1,
        category: ViolationCategory::ScopeCreep,
        severity: Severity::Blocker,
        code: "STS-S01".to_owned(),
        message,
        suggestion: "Restrict edits to repository-relative files within the allowed scope."
            .to_owned(),
    })
}

fn invalid(message: impl Into<String>) -> io::Error {
    io::Error::new(io::ErrorKind::InvalidData, message.into())
}
