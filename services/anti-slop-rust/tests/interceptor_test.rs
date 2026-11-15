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
    assert_eq!(
        findings[0].category,
        ViolationCategory::HypotheticalHardening
    );
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
    assert_eq!(
        findings[0].category,
        ViolationCategory::HypotheticalHardening
    );
    assert_eq!(findings[0].code, "STS-H02");
}

#[test]
fn test_multiline_go_error_swallowing() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/main.go b/main.go
--- a/main.go
+++ b/main.go
@@ -10,3 +10,5 @@
+	if err != nil {
+	}
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_multiline_python_error_swallowing() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/job.py b/job.py
--- a/job.py
+++ b/job.py
@@ -1,4 +1,6 @@
+try:
+    run()
+except Exception:
+    pass
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_multiline_js_catch_error_swallowing() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,6 @@
+try {
+    invoke();
+} catch (err) {
+}
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_documented_ignore_not_flagged() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/client.go b/client.go
--- a/client.go
+++ b/client.go
@@ -1,3 +1,5 @@
+if err != nil {
+    // expected: connection may already be closed
+}
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_valid_handler_not_flagged() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/client.go b/client.go
--- a/client.go
+++ b/client.go
@@ -1,3 +1,6 @@
+if err != nil {
+    log.Println(err)
+    return err
+}
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_comments_and_strings_not_flagged() {
    let interceptor = ShitInterceptor::new();
    let diff = r#"
diff --git a/docs.go b/docs.go
--- a/docs.go
+++ b/docs.go
@@ -1,2 +1,4 @@
+// if err != nil {
+// }
+const template = "except Exception:\n    pass"
"#;
    let findings = interceptor.audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_multiline_handler_stops_at_end_of_hunk() {
    let diff = r#"
diff --git a/worker.py b/worker.py
--- a/worker.py
+++ b/worker.py
@@ -8,1 +8,2 @@
     try:
+    except Exception:
@@ -70,1 +71,2 @@
         pass
+        ...
"#;
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_incomplete_brace_handler_is_inconclusive() {
    let diff = r#"
diff --git a/worker.go b/worker.go
--- a/worker.go
+++ b/worker.go
@@ -8,1 +8,2 @@
     start()
+    if err != nil {
"#;
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_multiline_catch_keeps_recovery_before_finally() {
    let diff = r#"
diff --git a/worker.ts b/worker.ts
--- a/worker.ts
+++ b/worker.ts
@@ -8,4 +8,10 @@
     try {
         run();
+    } catch (error) {
+        report(error);
+    } finally {
+        cleanup();
     }
 }
"#;
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}
