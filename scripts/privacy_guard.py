#!/usr/bin/env python3
"""Check Privacy and Data Lineage records and source code for Apple Privacy & Meta Data Infra rigor."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_SYSTEM_ARCHETYPES = {
    "event_driven_data_lakehouse",
    "user_identity_and_auth_service",
    "telemetry_and_analytics_pipeline",
    "multi_tenant_saas_backend",
    "mobile_client_telemetry",
}

VALID_SENSITIVITY_TIERS = {
    "restricted_pii",
    "confidential_telemetry",
    "sensitive_financial",
    "protected_health",
}

VALID_KMS_PROVIDERS = {
    "aws_kms",
    "gcp_kms",
    "hashicorp_vault",
    "apple_secure_enclave",
}

VALID_CIPHERS = {
    "AES-256-GCM",
    "XChaCha20-Poly1305",
}


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_target_system(record, require):
    target = record.get("target_system")
    require(isinstance(target, dict), "INVALID_TARGET_SYSTEM", "target_system must be a dictionary")
    if not isinstance(target, dict):
        return
    require(filled(target.get("module_under_test"), 5),
            "MISSING_MODULE_UNDER_TEST",
            "target_system.module_under_test must be at least 5 characters")
    require(choice(target.get("system_archetype"), VALID_SYSTEM_ARCHETYPES),
            "INVALID_SYSTEM_ARCHETYPE",
            "target_system.system_archetype must be one of: %s" % ", ".join(sorted(VALID_SYSTEM_ARCHETYPES)))
    regimes = target.get("regulatory_regimes")
    require(isinstance(regimes, list) and len(regimes) >= 1 and all(filled(r) for r in regimes),
            "MISSING_REGULATORY_REGIMES",
            "target_system.regulatory_regimes must declare at least one regime (e.g. gdpr, ccpa)")


def check_tainted_pii_types(record, require):
    tpt = record.get("tainted_pii_types")
    require(isinstance(tpt, dict), "INVALID_TAINTED_PII_TYPES", "tainted_pii_types must be a dictionary")
    if not isinstance(tpt, dict):
        return
    require(tpt.get("branded_types_enabled") is True,
            "BRANDED_TYPES_DISABLED",
            "tainted_pii_types.branded_types_enabled must be true to enforce nominal compile-time boundary sealing")
    require(filled(tpt.get("redaction_wrapper"), 5),
            "MISSING_REDACTION_WRAPPER",
            "tainted_pii_types.redaction_wrapper must name the wrapper container (e.g. Redacted<T>)")
    require(tpt.get("log_leakage_prevented") is True,
            "LOG_LEAKAGE_NOT_PREVENTED",
            "tainted_pii_types.log_leakage_prevented must be true")
    require(tpt.get("unredacted_serialization_banned") is True,
            "UNREDACTED_SERIALIZATION_NOT_BANNED",
            "tainted_pii_types.unredacted_serialization_banned must be true; toString() and toJSON() must mask PII")

    fields = tpt.get("audited_pii_fields")
    require(isinstance(fields, list) and len(fields) >= 2,
            "INSUFFICIENT_AUDITED_PII_FIELDS",
            "tainted_pii_types.audited_pii_fields must declare at least 2 distinct audited PII fields")
    if isinstance(fields, list):
        seen_names = set()
        for idx, item in enumerate(fields):
            valid = (
                isinstance(item, dict)
                and filled(item.get("field_name"), 2)
                and choice(item.get("sensitivity"), VALID_SENSITIVITY_TIERS)
                and filled(item.get("type_brand"), 5)
                and filled(item.get("serialization_policy"), 5)
            )
            require(valid, "INVALID_PII_FIELD_SPEC",
                    "audited_pii_fields[%d] requires field_name, valid sensitivity, type_brand, and serialization_policy" % idx)
            if isinstance(item, dict) and filled(item.get("field_name")):
                fn = item["field_name"].strip().casefold()
                require(fn not in seen_names, "DUPLICATE_PII_FIELD", "Audited PII field names must be distinct")
                seen_names.add(fn)


def check_cryptographic_erasure(record, require):
    ce = record.get("cryptographic_erasure")
    require(isinstance(ce, dict), "INVALID_CRYPTOGRAPHIC_ERASURE", "cryptographic_erasure must be a dictionary")
    if not isinstance(ce, dict):
        return
    require(ce.get("mechanism") == "crypto_shredding_key_per_subject",
            "INVALID_ERASURE_MECHANISM",
            "cryptographic_erasure.mechanism must be 'crypto_shredding_key_per_subject'")
    require(choice(ce.get("kms_provider"), VALID_KMS_PROVIDERS),
            "INVALID_KMS_PROVIDER",
            "cryptographic_erasure.kms_provider must be one of: %s" % ", ".join(sorted(VALID_KMS_PROVIDERS)))
    require(choice(ce.get("key_derivation_algorithm"), VALID_CIPHERS),
            "INVALID_KEY_DERIVATION_ALGORITHM",
            "cryptographic_erasure.key_derivation_algorithm must be one of: %s" % ", ".join(sorted(VALID_CIPHERS)))

    ledgers = ce.get("immutable_ledger_coverage")
    require(isinstance(ledgers, list) and len(ledgers) >= 2 and all(filled(l) for l in ledgers),
            "INSUFFICIENT_LEDGER_COVERAGE",
            "cryptographic_erasure.immutable_ledger_coverage must declare at least 2 immutable stores (e.g. kafka, iceberg)")

    latency = ce.get("revocation_latency_ms")
    require(isinstance(latency, int) and 1 <= latency <= 5000,
            "INVALID_REVOCATION_LATENCY",
            "cryptographic_erasure.revocation_latency_ms must be an integer between 1 and 5000 ms")
    require(ce.get("confirmation_receipt_verified") is True,
            "CONFIRMATION_RECEIPT_NOT_VERIFIED",
            "cryptographic_erasure.confirmation_receipt_verified must be true; verifiable audit receipts are mandatory")


def check_data_minimization_and_ttl(record, require):
    dmt = record.get("data_minimization_and_ttl")
    require(isinstance(dmt, dict), "INVALID_DATA_MINIMIZATION_AND_TTL",
            "data_minimization_and_ttl must be a dictionary")
    if not isinstance(dmt, dict):
        return
    require(dmt.get("purpose_binding_declared") is True,
            "PURPOSE_BINDING_NOT_DECLARED",
            "data_minimization_and_ttl.purpose_binding_declared must be true")
    require(dmt.get("retention_ttl_enforced") is True,
            "RETENTION_TTL_NOT_ENFORCED",
            "data_minimization_and_ttl.retention_ttl_enforced must be true; indefinite storage is banned")

    max_ttl = dmt.get("max_retention_days")
    require(isinstance(max_ttl, int) and 1 <= max_ttl <= 730,
            "INVALID_MAX_RETENTION_DAYS",
            "data_minimization_and_ttl.max_retention_days must be an integer between 1 and 730 days")
    require(filled(dmt.get("automated_gc_pipeline"), 5),
            "MISSING_AUTOMATED_GC_PIPELINE",
            "data_minimization_and_ttl.automated_gc_pipeline must describe the automated purge mechanism")
    require(filled(dmt.get("differential_privacy_or_anonymization"), 5),
            "MISSING_ANONYMIZATION_SPEC",
            "data_minimization_and_ttl.differential_privacy_or_anonymization must describe the anonymization or DP method")


def check_data_lineage_and_flow(record, require):
    dlf = record.get("data_lineage_and_flow")
    require(isinstance(dlf, dict), "INVALID_DATA_LINEAGE_AND_FLOW",
            "data_lineage_and_flow must be a dictionary")
    if not isinstance(dlf, dict):
        return
    require(dlf.get("lineage_dag_modeled") is True,
            "LINEAGE_DAG_NOT_MODELED",
            "data_lineage_and_flow.lineage_dag_modeled must be true")
    require(dlf.get("forbidden_sinks_guarded") is True,
            "FORBIDDEN_SINKS_NOT_GUARDED",
            "data_lineage_and_flow.forbidden_sinks_guarded must be true")

    allowlist = dlf.get("telemetry_egress_allowlist")
    require(isinstance(allowlist, list) and len(allowlist) >= 1 and all(filled(a) for a in allowlist),
            "MISSING_TELEMETRY_ALLOWLIST",
            "data_lineage_and_flow.telemetry_egress_allowlist must list authorized egress destinations")
    require(dlf.get("third_party_sharing_fenced") is True,
            "THIRD_PARTY_SHARING_NOT_FENCED",
            "data_lineage_and_flow.third_party_sharing_fenced must be true")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(choice(action, {"proceed", "pause", "refuse"}), "INVALID_ACTION",
            "Verdict action must be proceed, pause, or refuse")
    require(filled(verdict.get("rationale"), 20),
            "MISSING_RATIONALE", "Verdict rationale must be at least 20 characters")
    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and bool(triggers) and all(filled(t) for t in triggers),
            "MISSING_REVISIT_TRIGGERS", "Verdict must declare at least one revisit trigger")
    return action


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    # Anti-Pattern 1: Direct logging of raw PII
    raw_pii_logging = bool(
        re.search(
            r"\b(?:console\.(?:log|info|warn|error)|logger\.(?:info|warn|error|debug)|logging\.(?:info|warning|error))\s*\([^)]*?\b(?:email|phone|ssn|raw_password|user\.email|user\.phone|req\.body)\b",
            source_text,
            re.IGNORECASE
        )
    )
    require(not raw_pii_logging, "SOURCE_RAW_PII_LOGGING",
            "Detected raw PII logging; wrap sensitive personal data in Redacted<T> types with toString()/toJSON() redaction")

    # Anti-Pattern 2: Unredacted PII in telemetry / analytics calls
    telemetry_pii = bool(
        re.search(
            r"\b(?:analytics|mixpanel|gtag|segment|amplitude)\.(?:track|identify|event)\s*\([^)]*?\b(?:email|phone|address|ssn)\s*:",
            source_text,
            re.IGNORECASE
        )
    )
    require(not telemetry_pii, "SOURCE_TELEMETRY_PII_LEAK",
            "Detected raw PII in analytics/telemetry call; strip personal identifiers or apply local Differential Privacy before egress")

    # Anti-Pattern 3: Naive soft-delete masquerading as GDPR erasure
    naive_soft_delete = bool(
        re.search(
            r"\b(?:is_deleted\s*=\s*(?:true|1)|deleted_at\s*=\s*(?:NOW\(\)|new\s+Date\(\)|datetime\.now\(\)))\b",
            source_text,
            re.IGNORECASE
        )
    )
    require(not naive_soft_delete, "SOURCE_NAIVE_SOFT_DELETE",
            "Detected naive soft-delete without crypto-shredding; GDPR Article 17 requires permanent cryptographic erasure or storage purge")

    # Anti-Pattern 4: Database table or schema storing user data without retention TTL
    unbounded_retention = bool(
        re.search(
            r"(?:CREATE\s+TABLE\s+(?:user_|customer_|client_|account_)[a-zA-Z0-9_]*|class\s+[a-zA-Z0-9_]*(?:UserProfile|UserActivity|CustomerData))",
            source_text,
            re.IGNORECASE
        )
    ) and not bool(
        re.search(r"\b(?:retention_ttl|ttl_days|retention_days|PARTITION\s+BY|TTL\s+recorded_at)\b", source_text, re.IGNORECASE)
    )
    require(not unbounded_retention, "SOURCE_UNBOUNDED_RETENTION_TABLE",
            "Detected user data table/entity lacking retention TTL; all personal data schemas must enforce an automated retention lifecycle")

    # Anti-Pattern 5: Unredacted toString exposing PII
    unredacted_tostring = bool(
        re.search(
            r"(?:toString|toJSON)\s*\([^)]*\)\s*[:{][^}]*?\b(?:this\.email|this\.phone|this\.ssn)\b",
            source_text,
            re.IGNORECASE
        )
    )
    require(not unredacted_tostring, "SOURCE_UNREDACTED_TOSTRING",
            "Detected toString()/toJSON() returning raw PII; sensitive entities must emit [REDACTED] by default")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_target_system(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_tainted_pii_types(record, require)
        check_cryptographic_erasure(record, require)
        check_data_minimization_and_ttl(record, require)
        check_data_lineage_and_flow(record, require)

    if source_text is not None:
        findings.extend(scan_source_hazards(source_text))

    return {
        "record_status": "incomplete" if findings else "complete",
        "verdict_action": action,
        "machine_check_only": True,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--source", type=Path, default=None,
                        help="Optional source file to scan for raw PII logging, telemetry leaks, naive soft-delete, or unbounded retention")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid Privacy & Data Lineage record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Privacy & Data Lineage record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: Type-level redaction, KMS crypto-shredding, and automated GC must be verified in test suites.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
