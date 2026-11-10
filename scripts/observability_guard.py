#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Check Observability & SLO records for Google Monarch & Dapper compliance.

Audits both JSON assessment records against the ObservabilitySloRecord schema
and source code files (--source) for metric cardinality explosions, gauge-averaged
latencies, broken async W3C trace context propagation, and unstructured logging.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

BANNED_HIGH_CARDINALITY_KEYS = {
    "user_id",
    "userid",
    "app.user_id",
    "customer_id",
    "customerid",
    "account_id",
    "accountid",
    "request_id",
    "requestid",
    "http.request_id",
    "trace_id",
    "traceid",
    "span_id",
    "spanid",
    "correlation_id",
    "correlationid",
    "order_id",
    "orderid",
    "app.order_id",
    "session_id",
    "sessionid",
    "email",
    "ip",
    "ip_address",
    "client_ip",
    "idempotency_key",
    "app.idempotency_key",
    "url",
    "req.url",
    "raw_url",
    "error.message",
}

VALID_TELEMETRY_STANDARDS = {
    "opentelemetry_w3c_dapper",
    "google_monarch_dapper_otel",
    "prometheus_openmetrics_w3c",
}

VALID_EXECUTION_BOUNDARIES = {
    "frontend_to_http_gateway",
    "http_or_grpc_service",
    "async_message_queue_or_outbox",
    "background_worker_consumer",
    "database_client_query",
}

VALID_INSTRUMENT_TYPES = {
    "explicit_bucket_histogram",
    "exponential_histogram",
}

VALID_VERDICT_ACTIONS = {"proceed", "pause", "refuse"}


def filled(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def choice(value: Any, choices: Set[str]) -> bool:
    return isinstance(value, str) and value in choices


def check_target_service(record: Dict[str, Any], require) -> None:
    svc = record.get("target_service")
    require(isinstance(svc, dict), "INVALID_TARGET_SERVICE", "target_service must be a dictionary")
    if not isinstance(svc, dict):
        return

    name = svc.get("service_name")
    require(filled(name) and len(str(name).strip()) >= 5,
            "INVALID_SERVICE_NAME", "target_service.service_name must be a string of at least 5 characters")

    std = svc.get("telemetry_standard")
    require(choice(std, VALID_TELEMETRY_STANDARDS),
            "INVALID_TELEMETRY_STANDARD",
            f"target_service.telemetry_standard must be one of {sorted(VALID_TELEMETRY_STANDARDS)}")

    boundaries = svc.get("execution_boundaries")
    require(isinstance(boundaries, list) and len(boundaries) >= 2,
            "INVALID_EXECUTION_BOUNDARIES", "target_service.execution_boundaries must contain at least 2 boundaries")
    if isinstance(boundaries, list):
        for b in boundaries:
            require(choice(b, VALID_EXECUTION_BOUNDARIES),
                    "INVALID_BOUNDARY_ITEM",
                    f"Unknown boundary '{b}'; must be one of {sorted(VALID_EXECUTION_BOUNDARIES)}")


def check_metric_cardinality(record: Dict[str, Any], require) -> None:
    card = record.get("metric_cardinality_governance")
    require(isinstance(card, dict), "INVALID_METRIC_CARDINALITY", "metric_cardinality_governance must be a dictionary")
    if not isinstance(card, dict):
        return

    banned = card.get("dynamic_ids_banned_in_metric_labels")
    require(banned is True, "DYNAMIC_IDS_NOT_BANNED",
            "metric_cardinality_governance.dynamic_ids_banned_in_metric_labels must be true")

    unmatched = card.get("unmatched_routes_collapsed_to_constant")
    require(unmatched is True, "UNMATCHED_ROUTES_NOT_COLLAPSED",
            "metric_cardinality_governance.unmatched_routes_collapsed_to_constant must be true")

    max_prod = card.get("max_label_cardinality_product")
    require(isinstance(max_prod, int) and 1 <= max_prod <= 1000,
            "INVALID_CARDINALITY_PRODUCT",
            "metric_cardinality_governance.max_label_cardinality_product must be an integer between 1 and 1000")

    approved = card.get("approved_low_cardinality_labels")
    require(isinstance(approved, list) and len(approved) >= 2,
            "INVALID_APPROVED_LABELS",
            "metric_cardinality_governance.approved_low_cardinality_labels must contain at least 2 low-cardinality keys")
    if isinstance(approved, list):
        for label in approved:
            low = str(label).lower().strip()
            require(low not in BANNED_HIGH_CARDINALITY_KEYS,
                    "HIGH_CARDINALITY_LABEL_IN_METRIC",
                    f"Label '{label}' is a high-cardinality attribute forbidden in TSDB metric labels")

    routed = card.get("high_cardinality_routed_to_traces_and_logs")
    require(isinstance(routed, list) and len(routed) >= 3,
            "INSUFFICIENT_ROUTED_HIGH_CARDINALITY",
            "metric_cardinality_governance.high_cardinality_routed_to_traces_and_logs must specify at least 3 high-cardinality fields routed to traces/logs")


def check_latency_histograms(record: Dict[str, Any], require) -> None:
    hist = record.get("latency_histograms_and_quantiles")
    require(isinstance(hist, dict), "INVALID_LATENCY_HISTOGRAMS", "latency_histograms_and_quantiles must be a dictionary")
    if not isinstance(hist, dict):
        return

    inst = hist.get("instrument_type")
    require(choice(inst, VALID_INSTRUMENT_TYPES),
            "INVALID_INSTRUMENT_TYPE",
            f"latency_histograms_and_quantiles.instrument_type must be one of {sorted(VALID_INSTRUMENT_TYPES)}")

    gauge_banned = hist.get("gauge_or_average_latency_banned")
    require(gauge_banned is True, "GAUGE_LATENCY_NOT_BANNED",
            "latency_histograms_and_quantiles.gauge_or_average_latency_banned must be true")

    buckets = hist.get("explicit_buckets_ms")
    require(isinstance(buckets, list) and len(buckets) >= 5,
            "INSUFFICIENT_HISTOGRAM_BUCKETS",
            "latency_histograms_and_quantiles.explicit_buckets_ms must contain at least 5 calibrated bucket boundaries")
    if isinstance(buckets, list):
        prev = 0.0
        for b in buckets:
            require(isinstance(b, (int, float)) and b > prev,
                    "NON_MONOTONIC_BUCKETS",
                    f"Bucket '{b}' is non-positive or not strictly ascending (previous was {prev})")
            if isinstance(b, (int, float)):
                prev = float(b)

    quantiles = hist.get("tracked_quantiles")
    require(isinstance(quantiles, list) and set(quantiles) >= {"p50", "p95", "p99"},
            "MISSING_MANDATORY_QUANTILES",
            "latency_histograms_and_quantiles.tracked_quantiles must include 'p50', 'p95', and 'p99'")

    exemplars = hist.get("trace_exemplars_attached")
    require(exemplars is True, "EXEMPLARS_NOT_ATTACHED",
            "latency_histograms_and_quantiles.trace_exemplars_attached must be true")


def check_red_and_use_metrics(record: Dict[str, Any], require) -> None:
    # RED & USE metrics block
    red_use = record.get("red_and_use_metrics")
    if red_use is None:
        return
    require(isinstance(red_use, dict), "INVALID_RED_USE_METRICS", "red_and_use_metrics must be a dictionary")
    if not isinstance(red_use, dict):
        return

    red_enabled = red_use.get("red_endpoint_metrics_enabled")
    require(red_enabled is True, "RED_METRICS_DISABLED",
            "red_and_use_metrics.red_endpoint_metrics_enabled must be true")

    use_enabled = red_use.get("use_resource_metrics_enabled")
    require(use_enabled is True, "USE_METRICS_DISABLED",
            "red_and_use_metrics.use_resource_metrics_enabled must be true")

    monitored = red_use.get("monitored_resources")
    require(isinstance(monitored, list) and len(monitored) >= 2,
            "INSUFFICIENT_MONITORED_RESOURCES",
            "red_and_use_metrics.monitored_resources must list at least 2 resources (e.g. cpu, memory, connection_pool, queue)")
    if isinstance(monitored, list):
        for res in monitored:
            if isinstance(res, dict):
                require(all(k in res for k in ("resource", "utilization", "saturation", "errors")),
                        "INVALID_RESOURCE_USE_ENTRY",
                        f"Resource entry '{res.get('resource')}' must specify utilization, saturation, and errors metrics")


def check_w3c_context_propagation(record: Dict[str, Any], require) -> None:
    prop = record.get("w3c_context_propagation")
    require(isinstance(prop, dict), "INVALID_W3C_PROPAGATION", "w3c_context_propagation must be a dictionary")
    if not isinstance(prop, dict):
        return

    fmt = prop.get("propagation_format")
    require(fmt == "w3c_traceparent_and_tracestate", "INVALID_PROPAGATION_FORMAT",
            "w3c_context_propagation.propagation_format must be 'w3c_traceparent_and_tracestate'")

    require(prop.get("correlation_id_enforced") is True, "CORRELATION_ID_NOT_ENFORCED",
            "w3c_context_propagation.correlation_id_enforced must be true")

    require(prop.get("async_queue_and_worker_headers_injected") is True, "QUEUE_HEADERS_NOT_INJECTED",
            "w3c_context_propagation.async_queue_and_worker_headers_injected must be true")

    require(prop.get("async_consumer_context_extracted") is True, "CONSUMER_CONTEXT_NOT_EXTRACTED",
            "w3c_context_propagation.async_consumer_context_extracted must be true")

    require(prop.get("database_query_span_propagated") is True, "DATABASE_SPAN_NOT_PROPAGATED",
            "w3c_context_propagation.database_query_span_propagated must be true")

    require(prop.get("in_memory_trace_continuity_verified") is True, "TRACE_CONTINUITY_NOT_VERIFIED",
            "w3c_context_propagation.in_memory_trace_continuity_verified must be true")


def check_structured_logging(record: Dict[str, Any], require) -> None:
    log = record.get("structured_logging_and_redaction")
    require(isinstance(log, dict), "INVALID_STRUCTURED_LOGGING", "structured_logging_and_redaction must be a dictionary")
    if not isinstance(log, dict):
        return

    fmt = log.get("log_format")
    require(fmt == "structured_json", "INVALID_LOG_FORMAT",
            "structured_logging_and_redaction.log_format must be 'structured_json'")

    require(log.get("raw_console_log_banned") is True, "RAW_CONSOLE_LOG_NOT_BANNED",
            "structured_logging_and_redaction.raw_console_log_banned must be true")

    fields = log.get("mandatory_correlation_fields")
    require(isinstance(fields, list) and len(fields) >= 3,
            "INSUFFICIENT_CORRELATION_FIELDS",
            "structured_logging_and_redaction.mandatory_correlation_fields must list at least 3 fields (e.g. trace_id, span_id, correlation_id)")

    redacted = log.get("redacted_sensitive_keys")
    require(isinstance(redacted, list) and len(redacted) >= 3,
            "INSUFFICIENT_REDACTED_KEYS",
            "structured_logging_and_redaction.redacted_sensitive_keys must list at least 3 sensitive keys")


def check_slo_and_burn_rate(record: Dict[str, Any], require) -> None:
    slo = record.get("slo_and_burn_rate_alerts")
    require(isinstance(slo, dict), "INVALID_SLO_ALERTS", "slo_and_burn_rate_alerts must be a dictionary")
    if not isinstance(slo, dict):
        return

    avail = slo.get("availability_target_percent")
    require(isinstance(avail, (int, float)) and 90.0 <= avail < 100.0,
            "INVALID_AVAILABILITY_TARGET",
            "slo_and_burn_rate_alerts.availability_target_percent must be a float between 90.0 and 99.999")

    p95 = slo.get("latency_p95_target_ms")
    require(isinstance(p95, (int, float)) and p95 > 0,
            "INVALID_P95_TARGET", "slo_and_burn_rate_alerts.latency_p95_target_ms must be > 0")

    p99 = slo.get("latency_p99_target_ms")
    require(isinstance(p99, (int, float)) and p99 > (p95 or 0),
            "INVALID_P99_TARGET", "slo_and_burn_rate_alerts.latency_p99_target_ms must be greater than latency_p95_target_ms")

    fast = slo.get("fast_burn_multi_window")
    require(isinstance(fast, dict), "INVALID_FAST_BURN", "slo_and_burn_rate_alerts.fast_burn_multi_window must be a dictionary")
    if isinstance(fast, dict):
        mult = fast.get("burn_rate_multiplier")
        require(isinstance(mult, (int, float)) and mult >= 10.0,
                "LOW_FAST_BURN_MULTIPLIER", "fast_burn_multi_window.burn_rate_multiplier must be >= 10.0")
        require(filled(fast.get("long_window")) and filled(fast.get("short_window")),
                "MISSING_FAST_BURN_WINDOWS", "fast_burn_multi_window requires long_window and short_window")
        require(fast.get("action") in ("page_and_halt_rollout", "page_oncall"),
                "INVALID_FAST_BURN_ACTION", "fast_burn_multi_window.action must page or halt rollout")

    slow = slo.get("slow_burn_multi_window")
    require(isinstance(slow, dict), "INVALID_SLOW_BURN", "slo_and_burn_rate_alerts.slow_burn_multi_window must be a dictionary")
    if isinstance(slow, dict):
        mult = slow.get("burn_rate_multiplier")
        require(isinstance(mult, (int, float)) and mult >= 1.0,
                "LOW_SLOW_BURN_MULTIPLIER", "slow_burn_multi_window.burn_rate_multiplier must be >= 1.0")
        require(filled(slow.get("long_window")) and filled(slow.get("short_window")),
                "MISSING_SLOW_BURN_WINDOWS", "slow_burn_multi_window requires long_window and short_window")
        require(slow.get("action") in ("open_remediation_ticket", "page_oncall"),
                "INVALID_SLOW_BURN_ACTION", "slow_burn_multi_window.action must open ticket or page")

    non_impact = slo.get("non_impact_alerts_banned")
    if non_impact is not None:
        require(non_impact is True, "NON_IMPACT_ALERTS_NOT_BANNED",
                "slo_and_burn_rate_alerts.non_impact_alerts_banned must be true")


def check_verdict(record: Dict[str, Any], require) -> None:
    verdict = record.get("verdict")
    require(isinstance(verdict, dict), "INVALID_VERDICT", "verdict must be a dictionary")
    if not isinstance(verdict, dict):
        return

    act = verdict.get("action")
    require(choice(act, VALID_VERDICT_ACTIONS),
            "INVALID_VERDICT_ACTION", f"verdict.action must be one of {sorted(VALID_VERDICT_ACTIONS)}")

    rat = verdict.get("rationale")
    require(filled(rat) and len(str(rat).strip()) >= 20,
            "INVALID_VERDICT_RATIONALE", "verdict.rationale must be at least 20 characters")

    triggers = verdict.get("revisit_triggers")
    require(isinstance(triggers, list) and len(triggers) >= 1,
            "INVALID_REVISIT_TRIGGERS", "verdict.revisit_triggers must contain at least 1 trigger")


def scan_source_code(source_path: Path) -> List[Dict[str, Any]]:
    """Statically scans source code for observability & SLO anti-patterns."""
    findings = []
    if not source_path.exists():
        findings.append({
            "code": "SOURCE_NOT_FOUND",
            "message": f"Source file not found: {source_path}",
            "line": 0,
        })
        return findings

    try:
        content = source_path.read_text(encoding="utf-8")
    except Exception as e:
        findings.append({
            "code": "SOURCE_READ_ERROR",
            "message": f"Could not read source file: {e}",
            "line": 0,
        })
        return findings

    lines = content.splitlines()

    # Regex patterns for static hazard detection
    banned_label_re = re.compile(
        r"""(?:counter\.add|histogram\.record|labels\s*\()\s*[^)]*?\b(?:user_?id|account_?id|customer_?id|request_?id|trace_?id|span_?id|order_?id|email|client_?ip|req\.url|req\.path)\b""",
        re.IGNORECASE,
    )
    gauge_avg_re = re.compile(
        r"""(?:gauge\.set|gauge\.record)\s*\(\s*(?:avg|average|p99|p95|mean)""",
        re.IGNORECASE,
    )
    raw_console_re = re.compile(
        r"""\bconsole\.(?:log|error|warn|info|debug)\s*\(""",
    )
    raw_logger_error_re = re.compile(
        r"""\blogger\.error\s*\(\s*(?:['"`][^'"`]+['"`]\s*\+\s*\w+|['"`][^'"`]+['"`]\s*\))""",
    )
    noisy_alert_re = re.compile(
        r"""(?:alert|rule)\s*:\s*.*(?:cpu\s*>\s*80|memory\s*>\s*85|disk\s*>\s*90).*""",
        re.IGNORECASE,
    )

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("#") or stripped.startswith("*"):
            continue

        if banned_label_re.search(line):
            findings.append({
                "code": "HIGH_CARDINALITY_METRIC_CALL",
                "message": f"Detected high-cardinality label passed directly into metric recorder: {stripped[:80]}",
                "line": idx,
            })

        if gauge_avg_re.search(line):
            findings.append({
                "code": "GAUGE_AVERAGED_LATENCY",
                "message": f"Detected gauge used to record latency average or percentile: {stripped[:80]}",
                "line": idx,
            })

        if raw_console_re.search(line):
            findings.append({
                "code": "RAW_CONSOLE_LOGGING",
                "message": f"Detected raw console.* call in service path: {stripped[:80]}",
                "line": idx,
            })

        if raw_logger_error_re.search(line):
            findings.append({
                "code": "UNSTRUCTURED_LOGGER_ERROR",
                "message": f"Detected unstructured logger.error without trace/context correlation: {stripped[:80]}",
                "line": idx,
            })

        if noisy_alert_re.search(line):
            findings.append({
                "code": "NON_IMPACT_RESOURCE_ALERT",
                "message": f"Detected threshold-only resource alert without user impact correlation: {stripped[:80]}",
                "line": idx,
            })

    return findings


def audit(record: Dict[str, Any], source_path: Optional[Path] = None) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []

    def require(condition: bool, code: str, message: str) -> None:
        if not condition:
            findings.append({"code": code, "message": message})

    check_target_service(record, require)
    check_metric_cardinality(record, require)
    check_latency_histograms(record, require)
    check_red_and_use_metrics(record, require)
    check_w3c_context_propagation(record, require)
    check_structured_logging(record, require)
    check_slo_and_burn_rate(record, require)
    check_verdict(record, require)

    source_findings = []
    if source_path:
        source_findings = scan_source_code(source_path)
        findings.extend(source_findings)

    status = "complete" if not findings else "incomplete"
    verdict_action = record.get("verdict", {}).get("action", "unknown") if isinstance(record.get("verdict"), dict) else "unknown"

    return {
        "record_status": status,
        "verdict_action": verdict_action,
        "machine_check_only": True,
        "findings": findings,
        "source_scanned": str(source_path) if source_path else None,
        "source_findings_count": len(source_findings),
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit Observability & SLO records for Google Monarch & Dapper compliance."
    )
    parser.add_argument("command", nargs="?", default="audit", choices=["audit"])
    parser.add_argument("record", help="Path to observability-slo-record.json")
    parser.add_argument("--source", help="Optional source file to scan for telemetry anti-patterns")
    parser.add_argument("--json", action="store_true", help="Output audit results as JSON")

    args = parser.parse_args()

    record_path = Path(args.record)
    if not record_path.exists():
        err = {"error": f"Record file not found: {record_path}"}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"Error: Record file not found: {record_path}", file=sys.stderr)
        return 1

    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
    except Exception as e:
        err = {"error": f"Invalid JSON in record file: {e}"}
        if args.json:
            print(json.dumps(err, indent=2))
        else:
            print(f"Error: Invalid JSON in record file: {e}", file=sys.stderr)
        return 1

    source_path = Path(args.source) if args.source else None
    result = audit(data, source_path)

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"Observability & SLO Record Status: {result['record_status'].upper()}")
        print(f"Verdict Action: {result['verdict_action']}")
        if result["source_scanned"]:
            print(f"Source Scanned: {result['source_scanned']} ({result['source_findings_count']} issues)")
        if result["findings"]:
            print(f"\nFindings ({len(result['findings'])}):")
            for f in result["findings"]:
                loc = f" [line {f['line']}]" if "line" in f else ""
                print(f"  - [{f['code']}]{loc} {f['message']}")

    if result["record_status"] == "complete" and result["verdict_action"] in ("proceed", "pause"):
        return 0
    return 2


if __name__ == "__main__":
    sys.exit(main())
