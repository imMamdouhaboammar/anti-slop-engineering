use anti_slop_rust::ladder_auditor::LadderAuditor;
use anti_slop_rust::model::ViolationCategory;

#[test]
fn test_handrolled_uuid_flagged() {
    let auditor = LadderAuditor::new();
    let code = r#"
const id = Math.random().toString(36).substring(2, 9);
"#;
    let findings = auditor.audit_code("src/id.ts", code);
    assert_eq!(findings.len(), 1);
    assert_eq!(findings[0].category, ViolationCategory::MissingBuiltIn);
    assert_eq!(findings[0].code, "BORING-KISS-01");
}

#[test]
fn test_handrolled_query_parser_flagged() {
    let auditor = LadderAuditor::new();
    let code = r#"
const params = window.location.search.split('?')[1].split('&').map(p => p.split('='));
"#;
    let findings = auditor.audit_code("src/url.ts", code);
    assert_eq!(findings.len(), 1);
    assert_eq!(findings[0].code, "BORING-KISS-02");
}

#[test]
fn test_conjunction_naming_flagged() {
    let auditor = LadderAuditor::new();
    let code = r#"
export class UserAndOrgManager {
}
"#;
    let findings = auditor.audit_code("src/manager.ts", code);
    assert_eq!(findings.len(), 1);
    assert_eq!(findings[0].code, "BORING-DRY-01");
}
