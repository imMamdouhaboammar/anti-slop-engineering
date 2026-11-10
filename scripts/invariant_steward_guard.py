#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Repo Memory & Invariant Steward (الذاكرة المعمارية للمنظومة).

Maintains the architectural memory of the repository by syncing approved invariants
from historical decision records into a living, compact Invariant Ledger (JSON & TOON)
read by AI agents in Gate 0, and detecting architectural drift in Git pull requests
or diffs without a formal Reassessment Trigger.
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

VALID_CATEGORIES = {
    "concurrency_and_scale",
    "security_and_auth",
    "api_contract",
    "telemetry_and_slo",
    "data_lineage",
    "rollout_and_compatibility",
    "hardware_and_perf",
    "testing_and_simulation",
    "architecture",
}

VALID_STATUSES = {"active", "superseded", "deprecated", "waived"}

VALID_REASSESSMENT_ACTIONS = {"supersede", "waive", "deprecate"}


def filled(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def choice(value: Any, choices: Set[str]) -> bool:
    return isinstance(value, str) and value in choices


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _record_finding(findings: List[Dict[str, Any]], ok: bool, code: str, message: str, severity: str = "block") -> None:
    if not ok:
        findings.append({"severity": severity, "code": code, "message": message})


def validate_invariant_item(item: Dict[str, Any], index: int, require) -> bool:
    require(isinstance(item, dict), "INVALID_INVARIANT_ITEM", f"Invariant at index {index} must be an object")
    if not isinstance(item, dict):
        return False

    inv_id = item.get("id")
    require(filled(inv_id), "MISSING_INVARIANT_ID", f"Invariant at index {index} must declare non-empty id")

    category = item.get("category")
    require(choice(category, VALID_CATEGORIES), "INVALID_CATEGORY",
            f"Invariant {inv_id or index} category must be one of: {', '.join(sorted(VALID_CATEGORIES))}")

    assertion = item.get("assertion")
    require(filled(assertion) and len(str(assertion).strip()) >= 15, "INVALID_ASSERTION",
            f"Invariant {inv_id or index} must declare an assertion >= 15 chars")

    rationale = item.get("rationale")
    require(filled(rationale) and len(str(rationale).strip()) >= 15, "INVALID_RATIONALE",
            f"Invariant {inv_id or index} must declare a rationale >= 15 chars")

    status = item.get("status")
    require(choice(status, VALID_STATUSES), "INVALID_STATUS",
            f"Invariant {inv_id or index} status must be one of: {', '.join(sorted(VALID_STATUSES))}")

    scope = item.get("enforcement_scope")
    require(isinstance(scope, dict), "INVALID_ENFORCEMENT_SCOPE",
            f"Invariant {inv_id or index} must declare an enforcement_scope dictionary")

    authority = item.get("authority")
    require(isinstance(authority, dict) and filled(authority.get("record_type")), "INVALID_AUTHORITY",
            f"Invariant {inv_id or index} must declare authority with valid record_type")

    return True


def audit_ledger(ledger_data: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    require = lambda ok, code, msg, sev="block": _record_finding(findings, ok, code, msg, sev)

    require(isinstance(ledger_data, dict), "INVALID_LEDGER_ROOT", "Ledger root must be a JSON object")
    if not isinstance(ledger_data, dict):
        return {"record_status": "incomplete", "findings": findings, "invariants_count": 0}

    invariants = ledger_data.get("invariants")
    require(isinstance(invariants, list) and len(invariants) > 0, "EMPTY_INVARIANTS",
            "Ledger must declare a non-empty 'invariants' list")

    if isinstance(invariants, list):
        seen_ids: Set[str] = set()
        for idx, inv in enumerate(invariants):
            if validate_invariant_item(inv, idx, require):
                iid = str(inv.get("id")).strip().casefold()
                require(iid not in seen_ids, "DUPLICATE_INVARIANT_ID", f"Duplicate invariant id: {inv.get('id')}")
                seen_ids.add(iid)

    status = "complete" if not findings else "incomplete"
    return {
        "record_status": status,
        "machine_check_only": True,
        "invariants_count": len(invariants) if isinstance(invariants, list) else 0,
        "findings": findings,
    }


def audit_reassessment_trigger(data: Dict[str, Any]) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    require = lambda ok, code, msg, sev="block": _record_finding(findings, ok, code, msg, sev)

    require(isinstance(data, dict), "INVALID_REASSESSMENT_ROOT", "Reassessment record must be a JSON object")
    if not isinstance(data, dict):
        return {"record_status": "incomplete", "findings": findings}

    target_id = data.get("target_invariant_id")
    require(filled(target_id), "MISSING_TARGET_INVARIANT_ID", "Must specify target_invariant_id")

    action = data.get("action")
    require(choice(action, VALID_REASSESSMENT_ACTIONS), "INVALID_REASSESSMENT_ACTION",
            f"Action must be one of: {', '.join(sorted(VALID_REASSESSMENT_ACTIONS))}")

    justification = data.get("justification")
    require(filled(justification) and len(str(justification).strip()) >= 20, "INVALID_JUSTIFICATION",
            "Reassessment justification must be at least 20 characters")

    trade_off = data.get("trade_off_delta")
    require(isinstance(trade_off, dict), "INVALID_TRADE_OFF", "trade_off_delta must be an object")
    if isinstance(trade_off, dict):
        require(filled(trade_off.get("gain")), "MISSING_GAIN", "trade_off_delta requires 'gain'")
        require(filled(trade_off.get("risk")), "MISSING_RISK", "trade_off_delta requires 'risk'")

    authority = data.get("authority")
    require(isinstance(authority, dict) and filled(authority.get("author")), "INVALID_AUTHORITY",
            "authority requires non-empty author")

    verification = data.get("verification_proof")
    require(filled(verification), "MISSING_VERIFICATION_PROOF", "Must supply verification_proof")

    status = "complete" if not findings else "incomplete"
    return {
        "record_status": status,
        "machine_check_only": True,
        "target_invariant_id": target_id,
        "action": action,
        "findings": findings,
    }


def extract_invariants_from_record(path: Path) -> List[Dict[str, Any]]:
    try:
        content = path.read_text(encoding="utf-8")
        data = json.loads(content)
    except Exception:
        return []

    if not isinstance(data, dict):
        return []

    extracted: List[Dict[str, Any]] = []
    file_sha = sha256_text(content)
    stem = path.stem.lower()

    # Direct invariant lists inside record
    if "invariants" in data and isinstance(data["invariants"], list):
        for idx, inv in enumerate(data["invariants"]):
            if isinstance(inv, dict) and filled(inv.get("assertion")):
                iid = inv.get("id") or f"INV-{stem.upper()}-{idx + 1:03d}"
                extracted.append({
                    "id": iid,
                    "category": inv.get("category", "architecture"),
                    "assertion": inv.get("assertion"),
                    "rationale": inv.get("rationale", inv.get("assertion")),
                    "enforcement_scope": inv.get("enforcement_scope", {"paths": ["**/*"]}),
                    "authority": {
                        "record_type": stem,
                        "record_file": str(path),
                        "record_sha256": file_sha,
                        "author": data.get("author", "Unknown"),
                    },
                    "status": inv.get("status", "active"),
                    "reassessment_threshold": inv.get("reassessment_threshold", "Formal reassessment required"),
                })
        return extracted

    # Synthesize from specific anti-slop record types
    if "paranoid" in stem or "concurrency_controls" in data:
        cc = data.get("concurrency_controls", {})
        idem = cc.get("idempotency", {})
        if idem.get("enabled"):
            extracted.append({
                "id": "INV-PARANOID-IDEMPOTENCY",
                "category": "concurrency_and_scale",
                "assertion": f"State mutations must enforce {idem.get('key_header', 'Idempotency-Key')} with {idem.get('storage', 'persistent storage')}.",
                "rationale": "Eliminates duplicate execution and race conditions under 10M concurrent sessions.",
                "enforcement_scope": {
                    "paths": ["src/api/**", "src/controllers/**", "src/routes/**", "**/api/**"],
                    "patterns": [idem.get("key_header", "Idempotency-Key")],
                    "forbidden_patterns": ["Math.random()"],
                },
                "authority": {"record_type": "paranoid_record", "record_file": str(path), "record_sha256": file_sha},
                "status": "active",
                "reassessment_threshold": "Requires distributed idempotency benchmark and load-test verification.",
            })
        limits = data.get("bounded_limits", {})
        if limits.get("max_read_limit"):
            extracted.append({
                "id": "INV-PARANOID-BOUNDED-READ",
                "category": "concurrency_and_scale",
                "assertion": f"Database reads must be keyset-paginated with max_read_limit <= {limits.get('max_read_limit')}.",
                "rationale": "Prevents memory exhaustion and full-table-scan database brownouts.",
                "enforcement_scope": {
                    "paths": ["src/db/**", "src/repositories/**", "**/db/**"],
                    "patterns": ["limit", "cursor"],
                    "forbidden_patterns": ["OFFSET 100", "OFFSET 500"],
                },
                "authority": {"record_type": "paranoid_record", "record_file": str(path), "record_sha256": file_sha},
                "status": "active",
                "reassessment_threshold": "Requires database index and query latency proof.",
            })

    if "rollout" in stem or "wire_compatibility" in data:
        wc = data.get("wire_compatibility", {})
        if wc.get("additive_only") or wc.get("tolerant_reader"):
            extracted.append({
                "id": "INV-ROLLOUT-WIRE-COMPAT",
                "category": "rollout_and_compatibility",
                "assertion": "Wire contracts must remain N-1/N+1 compatible: additive changes only and tolerant readers.",
                "rationale": "Rejects the atomic cutover fantasy and ensures zero downtime during rolling deployments.",
                "enforcement_scope": {
                    "paths": ["proto/**", "schemas/**", "src/contracts/**", "api/**"],
                    "patterns": ["optional", "reserved"],
                    "forbidden_patterns": ["required field removed", "renamed field"],
                },
                "authority": {"record_type": "rollout_record", "record_file": str(path), "record_sha256": file_sha},
                "status": "active",
                "reassessment_threshold": "Requires multi-phase deprecation window and backwards compatibility gate.",
            })

    if "observability" in stem or "stream_cardinality" in data:
        extracted.append({
            "id": "INV-OBSERVABILITY-CARDINALITY",
            "category": "telemetry_and_slo",
            "assertion": "Metric dimensions must remain bounded: dynamic IDs in label keys are strictly prohibited.",
            "rationale": "Prevents metric storage explosion and OOMs in time-series telemetry systems.",
            "enforcement_scope": {
                "paths": ["src/telemetry/**", "src/metrics/**", "**/observability/**"],
                "patterns": ["histogram", "counter"],
                "forbidden_patterns": ["user_id", "request_id", "order_id"],
            },
            "authority": {"record_type": "observability_record", "record_file": str(path), "record_sha256": file_sha},
            "status": "active",
            "reassessment_threshold": "Requires Monarch telemetry capacity review.",
        })

    if "tagore" in stem or "tagore" in data or "discourse_vector" in data.get("metrics", {}):
        extracted.append({
            "id": "INV-TAGORE-ENGINEERING-DISCOURSE-AND-SUBSTANCE",
            "category": "architecture",
            "assertion": (
                "Engineering prose must clear the Tagore >= 56/80 threshold, satisfy both "
                "mechanics (>=35/50) and substance (>=21/30) floors, eliminate the 29 cataloged tells, "
                "and ground claims in empirical measurements."
            ),
            "rationale": (
                "Eliminates AI significance puffery, copula avoidance, superficial participle chaining, "
                "and sterile soulless wire-copy lacking technical conviction or operational trade-offs."
            ),
            "enforcement_scope": {
                "paths": ["*.md", "docs/**", ".github/**", "**/PR_DESCRIPTION.md"],
                "patterns": ["PROCEED", "clean", "ssr"],
                "forbidden_patterns": [
                    "serves as an enduring testament",
                    "marking a pivotal milestone",
                    "evolving landscape",
                    "I hope this helps!",
                ],
            },
            "authority": {"record_type": "tagore_record", "record_file": str(path), "record_sha256": file_sha},
            "status": "active",
            "reassessment_threshold": "Requires formal technical writing and maintainer consensus.",
        })

    if "decision" in stem or "decision_action" in data:
        verdict = data.get("decision_action") or data.get("verdict", {}).get("action")
        rationale = data.get("rationale") or data.get("verdict", {}).get("rationale", "Architectural baseline decision")
        if verdict in ("proceed", "pause") and filled(data.get("goal")):
            extracted.append({
                "id": f"INV-DECISION-{abs(hash(data.get('goal', ''))) % 10000:04d}",
                "category": "architecture",
                "assertion": f"Architectural contract for: {data.get('goal')}",
                "rationale": rationale,
                "enforcement_scope": {"paths": ["**/*"]},
                "authority": {"record_type": "decision_record", "record_file": str(path), "record_sha256": file_sha},
                "status": "active",
                "reassessment_threshold": "Requires revisit trigger condition satisfaction.",
            })

    return extracted


def sync_ledger(record_dirs: List[Path], output_path: Path) -> Dict[str, Any]:
    candidates: List[Path] = []
    for d in record_dirs:
        if d.is_file() and d.suffix == ".json":
            candidates.append(d)
        elif d.is_dir():
            for p in d.rglob("*.json"):
                name = p.name.lower()
                if "record" in name or "decision" in name or "ledger" in name:
                    if p != output_path:
                        candidates.append(p)

    all_invariants: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()

    for path in sorted(candidates):
        invs = extract_invariants_from_record(path)
        for inv in invs:
            iid = inv["id"].strip().casefold()
            if iid not in seen_ids:
                seen_ids.add(iid)
                all_invariants.append(inv)

    ledger_payload = {
        "schema_version": "1.0.0",
        "generated_at": "2026-11-10T18:00:00Z",
        "invariants_count": len(all_invariants),
        "invariants": all_invariants,
    }
    raw_json = json.dumps(ledger_payload, indent=2)
    ledger_hash = sha256_text(raw_json)
    ledger_payload["ledger_hash"] = ledger_hash

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(ledger_payload, indent=2) + "\n", encoding="utf-8")

    # Generate companion compact TOON format for Gate 0 agent ingestion
    toon_path = output_path.with_suffix(".toon")
    generate_compact_toon(ledger_payload, toon_path)

    return {
        "sync_status": "complete",
        "scanned_files": len(candidates),
        "invariants_indexed": len(all_invariants),
        "ledger_file": str(output_path),
        "toon_file": str(toon_path),
        "ledger_hash": ledger_hash,
    }


def generate_compact_toon(ledger: Dict[str, Any], toon_path: Path) -> None:
    lines = [
        f"invariant_ledger[count={ledger.get('invariants_count', 0)},hash={ledger.get('ledger_hash', '')[:12]}]:",
    ]
    for inv in ledger.get("invariants", []):
        iid = inv.get("id")
        cat = inv.get("category", "")
        status = inv.get("status", "active")
        scope_paths = ",".join(inv.get("enforcement_scope", {}).get("paths", []))
        lines.append(f"  entry[id={iid},cat={cat},status={status},paths={scope_paths}]:")
        lines.append(f"    assert: {inv.get('assertion')}")
        forbidden = inv.get("enforcement_scope", {}).get("forbidden_patterns", [])
        if forbidden:
            lines.append(f"    forbid: {', '.join(forbidden)}")
    toon_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def path_matches_glob(file_path: str, glob_pattern: str) -> bool:
    norm_path = file_path.replace("\\", "/")
    norm_pattern = glob_pattern.replace("\\", "/")
    if norm_pattern == "**/*" or norm_pattern == "**":
        return True
    if norm_pattern.startswith("**/"):
        suffix = norm_pattern[3:]
        if norm_path.endswith(suffix) or ("/" + suffix) in norm_path:
            return True
    if norm_pattern.endswith("/**"):
        prefix = norm_pattern[:-3]
        if norm_path.startswith(prefix + "/") or norm_path == prefix:
            return True
    # Basic wildcard regex
    regex_pattern = "^" + re.escape(norm_pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*") + "$"
    return bool(re.match(regex_pattern, norm_path))


def check_file_scope(file_path: str, scope: Dict[str, Any]) -> bool:
    paths = scope.get("paths", [])
    if not paths:
        return False
    return any(path_matches_glob(file_path, pattern) for pattern in paths)


def get_git_diff(base: str = "HEAD") -> Tuple[str, List[str]]:
    cmd = ["git", "diff", base]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        diff_text = proc.stdout
        # Also get list of modified files
        name_proc = subprocess.run(["git", "diff", "--name-only", base], capture_output=True, text=True, check=False)
        files = [line.strip() for line in name_proc.stdout.splitlines() if line.strip()]
        return diff_text, files
    except Exception:
        return "", []


def parse_diff_by_file(diff_text: str) -> Dict[str, List[Tuple[str, str]]]:
    files: Dict[str, List[Tuple[str, str]]] = {}
    current_file = ""
    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" b/")
            if len(parts) >= 2:
                current_file = parts[-1].strip()
                files[current_file] = []
        elif current_file:
            if line.startswith("+") and not line.startswith("+++"):
                files[current_file].append(("+", line[1:]))
            elif line.startswith("-") and not line.startswith("---"):
                files[current_file].append(("-", line[1:]))
    return files


def is_doc_file(file_path: str) -> bool:
    norm = file_path.lower()
    return norm.endswith((".md", ".txt", ".rst", ".adoc"))


def detect_drift(
    ledger: Dict[str, Any],
    diff_text: str,
    changed_files: List[str],
    reassessment: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    findings: List[Dict[str, Any]] = []
    waived_invariants: Set[str] = set()

    if reassessment and reassessment.get("record_status") == "complete":
        target = reassessment.get("target_invariant_id")
        if target:
            waived_invariants.add(str(target).strip().casefold())

    active_invariants = [
        inv for inv in ledger.get("invariants", [])
        if inv.get("status") == "active"
    ]

    diff_by_file = parse_diff_by_file(diff_text)
    # If diff_by_file is empty but changed_files exist, map empty
    for f in changed_files:
        if f not in diff_by_file:
            diff_by_file[f] = []

    for inv in active_invariants:
        iid = inv.get("id", "UNKNOWN")
        norm_iid = iid.strip().casefold()
        if norm_iid in waived_invariants:
            continue

        scope = inv.get("enforcement_scope", {})
        forbidden = scope.get("forbidden_patterns", [])
        required = scope.get("patterns", [])
        paths = scope.get("paths", [])

        targets_docs = any(is_doc_file(p) or p in ("**/*", "**") for p in paths)

        # Check only changed files matching this invariant's scope
        for file_path, lines in diff_by_file.items():
            if not check_file_scope(file_path, scope):
                continue
            # Skip documentation files unless the invariant specifically targets documentation
            if is_doc_file(file_path) and not targets_docs:
                continue

            # Scan added lines in this governed file for forbidden patterns
            for forbidden_pat in forbidden:
                pat_regex = re.compile(re.escape(forbidden_pat), re.IGNORECASE)
                for prefix, line in lines:
                    if prefix == "+":
                        if pat_regex.search(line):
                            findings.append({
                                "severity": "block",
                                "code": "INVARIANT_FORBIDDEN_PATTERN",
                                "invariant_id": iid,
                                "rule": inv.get("assertion"),
                                "file": file_path,
                                "forbidden_pattern": forbidden_pat,
                                "violating_line": line.strip()[:100],
                                "message": f"{file_path} introduces forbidden pattern '{forbidden_pat}' governed by active invariant {iid}.",
                                "remediation": f"Remove forbidden pattern or open official Reassessment Trigger for {iid}.",
                            })

            # Check if required pattern was deleted from this governed file without replacement
            for req_pat in required:
                pat_regex = re.compile(re.escape(req_pat), re.IGNORECASE)
                deleted = any(prefix == "-" and pat_regex.search(line) for prefix, line in lines)
                added = any(prefix == "+" and pat_regex.search(line) for prefix, line in lines)
                if deleted and not added:
                    findings.append({
                        "severity": "block",
                        "code": "INVARIANT_PATTERN_REMOVED",
                        "invariant_id": iid,
                        "rule": inv.get("assertion"),
                        "file": file_path,
                        "removed_pattern": req_pat,
                        "message": f"Active invariant {iid} requires '{req_pat}', but it was removed in {file_path}.",
                        "remediation": f"Restore '{req_pat}' or file an official Reassessment Trigger for {iid}.",
                    })

    drift_detected = len(findings) > 0
    return {
        "drift_detected": drift_detected,
        "status": "drift_found" if drift_detected else "clean",
        "changed_files_count": len(changed_files),
        "invariants_checked": len(active_invariants),
        "waived_invariants": list(waived_invariants),
        "findings": findings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repo Memory & Invariant Steward - Guarding Architectural Memory & Drift."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: sync
    sync_p = subparsers.add_parser("sync", help="Sync decision records into Invariant Ledger")
    sync_p.add_argument("--records", nargs="*", default=["skills", "docs", ".anti-slop"],
                        help="Directories or files to scan for decision records")
    sync_p.add_argument("--output", default=".anti-slop/invariant-ledger.json",
                        help="Path to write compiled invariant ledger")
    sync_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # Subcommand: audit
    audit_p = subparsers.add_parser("audit", help="Audit an Invariant Ledger file")
    audit_p.add_argument("ledger", type=Path, help="Path to invariant-ledger.json")
    audit_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # Subcommand: reassess
    reassess_p = subparsers.add_parser("reassess", help="Validate a proposed Reassessment Trigger record")
    reassess_p.add_argument("trigger", type=Path, help="Path to reassessment-trigger.json")
    reassess_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    # Subcommand: drift
    drift_p = subparsers.add_parser("drift", help="Detect architectural drift in Git diff or files")
    drift_p.add_argument("--base", default="HEAD", help="Git base commit to diff against")
    drift_p.add_argument("--diff", type=Path, help="Optional raw diff file instead of git diff")
    drift_p.add_argument("--ledger", type=Path, default=Path(".anti-slop/invariant-ledger.json"),
                         help="Path to invariant ledger")
    drift_p.add_argument("--reassessment", type=Path, help="Optional reassessment-trigger.json")
    drift_p.add_argument("--json", action="store_true", help="Output machine-readable JSON")

    args = parser.parse_args()

    if args.command == "sync":
        rec_dirs = [Path(r) for r in args.records]
        out_file = Path(args.output)
        res = sync_ledger(rec_dirs, out_file)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print("Invariant Ledger Sync Complete:")
            print(f"  Scanned records:     {res['scanned_files']}")
            print(f"  Invariants indexed:  {res['invariants_indexed']}")
            print(f"  Ledger written to:   {res['ledger_file']}")
            print(f"  Compact TOON to:     {res['toon_file']}")
            print(f"  Ledger SHA256:       {res['ledger_hash'][:16]}...")
        return 0

    elif args.command == "audit":
        if not args.ledger.exists():
            print(f"Error: Ledger file not found: {args.ledger}", file=sys.stderr)
            return 1
        try:
            data = json.loads(args.ledger.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error: Failed to parse ledger JSON: {e}", file=sys.stderr)
            return 1
        res = audit_ledger(data)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Invariant Ledger Audit: {res['record_status'].upper()} ({res['invariants_count']} invariants)")
            for f in res["findings"]:
                print(f"  [{f['severity']}] {f['code']}: {f['message']}")
        return 0 if res["record_status"] == "complete" else 2

    elif args.command == "reassess":
        if not args.trigger.exists():
            print(f"Error: Reassessment trigger file not found: {args.trigger}", file=sys.stderr)
            return 1
        try:
            data = json.loads(args.trigger.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error: Failed to parse reassessment JSON: {e}", file=sys.stderr)
            return 1
        res = audit_reassessment_trigger(data)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Reassessment Trigger Audit: {res['record_status'].upper()} (Target: {res.get('target_invariant_id')})")
            for f in res["findings"]:
                print(f"  [{f['severity']}] {f['code']}: {f['message']}")
        return 0 if res["record_status"] == "complete" else 2

    elif args.command == "drift":
        ledger_path = args.ledger
        if not ledger_path.exists():
            # If default ledger doesn't exist, try scanning skills/examples to create one in-memory
            fallback_res = sync_ledger([Path("skills"), Path(".agents/skills")], Path("/tmp/temp_invariant_ledger.json"))
            ledger_data = json.loads(Path("/tmp/temp_invariant_ledger.json").read_text(encoding="utf-8"))
        else:
            try:
                ledger_data = json.loads(ledger_path.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"Error reading ledger: {e}", file=sys.stderr)
                return 1

        reassessment_data = None
        if args.reassessment and args.reassessment.exists():
            try:
                reassessment_data = audit_reassessment_trigger(json.loads(args.reassessment.read_text(encoding="utf-8")))
            except Exception as e:
                print(f"Warning: Failed to parse reassessment file: {e}", file=sys.stderr)

        if args.diff and args.diff.exists():
            diff_text = args.diff.read_text(encoding="utf-8")
            changed_files = [line.split(" b/")[-1].strip() for line in diff_text.splitlines() if line.startswith("diff --git ")]
        else:
            diff_text, changed_files = get_git_diff(args.base)

        drift_res = detect_drift(ledger_data, diff_text, changed_files, reassessment_data)
        if args.json:
            print(json.dumps(drift_res, indent=2))
        else:
            print(f"Architectural Drift Audit: {drift_res['status'].upper()} ({drift_res['invariants_checked']} checked)")
            if drift_res["findings"]:
                print(f"\nDrift Violations ({len(drift_res['findings'])}):")
                for f in drift_res["findings"]:
                    print(f"  - [{f['code']}] {f['invariant_id']}: {f['message']}")
                    print(f"    Remediation: {f['remediation']}")
            else:
                print("  No architectural drift detected. All active invariants preserved.")

        return 2 if drift_res["drift_detected"] else 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
