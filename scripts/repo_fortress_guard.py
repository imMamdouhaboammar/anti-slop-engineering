#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Repo Fortress Guard & Scaffolder (Zero-Dependency Python >=3.9)
Enforces repository fortification, anti-suppression gating, static analysis hardening,
and automated three-tier quality shield verification.
"""

import argparse
import json
import os
import re
from pathlib import Path
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

FORBIDDEN_SUPPRESSIONS = re.compile(
    r"^\+.*(oxlint-disable|eslint-disable|@ts-ignore|@ts-expect-error|# noqa|# type:\s*ignore|as unknown as)",
    re.MULTILINE
)


def get_git_diff(base: Optional[str] = None, staged: bool = False) -> str:
    cmd = ["git", "diff", "-U0"]
    if staged:
        cmd.append("--cached")
    elif base:
        cmd.append(base)
    
    cmd.extend([
        "--",
        ":!.github/workflows/lint-gate.yml",
        ":!*.md",
        ":!tests/**"
    ])
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
        return res.stdout
    except Exception:
        return ""


def audit_repository(root: Path, base: Optional[str] = None, staged: bool = False) -> Dict[str, Any]:
    tier1_lefthook = (root / "lefthook.yml").is_file() or (root / ".lefthook.yml").is_file()
    tier1_commitlint = (
        (root / "commitlint.config.mjs").is_file()
        or (root / "commitlint.config.js").is_file()
        or (root / ".commitlintrc.json").is_file()
    )
    
    tier2_ci = (root / ".github" / "workflows" / "lint-gate.yml").is_file()
    
    tier3_release_config = (root / "release-please-config.json").is_file()
    tier3_release_manifest = (root / ".release-please-manifest.json").is_file()
    tier3_release_workflow = (root / ".github" / "workflows" / "release-please.yml").is_file()
    
    has_dockerfile = (root / "Dockerfile").is_file()
    has_docker_compose = (root / "docker-compose.yml").is_file() or (root / "docker-compose.yaml").is_file()

    # Check for forbidden suppressions in git diff if in a git repo
    diff_content = get_git_diff(base, staged)
    suppression_violations: List[str] = []
    if diff_content:
        for line in diff_content.splitlines():
            if FORBIDDEN_SUPPRESSIONS.match(line):
                suppression_violations.append(line.strip())

    tier1_status = tier1_lefthook and tier1_commitlint
    tier2_status = tier2_ci
    tier3_status = tier3_release_config and tier3_release_manifest and tier3_release_workflow
    clean_diff = len(suppression_violations) == 0

    score = 0
    total_checks = 5
    if tier1_lefthook: score += 1
    if tier1_commitlint: score += 1
    if tier2_ci: score += 1
    if tier3_status: score += 1
    if clean_diff: score += 1

    passed = tier1_status and tier2_status and clean_diff

    return {
        "status": "PASS" if passed else "REWORK",
        "score": f"{score}/{total_checks}",
        "tier1_local_hooks": {
            "lefthook": tier1_lefthook,
            "commitlint": tier1_commitlint,
            "status": "HEALTHY" if tier1_status else "MISSING"
        },
        "tier2_ci_gate": {
            "lint_gate_workflow": tier2_ci,
            "status": "HEALTHY" if tier2_status else "MISSING"
        },
        "tier3_release_engine": {
            "release_please_config": tier3_release_config,
            "release_please_manifest": tier3_release_manifest,
            "release_please_workflow": tier3_release_workflow,
            "status": "HEALTHY" if tier3_status else "PARTIAL/MISSING"
        },
        "containerization": {
            "dockerfile": has_dockerfile,
            "docker_compose": has_docker_compose
        },
        "anti_suppression_guard": {
            "clean_diff": clean_diff,
            "violation_count": len(suppression_violations),
            "violations": suppression_violations[:10]
        }
    }


def run_scaffold(args_list: List[str]) -> int:
    init_script = Path(__file__).resolve().parent.parent / "skills" / "repo-fortress" / "scripts" / "init_fortress.py"
    if not init_script.is_file():
        # Fallback to local skills
        init_script = Path(__file__).resolve().parent / "init_fortress.py"
    if init_script.is_file():
        cmd = [sys.executable, str(init_script)] + args_list
        return subprocess.run(cmd).returncode
    print("Error: init_fortress.py not found in skills/repo-fortress/scripts/")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repo Fortress Guard: Zero-Tolerance Quality Shield Audit & Scaffolder"
    )
    subparsers = parser.add_subparsers(dest="subcommand")

    # audit subcommand
    audit_parser = subparsers.add_parser("audit", help="Audit repository fortification and anti-suppression status")
    audit_parser.add_argument("--root", type=str, default=".", help="Root of project")
    audit_parser.add_argument("--base", type=str, default="HEAD", help="Base git commit/ref to compare against")
    audit_parser.add_argument("--staged", action="store_true", help="Audit staged changes only")
    audit_parser.add_argument("--json", action="store_true", help="Emit JSON output")

    # init / scaffold subcommand
    init_parser = subparsers.add_parser("init", help="Scaffold three-tier quality shield")
    init_parser.add_argument("--root", type=str, default=".", help="Root of project")
    init_parser.add_argument("--all", action="store_true", help="Scaffold all 3 tiers")
    init_parser.add_argument("--hooks", action="store_true", help="Scaffold Tier 1 (Lefthook + Commitlint)")
    init_parser.add_argument("--ci", action="store_true", help="Scaffold Tier 2 (GitHub Actions lint-gate.yml)")
    init_parser.add_argument("--release", action="store_true", help="Scaffold Tier 3 (Release Please)")
    init_parser.add_argument("--docker", action="store_true", help="Scaffold production Docker & Compose")
    init_parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    init_parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    # Allow direct execution without subcommand (defaults to audit)
    if len(sys.argv) > 1 and sys.argv[1] in ["init", "scaffold", "setup"]:
        scaffold_args = sys.argv[2:]
        return run_scaffold(scaffold_args)

    # Parse arguments
    args, unknown = parser.parse_known_args()

    if args.subcommand == "init":
        return run_scaffold(sys.argv[2:])

    # Default: Audit
    root_dir = Path(getattr(args, "root", ".")).resolve()
    base_ref = getattr(args, "base", "HEAD")
    staged_mode = getattr(args, "staged", False)
    json_mode = getattr(args, "json", False) or ("--json" in sys.argv)

    results = audit_repository(root_dir, base=base_ref, staged=staged_mode)

    if json_mode:
        print(json.dumps(results, indent=2))
    else:
        print("============================================================================")
        print("🏰 REPO FORTRESS QUALITY AUDIT RESULT")
        print("============================================================================")
        print(f"Status:             {results['status']}")
        print(f"Score:              {results['score']}")
        print(f"Tier 1 (Hooks):     {results['tier1_local_hooks']['status']}")
        print(f"Tier 2 (CI Gate):   {results['tier2_ci_gate']['status']}")
        print(f"Tier 3 (Release):   {results['tier3_release_engine']['status']}")
        print(f"Anti-Suppression:   {'PASS' if results['anti_suppression_guard']['clean_diff'] else 'VIOLATIONS DETECTED'}")
        if results['anti_suppression_guard']['violations']:
            print("\n⚠️ Violations:")
            for v in results['anti_suppression_guard']['violations']:
                print(f"  - {v}")
        print("============================================================================")

    return 0 if results["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
