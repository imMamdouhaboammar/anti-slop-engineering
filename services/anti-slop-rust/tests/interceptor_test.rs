use anti_slop_rust::model::{Severity, ViolationCategory};
use anti_slop_rust::shit_interceptor::ShitInterceptor;

#[test]
fn test_scope_creep_detection() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/services/auth.ts b/services/auth.ts
--- a/services/auth.ts
+++ b/services/auth.ts
@@ -1,3 +1,4 @@
+export const token = 1;
diff --git a/.github/workflows/deploy.yml b/.github/workflows/deploy.yml
--- a/.github/workflows/deploy.yml
+++ b/.github/workflows/deploy.yml
@@ -10,3 +10,4 @@
+      run: echo "unrequested change"
"#;
    let allowed = vec!["services/auth.ts"];
    let findings = interceptor.audit_diff(diff, Some(&allowed), false);
    assert_eq!(findings.len(), 1);
    assert_eq!(findings[0].category, ViolationCategory::ScopeCreep);
    assert_eq!(findings[0].severity, Severity::Blocker);
    assert!(findings[0].file.contains("deploy.yml"));
}

#[test]
fn test_intent_violation_detection() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/README.md b/README.md
--- a/README.md
+++ b/README.md
@@ -1,2 +1,3 @@
+# Added in read only mode
"#;
    let findings = interceptor.audit_diff(diff, None, true);
    assert_eq!(findings.len(), 1);
    assert_eq!(findings[0].category, ViolationCategory::IntentViolation);
    assert_eq!(findings[0].severity, Severity::Blocker);
}

#[test]
fn test_hypothetical_hardening_checksum() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/export.ts b/export.ts
--- a/export.ts
+++ b/export.ts
@@ -10,2 +10,3 @@
+await writeFile("report.csv.sha256", createHash("sha256").update(csv).digest("hex"));
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert_eq!(findings.len(), 1);
    assert_eq!(findings[0].category, ViolationCategory::HypotheticalHardening);
    assert_eq!(findings[0].code, "STS-H01");
}

#[test]
fn test_hypothetical_error_swallowing() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/worker.py b/worker.py
--- a/worker.py
+++ b/worker.py
@@ -5,3 +5,4 @@
+except Exception: pass
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert_eq!(findings.len(), 1);
    assert_eq!(findings[0].category, ViolationCategory::HypotheticalHardening);
    assert_eq!(findings[0].code, "STS-H02");
}
