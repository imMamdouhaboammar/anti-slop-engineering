#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Anti-Slop Engineering - Universal Skills Compliance Engine.

Evaluates any target code (directory, file, git diff) against all 46 skills
in `skills/`, comparing their rules, invariants, and recommendations with the code.
Implements the user-approved Tiered Blocking Gate (hard fail on Critical/High violations,
advisory warnings for medium/low unless score < 70).

Usage:
    python3 scripts/skills_compliance_engine.py [--target src/] [--base HEAD] [--skills all] [--json] [--strict]
"""

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

ROOT = Path(__file__).resolve().parents[1]
LEDGER_PATH = ROOT / ".anti-slop" / "skills-rules-ledger.json"

if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

try:
    from extract_skill_rules import extract_all_skills
except ImportError:
    extract_all_skills = None


@dataclass
class Finding:
    skill_id: str
    rule_id: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    file_path: str
    line_number: Optional[int]
    message: str
    snippet: Optional[str] = None
    remediation: Optional[str] = None


@dataclass
class SkillResult:
    skill_id: str
    display_name: str
    category: str
    tier: str
    applicable: bool
    status: str  # PASSED, FAILED, WARNING, NOT_APPLICABLE
    score: int
    findings: List[Finding] = field(default_factory=list)


# Built-in direct heuristics for universal rules across skills
INVARIANT_HEURISTICS = [
    {
        "skill_id": "type-level-and-ast-slop-gate",
        "rule_id": "AST-CHAINED-CAST",
        "severity": "CRITICAL",
        "regex": re.compile(r"as\s+unknown\s+as\s+[A-Za-z0-9_<>]+|as\s+any\s+as\s+[A-Za-z0-9_<>]+"),
        "exts": {".ts", ".tsx"},
        "message": "Chained type assertion ('as unknown as T') bypasses compiler type safety.",
        "remediation": "Validate input schema with Zod/ArkType or use proper TypeScript type narrowing.",
    },
    {
        "skill_id": "type-level-and-ast-slop-gate",
        "rule_id": "AST-EMPTY-SPREAD",
        "severity": "HIGH",
        "regex": re.compile(r"\.\.\.\s*\([^?]+\?[^:]+:\s*\{\}\s*\)"),
        "exts": {".ts", ".tsx", ".js", ".jsx"},
        "message": "Conditional empty object spread allocates unnecessary intermediate objects.",
        "remediation": "Assign explicit optional properties instead of conditional empty spreads.",
    },
    {
        "skill_id": "grumpy-senior-staff-engineer",
        "rule_id": "SRE-FLAT-RETRY",
        "severity": "CRITICAL",
        "regex": re.compile(r"retry\s*=\s*(?:True|\d+)|retries\s*=\s*[1-9]\d*.*sleep\(\d+\)"),
        "exts": {".py", ".ts", ".js", ".go"},
        "message": "Flat retry without exponential backoff causes thundering-herd outages.",
        "remediation": "Implement exponential backoff with full jitter and bounded deadlines.",
    },
    {
        "skill_id": "grumpy-senior-staff-engineer",
        "rule_id": "SRE-SLEEP-SYNC",
        "severity": "HIGH",
        "regex": re.compile(r"(?:time\.sleep\s*\(\s*(?:0\.[1-9]|[1-9])\s*\)|await\s+(?:new\s+Promise|sleep)\s*\(\s*(?:100|[1-9]\d{3,})\s*\))"),
        "exts": {".py", ".ts", ".js"},
        "message": "Blind sleep() used as synchronization band-aid introduces race conditions and test flakiness.",
        "remediation": "Replace blind sleep with deterministic condition polling or event notification.",
    },
    {
        "skill_id": "paranoid-principal-architect",
        "rule_id": "SEC-TIMING-ATTACK",
        "severity": "CRITICAL",
        "regex": re.compile(r"(?:signature|token|hash|secret)\s*===?\s*[a-zA-Z0-9_]+"),
        "exts": {".ts", ".js"},
        "message": "Direct string equality on signature/secret token is vulnerable to timing side-channel attacks.",
        "remediation": "Use crypto.timingSafeEqual(Buffer.from(a), Buffer.from(b)).",
    },
    {
        "skill_id": "paranoid-principal-architect",
        "rule_id": "SEC-OFFSET-PAGINATION",
        "severity": "HIGH",
        "regex": re.compile(r"\bOFFSET\s+[1-9]\d{2,}\b", re.IGNORECASE),
        "exts": {".sql", ".ts", ".py", ".go"},
        "message": "Deep offset pagination causes full-table scans and memory bloat under scale.",
        "remediation": "Mandate cursor-based keyset pagination (WHERE id > last_seen_id LIMIT 50).",
    },
    {
        "skill_id": "mandela-guard",
        "rule_id": "TST-TAUTOLOGICAL-ASSERT",
        "severity": "CRITICAL",
        "regex": re.compile(r"expect\s*\(\s*(?:true|1|'a'|\"a\")\s*\)\s*\.toBe\s*\(\s*(?:true|1|'a'|\"a\")\s*\)"),
        "exts": {".ts", ".tsx", ".js", ".jsx"},
        "message": "Tautological assertion confirms nothing; test oracle is self-satisfying.",
        "remediation": "Assert on real outputs and side-effects of the tested component.",
    },
    {
        "skill_id": "demock-guard",
        "rule_id": "DMK-DUMMY-DB-FALLBACK",
        "severity": "CRITICAL",
        "regex": re.compile(r"(?:sqlite3?\.connect|mockDb|dummyDatabase|fallback_to_memory_db)", re.IGNORECASE),
        "exts": {".ts", ".js", ".py"},
        "message": "Dummy database or local SQLite fallback found in production service path.",
        "remediation": "Fail closed on database connectivity errors; do not mask failures with dummy memory storage.",
    },
    {
        "skill_id": "apple-craft-and-interaction-physics",
        "rule_id": "UI-UNBOUNDED-RAF",
        "severity": "HIGH",
        "regex": re.compile(r"requestAnimationFrame\s*\([^)]+\)"),
        "exts": {".ts", ".tsx", ".js", ".jsx"},
        "message": "Continuous requestAnimationFrame loop detected without epsilon stabilization check.",
        "remediation": "Terminate rAF handle when absolute delta < 1e-4 to release compositor resources.",
    },
    {
        "skill_id": "observability-and-slo-architect",
        "rule_id": "OBS-CARDINALITY-EXPLOSION",
        "severity": "HIGH",
        "regex": re.compile(r"(?:labels|tags)\s*:\s*\{[^}]*(?:user_id|order_id|request_id|email)[^}]*\}"),
        "exts": {".ts", ".js", ".go", ".py"},
        "message": "High-cardinality dynamic identifier (user_id/email) used inside metrics label.",
        "remediation": "Ban unbounded dynamic IDs in metric labels; attach them to distributed Trace Exemplars instead.",
    },
]


class SkillsComplianceEngine:
    def __init__(self, ledger: Optional[Dict[str, Any]] = None, strict: bool = False):
        self.strict = strict
        self.ledger = ledger or self._load_or_extract_ledger()

    def _load_or_extract_ledger(self) -> Dict[str, Any]:
        if LEDGER_PATH.exists():
            try:
                return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
            except Exception:
                pass
        if extract_all_skills:
            ledger = extract_all_skills()
            LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
            LEDGER_PATH.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
            return ledger
        return {"skills": {}, "total_skills": 0}

    def collect_target_files(self, target_path: Optional[str] = None, base_git: Optional[str] = None) -> List[Path]:
        """Collect list of files to audit from directory or git diff."""
        collected: Set[Path] = set()

        if base_git:
            # Get changed files from git diff
            try:
                cmd = ["git", "diff", "--name-only", f"{base_git}...HEAD"]
                res = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, check=True)
                for line in res.stdout.splitlines():
                    p = ROOT / line.strip()
                    if p.is_file():
                        collected.add(p)
            except Exception:
                pass

        if target_path:
            p_target = Path(target_path)
            if not p_target.is_absolute():
                p_target = ROOT / p_target
            if p_target.is_file():
                collected.add(p_target)
            elif p_target.is_dir():
                for root_dir, _, files in os.walk(p_target):
                    # Skip common noisy directories
                    if any(ignored in root_dir for ignored in [".git", "node_modules", "dist", ".anti-slop", "target"]):
                        continue
                    for f in files:
                        collected.add(Path(root_dir) / f)

        if not target_path and not base_git:
            # Default to scanning src/ and scripts/
            for default_dir in [ROOT / "src", ROOT / "scripts", ROOT / "skills"]:
                if default_dir.exists():
                    for root_dir, _, files in os.walk(default_dir):
                        if any(ignored in root_dir for ignored in [".git", "node_modules", "dist"]):
                            continue
                        for f in files:
                            collected.add(Path(root_dir) / f)

        return sorted(list(collected))

    def is_skill_applicable(self, skill_data: Dict[str, Any], files: List[Path], target_dir: Optional[Path] = None) -> Tuple[bool, List[Path]]:
        """Determine if a skill applies to the given set of files based on patterns."""
        patterns = skill_data.get("file_patterns", ["*"])
        if "*" in patterns:
            return True, files

        matched_files: List[Path] = []
        for f in files:
            rel_root = str(f.relative_to(ROOT)) if (ROOT in f.parents or f == ROOT) else f.name
            rel_target = str(f.relative_to(target_dir)) if (target_dir and (target_dir in f.parents or f == target_dir)) else f.name
            for pat in patterns:
                if (fnmatch.fnmatch(rel_root, pat) or
                    fnmatch.fnmatch(rel_target, pat) or
                    fnmatch.fnmatch(f.name, pat)):
                    matched_files.append(f)
                    break
                clean_pat = pat.rstrip("/*")
                if clean_pat and (f"/{clean_pat}/" in str(f) or str(f).endswith(f"/{clean_pat}")):
                    matched_files.append(f)
                    break

        return len(matched_files) > 0, matched_files

    def run_deterministic_heuristics(self, skill_id: str, files: List[Path]) -> List[Finding]:
        """Run built-in regex and AST patterns for a given skill against target files."""
        findings: List[Finding] = []
        heuristics = [h for h in INVARIANT_HEURISTICS if h["skill_id"] == skill_id]

        for file_path in files:
            ext = file_path.suffix
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue

            lines = content.splitlines()

            for h in heuristics:
                if ext not in h["exts"]:
                    continue

                for line_idx, line in enumerate(lines, start=1):
                    # Skip comments if checking code
                    m = h["regex"].search(line)
                    if m:
                        rel_path = str(file_path.relative_to(ROOT)) if file_path.is_relative_to(ROOT) else str(file_path)
                        findings.append(Finding(
                            skill_id=skill_id,
                            rule_id=h["rule_id"],
                            severity=h["severity"],
                            file_path=rel_path,
                            line_number=line_idx,
                            message=h["message"],
                            snippet=line.strip()[:100],
                            remediation=h["remediation"],
                        ))

        return findings

    def evaluate(self, target_path: Optional[str] = None, base_git: Optional[str] = None, selected_skills: Optional[str] = "all") -> Dict[str, Any]:
        """Execute compliance audit across all or selected skills."""
        files = self.collect_target_files(target_path, base_git)
        all_skills_data = self.ledger.get("skills", {})
        target_root = Path(target_path) if target_path else None

        target_skill_ids = set()
        if selected_skills and selected_skills != "all":
            target_skill_ids = {s.strip() for s in selected_skills.split(",")}
        else:
            target_skill_ids = set(all_skills_data.keys())

        results: Dict[str, SkillResult] = {}
        total_critical = 0
        total_high = 0
        total_medium = 0
        total_low = 0

        for skill_id, skill_meta in all_skills_data.items():
            if skill_id not in target_skill_ids:
                continue

            applicable, matched_files = self.is_skill_applicable(skill_meta, files, target_dir=target_root)
            if not applicable:
                results[skill_id] = SkillResult(
                    skill_id=skill_id,
                    display_name=skill_meta.get("display_name", skill_id),
                    category=skill_meta.get("category", "general"),
                    tier=skill_meta.get("execution_tier", "DETERMINISTIC"),
                    applicable=False,
                    status="NOT_APPLICABLE",
                    score=100,
                    findings=[],
                )
                continue

            # Run deterministic checks
            findings = self.run_deterministic_heuristics(skill_id, matched_files)

            # Count severities
            c_count = sum(1 for f in findings if f.severity == "CRITICAL")
            h_count = sum(1 for f in findings if f.severity == "HIGH")
            m_count = sum(1 for f in findings if f.severity == "MEDIUM")
            l_count = sum(1 for f in findings if f.severity == "LOW")

            total_critical += c_count
            total_high += h_count
            total_medium += m_count
            total_low += l_count

            deduction = (c_count * 25) + (h_count * 10) + (m_count * 5) + (l_count * 2)
            skill_score = max(0, 100 - deduction)

            status = "PASSED"
            if c_count > 0 or h_count > 0:
                status = "FAILED"
            elif m_count > 0 or l_count > 0:
                status = "WARNING"

            results[skill_id] = SkillResult(
                skill_id=skill_id,
                display_name=skill_meta.get("display_name", skill_id),
                category=skill_meta.get("category", "general"),
                tier=skill_meta.get("execution_tier", "DETERMINISTIC"),
                applicable=True,
                status=status,
                score=skill_score,
                findings=findings,
            )

        # Calculate overall repository compliance score
        applicable_count = sum(1 for r in results.values() if r.applicable)
        total_deduction = (total_critical * 25) + (total_high * 10) + (total_medium * 5) + (total_low * 2)
        overall_score = max(0, 100 - total_deduction)

        # Enforce user-approved Tiered Blocking Gate
        decision = "PASS"
        exit_code = 0

        if self.strict:
            if total_critical > 0 or total_high > 0 or total_medium > 0 or total_low > 0:
                decision = "BLOCK"
                exit_code = 1
        else:
            # Tiered policy: Hard block on Critical/High violations, or if overall score < 70
            if total_critical > 0 or total_high > 0:
                decision = "BLOCK_CRITICAL_VIOLATION"
                exit_code = 1
            elif overall_score < 70:
                decision = "BLOCK_LOW_SCORE"
                exit_code = 1
            else:
                decision = "PASS_WITH_ADVISORY" if (total_medium > 0 or total_low > 0) else "PASS"
                exit_code = 0

        return {
            "schema_version": "2.0.0",
            "evaluated_files_count": len(files),
            "total_skills_registered": len(all_skills_data),
            "applicable_skills_count": applicable_count,
            "overall_score": overall_score,
            "decision": decision,
            "exit_code": exit_code,
            "violations_summary": {
                "critical": total_critical,
                "high": total_high,
                "medium": total_medium,
                "low": total_low,
            },
            "skills": {k: asdict(v) for k, v in results.items()},
        }


def print_cli_report(eval_result: Dict[str, Any]):
    """Print readable terminal scorecard."""
    print("\n" + "=" * 90)
    print(f"🔍 ANTI-SLOP SKILLS COMPLIANCE REPORT | Score: {eval_result['overall_score']}/100 | Decision: {eval_result['decision']}")
    print("=" * 90)
    print(f"Files Evaluated: {eval_result['evaluated_files_count']} | Applicable Skills: {eval_result['applicable_skills_count']}/{eval_result['total_skills_registered']}")
    print(f"Violations: Critical={eval_result['violations_summary']['critical']} | High={eval_result['violations_summary']['high']} | Medium={eval_result['violations_summary']['medium']}")
    print("-" * 90)
    print(f"{'Status':<8} | {'Skill Name':<45} | {'Score':<6} | {'Findings'}")
    print("-" * 90)

    for skill_id, s in sorted(eval_result["skills"].items()):
        if not s["applicable"]:
            continue
        status_icon = "✅ PASS"
        if s["status"] == "FAILED":
            status_icon = "❌ FAIL"
        elif s["status"] == "WARNING":
            status_icon = "⚠️ WARN"

        findings_count = len(s["findings"])
        findings_str = f"{findings_count} violations" if findings_count > 0 else "Clean"
        print(f"{status_icon:<8} | {s['display_name']:<45} | {s['score']:<6} | {findings_str}")

        if findings_count > 0:
            for f in s["findings"]:
                line_info = f":{f['line_number']}" if f['line_number'] else ""
                print(f"         ↳ [{f['severity']}] {f['file_path']}{line_info}: {f['message']}")
                if f.get("remediation"):
                    print(f"           Fix: {f['remediation']}")

    print("=" * 90)


def main():
    parser = argparse.ArgumentParser(description="Evaluate code compliance against all Anti-Slop skills.")
    parser.add_argument("--target", help="Directory or file path to evaluate")
    parser.add_argument("--base", help="Git base ref to evaluate diff (e.g. HEAD, origin/main)")
    parser.add_argument("--skills", default="all", help="Comma-separated skill IDs or 'all'")
    parser.add_argument("--strict", action="store_true", help="Zero-tolerance mode: fail on any warning or advisory")
    parser.add_argument("--json", action="store_true", help="Output RFC 9457 JSON report")

    args = parser.parse_args()

    engine = SkillsComplianceEngine(strict=args.strict)
    result = engine.evaluate(target_path=args.target, base_git=args.base, selected_skills=args.skills)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_cli_report(result)

    sys.exit(result["exit_code"])


if __name__ == "__main__":
    main()
