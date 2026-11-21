#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Universal Skills Invariant Extractor for Anti-Slop Engineering.

Extracts axioms, laws, negative patterns, and evaluation rubrics from all 46
bundled skills in `skills/` and maps them to deterministic guard scripts,
producing `.anti-slop/skills-rules-ledger.json`.

Usage:
    python3 scripts/extract_skill_rules.py [--output .anti-slop/skills-rules-ledger.json] [--summary]
"""

import argparse
import datetime
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT / "skills"
SCRIPTS_DIR = ROOT / "scripts"
OUTPUT_PATH = ROOT / ".anti-slop" / "skills-rules-ledger.json"

# Explicit mapping of skills to guard scripts and domains
SKILL_GUARD_MAP: Dict[str, Dict[str, Any]] = {
    "anti-slop-engineering": {
        "guard_script": "diff_guard.py",
        "category": "core_hygiene",
        "file_patterns": ["*"],
        "severity": "CRITICAL",
    },
    "api-ergonomics-and-contract-governor": {
        "guard_script": "api_contract_guard.py",
        "category": "api_contract",
        "file_patterns": ["*.ts", "*.js", "*.py", "*.go", "*.rs", "api/**"],
        "severity": "HIGH",
    },
    "apple-craft-and-frame-budget": {
        "guard_script": "frame_budget_guard.py",
        "category": "apple_craft_and_ui",
        "file_patterns": ["*.tsx", "*.jsx", "*.vue", "*.svelte", "*.css", "*.html"],
        "severity": "HIGH",
    },
    "apple-craft-and-interaction-physics": {
        "guard_script": "apple_craft_guard.py",
        "category": "apple_craft_and_ui",
        "file_patterns": ["*.tsx", "*.jsx", "*.vue", "*.svelte", "*.css", "*.html"],
        "severity": "CRITICAL",
    },
    "asset-provenance-guard": {
        "guard_script": "asset_provenance_guard.py",
        "category": "security_and_governance",
        "file_patterns": ["assets/**", "public/**", "*.png", "*.svg", "*.jpg"],
        "severity": "HIGH",
    },
    "backprop-guard": {
        "guard_script": "backprop_guard.py",
        "category": "agent_governance",
        "file_patterns": ["rules/**", "AGENTS.md", ".anti-slop/**"],
        "severity": "MEDIUM",
    },
    "chaos-and-degradation-choreographer": {
        "guard_script": None,
        "category": "sre_and_architecture",
        "file_patterns": ["src/**", "services/**", "k8s/**"],
        "severity": "HIGH",
    },
    "chromatic-drift-guard": {
        "guard_script": "chroma_drift_guard.py",
        "category": "apple_craft_and_ui",
        "file_patterns": ["*.css", "*.tsx", "*.jsx", "tailwind.config.*"],
        "severity": "MEDIUM",
    },
    "cognitive-load-and-attention-governor": {
        "guard_script": "attention_guard.py",
        "category": "agent_governance",
        "file_patterns": ["*.md", "PR_DESCRIPTION.md", "docs/**"],
        "severity": "MEDIUM",
    },
    "comment-budget-guard": {
        "guard_script": "comment_budget_guard.py",
        "category": "code_hygiene",
        "file_patterns": ["*.ts", "*.tsx", "*.js", "*.jsx", "*.py", "*.go", "*.rs"],
        "severity": "HIGH",
    },
    "context-window-and-token-economics-architect": {
        "guard_script": None,
        "category": "agent_governance",
        "file_patterns": ["*.prompt", "*.md", "prompts/**", "agents/**"],
        "severity": "MEDIUM",
    },
    "cryptographic-agility-and-secret-lifecycle-gate": {
        "guard_script": None,
        "category": "security_and_governance",
        "file_patterns": ["*.env*", "src/security/**", "src/crypto/**", "**/auth/**"],
        "severity": "CRITICAL",
    },
    "decision-guard": {
        "guard_script": "decision_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["docs/**", "adr/**", "src/**"],
        "severity": "HIGH",
    },
    "demock-guard": {
        "guard_script": "demock_guard.py",
        "category": "code_hygiene",
        "file_patterns": ["*.ts", "*.js", "*.py", "src/**", "services/**", "lib/**"],
        "severity": "CRITICAL",
    },
    "design-system-drift-guard": {
        "guard_script": "system_drift_guard.py",
        "category": "apple_craft_and_ui",
        "file_patterns": ["*.tsx", "*.jsx", "*.css", "components/**"],
        "severity": "MEDIUM",
    },
    "deterministic-simulation-and-property-testing": {
        "guard_script": "simulation_guard.py",
        "category": "testing_and_simulation",
        "file_patterns": ["tests/**", "*.test.*", "*_test.*"],
        "severity": "HIGH",
    },
    "distributed-consensus-and-concurrency-gate": {
        "guard_script": None,
        "category": "sre_and_architecture",
        "file_patterns": ["src/cluster/**", "src/raft/**", "src/concurrency/**"],
        "severity": "CRITICAL",
    },
    "finops-and-unit-economics-governor": {
        "guard_script": None,
        "category": "sre_and_architecture",
        "file_patterns": ["terraform/**", "infra/**", "src/queries/**"],
        "severity": "MEDIUM",
    },
    "future-scale-gate": {
        "guard_script": "future_scale_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["src/**", "services/**", "docs/adr/**"],
        "severity": "HIGH",
    },
    "grumpy-senior-staff-engineer": {
        "guard_script": "sre_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["*.ts", "*.js", "*.py", "*.go", "*.rs"],
        "severity": "CRITICAL",
    },
    "honeypot-trap-guard": {
        "guard_script": "honeypot_trap_guard.py",
        "category": "security_and_governance",
        "file_patterns": [".github/**", "*.md", "templates/**"],
        "severity": "CRITICAL",
    },
    "house-tell-guard": {
        "guard_script": "house_tell_guard.py",
        "category": "agent_governance",
        "file_patterns": ["*.ts", "*.js", "*.py", "*.go", "*.rs", "*.md"],
        "severity": "HIGH",
    },
    "install-anti-slop": {
        "guard_script": "safe_install.py",
        "category": "core_hygiene",
        "file_patterns": ["package.json", "install.sh", "Makefile"],
        "severity": "HIGH",
    },
    "llm-eval-and-prompt-injection-fortress": {
        "guard_script": None,
        "category": "security_and_governance",
        "file_patterns": ["prompts/**", "src/ai/**", "src/llm/**"],
        "severity": "CRITICAL",
    },
    "mandela-guard": {
        "guard_script": "mandela_guard.py",
        "category": "testing_and_simulation",
        "file_patterns": ["tests/**", "*.test.*", "*_test.*"],
        "severity": "CRITICAL",
    },
    "mechanical-sympathy-and-perf-gate": {
        "guard_script": "perf_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["*.ts", "*.js", "*.py", "*.go", "*.rs"],
        "severity": "HIGH",
    },
    "mechanical-sympathy-profiler": {
        "guard_script": "profiler_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["*.ts", "*.js", "*.py", "*.go", "*.rs"],
        "severity": "HIGH",
    },
    "motion-runtime-guard": {
        "guard_script": "motion_runtime_guard.py",
        "category": "apple_craft_and_ui",
        "file_patterns": ["*.tsx", "*.jsx", "*.css", "*.js"],
        "severity": "MEDIUM",
    },
    "observability-and-slo-architect": {
        "guard_script": "observability_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["src/telemetry/**", "src/metrics/**", "**/observability/**", "*.ts", "*.go"],
        "severity": "HIGH",
    },
    "observability-and-slo-gate": {
        "guard_script": "observability_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["src/telemetry/**", "src/metrics/**", "**/observability/**"],
        "severity": "HIGH",
    },
    "paranoid-principal-architect": {
        "guard_script": "paranoid_guard.py",
        "category": "security_and_governance",
        "file_patterns": ["*.ts", "*.js", "*.py", "*.go", "src/api/**", "src/controllers/**", "src/routes/**", "src/auth/**"],
        "severity": "CRITICAL",
    },
    "pr-boundary-guard": {
        "guard_script": "pr_boundary_guard.py",
        "category": "core_hygiene",
        "file_patterns": [".github/**", "**/PR_TEMPLATE.md"],
        "severity": "MEDIUM",
    },
    "privacy-and-data-lineage-gate": {
        "guard_script": "privacy_guard.py",
        "category": "security_and_governance",
        "file_patterns": ["src/models/**", "src/schema/**", "src/user/**", "db/**"],
        "severity": "CRITICAL",
    },
    "re0-handoff-guard": {
        "guard_script": "re0_handoff_guard.py",
        "category": "agent_governance",
        "file_patterns": ["*.md", "notes/**", "handoffs/**"],
        "severity": "HIGH",
    },
    "reduction-guard": {
        "guard_script": "reduction_guard.py",
        "category": "code_hygiene",
        "file_patterns": [".anti-slop/add-back-ledger.jsonl", "src/**"],
        "severity": "HIGH",
    },
    "repo-memory-and-invariant-steward": {
        "guard_script": "invariant_steward_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": [".anti-slop/invariant-ledger.json", "docs/adr/**"],
        "severity": "CRITICAL",
    },
    "root-fix-gate": {
        "guard_script": "root_fix_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["src/**", "services/**"],
        "severity": "HIGH",
    },
    "safe-evolution-and-rollout-choreographer": {
        "guard_script": "rollout_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["proto/**", "schemas/**", "src/contracts/**", "api/**"],
        "severity": "CRITICAL",
    },
    "scientific-fault-isolation": {
        "guard_script": "fault_isolation_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["src/**", "tests/**"],
        "severity": "HIGH",
    },
    "styleseed-guard": {
        "guard_script": "styleseed_guard.py",
        "category": "apple_craft_and_ui",
        "file_patterns": ["*.css", "*.tsx", "*.jsx", "styles/**"],
        "severity": "MEDIUM",
    },
    "supply-chain-and-sbom-sentinel": {
        "guard_script": None,
        "category": "security_and_governance",
        "file_patterns": ["package.json", "pnpm-lock.yaml", "bun.lockb", "bun.lock", "go.mod", "Cargo.lock"],
        "severity": "CRITICAL",
    },
    "tagore-guard": {
        "guard_script": "tagore_guard.py",
        "category": "agent_governance",
        "file_patterns": ["*.md", "docs/**", ".github/**"],
        "severity": "HIGH",
    },
    "type-level-and-ast-slop-gate": {
        "guard_script": "ast_slop_guard.py",
        "category": "code_hygiene",
        "file_patterns": ["*.ts", "*.tsx", "*.js", "*.jsx"],
        "severity": "CRITICAL",
    },
    "ui-and-copy-discipline": {
        "guard_script": "contrast_guard.py",
        "category": "apple_craft_and_ui",
        "file_patterns": ["*.tsx", "*.jsx", "*.html", "*.vue", "*.svelte"],
        "severity": "HIGH",
    },
    "verification-oracle-architect": {
        "guard_script": "verification_oracle_guard.py",
        "category": "testing_and_simulation",
        "file_patterns": ["tests/**", "*.test.*", "*_test.*"],
        "severity": "CRITICAL",
    },
    "zero-downtime-migration-gate": {
        "guard_script": "migration_guard.py",
        "category": "sre_and_architecture",
        "file_patterns": ["migrations/**", "db/**", "src/schema/**", "*.sql"],
        "severity": "CRITICAL",
    },
}


def parse_frontmatter(text: str) -> Dict[str, str]:
    """Parse YAML frontmatter from markdown file."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return {}

    fields = {}
    current_key = None
    multiline_parts = []
    for raw_line in lines[1:end_idx]:
        if not raw_line.strip():
            continue
        if current_key and raw_line[:1].isspace():
            multiline_parts.append(raw_line.strip())
            continue
        if current_key and multiline_parts:
            fields[current_key] = " ".join(multiline_parts).strip()
            multiline_parts = []
        current_key = None
        if ":" not in raw_line or raw_line[:1].isspace():
            continue
        k, v = raw_line.split(":", 1)
        k = k.strip()
        v = v.strip().strip('"').strip("'")
        if v in {"|", ">", "|-", ">-"}:
            current_key = k
            continue
        fields[k] = v
    if current_key and multiline_parts:
        fields[current_key] = " ".join(multiline_parts).strip()
    return fields


def extract_axioms_from_markdown(text: str) -> List[Dict[str, str]]:
    """Extract formal rules, laws, pillars and invariants from markdown headings and bullet lists."""
    axioms: List[Dict[str, str]] = []
    lines = text.splitlines()

    # Look for patterns like ### Pillar N:, ### Law N:, - **Rule: ...**, etc.
    law_heading_pattern = re.compile(r"^#{2,4}\s+(?:Law|Pillar|Truth|Invariant|Rule)\s*(\d+)?:?\s*(.+)$", re.IGNORECASE)
    bullet_law_pattern = re.compile(r"^[-*]\s+\*\*([^*]+)\*\*[:\s]+(.+)$")

    current_section = ""
    for idx, line in enumerate(lines):
        line_clean = line.strip()
        if line_clean.startswith("#"):
            current_section = line_clean

        m_head = law_heading_pattern.match(line_clean)
        if m_head:
            num = m_head.group(1) or str(len(axioms) + 1)
            title = m_head.group(2).strip()
            # Capture next 3 non-empty lines as assertion text
            body_lines = []
            for next_line in lines[idx + 1:idx + 6]:
                if next_line.strip().startswith("#"):
                    break
                if next_line.strip():
                    body_lines.append(next_line.strip())
            assertion = " ".join(body_lines) or title
            axioms.append({
                "id": f"AXIOM-{len(axioms) + 1}",
                "title": title,
                "assertion": assertion[:300],
            })
            continue

        m_bullet = bullet_law_pattern.match(line_clean)
        if m_bullet and any(kw in current_section.lower() for kw in ["invariant", "law", "pillar", "rule", "truth", "standard"]):
            b_title = m_bullet.group(1).strip()
            b_assertion = m_bullet.group(2).strip()
            axioms.append({
                "id": f"AXIOM-{len(axioms) + 1}",
                "title": b_title,
                "assertion": b_assertion[:300],
            })

    return axioms


def extract_all_skills() -> Dict[str, Any]:
    """Iterate through all skills and compile the universal rules ledger."""
    ledger: Dict[str, Any] = {
        "schema_version": "2.0.0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_skills": 0,
        "total_rules": 0,
        "skills": {},
    }

    skill_folders = sorted([p for p in SKILLS_DIR.iterdir() if p.is_dir() and (p / "SKILL.md").exists()])
    ledger["total_skills"] = len(skill_folders)

    rule_counter = 0

    for s_path in skill_folders:
        s_name = s_path.name
        skill_file = s_path / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        fm = parse_frontmatter(content)

        meta_config = SKILL_GUARD_MAP.get(s_name, {
            "guard_script": None,
            "category": "sre_and_architecture",
            "file_patterns": ["*"],
            "severity": "HIGH",
        })

        axioms = extract_axioms_from_markdown(content)
        if not axioms:
            # Fallback axiom from frontmatter description
            desc = fm.get("description", s_name)
            axioms.append({
                "id": "AXIOM-1",
                "title": f"Core Principle of {s_name}",
                "assertion": desc[:300],
            })

        rule_counter += len(axioms)

        ledger["skills"][s_name] = {
            "id": s_name,
            "display_name": fm.get("name", s_name),
            "description": fm.get("description", ""),
            "category": meta_config["category"],
            "severity": meta_config["severity"],
            "guard_script": meta_config["guard_script"],
            "file_patterns": meta_config["file_patterns"],
            "execution_tier": "DETERMINISTIC" if meta_config["guard_script"] else "SEMANTIC",
            "axioms_count": len(axioms),
            "axioms": axioms,
        }

    ledger["total_rules"] = rule_counter
    return ledger


def main():
    parser = argparse.ArgumentParser(description="Extract skill rules and compile into universal ledger.")
    parser.add_argument("--output", default=str(OUTPUT_PATH), help="Output path for the compiled JSON ledger")
    parser.add_argument("--summary", action="store_true", help="Print summary table of extracted skills")
    args = parser.parse_args()

    ledger = extract_all_skills()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"✅ Successfully compiled {ledger['total_skills']} skills ({ledger['total_rules']} axioms) to {out_path}")

    if args.summary:
        print("\n=== SKILLS INVARIANT LEDGER SUMMARY ===")
        print(f"{'Skill ID':<45} | {'Category':<22} | {'Tier':<14} | {'Axioms':<6} | {'Guard'}")
        print("-" * 110)
        for s_id, s_data in ledger["skills"].items():
            guard = s_data["guard_script"] or "(semantic-eval)"
            print(f"{s_id:<45} | {s_data['category']:<22} | {s_data['execution_tier']:<14} | {s_data['axioms_count']:<6} | {guard}")


if __name__ == "__main__":
    main()
