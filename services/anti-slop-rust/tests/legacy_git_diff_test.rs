use anti_slop_rust::triage_diff;
use std::process::Command;

#[test]
fn legacy_triage_attributes_real_git_content_and_metadata() {
    let script = r#"
from pathlib import Path
from subprocess import check_call, check_output
from tempfile import TemporaryDirectory

with TemporaryDirectory() as directory:
    root = Path(directory)

    def git(*args):
        check_call(["git", "-C", directory, *args])

    def write(relative, content):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    git("-c", "init.templateDir=", "init", "-q")
    git("config", "user.name", "Git Fixture")
    git("config", "user.email", "fixture@example.invalid")
    git("config", "commit.gpgSign", "false")
    git("config", "core.precomposeunicode", "true")
    git("config", "core.quotePath", "true")
    write("src/report/caf\u00e9.js", b"const value = {};\n")
    write("src/reporting/output.js", b"const value = {};\n")
    write("lib/old name.js", b"console.log('rename');\n")
    write("tools/helper.sh", b"exit 0\n")
    git("add", "--all")
    git("commit", "-qm", "fixture base")

    write("src/report/caf\u00e9.js", b"const value = {};\nconst clone = JSON.parse(JSON.stringify(value));\n")
    write("src/reporting/output.js", b"const value = {};\nconst appended = true;\n")
    git("mv", "lib/old name.js", "src/report/new name.js")
    git("add", "--all")
    git("update-index", "--chmod=+x", "tools/helper.sh")

    import sys
    sys.stdout.buffer.write(check_output([
        "git", "-C", directory, "diff", "--cached", "-M",
        "--no-color", "--no-ext-diff", "--no-textconv", "HEAD", "--",
    ]))
"#;
    let patch = Command::new("python3")
        .args(["-c", script])
        .output()
        .unwrap();
    assert!(
        patch.status.success(),
        "{}",
        String::from_utf8_lossy(&patch.stderr)
    );
    let patch = String::from_utf8(patch.stdout).unwrap();
    let report = triage_diff(&patch, Some(&["src/report"]), true);
    let findings = |code| {
        let mut matches: Vec<_> = report
            .findings
            .iter()
            .filter(|finding| finding.code == code)
            .map(|finding| (finding.file.as_str(), finding.line))
            .collect();
        matches.sort_unstable();
        matches
    };
    assert_eq!(
        findings("STS-S01"),
        [
            ("lib/old name.js", 1),
            ("src/reporting/output.js", 2),
            ("tools/helper.sh", 1),
        ]
    );
    assert_eq!(
        findings("STS-I01"),
        [
            ("src/report/café.js", 2),
            ("src/report/new name.js", 1),
            ("src/reporting/output.js", 2),
            ("tools/helper.sh", 1),
        ]
    );
    assert_eq!(findings("BORING-KISS-03"), [("src/report/café.js", 2)]);
}
