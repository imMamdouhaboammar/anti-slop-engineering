use anti_slop_rust::model::Severity;
use anti_slop_rust::triage_diff;
use std::fs;
use std::path::PathBuf;

fn fixture_path(name: &str) -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("..")
        .join("tests")
        .join("fixtures")
        .join("engine-parity")
        .join(name)
}

#[test]
fn golden_fixtures_match_declared_shared_contracts() {
    let clean = fs::read_to_string(fixture_path("clean.diff")).expect("clean.diff");
    let clean_report = triage_diff(&clean, None, false);
    assert_eq!(clean_report.summary.status, "PASSED");
    assert_eq!(clean_report.summary.total_findings, 0);

    let blocker = fs::read_to_string(fixture_path("blocker_error_swallow.diff")).expect("blocker diff");
    let blocker_report = triage_diff(&blocker, None, false);
    assert_eq!(blocker_report.summary.status, "BLOCKED");
    assert!(blocker_report
        .findings
        .iter()
        .any(|f| f.code == "STS-H02" && f.severity == Severity::Blocker));

    for fixture in [
        "deletion_only.diff",
        "renamed_file.diff",
        "whitespace_path.diff",
        "non_ascii_path.diff",
    ] {
        let diff = fs::read_to_string(fixture_path(fixture)).expect(fixture);
        let report = triage_diff(&diff, None, false);
        assert_eq!(
            report.summary.blockers, 0,
            "unexpected blockers for {fixture}: {:?}",
            report.findings
        );
    }
}

#[test]
fn triage_diff_handles_malformed_hunks_and_unicode_without_panicking() {
    // Deterministic seeded LCG generating edge-case unified diff fragments targeting hunk/path parsing.
    let fragments = [
        "diff --git a/src/a b.py b/src/a b.py\n",
        "diff --git \"a/src/caf\\303\\251.py\" \"b/src/caf\\303\\251.py\"\n",
        "+++ b/src/my file.py\n",
        "+++ /dev/null\n",
        "@@ -1 +0,0 @@\n",
        "@@ -0,0 +99999999999999999999999,2 @@\n",
        "@@ malformed header\n",
        "+except Exception: pass\r\n",
        "+++not a header\n",
        "-removed line\n",
        " context line\n",
        "+// comment café 🚀\n",
    ];

    let mut seed: u64 = 0x5EED_C0DE_2026;
    for _case in 0..128 {
        let mut synthetic = String::new();
        for _step in 0..10 {
            seed = seed.wrapping_mul(6364136223846793005).wrapping_add(1);
            let idx = ((seed >> 32) as usize) % fragments.len();
            synthetic.push_str(fragments[idx]);
        }
        let report = triage_diff(&synthetic, Some(&["src/"]), false);
        assert!(report.summary.total_findings >= report.summary.blockers);
    }
}
