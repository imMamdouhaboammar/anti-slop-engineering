#!/usr/bin/env python3
"""Check API Ergonomics and Contract Governance records and source code for Microsoft TypeScript & Stripe DX rigor."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_INTERFACE_TYPES = {
    "public_sdk",
    "internal_service_client",
    "cli_tool",
    "domain_module",
}
VALID_LANGUAGES = {"typescript", "python", "go", "rust"}
VALID_BACKOFF_STRATEGIES = {
    "exponential_full_jitter",
    "exponential_equal_jitter",
    "decorrelated_jitter",
}
VALID_COMPLIANCE = {"RFC_9457", "RFC_7807"}
VALID_VERDICTS = {"proceed", "pause", "refuse"}


def filled(value, min_len=1, depth=0, max_depth=100):
    if depth > max_depth:
        return False
    return isinstance(value, str) and len(value.strip()) >= min_len


def choice(value, values):
    return isinstance(value, str) and value in values


def _record_finding(findings, ok, code, message, severity="block", depth=0, max_depth=100):
    if depth > max_depth:
        return
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def check_target_interface(record, require):
    target = record.get("target_interface")
    require(isinstance(target, dict), "INVALID_TARGET_INTERFACE", "target_interface must be a dictionary")
    if not isinstance(target, dict):
        return
    require(filled(target.get("module_path"), 3),
            "MISSING_MODULE_PATH",
            "target_interface.module_path must be at least 3 characters")
    require(choice(target.get("interface_type"), VALID_INTERFACE_TYPES),
            "INVALID_INTERFACE_TYPE",
            "target_interface.interface_type must be one of: %s" % ", ".join(sorted(VALID_INTERFACE_TYPES)))
    require(choice(target.get("language"), VALID_LANGUAGES),
            "INVALID_LANGUAGE",
            "target_interface.language must be one of: %s" % ", ".join(sorted(VALID_LANGUAGES)))


def check_pit_of_success_defaults(record, require):
    pos = record.get("pit_of_success_defaults")
    require(isinstance(pos, dict), "INVALID_PIT_OF_SUCCESS", "pit_of_success_defaults must be a dictionary")
    if not isinstance(pos, dict):
        return
    require(pos.get("enabled") is True,
            "PIT_OF_SUCCESS_DISABLED",
            "pit_of_success_defaults.enabled must be true")
    timeout = pos.get("default_timeout_ms")
    require(isinstance(timeout, int) and 1000 <= timeout <= 60000,
            "INVALID_DEFAULT_TIMEOUT",
            "pit_of_success_defaults.default_timeout_ms must be an integer between 1000 and 60000 ms")
    retries = pos.get("auto_retry_max_attempts")
    require(isinstance(retries, int) and 1 <= retries <= 10,
            "INVALID_AUTO_RETRIES",
            "pit_of_success_defaults.auto_retry_max_attempts must be an integer between 1 and 10")
    require(choice(pos.get("backoff_strategy"), VALID_BACKOFF_STRATEGIES),
            "INVALID_BACKOFF_STRATEGY",
            "pit_of_success_defaults.backoff_strategy must be one of: %s" % ", ".join(sorted(VALID_BACKOFF_STRATEGIES)))
    page_limit = pos.get("default_page_limit")
    require(isinstance(page_limit, int) and 1 <= page_limit <= 100,
            "INVALID_DEFAULT_PAGE_LIMIT",
            "pit_of_success_defaults.default_page_limit must be an integer between 1 and 100")
    max_ceiling = pos.get("max_page_limit_ceiling")
    require(isinstance(max_ceiling, int) and 50 <= max_ceiling <= 1000,
            "INVALID_PAGE_CEILING",
            "pit_of_success_defaults.max_page_limit_ceiling must be an integer between 50 and 1000")
    require(pos.get("safe_tls_enforced") is True,
            "SAFE_TLS_NOT_ENFORCED",
            "pit_of_success_defaults.safe_tls_enforced must be true")


def check_illegal_states_unrepresentable(record, require):
    isu = record.get("illegal_states_unrepresentable")
    require(isinstance(isu, dict), "INVALID_ILLEGAL_STATES", "illegal_states_unrepresentable must be a dictionary")
    if not isinstance(isu, dict):
        return
    require(isu.get("discriminated_unions_enforced") is True,
            "DISCRIMINATED_UNIONS_DISABLED",
            "illegal_states_unrepresentable.discriminated_unions_enforced must be true")
    require(filled(isu.get("discriminator_field"), 2),
            "MISSING_DISCRIMINATOR_FIELD",
            "illegal_states_unrepresentable.discriminator_field must name tag field (e.g. status, kind)")
    require(isu.get("branded_types_enforced") is True,
            "BRANDED_TYPES_DISABLED",
            "illegal_states_unrepresentable.branded_types_enforced must be true to prevent parameter transposition")
    brands = isu.get("branded_type_identifiers")
    require(isinstance(brands, list) and len(brands) >= 2 and all(filled(b, 3) for b in brands),
            "INSUFFICIENT_BRANDED_IDENTIFIERS",
            "illegal_states_unrepresentable.branded_type_identifiers must declare at least 2 distinct nominal brands")
    require(isu.get("exhaustive_match_enforced") is True,
            "EXHAUSTIVE_MATCH_NOT_ENFORCED",
            "illegal_states_unrepresentable.exhaustive_match_enforced must be true; assertNever is mandatory")
    require(isu.get("zero_boolean_traps_verified") is True,
            "BOOLEAN_TRAPS_NOT_VERIFIED",
            "illegal_states_unrepresentable.zero_boolean_traps_verified must be true")


def check_progressive_disclosure(record, require):
    pd = record.get("progressive_disclosure")
    require(isinstance(pd, dict), "INVALID_PROGRESSIVE_DISCLOSURE", "progressive_disclosure must be a dictionary")
    if not isinstance(pd, dict):
        return
    require(filled(pd.get("tier_1_one_liner_facade"), 10),
            "MISSING_TIER_1_FACADE",
            "progressive_disclosure.tier_1_one_liner_facade must describe the 1-liner 80% entrypoint")
    require(pd.get("tier_2_options_bag_supported") is True,
            "TIER_2_OPTIONS_NOT_SUPPORTED",
            "progressive_disclosure.tier_2_options_bag_supported must be true")
    require(filled(pd.get("tier_3_power_escape_hatch"), 10),
            "MISSING_TIER_3_ESCAPE_HATCH",
            "progressive_disclosure.tier_3_power_escape_hatch must describe power builder or raw access")
    require(pd.get("namespace_pollution_prevented") is True,
            "NAMESPACE_POLLUTION_NOT_PREVENTED",
            "progressive_disclosure.namespace_pollution_prevented must be true")


def check_rfc9457_problem_details(record, require):
    rpd = record.get("rfc9457_problem_details")
    require(isinstance(rpd, dict), "INVALID_RFC9457_PROBLEM_DETAILS", "rfc9457_problem_details must be a dictionary")
    if not isinstance(rpd, dict):
        return
    require(choice(rpd.get("standard_compliance"), VALID_COMPLIANCE),
            "INVALID_RFC_COMPLIANCE",
            "rfc9457_problem_details.standard_compliance must be RFC_9457 or RFC_7807")
    require(filled(rpd.get("error_type_uri_prefix"), 5),
            "MISSING_ERROR_URI_PREFIX",
            "rfc9457_problem_details.error_type_uri_prefix must declare stable URI namespace")
    codes = rpd.get("deterministic_machine_codes")
    require(isinstance(codes, list) and len(codes) >= 2 and all(filled(c, 3) for c in codes),
            "INSUFFICIENT_MACHINE_CODES",
            "rfc9457_problem_details.deterministic_machine_codes must declare at least 2 deterministic codes")
    require(rpd.get("invalid_params_breakdown_supported") is True,
            "INVALID_PARAMS_NOT_SUPPORTED",
            "rfc9457_problem_details.invalid_params_breakdown_supported must be true")
    require(rpd.get("remediation_action_supported") is True,
            "REMEDIATION_ACTION_NOT_SUPPORTED",
            "rfc9457_problem_details.remediation_action_supported must be true")
    require(rpd.get("retryability_metadata_exposed") is True,
            "RETRYABILITY_NOT_EXPOSED",
            "rfc9457_problem_details.retryability_metadata_exposed must be true")


def check_verdict(record, require):
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return None
    action = verdict.get("action")
    require(choice(action, VALID_VERDICTS), "INVALID_ACTION",
            "Verdict action must be proceed, pause, or refuse")
    require(filled(verdict.get("rationale"), 20),
            "MISSING_RATIONALE", "Verdict rationale must be at least 20 characters")
    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and bool(triggers) and all(filled(t, 5) for t in triggers),
            "MISSING_REVISIT_TRIGGERS", "Verdict must declare at least one revisit trigger (>= 5 chars)")
    return action


def scan_source_hazards(source_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    # Anti-Pattern 1: Boolean parameter trap in function signatures
    boolean_trap_sig = bool(
        re.search(
            r"(?:function\s+[a-zA-Z0-9_]+\s*\([^)]*?\b[a-zA-Z0-9_]+\s*:\s*boolean\s*,\s*[a-zA-Z0-9_]+\s*:\s*boolean\b|\bdef\s+[a-zA-Z0-9_]+\s*\([^)]*?\b[a-zA-Z0-9_]+:\s*bool\s*=\s*(?:True|False)\s*,\s*[a-zA-Z0-9_]+:\s*bool)",
            source_text,
            re.IGNORECASE
        )
    )
    require(not boolean_trap_sig, "SOURCE_BOOLEAN_PARAMETER_TRAP",
            "Detected consecutive boolean parameters in function signature; replace with named option record or union literals")

    # Anti-Pattern 2: Consecutive positional boolean literals at call sites
    boolean_trap_call = bool(
        re.search(
            r"\b[a-zA-Z0-9_]+\s*\([^)]*?,\s*(?:true|false)\s*,\s*(?:true|false)\s*[,)]",
            source_text,
            re.IGNORECASE
        )
    )
    require(not boolean_trap_call, "SOURCE_BOOLEAN_CALL_TRAP",
            "Detected consecutive positional boolean literals in function call; refactor caller into named options bag")

    # Anti-Pattern 3: Bare Error throwing in public API
    bare_error_throw = bool(
        re.search(
            r"\bthrow\s+new\s+(?:Error|TypeError|RangeError)\s*\(\s*[\"'][^\"']+[\"']\s*\)",
            source_text
        )
    ) and not bool(
        re.search(r"\bclass\s+ProblemDetailsError\b", source_text)
    )
    require(not bare_error_throw, "SOURCE_BARE_ERROR_THROW",
            "Detected bare Error throwing in contract; standardize on RFC 9457 ProblemDetailsError with machine error code")

    # Anti-Pattern 4: Stringly-typed domain IDs in public method signatures
    stringly_typed_ids = bool(
        re.search(
            r"\b(?:create|update|retrieve|delete|transfer|refund)\s*\([^)]*?\b(?:userId|customerId|accountId|orderId|paymentId)\s*:\s*string\b",
            source_text
        )
    )
    require(not stringly_typed_ids, "SOURCE_STRINGLY_TYPED_IDENTIFIER",
            "Detected unbranded string for domain entity identifier; wrap raw string in nominal Branded Type (e.g. CustomerId)")

    # Anti-Pattern 5: Unbounded fetch without timeout/signal
    hanging_fetch = bool(
        re.search(
            r"\bfetch\s*\([^)]*?\)(?!\s*as\b)",
            source_text
        )
    ) and not bool(
        re.search(r"\b(?:signal|timeout|AbortSignal)\b", source_text)
    )
    require(not hanging_fetch, "SOURCE_HANGING_NETWORK_FETCH",
            "Detected fetch() call lacking AbortSignal or timeout; Pit-of-Success defaults mandate built-in timeout")

    return findings


def audit(record, source_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    check_target_interface(record, require)
    action = check_verdict(record, require)

    if action == "proceed":
        check_pit_of_success_defaults(record, require)
        check_illegal_states_unrepresentable(record, require)
        check_progressive_disclosure(record, require)
        check_rfc9457_problem_details(record, require)

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
                        help="Optional source file to scan for boolean traps, stringly IDs, bare errors, or hanging fetch")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        source_text = args.source.read_text(encoding="utf-8") if args.source else None
        result = audit(record, source_text=source_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid API Contract Governance record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("API Contract Governance record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: Branded types, discriminated unions, and progressive disclosure must be verified in test suites.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
