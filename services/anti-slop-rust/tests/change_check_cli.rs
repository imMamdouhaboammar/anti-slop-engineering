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
    serde_json::from_slice(&out.stdout).unwrap_or_else(|error| {
        panic!(
            "parse Rust report: {error}. stderr: {}",
            String::from_utf8_lossy(&out.stderr)
        )
    })
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
    (root / "src" / "link").write_bytes(b"\x00binary")
    git("add", ".")
    git("commit", "-qm", "base")
    git("mv", "old name.txt", "src/renamed name.txt")
    git("update-index", "--chmod=+x", "src/script.sh")
    binary.write_bytes(b"\x00two")
    git("add", "assets/data.bin")
    (root / "src" / "link").unlink()
    (root / "src" / "link").symlink_to("script.sh")
    git("add", "src/link")
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
    let changes: serde_json::Value = serde_json::from_str(&source).unwrap();
    assert!(changes["files"].as_array().unwrap().iter().any(|file| {
        file["status"] == "T"
            && file["binary"] == true
            && !file["hunks"].as_array().unwrap().is_empty()
    }));
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
        [
            "assets/data.bin",
            "src/link",
            "src/renamed name.txt",
            "src/script.sh"
        ]
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

#[test]
fn oversized_file_rejects_even_a_valid_json_prefix() {
    let path = std::env::temp_dir().join(format!(
        "anti-slop-change-check-{}-limit.json",
        std::process::id()
    ));
    let file = std::fs::File::options()
        .read(true)
        .write(true)
        .create_new(true)
        .open(&path)
        .unwrap();
    let prefix = br#"{"version":1,"snapshot":"index","base":"1111111111111111111111111111111111111111","target":null,"files":[],"untracked":[]}"#;
    let chunk = [b' '; 1024 * 1024];
    let mut file = std::io::BufWriter::new(file);
    file.write_all(prefix).unwrap();
    for _ in 0..64 {
        file.write_all(&chunk).unwrap();
    }
    file.flush().unwrap();
    drop(file);
    let out = Command::new(env!("CARGO_BIN_EXE_anti-slop-rust"))
        .args(["change-check", "--changeset"])
        .arg(&path)
        .output()
        .expect("run oversized input check");
    std::fs::remove_file(&path).unwrap();
    assert!(!out.status.success());
    assert!(out.stdout.is_empty());
    assert!(String::from_utf8_lossy(&out.stderr).contains("64 MiB"));
}

fn collect_quoted_binary_fixture() -> String {
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
    (root / "src").mkdir()
    (root / "assets").mkdir()
    cafe = root / "src" / "café données.py"
    cafe.write_text("import time\n\n\ndef café():\n    return 1\n", encoding="utf-8")
    (root / "assets" / "blob.bin").write_bytes(b"\x00\x01\x02binary-v1")
    (root / "src" / "control.py").write_text("def control():\n    return 1\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-qm", "base")
    cafe.write_text("import time\n\n\ndef café():\n    time.sleep(5)\n    return 1\n", encoding="utf-8")
    (root / "assets" / "blob.bin").write_bytes(b"\x00\x09\x08binary-v2")
    (root / "src" / "control.py").write_text("def control():\n    return 1\n    # edited\n", encoding="utf-8")
    print(json.dumps(collect_changes(root, "HEAD", "worktree")))
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
fn quoted_binary_and_control_records_reach_the_rust_check() {
    let source = collect_quoted_binary_fixture();
    let changes: serde_json::Value = serde_json::from_str(&source).unwrap();
    let record = |path: &str| {
        changes["files"]
            .as_array()
            .unwrap()
            .iter()
            .find(|file| file["new_path"]["text"] == path)
            .unwrap_or_else(|| panic!("producer lost the record for {path}"))
            .clone()
    };
    let quoted = record("src/café données.py");
    assert_eq!(quoted["status"], "M");
    assert_eq!(quoted["binary"], false);
    assert_eq!(quoted["added"], 1);
    assert_eq!(quoted["deleted"], 0);
    assert_eq!(
        quoted["hunks"],
        serde_json::json!([{"old_start": 4, "old_count": 0, "new_start": 5, "new_count": 1}])
    );
    let blob = record("assets/blob.bin");
    assert_eq!(blob["status"], "M");
    assert_eq!(blob["binary"], true);
    assert!(blob["added"].is_null() && blob["deleted"].is_null());
    assert!(blob["hunks"].as_array().unwrap().is_empty());
    let control = record("src/control.py");
    assert_eq!(control["status"], "M");
    assert_eq!(
        control["hunks"],
        serde_json::json!([{"old_start": 2, "old_count": 0, "new_start": 3, "new_count": 1}])
    );

    let out = check(&source, &["--read-only"]);
    let findings = report(&out, 1).findings;
    let mut paths: Vec<_> = findings.iter().map(|f| f.file.as_str()).collect();
    paths.sort_unstable();
    assert_eq!(
        paths,
        ["assets/blob.bin", "src/café données.py", "src/control.py"]
    );
    assert!(findings.iter().all(|f| f.code == "STS-I01" && f.line == 1));
}

#[test]
fn binary_records_with_fabricated_hunks_are_rejected() {
    let input = r#"{"version":1,"snapshot":"worktree","base":"1111111111111111111111111111111111111111","target":null,"files":[{"status":"M","old_path":{"text":"assets/blob.bin","raw_hex":null},"new_path":{"text":"assets/blob.bin","raw_hex":null},"old_mode":"100644","new_mode":"100644","score":null,"added":null,"deleted":null,"binary":true,"hunks":[{"old_start":1,"old_count":1,"new_start":1,"new_count":1}]}],"untracked":[]}"#;
    let out = check(input, &["--read-only"]);
    assert!(!out.status.success());
    assert!(out.stdout.is_empty());
    assert!(
        String::from_utf8_lossy(&out.stderr).contains("file counts"),
        "{}",
        String::from_utf8_lossy(&out.stderr)
    );
}
