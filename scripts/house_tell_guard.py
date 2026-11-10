#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Agent House-Tell & Triple-Reflex Inversion Guard.

Enforces the Gate 0 Pre-Commit Inversion Contract before code generation:
1. Signature Peak (The ONE primary distinct element)
2. Color Strategy & Target Lightness (OKLCH tier + numeric L)
3. Typographic Contrast Axis (rejecting Inter/Space Grotesk AI defaults)
4. Grid/Structure Break (concrete asymmetric disruption)
5. Motion Budget (<=3 pattern families)
6. Category Reflex Inversion (1st order, 2nd order, and chosen deviation)
7. House Tells Broken (minimum 2 habits of the agent itself contractually barred)

Usage:
    python3 scripts/house_tell_guard.py --file .anti-slop/commit-sheet.json
    python3 scripts/house_tell_guard.py --file design/COMMIT-SHEET.md --json
    python3 scripts/house_tell_guard.py --init-template
    python3 scripts/house_tell_guard.py --selftest
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

BANNED_TRUISMS = [
    "modern, clean",
    "clean and modern",
    "beautiful animations throughout",
    "sleek and intuitive",
    "user-friendly design",
    "best practices",
    "inter for everything",
    "inter is readable",
]

DEFAULT_HOUSE_TELLS = [
    "near-black background as automatic premium signal",
    "mono service labels in corners (v1.0 / SYS_OK)",
    "logo/status/action top bar layout",
    "scroll-instruction footer with chevron",
    "amber-or-acid accent on neutral dark ground",
    "wordmark-as-hero filling viewport",
    "emissive glow standing in for lighting",
    "decorative comment banners (// =====)",
    "three-column identical feature cards",
]


def is_truism_or_generic(val: str) -> bool:
    """Detect ungrounded generic AI slop answers."""
    cleaned = val.lower().strip()
    if len(cleaned) < 15:
        return True
    for banned in BANNED_TRUISMS:
        if banned in cleaned:
            return True
    return False


def parse_markdown_commit_sheet(content: str) -> Dict[str, Any]:
    """Extract commit sheet fields from markdown formatted document."""
    data: Dict[str, Any] = {
        "signature_peak": "",
        "color_tier": "COMMITTED",
        "target_lightness": 0.50,
        "contrast_axis": "",
        "grid_break": "",
        "motion_budget": [],
        "category_reflex": {
            "first_order": "",
            "second_order": "",
            "chosen_deviation": "",
        },
        "house_tells_broken": [],
    }

    # 1. Peak
    m_peak = re.search(r"##\s*1\.\s*Peak[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.I)
    if m_peak:
        lines = [line.strip().lstrip("✓").lstrip("✗").strip() for line in m_peak.group(1).splitlines() if line.strip() and not line.strip().startswith("<!--") and not line.strip().startswith(">")]
        data["signature_peak"] = " ".join(lines).strip()

    # 2. Color & Lightness
    m_color = re.search(r"##\s*2\.\s*Color[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.I)
    if m_color:
        block = m_color.group(1)
        m_l = re.search(r"(?:target\s*mean\s*L|background\s*L|L\s*≈|L\s*=)\s*([\d.]+)", block, re.I)
        if m_l:
            data["target_lightness"] = float(m_l.group(1))
        for tier in ("RESTRAINED", "COMMITTED", "FULL_PALETTE", "DRENCHED"):
            if tier.lower() in block.lower():
                data["color_tier"] = tier
                break

    # 3. Type
    m_type = re.search(r"##\s*3\.\s*Type[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.I)
    if m_type:
        lines = [line.strip() for line in m_type.group(1).splitlines() if line.strip() and not line.strip().startswith("<!--") and not line.strip().startswith(">")]
        data["contrast_axis"] = " ".join(lines).strip()

    # 4. Grid break
    m_grid = re.search(r"##\s*4\.\s*Grid break[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.I)
    if m_grid:
        lines = [line.strip() for line in m_grid.group(1).splitlines() if line.strip() and not line.strip().startswith("<!--") and not line.strip().startswith(">")]
        data["grid_break"] = " ".join(lines).strip()

    # 5. Motion budget
    m_motion = re.search(r"##\s*5\.\s*Motion budget[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.I)
    if m_motion:
        items = re.findall(r"\(\d+\)\s*([^\n,;()]+)", m_motion.group(1))
        if items:
            data["motion_budget"] = [it.strip() for it in items if it.strip()]
        else:
            lines = [line.strip() for line in m_motion.group(1).splitlines() if line.strip() and not line.strip().startswith("<!--") and not line.strip().startswith(">")]
            data["motion_budget"] = lines[:3]

    # 6. Reflex check
    m_ref = re.search(r"##\s*6\.\s*Reflex check[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.I)
    if m_ref:
        block = m_ref.group(1)
        m_a = re.search(r"(?:a\)|1st order:?)\s*([^\n]+)", block, re.I)
        m_b = re.search(r"(?:b\)|2nd order:?)\s*([^\n]+)", block, re.I)
        m_c = re.search(r"(?:c\)|ours|deviation:?)\s*([^\n]+)", block, re.I)
        if m_a: data["category_reflex"]["first_order"] = m_a.group(1).strip()
        if m_b: data["category_reflex"]["second_order"] = m_b.group(1).strip()
        if m_c: data["category_reflex"]["chosen_deviation"] = m_c.group(1).strip()

    # 7. House tells broken
    m_tells = re.search(r"##\s*7\.\s*House tells broken[^\n]*\n(.*?)(?=\n##|\Z)", content, re.DOTALL | re.I)
    if m_tells:
        tell_lines = [line.strip() for line in m_tells.group(1).splitlines() if line.strip() and not line.strip().startswith("<!--") and not line.strip().startswith(">")]
        for tl in tell_lines:
            if "→" in tl:
                parts = tl.split("→", 1)
                data["house_tells_broken"].append({"tell": parts[0].strip(), "replacement": parts[1].strip()})
            elif "->" in tl:
                parts = tl.split("->", 1)
                data["house_tells_broken"].append({"tell": parts[0].strip(), "replacement": parts[1].strip()})
            elif len(tl) > 10:
                data["house_tells_broken"].append({"tell": tl, "replacement": "deliberate alternative"})

    return data


def evaluate_commit_sheet(sheet_path: Path) -> Dict[str, Any]:
    """Audit commit sheet for required commitments, non-truisms, and house tells."""
    findings: List[Dict[str, Any]] = []

    if not sheet_path.exists():
        return {
            "schema_version": "1.0.0",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "verdict": "REJECT",
            "commit_sheet_path": str(sheet_path),
            "commit_sheet_hash": "",
            "signature_peak": "",
            "color_tier": "COMMITTED",
            "target_lightness": 0.0,
            "contrast_axis": "",
            "grid_break": "",
            "motion_budget": [],
            "category_reflex": {"first_order": "", "second_order": "", "chosen_deviation": ""},
            "house_tells_broken": [],
            "findings_count": 1,
            "findings": [{
                "id": "HT-MISSING-SHEET",
                "file": str(sheet_path),
                "line": 1,
                "class": "MISSING_COMMIT_SHEET",
                "severity": "BLOCKING",
                "evidence": f"Pre-commit sheet does not exist at {sheet_path}",
                "recommendation": "Author .anti-slop/commit-sheet.json or design/COMMIT-SHEET.md before code generation.",
            }],
        }

    raw_text = sheet_path.read_text(encoding="utf-8")
    sheet_hash = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()

    if sheet_path.suffix.lower() == ".json":
        try:
            data = json.loads(raw_text)
        except Exception as e:
            return {
                "schema_version": "1.0.0",
                "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "verdict": "REJECT",
                "commit_sheet_path": str(sheet_path),
                "commit_sheet_hash": sheet_hash,
                "signature_peak": "",
                "color_tier": "COMMITTED",
                "target_lightness": 0.0,
                "contrast_axis": "",
                "grid_break": "",
                "motion_budget": [],
                "category_reflex": {"first_order": "", "second_order": "", "chosen_deviation": ""},
                "house_tells_broken": [],
                "findings_count": 1,
                "findings": [{
                    "id": "HT-INVALID-JSON",
                    "file": str(sheet_path),
                    "line": 1,
                    "class": "MISSING_COMMIT_SHEET",
                    "severity": "BLOCKING",
                    "evidence": f"Failed to parse JSON commit sheet: {e}",
                    "recommendation": "Fix JSON syntax in commit sheet.",
                }],
            }
    else:
        data = parse_markdown_commit_sheet(raw_text)

    # 1. Peak check
    peak = data.get("signature_peak", "")
    if not peak or is_truism_or_generic(peak):
        findings.append({
            "id": "HT-GENERIC-PEAK",
            "file": str(sheet_path),
            "line": 1,
            "class": "GENERIC_COMMITMENT_TRUISM",
            "severity": "BLOCKING",
            "evidence": f"Signature peak is generic or empty: '{peak}'",
            "recommendation": "Name the ONE distinct signature interaction/scene (e.g. 300vh canvas disassembly).",
        })

    # 2. Type contrast axis & Inter check
    axis = data.get("contrast_axis", "")
    inter_as_default = bool(re.search(r"^\s*inter\b|display\s*:\s*inter\b|text\s*:\s*inter\b|inter\s+for\b", axis, re.I))
    if not axis or inter_as_default or is_truism_or_generic(axis):
        findings.append({
            "id": "HT-TYPE-AXIS",
            "file": str(sheet_path),
            "line": 1,
            "class": "GENERIC_COMMITMENT_TRUISM",
            "severity": "BLOCKING",
            "evidence": f"Type pairing lacks contrast axis or adopts Inter as default: '{axis}'",
            "recommendation": "Pair on a contrast axis (serif display + grotesque text) and reject default Inter.",
        })

    # 3. Motion budget check (max 3)
    mb = data.get("motion_budget", [])
    if not isinstance(mb, list) or len(mb) == 0:
        findings.append({
            "id": "HT-MOTION-EMPTY",
            "file": str(sheet_path),
            "line": 1,
            "class": "MOTION_BUDGET_OVERFLOW",
            "severity": "BLOCKING",
            "evidence": "Motion budget is empty.",
            "recommendation": "Declare 1 to 3 named scroll-pattern families.",
        })
    elif len(mb) > 3:
        findings.append({
            "id": "HT-MOTION-EXCEEDED",
            "file": str(sheet_path),
            "line": 1,
            "class": "MOTION_BUDGET_OVERFLOW",
            "severity": "BLOCKING",
            "evidence": f"Motion budget declares {len(mb)} patterns (> 3 max allowed).",
            "recommendation": "Cap motion budget to at most 3 scroll-triggered pattern families.",
        })

    # 4. Reflex check
    ref = data.get("category_reflex", {})
    if not ref.get("first_order") or not ref.get("second_order") or not ref.get("chosen_deviation"):
        findings.append({
            "id": "HT-REFLEX-COLLAPSE",
            "file": str(sheet_path),
            "line": 1,
            "class": "CATEGORY_REFLEX_COLLAPSE",
            "severity": "BLOCKING",
            "evidence": "Category reflex check is incomplete (requires 1st order, 2nd order, and chosen deviation).",
            "recommendation": "Document what generic AI does (1st order), what avoiding that does (2nd order), and your brand deviation.",
        })

    # 5. House tells broken (minimum 2 required)
    tells_broken = data.get("house_tells_broken", [])
    if not isinstance(tells_broken, list) or len(tells_broken) < 2:
        findings.append({
            "id": "HT-INSUFFICIENT-TELLS",
            "file": str(sheet_path),
            "line": 1,
            "class": "INSUFFICIENT_HOUSE_TELLS_BROKEN",
            "severity": "BLOCKING",
            "evidence": f"Only {len(tells_broken)} house tells broken declared (minimum 2 required).",
            "recommendation": "Name at least 2 habits of the agent itself from taste.md §2.5 that are deliberately broken.",
        })

    verdict = "PROCEED"
    if any(f["severity"] == "BLOCKING" for f in findings):
        verdict = "REJECT"
    elif findings:
        verdict = "WARNING"

    return {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "commit_sheet_path": str(sheet_path),
        "commit_sheet_hash": sheet_hash,
        "signature_peak": peak,
        "color_tier": data.get("color_tier", "COMMITTED"),
        "target_lightness": float(data.get("target_lightness", 0.50)),
        "contrast_axis": axis,
        "grid_break": data.get("grid_break", ""),
        "motion_budget": mb,
        "category_reflex": ref,
        "house_tells_broken": tells_broken,
        "findings_count": len(findings),
        "findings": findings,
    }


def generate_template_commit_sheet() -> Dict[str, Any]:
    """Generate default compliant commit-sheet template."""
    return {
        "signature_peak": "Hero: technical cutaway view disassembling into 8 floating schematics on scroll",
        "color_tier": "COMMITTED",
        "target_lightness": 0.55,
        "contrast_axis": "Display: Fraunces (soft serif) × Text: Archivo (grotesque); Inter rejected",
        "grid_break": "Product schematic in Section 2 crosses into Section 3 with -120px overlap",
        "motion_budget": [
            "Scrub-pinned hero camera travel",
            "Per-word headline unblur reveals",
            "Depth parallax in architecture section"
        ],
        "category_reflex": {
            "first_order": "Dark background with neon blue glow and terminal monospace",
            "second_order": "Off-white editorial serif anti-SaaS cliché",
            "chosen_deviation": "Terracotta daylit paper with precise CAD architectural line work"
        },
        "house_tells_broken": [
            {
                "tell": "near-black background as automatic premium signal",
                "replacement": "daylit L=0.55 paper ground where directional shadows create depth"
            },
            {
                "tell": "mono service labels in corners (v1.0 / SYS_OK)",
                "replacement": "zero ornamental corner chrome; clean editorial margins"
            }
        ]
    }


def run_selftest() -> None:
    """Validate commit sheet parsing and rules."""
    tpl = generate_template_commit_sheet()
    tmp_path = Path("/tmp/test_commit_sheet.json")
    tmp_path.write_text(json.dumps(tpl), encoding="utf-8")
    report = evaluate_commit_sheet(tmp_path)
    assert report["verdict"] == "PROCEED", f"Expected PROCEED, got: {report}"
    assert len(report["house_tells_broken"]) >= 2
    print("PASS: House tell guard selftest green.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Agent House-Tell & Triple-Reflex Inversion Guard."
    )
    parser.add_argument("--file", type=str, default=".anti-slop/commit-sheet.json", help="Path to commit sheet")
    parser.add_argument("--init-template", action="store_true", help="Generate template commit-sheet.json")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Fail with code 2 on warnings")
    parser.add_argument("--selftest", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    if args.init_template:
        out_dir = Path(".anti-slop")
        out_dir.mkdir(parents=True, exist_ok=True)
        target = out_dir / "commit-sheet.json"
        target.write_text(json.dumps(generate_template_commit_sheet(), indent=2), encoding="utf-8")
        print(f"Created template commit sheet at {target}")
        return 0

    sheet_path = Path(args.file).resolve()
    report = evaluate_commit_sheet(sheet_path)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"House Tell Guard Verdict: {report['verdict']}")
        print(f"Commit Sheet: {report['commit_sheet_path']}")
        print(f"Signature Peak: {report['signature_peak']}")
        print(f"House Tells Broken: {len(report['house_tells_broken'])}")
        print(f"Total Findings: {report['findings_count']}")
        for f in report["findings"]:
            print(f"  [{f['severity']}] {f['class']}: {f['evidence']}")
            print(f"      Fix: {f['recommendation']}")

    if report["verdict"] == "REJECT" or (args.strict and report["verdict"] == "WARNING"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
