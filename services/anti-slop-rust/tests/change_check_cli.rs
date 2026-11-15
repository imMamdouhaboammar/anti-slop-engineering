use anti_slop_rust::model::AuditReport;
use std::io::Write;
use std::process::{Command, Output, Stdio};

fn check(input: &str, args: &[&str]) -> Output {
    let mut cmd = Command::new(env!("CARGO_BIN_EXE_anti-slop-rust"));
    cmd.args(["change-check", "--format", "json"])
        .args(args)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());
    let mut child = cmd.spawn().expect("start Rust change check");
    child
        .stdin
        .take()
        .unwrap()
        .write_all(input.as_bytes())
        .unwrap();
    child.wait_with_output().expect("collect Rust change check")
}

fn report(out: &Output, code: i32) -> AuditReport {
    assert_eq!(
        out.status.code(),
        Some(code),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    serde_json::from_slice(&out.stdout).expect("parse Rust report")
}

fn collect_fixture() -> String {
    let producer = std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../../scripts");
    let script = r#"
import json
from pathlib import Path
import subprocess
import sys
import tempfile
sys.path.insert(0, sys.argv[1])
from git_changeset import collect_changes

with tempfile.TemporaryDirectory() as temp:
    root = Path(temp)
    def git(*args):
        subprocess.run(["git", "-C", temp, *args], check=True, stdout=subprocess.DEVNULL)
    git("init", "-q")
    git("config", "user.name", "Change Fixture")
    git("config", "user.email", "fixture@example.invalid")
    for name in ("src", "assets"):
        (root / name).mkdir()
    source = root / "old name.txt"
    source.write_text("stable rename content\n", encoding="utf-8")
    binary = root / "assets" / "data.bin"
    binary.write_bytes(b"\x00one")
    (root / "src" / "script.sh").write_text("exit 0\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")
    git("mv", "old name.txt", "src/renamed name.txt")
    git("update-index", "--chmod=+x", "src/script.sh")
    binary.write_bytes(b"\x00two")
    git("add", "assets/data.bin")
    (root / "untracked.txt").write_text("local only\n", encoding="utf-8")
    print(json.dumps(collect_changes(root, "HEAD", "index")))
"#;
    let out = Command::new("python3")
        .arg("-c")
        .arg(script)
        .arg(producer)
        .output()
        .unwrap();
    assert!(
        out.status.success(),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
    String::from_utf8(out.stdout).unwrap()
}

#[test]
fn python_v1_index_records_reach_the_rust_check() {
    let source = collect_fixture();
    let out = check(&source, &["--read-only", "--allowed", "src/"]);
    let findings = report(&out, 1).findings;
    let paths = |code| {
        let mut paths: Vec<_> = findings
            .iter()
            .filter(|f| f.code == code)
            .map(|f| f.file.as_str())
            .collect();
        paths.sort_unstable();
        paths
    };
    assert_eq!(
        paths("STS-I01"),
        ["assets/data.bin", "src/renamed name.txt", "src/script.sh"]
    );
    assert_eq!(paths("STS-S01"), ["assets/data.bin", "old name.txt"]);
    assert!(findings.iter().all(|f| f.line == 1));
}

#[test]
fn unknown_versions_and_invalid_envelopes_fail_before_report() {
    for (input, error) in [
        (
            r#"{"version":2,"snapshot":"index","base":"1111111111111111111111111111111111111111","target":null,"files":[],"untracked":[]}"#,
            "version",
        ),
        (
            r#"{"version":1,"snapshot":"commit","base":"1111111111111111111111111111111111111111","target":null,"files":[],"untracked":[]}"#,
            "target",
        ),
        (
            r#"{"version":1,"snapshot":"index","base":"1111111111111111111111111111111111111111","target":null,"files":[{"status":"A","old_path":{"text":"a","raw_hex":null},"new_path":null,"added":0,"deleted":0,"binary":false,"hunks":[]}],"untracked":[]}"#,
            "path",
        ),
    ] {
        let out = check(input, &["--read-only"]);
        assert!(!out.status.success());
        assert!(out.stdout.is_empty());
        assert!(
            String::from_utf8_lossy(&out.stderr).contains(error),
            "{}",
            String::from_utf8_lossy(&out.stderr)
        );
    }
}

#[test]
fn unsupported_path_bytes_are_explicit_and_untracked_requires_opt_in() {
    let input = r#"{"version":1,"snapshot":"worktree","base":"1111111111111111111111111111111111111111","target":null,"files":[{"status":"A","new_path":{"text":null,"raw_hex":"ff"},"old_path":null,"old_mode":null,"new_mode":"100644","score":null,"added":0,"deleted":0,"binary":false,"hunks":[]}],"untracked":[{"text":"untracked.txt","raw_hex":null}]}"#;
    let direct = check(input, &["--allowed", "src/"]);
    let result = report(&direct, 1);
    assert_eq!(result.findings.len(), 1);
    assert_eq!(result.findings[0].file, "unknown");
    assert!(result.findings[0].message.contains("non-UTF-8"));

    let all = check(input, &["--read-only", "--include-untracked"]);
    let result = report(&all, 1);
    assert!(result.findings.iter().any(|f| f.file == "untracked.txt"));
    assert!(result.findings.iter().any(|f| f.file == "unknown"));
}
