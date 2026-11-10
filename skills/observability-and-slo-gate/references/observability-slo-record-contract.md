# Observability & SLO Record Contract

When instrumenting services, background workers, queues, or databases, remediating metric cardinality explosions, or establishing production SLO gates, save the observability architecture assessment as a persistent JSON record (`observability-slo-record.json`).

## Schema Specification (`schema_version: "1.0"`)

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "ObservabilitySloRecord",
  "type": "object",
  "required": [
    "schema_version",
    "target_service",
    "metric_cardinality_governance",
    "latency_histograms_and_quantiles",
    "w3c_context_propagation",
    "structured_logging_and_redaction",
    "slo_and_burn_rate_alerts",
    "verdict"
  ],
  "properties": {
    "schema_version": { "type": "string", "const": "1.0" },
    "target_service": {
      "type": "object",
      "required": ["service_name", "telemetry_standard", "execution_boundaries"],
      "properties": {
        "service_name": { "type": "string", "minLength": 5 },
        "telemetry_standard": {
          "type": "string",
          "enum": ["opentelemetry_w3c_dapper", "prometheus_openmetrics_w3c"]
        },
        "execution_boundaries": {
          "type": "array",
          "minItems": 2,
          "items": {
            "type": "string",
            "enum": [
              "frontend_to_http_gateway",
              "http_or_grpc_service",
              "async_message_queue_or_outbox",
              "background_worker_consumer",
              "database_client_query"
            ]
          }
        }
      }
    },
    "metric_cardinality_governance": {
      "type": "object",
      "required": [
        "dynamic_ids_banned_in_metric_labels",
        "unmatched_routes_collapsed_to_constant",
        "max_label_cardinality_product",
        "approved_low_cardinality_labels",
        "high_cardinality_routed_to_traces_and_logs"
      ],
      "properties": {
        "dynamic_ids_banned_in_metric_labels": { "type": "boolean", "const": true },
        "unmatched_routes_collapsed_to_constant": { "type": "boolean", "const": true },
        "max_label_cardinality_product": { "type": "integer", "minimum": 1, "maximum": 1000 },
        "approved_low_cardinality_labels": {
          "type": "array",
          "minItems": 2,
          "items": { "type": "string" }
        },
        "high_cardinality_routed_to_traces_and_logs": {
          "type": "array",
          "minItems": 3,
          "items": { "type": "string" }
        }
      }
    },
    "latency_histograms_and_quantiles": {
      "type": "object",
      "required": [
        "instrument_type",
        "gauge_or_average_latency_banned",
        "explicit_buckets_ms",
        "tracked_quantiles",
        "trace_exemplars_attached"
      ],
      "properties": {
        "instrument_type": {
          "type": "string",
          "enum": ["explicit_bucket_histogram", "exponential_histogram"]
        },
        "gauge_or_average_latency_banned": { "type": "boolean", "const": true },
        "explicit_buckets_ms": {
          "type": "array",
          "minItems": 5,
          "items": { "type": "number", "exclusiveMinimum": 0 }
        },
        "tracked_quantiles": {
          "type": "array",
          "minItems": 3,
          "items": { "type": "string", "enum": ["p50", "p95", "p99"] }
        },
        "trace_exemplars_attached": { "type": "boolean", "const": true }
      }
    },
    "w3c_context_propagation": {
      "type": "object",
      "required": [
        "propagation_format",
        "correlation_id_enforced",
        "async_queue_and_worker_headers_injected",
        "async_consumer_context_extracted",
        "database_query_span_propagated",
        "in_memory_trace_continuity_verified"
      ],
      "properties": {
        "propagation_format": { "type": "string", "const": "w3c_traceparent_and_tracestate" },
        "correlation_id_enforced": { "type": "boolean", "const": true },
        "async_queue_and_worker_headers_injected": { "type": "boolean", "const": true },
        "async_consumer_context_extracted": { "type": "boolean", "const": true },
        "database_query_span_propagated": { "type": "boolean", "const": true },
        "in_memory_trace_continuity_verified": { "type": "boolean", "const": true }
      }
    },
    "structured_logging_and_redaction": {
      "type": "object",
      "required": [
        "log_format",
        "raw_console_log_banned",
        "mandatory_correlation_fields",
        "redacted_sensitive_keys"
      ],
      "properties": {
        "log_format": { "type": "string", "const": "structured_json" },
        "raw_console_log_banned": { "type": "boolean", "const": true },
        "mandatory_correlation_fields": {
          "type": "array",
          "minItems": 3,
          "items": { "type": "string" }
        },
        "redacted_sensitive_keys": {
          "type": "array",
          "minItems": 3,
          "items": { "type": "string" }
        }
      }
    },
    "slo_and_burn_rate_alerts": {
      "type": "object",
      "required": [
        "availability_target_percent",
        "latency_p95_target_ms",
        "latency_p99_target_ms",
        "fast_burn_multi_window",
        "slow_burn_multi_window"
      ],
      "properties": {
        "availability_target_percent": { "type": "number", "minimum": 90, "maximum": 99.999 },
        "latency_p95_target_ms": { "type": "number", "exclusiveMinimum": 0 },
        "latency_p99_target_ms": { "type": "number", "exclusiveMinimum": 0 },
        "fast_burn_multi_window": {
          "type": "object",
          "required": ["burn_rate_multiplier", "long_window", "short_window", "action"],
          "properties": {
            "burn_rate_multiplier": { "type": "number", "minimum": 10 },
            "long_window": { "type": "string" },
            "short_window": { "type": "string" },
            "action": { "type": "string", "enum": ["page_and_halt_rollout", "page_oncall"] }
          }
        },
        "slow_burn_multi_window": {
          "type": "object",
          "required": ["burn_rate_multiplier", "long_window", "short_window", "action"],
          "properties": {
            "burn_rate_multiplier": { "type": "number", "minimum": 1 },
            "long_window": { "type": "string" },
            "short_window": { "type": "string" },
            "action": { "type": "string", "enum": ["page_oncall", "open_remediation_ticket"] }
          }
        }
      }
    },
    "verdict": {
      "type": "object",
      "required": ["action", "rationale", "revisit_triggers"],
      "properties": {
        "action": { "type": "string", "enum": ["proceed", "pause", "refuse"] },
        "rationale": { "type": "string", "minLength": 20 },
        "revisit_triggers": {
          "type": "array",
          "minItems": 1,
          "items": { "type": "string" }
        }
      }
    }
  }
}
```

## Audit Tooling

Validate Observability & SLO records or scan instrumented source files (`--source`) for high-cardinality metric labels (`user_id`, `request_id`, `trace_id`, `order_id`, `email`, raw `req.url` in metrics), Gauge latency anti-patterns, raw `console.log` calls, and missing `traceparent` propagation using:

```bash
python3 scripts/observability_guard.py audit <record.json> [--source <service_file.ts>] --json
# or via CLI:
npx anti-slop-engineering observability audit <record.json> [--source <service_file.ts>] --json
```

Exit codes:
- `0`: Structurally compliant Observability & SLO record (low-cardinality metric labels $\le 1,000$, P50/P95/P99 Histograms with Exemplars, W3C `traceparent` + `correlation_id` across queues/workers/DB, trace-correlated JSON logs with secret redaction, Multi-Window Burn-Rate SLOs, and zero telemetry hazards in `--source`).
- `1`: JSON parsing or file access failure.
- `2`: Validation findings detected in the record or `--source` file.
