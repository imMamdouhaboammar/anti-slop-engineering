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
@@ -1 +1,5 @@
+try:
+    run()
+except Exception:
+    pass
 finish()
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

#[test]
fn test_empty_catch_before_finally_is_reported() {
    let diff = r#"
diff --git a/worker.ts b/worker.ts
--- a/worker.ts
+++ b/worker.ts
@@ -8,4 +8,7 @@
     try {
         run();
+    } catch (error) {
+    } finally {
+        cleanup();
     }
 }
"#;
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02" && f.line == 10));
}

#[test]
fn test_multiline_handler_detects_body_removal_under_unchanged_header() {
    let diff = "diff --git a/worker.go b/worker.go\n--- a/worker.go\n+++ b/worker.go\n@@ -10,5 +10,4 @@\n func apply() {\n     if err != nil {\n-        report(err)\n     }\n }\n";
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    let matches: Vec<_> = findings.iter().filter(|f| f.code == "STS-H02").collect();
    assert_eq!(matches.len(), 1);
    assert_eq!(matches[0].line, 11);
    assert_eq!(matches[0].file, "worker.go");
}

#[test]
fn test_multiline_handler_detects_python_replacement_under_unchanged_header() {
    let diff = "diff --git a/worker.py b/worker.py\n--- a/worker.py\n+++ b/worker.py\n@@ -8,4 +8,4 @@\n     except RuntimeError:\n-        report()\n+        pass\n     finish()\n \n";
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02" && f.line == 8));
}

#[test]
fn test_multiline_handler_ignores_change_at_python_dedent() {
    let diff = "diff --git a/worker.py b/worker.py\n--- a/worker.py\n+++ b/worker.py\n@@ -8,4 +8,4 @@\n     except RuntimeError:\n         pass\n-    old_finish()\n+    finish()\n \n";
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_multiline_handler_needs_python_suite_boundary() {
    let diff = "diff --git a/worker.py b/worker.py\n--- a/worker.py\n+++ b/worker.py\n@@ -8,1 +8,3 @@\n     try:\n+    except RuntimeError:\n+        pass\n";
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_multiline_handler_suppresses_proven_non_code_spans() {
    let fixtures = [
        (
            "worker.go",
            " var description = \x60\n+if err != nil {\n+}\n \x60\n",
        ),
        ("worker.ts", " /* demo\n+catch (err) {\n+}\n */\n"),
        (
            "worker.py",
            " message = \"\"\"\n+except RuntimeError: pass\n \"\"\"\n",
        ),
        ("worker.ts", "+run(); // catch (err) {}\n"),
    ];
    for (path, hunk) in fixtures {
        let diff = format!(
            "diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@ -8,2 +8,4 @@\n{hunk}"
        );
        let findings = ShitInterceptor::new().audit_diff(&diff, None, false);
        assert!(
            !findings.iter().any(|f| f.code == "STS-H02"),
            "{path}: {hunk}"
        );
    }
}

#[test]
fn test_multiline_handler_recognizes_following_code_after_inline_comment() {
    let diff = "diff --git a/worker.ts b/worker.ts\n--- a/worker.ts\n+++ b/worker.ts\n@@ -8,1 +8,4 @@\n try {\n+} catch (error) {\n+    /* no explanatory reason */\n+} finally { finish(); }\n";
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02" && f.line == 9));
}

#[test]
fn test_multiline_handler_keeps_triple_quoted_expression_as_code() {
    let diff = "diff --git a/worker.py b/worker.py\n--- a/worker.py\n+++ b/worker.py\n@@ -8,1 +8,6 @@\n+except RuntimeError:\n+    \"\"\"diagnostic text\n+    continued\n+    \"\"\"\n+    pass\n finish()\n";
    let findings = ShitInterceptor::new().audit_diff(diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

fn literal_fixture_diff(path: &str, before: &str, after: &str) -> String {
    use std::fs;
    use std::process::Command;

    let root =
        std::env::temp_dir().join(format!("anti-slop-literal-{}-{path}", std::process::id()));
    fs::create_dir(&root).expect("create fixture Git directory");
    let git = |args: &[&str]| {
        let result = Command::new("git")
            .current_dir(&root)
            .args(args)
            .output()
            .unwrap();
        assert!(
            result.status.success(),
            "git {args:?}: {}",
            String::from_utf8_lossy(&result.stderr)
        );
        result.stdout
    };
    git(&["init", "-q"]);
    git(&["config", "user.email", "fixture@example.invalid"]);
    git(&["config", "user.name", "Fixture"]);
    git(&["config", "core.hooksPath", ".git/no-fixture-hooks"]);
    git(&["config", "commit.gpgSign", "false"]);
    fs::write(root.join(path), before).unwrap();
    git(&["add", "--", path]);
    git(&["commit", "-qm", "literal fixture"]);
    fs::write(root.join(path), after).unwrap();
    let patch = git(&[
        "diff",
        "--no-ext-diff",
        "--no-color",
        "--unified=20",
        "HEAD",
        "--",
        path,
    ]);
    fs::remove_dir_all(&root).unwrap();
    String::from_utf8(patch).unwrap()
}

#[test]
fn test_literal_context_skips_js_template_text_and_resumes_code() {
    let before = "const sample = \x60\nold sample\n\x60;\ntry {\n    run();\n} catch (err) {\n    report(err);\n}\n";
    let after =
        "const sample = \x60\ncatch (err) {\n}\n\x60;\ntry {\n    run();\n} catch (err) {\n}\n";
    let diff = literal_fixture_diff("worker.ts", before, after);
    let findings = ShitInterceptor::new().audit_diff(&diff, None, false);
    let lines: Vec<_> = findings
        .iter()
        .filter(|f| f.code == "STS-H02")
        .map(|f| f.line)
        .collect();
    assert_eq!(lines, [7]);
}

#[test]
fn test_literal_context_keeps_code_inside_template_interpolation() {
    let before = "const sample = \x60value ${(() => {\n    try {\n        run();\n    } catch (err) {\n        report(err);\n    }\n})()}\x60;\n";
    let after = before.replace("        report(err);\n", "");
    let diff = literal_fixture_diff("embedded.ts", before, &after);
    let findings = ShitInterceptor::new().audit_diff(&diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02" && f.line == 4));
}

#[test]
fn test_literal_context_keeps_escaped_python_triple_delimiter_inside_string() {
    let before = "message = \"\"\"start\nold sample\n\"\"\"\nfinish()\n";
    let after = "message = \"\"\"start\n\\\"\"\"escaped boundary\nexcept RuntimeError: pass\n\"\"\"\nfinish()\n";
    let diff = literal_fixture_diff("worker.py", before, after);
    let findings = ShitInterceptor::new().audit_diff(&diff, None, false);
    assert!(!findings.iter().any(|f| f.code == "STS-H02"));
}

#[test]
fn test_literal_context_remains_conservative_after_interpolation() {
    let before = "const sample = \x60value \x24{value}\x60;\ntry {\n    run();\n} catch (err) {\n    report(err);\n}\n";
    let after = before.replace("    report(err);\n", "");
    let diff = literal_fixture_diff("after-embedded.ts", before, &after);
    let findings = ShitInterceptor::new().audit_diff(&diff, None, false);
    assert!(findings.iter().any(|f| f.code == "STS-H02" && f.line == 4));
}
