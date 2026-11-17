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

fn swallow_findings(diff: &str) -> Vec<usize> {
    let interceptor = ShitInterceptor::new();
    interceptor
        .audit_diff(diff, None, false)
        .iter()
        .filter(|f| f.code == "STS-H02")
        .map(|f| f.line)
        .collect()
}

#[test]
fn test_multiline_python_error_swallowing() {
    let diff = r#"
diff --git a/job.py b/job.py
--- a/job.py
+++ b/job.py
@@ -1 +1,5 @@
+try:
+    run()
+except Exception:
+    pass
 finish()
"#;
    assert_eq!(swallow_findings(diff), vec![3]);
}

#[test]
fn test_multiline_js_catch_error_swallowing() {
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
    assert_eq!(swallow_findings(diff), vec![3]);
}

#[test]
fn test_multiline_nonempty_catch_not_flagged() {
    let diff = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,6 @@
+try {
+    invoke();
+} catch (err) {
+    console.error(err);
+}
"#;
    assert!(swallow_findings(diff).is_empty());
}

#[test]
fn test_multiline_python_nonempty_suite_not_flagged() {
    let diff = r#"
diff --git a/job.py b/job.py
--- a/job.py
+++ b/job.py
@@ -1 +1,5 @@
+try:
+    run()
+except Exception:
+    log_failure()
 finish()
"#;
    assert!(swallow_findings(diff).is_empty());
}

#[test]
fn test_python_except_replacement_flagged() {
    let diff = "diff --git a/worker.py b/worker.py\n--- a/worker.py\n+++ b/worker.py\n@@ -8,4 +8,4 @@\n     except RuntimeError:\n-        report()\n+        pass\n     finish()\n";
    assert_eq!(swallow_findings(diff), vec![9]);
}

#[test]
fn test_template_literal_catch_skeleton_not_flagged() {
    let diff = r#"
diff --git a/tpl.ts b/tpl.ts
--- a/tpl.ts
+++ b/tpl.ts
@@ -1 +1,5 @@
+const tpl = `
+} catch (e) {
+}
+`;
 finish();
"#;
    assert!(swallow_findings(diff).is_empty());
}

#[test]
fn test_python_triple_quoted_string_not_flagged() {
    let diff = r#"
diff --git a/doc.py b/doc.py
--- a/doc.py
+++ b/doc.py
@@ -1 +1,5 @@
+message = """
+except Exception:
+    pass
+"""
 finish()
"#;
    assert!(swallow_findings(diff).is_empty());
}

#[test]
fn test_catch_with_reason_comment_not_flagged() {
    let diff = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,6 @@
+try {
+    invoke();
+} catch (err) {
+    // intentional: best-effort cleanup
+}
"#;
    assert!(swallow_findings(diff).is_empty());
}

#[test]
fn test_hunk_ending_at_pass_not_flagged() {
    // Conservative boundary: the suite may continue past the hunk, so a
    // hunk that ends exactly at the `pass` line is not flagged.
    let diff = r#"
diff --git a/job.py b/job.py
--- a/job.py
+++ b/job.py
@@ -5,0 +6,4 @@
+try:
+    run()
+except Exception:
+    pass
"#;
    assert!(swallow_findings(diff).is_empty());
}

#[test]
fn test_catch_opening_line_and_block_comment_reasons_not_flagged() {
    let opening_line = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,5 @@
+try {
+    invoke();
+} catch (err) { // intentional
+}
"#;
    assert!(swallow_findings(opening_line).is_empty());

    let inline_block = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,4 @@
+try {
+    invoke();
+} catch (err) { /* intentional */ }
"#;
    assert!(swallow_findings(inline_block).is_empty());

    let multiline_block = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,8 @@
+try {
+    invoke();
+} catch (err) {
+/*
+ * intentional: best-effort cleanup
+ */
+}
"#;
    assert!(swallow_findings(multiline_block).is_empty());
}

#[test]
fn test_comment_outside_catch_block_does_not_exempt_empty_handler() {
    let before_catch = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,5 @@
+try {
+    invoke();
+/* intentional */ } catch (err) {
+}
"#;
    assert_eq!(swallow_findings(before_catch), vec![3]);

    let unrelated_block = r#"
diff --git a/app.ts b/app.ts
--- a/app.ts
+++ b/app.ts
@@ -1,4 +1,4 @@
+try {
+    invoke();
+} catch (err) { /* todo */ }
"#;
    assert_eq!(swallow_findings(unrelated_block), vec![3]);
}
