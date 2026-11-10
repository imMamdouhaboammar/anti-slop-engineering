#!/usr/bin/env python3
"""Check zero-downtime migration records and SQL files for Expand-Migrate-Contract, lock-free DDL, and N/N-1 wire compatibility."""

import argparse
import json
import re
import sys
from pathlib import Path

VALID_PHASES = {"expand", "migrate", "contract"}
VALID_ENGINES = {"postgresql", "mysql", "spanner", "sqlite_local"}
VALID_CONSTRAINT_STRATEGIES = {
    "not_valid_then_validate",
    "online_inplace_lock_none",
    "none_required",
}
VALID_WIRE_FORMATS = {"json", "protobuf", "graphql", "sql_only"}
VALID_PINNING_STRATEGIES = {
    "additive_tolerant_reader",
    "stripe_date_header_gate",
    "dual_endpoint_v1_v2",
    "internal_rolling_only",
}


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


def check_evolution_strategy(record, require):
    strategy = record.get("evolution_strategy")
    require(isinstance(strategy, dict), "INVALID_EVOLUTION_STRATEGY",
            "evolution_strategy must be a dictionary")
    if not isinstance(strategy, dict):
        return

    require(strategy.get("pattern") == "expand_migrate_contract",
            "INVALID_EVOLUTION_PATTERN",
            "evolution_strategy.pattern must be 'expand_migrate_contract'")
    require(choice(strategy.get("current_phase"), VALID_PHASES),
            "INVALID_CURRENT_PHASE",
            "evolution_strategy.current_phase must be expand, migrate, or contract")

    phases = strategy.get("phases")
    require(isinstance(phases, dict), "MISSING_PHASES",
            "evolution_strategy.phases must define expand, migrate, and contract")
    if not isinstance(phases, dict):
        return

    expand = phases.get("expand")
    require(isinstance(expand, dict)
            and filled(expand.get("description"), 15)
            and isinstance(expand.get("dual_write_enabled"), bool)
            and expand.get("n_minus_1_compatible") is True,
            "INVALID_EXPAND_PHASE",
            "phases.expand needs description (>=15 chars), boolean dual_write_enabled, and n_minus_1_compatible=true")

    migrate = phases.get("migrate")
    require(isinstance(migrate, dict)
            and filled(migrate.get("description"), 15)
            and filled(migrate.get("read_cutover_strategy"), 10)
            and filled(migrate.get("verification_gate"), 10),
            "INVALID_MIGRATE_PHASE",
            "phases.migrate needs description (>=15 chars), read_cutover_strategy, and verification_gate")

    contract = phases.get("contract")
    require(isinstance(contract, dict)
            and filled(contract.get("description"), 15)
            and filled(contract.get("drain_prerequisite"), 10),
            "INVALID_CONTRACT_PHASE",
            "phases.contract needs description (>=15 chars) and drain_prerequisite")


def check_ddl_safety(record, require):
    ddl = record.get("ddl_safety")
    require(isinstance(ddl, dict), "INVALID_DDL_SAFETY", "ddl_safety must be a dictionary")
    if not isinstance(ddl, dict):
        return

    require(choice(ddl.get("engine"), VALID_ENGINES), "INVALID_DB_ENGINE",
            "ddl_safety.engine must be one of: %s" % ", ".join(sorted(VALID_ENGINES)))

    lock_timeout = ddl.get("lock_timeout_ms")
    require(isinstance(lock_timeout, int) and 100 <= lock_timeout <= 5000,
            "UNSAFE_LOCK_TIMEOUT",
            "ddl_safety.lock_timeout_ms must be an integer between 100 and 5000")

    stmt_timeout = ddl.get("statement_timeout_ms")
    require(isinstance(stmt_timeout, int) and 1000 <= stmt_timeout <= 60000,
            "UNSAFE_STATEMENT_TIMEOUT",
            "ddl_safety.statement_timeout_ms must be an integer between 1000 and 60000")

    require(ddl.get("concurrent_index_creation") is True,
            "BLOCKING_INDEX_CREATION",
            "ddl_safety.concurrent_index_creation must be true")

    require(choice(ddl.get("constraint_validation_strategy"), VALID_CONSTRAINT_STRATEGIES),
            "INVALID_CONSTRAINT_STRATEGY",
            "ddl_safety.constraint_validation_strategy must be one of: %s"
            % ", ".join(sorted(VALID_CONSTRAINT_STRATEGIES)))

    require(ddl.get("prohibited_operations_absent") is True,
            "PROHIBITED_DDL_PRESENT",
            "ddl_safety.prohibited_operations_absent must be true")


def check_backfill_plan(record, require):
    backfill = record.get("backfill_plan")
    require(isinstance(backfill, dict), "INVALID_BACKFILL_PLAN",
            "backfill_plan must be a dictionary")
    if not isinstance(backfill, dict):
        return

    require(backfill.get("decoupled_from_ddl") is True,
            "COUPLED_DDL_BACKFILL",
            "backfill_plan.decoupled_from_ddl must be true (never run bulk UPDATE inside DDL)")

    batch_size = backfill.get("batch_size")
    require(isinstance(batch_size, int) and 1 <= batch_size <= 5000,
            "UNBOUNDED_BACKFILL_BATCH",
            "backfill_plan.batch_size must be an integer between 1 and 5000")

    throttle = backfill.get("throttle_delay_ms")
    require(isinstance(throttle, int) and throttle >= 10,
            "MISSING_BACKFILL_THROTTLE",
            "backfill_plan.throttle_delay_ms must be an integer >= 10")

    require(backfill.get("idempotent") is True,
            "NON_IDEMPOTENT_BACKFILL",
            "backfill_plan.idempotent must be true")


def check_wire_compatibility(record, require):
    wire = record.get("wire_compatibility")
    require(isinstance(wire, dict), "INVALID_WIRE_COMPATIBILITY",
            "wire_compatibility must be a dictionary")
    if not isinstance(wire, dict):
        return

    formats = wire.get("formats")
    require(isinstance(formats, list) and bool(formats)
            and all(choice(fmt, VALID_WIRE_FORMATS) for fmt in formats),
            "INVALID_WIRE_FORMATS",
            "wire_compatibility.formats must be a non-empty list of valid wire formats")

    require(wire.get("backward_compatible_n_reads_n_minus_1") is True,
            "BACKWARD_WIRE_INCOMPATIBLE",
            "wire_compatibility.backward_compatible_n_reads_n_minus_1 must be true")

    require(wire.get("forward_compatible_n_minus_1_reads_n") is True,
            "FORWARD_WIRE_INCOMPATIBLE",
            "wire_compatibility.forward_compatible_n_minus_1_reads_n must be true")

    require(filled(wire.get("active_client_horizon"), 5),
            "MISSING_CLIENT_HORIZON",
            "wire_compatibility.active_client_horizon must specify the active client window")

    require(wire.get("protobuf_reserved_enforced") is True,
            "PROTOBUF_RESERVED_MISSING",
            "wire_compatibility.protobuf_reserved_enforced must be true")

    require(choice(wire.get("version_pinning_strategy"), VALID_PINNING_STRATEGIES),
            "INVALID_PINNING_STRATEGY",
            "wire_compatibility.version_pinning_strategy must be one of: %s"
            % ", ".join(sorted(VALID_PINNING_STRATEGIES)))


def check_rollback_safety(record, require):
    rollback = record.get("rollback_safety")
    require(isinstance(rollback, dict), "INVALID_ROLLBACK_SAFETY",
            "rollback_safety must be a dictionary")
    if not isinstance(rollback, dict):
        return

    require(rollback.get("n_minus_1_binary_safe_without_db_rollback") is True,
            "UNSAFE_BINARY_ROLLBACK",
            "rollback_safety.n_minus_1_binary_safe_without_db_rollback must be true")

    require(filled(rollback.get("rehearsal_evidence"), 15),
            "MISSING_REHEARSAL_EVIDENCE",
            "rollback_safety.rehearsal_evidence must be at least 15 characters")


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


def scan_sql_hazards(sql_text):
    findings = []
    require = lambda ok, code, message: _record_finding(findings, ok, code, message, "block")

    cleaned = re.sub(r"--[^\n]*", "", sql_text)
    cleaned = re.sub(r"/\*.*?\*/", "", cleaned, flags=re.DOTALL)

    has_ddl = bool(re.search(r"\b(ALTER\s+TABLE|CREATE\s+(?:UNIQUE\s+)?INDEX|DROP\s+INDEX|DROP\s+TABLE)\b",
                             cleaned, re.IGNORECASE))
    if has_ddl:
        has_lock_timeout = bool(re.search(r"\b(lock_timeout|lock_wait_timeout)\b", cleaned, re.IGNORECASE))
        require(has_lock_timeout, "SQL_MISSING_LOCK_TIMEOUT",
                "DDL migration is missing an explicit SET [LOCAL] lock_timeout / lock_wait_timeout guard")

    for match in re.finditer(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b(?P<rest>[^;]*);", cleaned, re.IGNORECASE):
        stmt = match.group(0)
        require(bool(re.search(r"\bCONCURRENTLY\b", stmt, re.IGNORECASE)),
                "SQL_BLOCKING_CREATE_INDEX",
                "CREATE INDEX without CONCURRENTLY blocks all table writes in PostgreSQL")

    in_tx = bool(re.search(r"\bBEGIN\b", cleaned, re.IGNORECASE)) and bool(
        re.search(r"\bCOMMIT\b", cleaned, re.IGNORECASE))
    has_concurrent_idx = bool(re.search(r"\b(CREATE|DROP)\s+(?:UNIQUE\s+)?INDEX\s+CONCURRENTLY\b",
                                        cleaned, re.IGNORECASE))
    require(not (in_tx and has_concurrent_idx), "SQL_CONCURRENT_INDEX_IN_TX",
            "CREATE/DROP INDEX CONCURRENTLY cannot execute inside a BEGIN ... COMMIT transaction block")

    require(not re.search(r"\bRENAME\s+(?:COLUMN|TO)\b", cleaned, re.IGNORECASE),
            "SQL_DIRECT_RENAME",
            "Direct RENAME COLUMN / RENAME TABLE breaks running Version N-1 application pods; use Expand-Migrate-Contract")

    for match in re.finditer(r"\bADD\s+CONSTRAINT\s+\S+\s+(?:FOREIGN\s+KEY|CHECK)\b(?P<rest>[^;]*);",
                             cleaned, re.IGNORECASE):
        stmt = match.group(0)
        require(bool(re.search(r"\bNOT\s+VALID\b", stmt, re.IGNORECASE)),
                "SQL_UNVALIDATED_CONSTRAINT_LOCK",
                "ADD CONSTRAINT FOREIGN KEY / CHECK without NOT VALID scans the entire table under an exclusive lock")

    return findings


def audit(record, sql_text=None):
    findings = []
    require = lambda ok, code, message, severity="block": _record_finding(findings, ok, code, message, severity)

    require(filled(record.get("goal"), 10), "MISSING_GOAL",
            "Record must specify the migration and contract evolution goal")
    action = check_verdict(record, require)

    if action in {"proceed", "pause"}:
        check_evolution_strategy(record, require)
        check_ddl_safety(record, require)
        check_backfill_plan(record, require)
        check_wire_compatibility(record, require)
        check_rollback_safety(record, require)

    if sql_text is not None:
        findings.extend(scan_sql_hazards(sql_text))

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
    parser.add_argument("--sql", type=Path, default=None,
                        help="Optional SQL migration file to scan for blocking DDL hazards")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    try:
        record = json.loads(args.record.read_text(encoding="utf-8"))
        if not isinstance(record, dict):
            raise ValueError("Record root must be a JSON object")
        sql_text = args.sql.read_text(encoding="utf-8") if args.sql else None
        result = audit(record, sql_text=sql_text)
    except (OSError, UnicodeError, ValueError) as error:
        print("Invalid zero-downtime migration record: %s" % error, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("Zero-Downtime Migration record: %s (%s)" % (result["record_status"], result["verdict_action"]))
        for item in result["findings"]:
            print("  [%s] %s: %s" % (item["severity"], item["code"], item["message"]))
        print("Structural audit only: live replica lag and multi-version shadow traffic must be verified independently.")

    return 2 if result["record_status"] == "incomplete" else 0


if __name__ == "__main__":
    sys.exit(main())
