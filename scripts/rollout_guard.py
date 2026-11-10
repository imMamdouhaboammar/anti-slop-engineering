#!/usr/bin/env python3
"""Check safe evolution and rollout choreography records and source code for wire compatibility, shadow reads, feature flags, and Strangler Fig safety."""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path

VALID_PROTOCOLS = {"protobuf", "thrift", "json_rest", "graphql", "grpc"}
VALID_COMPATIBILITY_MODES = {
    "bidirectional_n_minus_one_n_plus_one",
    "backward_only",
    "breaking_migration_fenced",
}
VALID_DEPRECATION_PHASES = {
    "expand",
    "dual_read",
    "contract",
    "decommission",
    "none_additive_only",
}
VALID_ISOLATION_MODES = {
    "asynchronous_worker",
    "edge_proxy_tee",
    "event_queue",
    "none_direct_canary",
}
VALID_FLAG_PHASES = {
    "draft",
    "shadow",
    "canary",
    "graduated",
    "deprecated",
    "tombstoned",
}
VALID_KILL_SWITCH_MECHANISMS = {
    "in_memory_push",
    "redis_pubsub",
    "etcd_watch",
    "aws_appconfig",
}
VALID_FACADE_TYPES = {
    "api_gateway",
    "reverse_proxy",
    "service_mesh",
    "none_in_service_evolution",
}
VALID_TARGET_ENVIRONMENTS = {"production", "staging", "canary"}
VALID_VERDICTS = {"proceed", "pause", "refuse"}


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return isinstance(value, str) and value in values


def parse_iso_datetime(value):
    if not isinstance(value, str):
        return None
    cleaned = value.strip().replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(cleaned)
    except ValueError:
        return None


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_system_identity(record, require):
    ident = record.get("system_identity")
    require(isinstance(ident, dict), "INVALID_SYSTEM_IDENTITY", "system_identity must be a dictionary")
    if not isinstance(ident, dict):
        return

    require(filled(ident.get("service_name"), 3), "MISSING_SERVICE_NAME",
            "system_identity.service_name must be a string of at least 3 characters")
    require(filled(ident.get("component"), 2), "MISSING_COMPONENT",
            "system_identity.component must be a string of at least 2 characters")
    require(filled(ident.get("owner_team"), 3), "MISSING_OWNER_TEAM",
            "system_identity.owner_team must be a string of at least 3 characters")
    require(choice(ident.get("target_environment"), VALID_TARGET_ENVIRONMENTS),
            "INVALID_ENVIRONMENT", "system_identity.target_environment must be production, staging, or canary")


def check_wire_compatibility(record, require, is_proceed):
    wire = record.get("wire_compatibility")
    require(isinstance(wire, dict), "INVALID_WIRE_COMPATIBILITY", "wire_compatibility must be a dictionary")
    if not isinstance(wire, dict):
        return

    require(choice(wire.get("protocol"), VALID_PROTOCOLS), "INVALID_WIRE_PROTOCOL",
            "wire_compatibility.protocol must be one of: protobuf, thrift, json_rest, graphql, grpc")
    require(choice(wire.get("compatibility_mode"), VALID_COMPATIBILITY_MODES),
            "INVALID_COMPATIBILITY_MODE",
            "wire_compatibility.compatibility_mode must be bidirectional_n_minus_one_n_plus_one, backward_only, or breaking_migration_fenced")

    tolerant = wire.get("tolerant_reader_enforced")
    additive = wire.get("additive_only_verified")

    require(isinstance(tolerant, bool), "INVALID_TOLERANT_READER",
            "wire_compatibility.tolerant_reader_enforced must be a boolean")
    require(isinstance(additive, bool), "INVALID_ADDITIVE_ONLY",
            "wire_compatibility.additive_only_verified must be a boolean")

    if is_proceed:
        require(tolerant is True, "TOLERANT_READER_NOT_ENFORCED",
                "Proceed requires tolerant_reader_enforced=true to guarantee fleet N-1/N+1 deserialization safety")
        require(additive is True, "ADDITIVE_ONLY_NOT_VERIFIED",
                "Proceed requires additive_only_verified=true; field removals or direct renames in single PR are prohibited")

    require(choice(wire.get("deprecation_phase"), VALID_DEPRECATION_PHASES),
            "INVALID_DEPRECATION_PHASE",
            "wire_compatibility.deprecation_phase must be expand, dual_read, contract, decommission, or none_additive_only")


def check_dark_launch_and_shadow(record, require, is_proceed):
    shadow = record.get("dark_launch_and_shadow")
    require(isinstance(shadow, dict), "INVALID_DARK_LAUNCH", "dark_launch_and_shadow must be a dictionary")
    if not isinstance(shadow, dict):
        return

    enabled = shadow.get("shadow_mode_enabled")
    require(isinstance(enabled, bool), "INVALID_SHADOW_ENABLED",
            "dark_launch_and_shadow.shadow_mode_enabled must be a boolean")

    pct = shadow.get("traffic_mirror_percentage")
    require(isinstance(pct, (int, float)) and 0.0 <= pct <= 100.0,
            "INVALID_MIRROR_PERCENTAGE",
            "dark_launch_and_shadow.traffic_mirror_percentage must be a number between 0.0 and 100.0")

    require(choice(shadow.get("execution_isolation"), VALID_ISOLATION_MODES),
            "INVALID_EXECUTION_ISOLATION",
            "dark_launch_and_shadow.execution_isolation must be asynchronous_worker, edge_proxy_tee, event_queue, or none_direct_canary")

    fencing = shadow.get("side_effect_fencing")
    require(isinstance(fencing, dict), "INVALID_SIDE_EFFECT_FENCING",
            "dark_launch_and_shadow.side_effect_fencing must be a dictionary")
    if isinstance(fencing, dict):
        storage = fencing.get("storage_mutations_blocked")
        apis = fencing.get("external_apis_mocked")
        comms = fencing.get("user_communications_suppressed")
        require(isinstance(storage, bool) and isinstance(apis, bool) and isinstance(comms, bool),
                "INVALID_FENCING_FLAGS",
                "side_effect_fencing requires boolean storage_mutations_blocked, external_apis_mocked, and user_communications_suppressed")

        if is_proceed and enabled is True:
            require(storage is True, "UNFENCED_STORAGE_MUTATIONS",
                    "Shadow mode cannot proceed with live storage mutations; mutations must be blocked or sandboxed")
            require(apis is True, "UNFENCED_EXTERNAL_APIS",
                    "Shadow mode cannot proceed with live third-party API egress; external APIs must be mocked/stubbed")
            require(comms is True, "UNFENCED_USER_COMMUNICATIONS",
                    "Shadow mode cannot proceed without suppressing customer emails, SMS, and push notifications")

    parity = shadow.get("parity_gate")
    require(isinstance(parity, dict), "INVALID_PARITY_GATE", "dark_launch_and_shadow.parity_gate must be a dictionary")
    if isinstance(parity, dict):
        samples = parity.get("sample_size_evaluated")
        mismatch = parity.get("measured_mismatch_rate")
        p99_shadow = parity.get("p99_latency_shadow_ms")
        p99_base = parity.get("p99_latency_baseline_ms")

        require(isinstance(samples, int) and samples >= 0, "INVALID_PARITY_SAMPLES",
                "parity_gate.sample_size_evaluated must be a non-negative integer")
        require(isinstance(mismatch, (int, float)) and 0.0 <= mismatch <= 1.0, "INVALID_MISMATCH_RATE",
                "parity_gate.measured_mismatch_rate must be a float between 0.0 and 1.0")
        require(isinstance(p99_shadow, int) and p99_shadow >= 0, "INVALID_P99_SHADOW",
                "parity_gate.p99_latency_shadow_ms must be a non-negative integer")
        require(isinstance(p99_base, int) and p99_base >= 0, "INVALID_P99_BASELINE",
                "parity_gate.p99_latency_baseline_ms must be a non-negative integer")

        if is_proceed and enabled is True:
            require(samples >= 100_000, "INSUFFICIENT_SHADOW_SAMPLES",
                    "Proceed requires at least 100,000 evaluated shadow requests to verify statistical parity")
            require(mismatch <= 0.001, "EXCESSIVE_SHADOW_MISMATCH",
                    "Proceed requires measured_mismatch_rate <= 0.001 (0.1%%); current rate is %.6f" % mismatch)


def check_feature_flag_governance(record, require, is_proceed):
    flag = record.get("feature_flag_governance")
    require(isinstance(flag, dict), "INVALID_FLAG_GOVERNANCE", "feature_flag_governance must be a dictionary")
    if not isinstance(flag, dict):
        return

    require(filled(flag.get("flag_id"), 3), "MISSING_FLAG_ID",
            "feature_flag_governance.flag_id must be a string of at least 3 characters")
    require(choice(flag.get("lifecycle_phase"), VALID_FLAG_PHASES), "INVALID_FLAG_PHASE",
            "feature_flag_governance.lifecycle_phase must be draft, shadow, canary, graduated, deprecated, or tombstoned")
    require(choice(flag.get("kill_switch_mechanism"), VALID_KILL_SWITCH_MECHANISMS), "INVALID_KILL_SWITCH_MECHANISM",
            "feature_flag_governance.kill_switch_mechanism must be in_memory_push, redis_pubsub, etcd_watch, or aws_appconfig")

    tested = flag.get("kill_switch_tested")
    latency = flag.get("kill_switch_latency_ms")
    require(isinstance(tested, bool), "INVALID_KILL_SWITCH_TESTED",
            "feature_flag_governance.kill_switch_tested must be a boolean")
    require(isinstance(latency, int) and latency >= 1, "INVALID_KILL_SWITCH_LATENCY",
            "feature_flag_governance.kill_switch_latency_ms must be an integer >= 1")

    if is_proceed:
        require(tested is True, "KILL_SWITCH_NOT_TESTED",
                "Proceed requires kill_switch_tested=true; unverified kill-switches are fatal operational risks")
        require(latency <= 1000, "SLOW_KILL_SWITCH_PROPAGATION",
                "Proceed requires kill_switch_latency_ms <= 1000ms; sub-second propagation is mandatory")

    created_at = parse_iso_datetime(flag.get("created_at"))
    expires_at = parse_iso_datetime(flag.get("expires_at"))

    require(created_at is not None, "INVALID_CREATED_AT",
            "feature_flag_governance.created_at must be a valid ISO datetime string")
    require(expires_at is not None, "INVALID_EXPIRES_AT",
            "feature_flag_governance.expires_at must be a valid ISO datetime string")

    if created_at is not None and expires_at is not None:
        ttl = (expires_at - created_at).total_seconds() / (24 * 3600)
        require(ttl > 0, "INVALID_TTL_WINDOW", "expires_at must be strictly after created_at")
        require(ttl <= 90.0, "FLAG_TTL_EXCEEDS_90_DAYS",
                "Feature flag TTL cannot exceed 90 days (configured for %.1f days); long-lived flags accumulate dead debt" % ttl)

    require(filled(flag.get("demolition_ticket"), 3), "MISSING_DEMOLITION_TICKET",
            "feature_flag_governance.demolition_ticket must reference an explicit debt cleanup issue")


def check_strangler_fig_protocol(record, require):
    strangler = record.get("strangler_fig_protocol")
    require(isinstance(strangler, dict), "INVALID_STRANGLER_FIG", "strangler_fig_protocol must be a dictionary")
    if not isinstance(strangler, dict):
        return

    require(choice(strangler.get("facade_type"), VALID_FACADE_TYPES), "INVALID_FACADE_TYPE",
            "strangler_fig_protocol.facade_type must be api_gateway, reverse_proxy, service_mesh, or none_in_service_evolution")
    require(filled(strangler.get("active_vertical_slice"), 3), "MISSING_VERTICAL_SLICE",
            "strangler_fig_protocol.active_vertical_slice must specify the domain slice")

    canary = strangler.get("canary_percentage")
    require(isinstance(canary, (int, float)) and 0.0 <= canary <= 100.0, "INVALID_CANARY_PERCENTAGE",
            "strangler_fig_protocol.canary_percentage must be a number between 0.0 and 100.0")

    triggers = strangler.get("automated_rollback_slo_triggers")
    require(isinstance(triggers, list) and len(triggers) >= 1 and all(filled(t, 5) for t in triggers),
            "MISSING_ROLLBACK_TRIGGERS",
            "strangler_fig_protocol.automated_rollback_slo_triggers must list at least one concrete SLO rollback rule")

    target_date = parse_iso_datetime(strangler.get("decommission_target_date"))
    require(target_date is not None, "INVALID_DECOMMISSION_DATE",
            "strangler_fig_protocol.decommission_target_date must be a valid ISO datetime string")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None

    status = verdict.get("status")
    require(choice(status, VALID_VERDICTS), "INVALID_STATUS", "verdict.status must be proceed, pause, or refuse")
    require(isinstance(verdict.get("findings"), list), "INVALID_FINDINGS_LIST", "verdict.findings must be a list")
    require(filled(verdict.get("sign_off_sre"), 3), "MISSING_SRE_SIGN_OFF",
            "verdict.sign_off_sre must identify the reviewing Principal SRE")
    return status


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    # 1. Unfenced shadow write hazards
    shadow_blocks = re.finditer(
        r"(?:shadow(?:Execution|Runner|Mode|Path)?|dryRun)\s*[:=]\s*(?:true|\{[^}]*\})",
        source_text, re.IGNORECASE
    )
    has_shadow = bool(list(shadow_blocks))

    if has_shadow:
        live_billing_call = bool(re.search(
            r"\b(?:stripe|adyen|paypal|braintree)\.(?:charges|payments|invoices)\.create\b",
            source_text, re.IGNORECASE
        ))
        live_comm_call = bool(re.search(
            r"\b(?:twilio|sendgrid|mailgun)\.(?:messages|emails)\.send\b",
            source_text, re.IGNORECASE
        ))

        require(not live_billing_call, "UNFENCED_SHADOW_BILLING",
                "Detected live payment API calls alongside shadow execution without verified fencing or mock sinks")
        require(not live_comm_call, "UNFENCED_SHADOW_COMMUNICATION",
                "Detected live email/SMS dispatch alongside shadow execution without suppression guard")

    # 2. Hardcoded feature flags without kill switch or expiration
    flag_defs = re.finditer(
        r"(?:const|let|var)\s+([A-Za-z0-9_]+Flag)\s*=\s*\{(?P<body>[^}]+)\}",
        source_text
    )
    for match in flag_defs:
        body = match.group("body")
        flag_name = match.group(1)
        has_kill = bool(re.search(r"\bkillSwitch\b", body, re.IGNORECASE))
        has_expires = bool(re.search(r"\b(?:expiresAt|ttl|expiration)\b", body, re.IGNORECASE))
        require(has_kill, "FLAG_MISSING_KILL_SWITCH",
                "Feature flag '%s' definition is missing a killSwitch configuration" % flag_name)
        require(has_expires, "FLAG_MISSING_EXPIRATION",
                "Feature flag '%s' is missing an explicit expiresAt / TTL timestamp" % flag_name)

    # 3. Big-Bang cutover detection (100% instant cutover comment or immediate shift)
    instant_cutover = bool(re.search(
        r"\b(?:switch|route|shift)\s+100%\s+(?:traffic|users)\s+(?:directly|immediately|at once)\b",
        source_text, re.IGNORECASE
    ))
    require(not instant_cutover, "BIG_BANG_CUTOVER_DETECTED",
            "Instant 100% traffic shift detected without canary tiers or Strangler Fig facade")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    require(record.get("schema_version") == "1.0", "INVALID_SCHEMA_VERSION",
            "schema_version must be '1.0'")

    status = check_verdict(record, require)
    is_proceed = (status == "proceed")

    check_system_identity(record, require)
    check_wire_compatibility(record, require, is_proceed)
    check_dark_launch_and_shadow(record, require, is_proceed)
    check_feature_flag_governance(record, require, is_proceed)
    check_strangler_fig_protocol(record, require)

    if source_text is not None:
        findings.extend(scan_source_hazards(source_text))

    has_blockers = any(f["severity"] == "block" for f in findings)

    if is_proceed and has_blockers:
        findings.append({
            "severity": "block",
            "code": "PROCEED_WITH_BLOCKERS",
            "message": "Record declared verdict 'proceed' but unresolved blocking findings exist",
        })

    return {
        "record_status": "incomplete" if has_blockers else "complete",
        "verdict_action": status,
        "machine_check_only": True,
        "findings": findings,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["audit", "scan"])
    parser.add_argument("record", type=Path, nargs="?", default=None,
                        help="Path to JSON rollout record (for audit)")
    parser.add_argument("--source", type=Path, default=None,
                        help="Optional source code file to scan for rollout anti-patterns")
    parser.add_argument("--files", nargs="*", type=Path, default=[],
                        help="Source files to scan (for scan command)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON report")
    args = parser.parse_args()

    if args.command == "audit":
        if args.record is None:
            print("Error: audit command requires a JSON record file path", file=sys.stderr)
            return 1
        try:
            record_data = json.loads(args.record.read_text(encoding="utf-8"))
            if not isinstance(record_data, dict):
                raise ValueError("Record root must be a JSON object")
            source_content = args.source.read_text(encoding="utf-8") if args.source else None
            result = audit(record_data, source_text=source_content)
        except (OSError, UnicodeError, ValueError) as error:
            print("Invalid rollout choreography record: %s" % error, file=sys.stderr)
            return 1

        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("Rollout Choreography Record: %s (%s)" % (result["record_status"], result["verdict_action"]))
            for item in result["findings"]:
                print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))

        return 2 if result["record_status"] == "incomplete" else 0

    if args.command == "scan":
        targets = args.files or ([args.source] if args.source else [])
        if not targets:
            print("Error: scan command requires --files or --source", file=sys.stderr)
            return 1
        all_findings = []
        for file_path in targets:
            try:
                content = file_path.read_text(encoding="utf-8")
                hazards = scan_source_hazards(content)
                for h in hazards:
                    h["file"] = str(file_path)
                all_findings.extend(hazards)
            except (OSError, UnicodeError) as err:
                print("Error reading %s: %s" % (file_path, err), file=sys.stderr)

        report = {
            "status": "fail" if any(f["severity"] == "block" for f in all_findings) else "pass",
            "findings": all_findings,
        }
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print("Rollout Source Scanner: %s" % report["status"])
            for f in all_findings:
                print("  [%s] %s (%s): %s" % (f["severity"], f["code"], f.get("file", ""), f["message"]))
        return 2 if report["status"] == "fail" else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
