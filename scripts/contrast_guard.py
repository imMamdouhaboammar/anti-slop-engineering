#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Zero-dependency WCAG 2.1 / 2.2 Contrast & Accessibility Guard.

Computes exact relative luminance and contrast ratios following WCAG standards.
Verifies normal text (4.5:1 AA, 7.0:1 AAA), large text (3.0:1 AA, 4.5:1 AAA),
and graphical UI components (3.0:1 WCAG 1.4.11).

Usage:
    python3 scripts/contrast_guard.py "#FFFFFF" "#1E293B"
    python3 scripts/contrast_guard.py "black on white"
    python3 scripts/contrast_guard.py --scan src/
    python3 scripts/contrast_guard.py --selftest
    python3 scripts/contrast_guard.py --json "#777777" "#FFFFFF"
"""

import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

NAMED_COLORS: Dict[str, Tuple[int, int, int]] = {
    "black": (0, 0, 0),
    "white": (255, 255, 255),
    "red": (255, 0, 0),
    "green": (0, 128, 0),
    "blue": (0, 0, 255),
    "yellow": (255, 255, 0),
    "gray": (128, 128, 128),
    "grey": (128, 128, 128),
    "lightgray": (211, 211, 211),
    "lightgrey": (211, 211, 211),
    "darkgray": (169, 169, 169),
    "darkgrey": (169, 169, 169),
    "slate-900": (15, 23, 42),
    "slate-800": (30, 41, 59),
    "slate-700": (51, 65, 85),
    "slate-500": (100, 116, 139),
    "slate-100": (241, 245, 249),
    "slate-50": (248, 250, 252),
    "gray-900": (17, 24, 39),
    "gray-700": (55, 65, 81),
    "gray-500": (107, 114, 128),
    "gray-400": (156, 163, 175),
    "gray-300": (209, 213, 219),
    "gray-100": (243, 244, 246),
    "zinc-900": (24, 24, 27),
    "zinc-800": (39, 39, 42),
    "zinc-500": (113, 113, 122),
    "zinc-100": (244, 244, 245),
}

# Known reference pairings with expected ratios and verdicts for selftest
SELFTEST_CASES = [
    ("white", "black", 21.0, True, True),
    ("black", "white", 21.0, True, True),
    ("#555555", "#000000", 2.82, False, False),
    ("#777777", "#FFFFFF", 4.48, False, True),  # Fails normal text AA (4.5), passes large (3.0)
    ("#595959", "#FFFFFF", 7.00, True, True),
    ("#1E293B", "#F8FAFC", 13.98, True, True),
    ("#3B82F6", "#FFFFFF", 3.68, False, True),  # Blue-500 on white fails AA normal text
    ("#1D4ED8", "#FFFFFF", 6.70, True, True),   # Blue-700 on white passes AA normal text
]


def parse_color(val: str) -> Tuple[int, int, int]:
    """Parse color string into RGB tuple (0-255). Supports hex (#RGB, #RRGGBB) and named colors."""
    token = val.strip().lower()
    if token in NAMED_COLORS:
        return NAMED_COLORS[token]
    
    clean = token.lstrip("#")
    if len(clean) == 3 and re.fullmatch(r"[0-9a-f]{3}", clean):
        clean = "".join(c * 2 for c in clean)
    
    if len(clean) == 6 and re.fullmatch(r"[0-9a-f]{6}", clean):
        return (
            int(clean[0:2], 16),
            int(clean[2:4], 16),
            int(clean[4:6], 16),
        )
    
    raise ValueError(f"Invalid color representation: '{val}'. Expected 3/6-char hex or supported named color.")


def relative_luminance(rgb: Tuple[int, int, int]) -> float:
    """Compute relative luminance according to WCAG 2.1 / 2.2."""
    def channel_linear(c_byte: int) -> float:
        c = c_byte / 255.0
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r_lin = channel_linear(rgb[0])
    g_lin = channel_linear(rgb[1])
    b_lin = channel_linear(rgb[2])
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(rgb1: Tuple[int, int, int], rgb2: Tuple[int, int, int]) -> float:
    """Calculate contrast ratio between two colors (range: 1.0 to 21.0)."""
    lum1 = relative_luminance(rgb1)
    lum2 = relative_luminance(rgb2)
    l_max = max(lum1, lum2)
    l_min = min(lum1, lum2)
    return (l_max + 0.05) / (l_min + 0.05)


def evaluate_contrast(color1_str: str, color2_str: str) -> Dict[str, object]:
    """Evaluate contrast pairing and return structured evaluation dictionary."""
    rgb1 = parse_color(color1_str)
    rgb2 = parse_color(color2_str)
    ratio = calculate_contrast_ratio(rgb1, rgb2)
    rounded_ratio = round(ratio, 2)

    pass_normal_aa = rounded_ratio >= 4.5
    pass_normal_aaa = rounded_ratio >= 7.0
    pass_large_aa = rounded_ratio >= 3.0
    pass_large_aaa = rounded_ratio >= 4.5
    pass_ui_component = rounded_ratio >= 3.0

    return {
        "color1": color1_str,
        "color2": color2_str,
        "rgb1": rgb1,
        "rgb2": rgb2,
        "ratio": rounded_ratio,
        "wcag_aa_normal": pass_normal_aa,
        "wcag_aaa_normal": pass_normal_aaa,
        "wcag_aa_large": pass_large_aa,
        "wcag_aaa_large": pass_large_aaa,
        "wcag_ui_component": pass_ui_component,
        "overall_status": "PASS" if pass_normal_aa else ("PASS_LARGE_ONLY" if pass_large_aa else "FAIL"),
    }


def scan_file_for_contrast(path: str) -> List[Dict[str, object]]:
    """Scan CSS/HTML/JSX/TSX source file for known Tailwind / CSS color pairings and check contrast."""
    findings = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception:
        return findings

    # Look for co-occurring text-* and bg-* classes on the same line
    tailwind_pair_pattern = re.compile(r"text-(gray|slate|zinc)-(300|400|500|700|900)\s+[^\"\'>]*bg-(white|black|slate-900|gray-900)")
    reverse_pair_pattern = re.compile(r"bg-(white|black|slate-900|gray-900)\s+[^\"\'>]*text-(gray|slate|zinc)-(300|400|500|700|900)")

    for line_idx, line in enumerate(lines, start=1):
        m1 = tailwind_pair_pattern.search(line)
        if m1:
            fg_name = f"{m1.group(1)}-{m1.group(2)}"
            bg_name = m1.group(3)
            eval_res = evaluate_contrast(fg_name, bg_name)
            if eval_res["overall_status"] != "PASS":
                findings.append({
                    "file": path,
                    "line": line_idx,
                    "fg": fg_name,
                    "bg": bg_name,
                    "ratio": eval_res["ratio"],
                    "status": eval_res["overall_status"],
                    "snippet": line.strip()[:100],
                })
        m2 = reverse_pair_pattern.search(line)
        if m2:
            bg_name = m2.group(1)
            fg_name = f"{m2.group(2)}-{m2.group(3)}"
            eval_res = evaluate_contrast(fg_name, bg_name)
            if eval_res["overall_status"] != "PASS":
                findings.append({
                    "file": path,
                    "line": line_idx,
                    "fg": fg_name,
                    "bg": bg_name,
                    "ratio": eval_res["ratio"],
                    "status": eval_res["overall_status"],
                    "snippet": line.strip()[:100],
                })

    return findings


def run_selftest() -> bool:
    """Execute selftest against known WCAG calibration cases."""
    print("Running WCAG 2.1 / 2.2 Contrast Guard Self-Test...")
    all_ok = True
    for c1, c2, min_ratio, exp_normal, exp_large in SELFTEST_CASES:
        res = evaluate_contrast(c1, c2)
        ratio_ok = abs(res["ratio"] - min_ratio) <= 0.05
        normal_ok = res["wcag_aa_normal"] == exp_normal
        large_ok = res["wcag_aa_large"] == exp_large
        if ratio_ok and normal_ok and large_ok:
            print(f"  ✓ {c1} on {c2}: ratio={res['ratio']} (Normal={res['wcag_aa_normal']}, Large={res['wcag_aa_large']})")
        else:
            print(f"  ✗ {c1} on {c2}: got ratio={res['ratio']} (expected ~{min_ratio}), Normal={res['wcag_aa_normal']}, Large={res['wcag_aa_large']}")
            all_ok = False
    return all_ok


def main() -> int:
    args = sys.argv[1:]
    if not args or "-h" in args or "--help" in args:
        print(__doc__)
        return 0

    json_mode = "--json" in args
    if json_mode:
        args = [a for a in args if a != "--json"]

    if "--selftest" in args:
        ok = run_selftest()
        if json_mode:
            print(json.dumps({"selftest": "PASS" if ok else "FAIL"}))
        return 0 if ok else 1

    if "--scan" in args:
        idx = args.index("--scan")
        target_path = args[idx + 1] if idx + 1 < len(args) else "."
        all_findings = []
        if os.path.isfile(target_path):
            all_findings.extend(scan_file_for_contrast(target_path))
        else:
            for root, _, files in os.walk(target_path):
                for f in files:
                    if f.endswith((".tsx", ".jsx", ".html", ".css", ".vue", ".svelte")):
                        all_findings.extend(scan_file_for_contrast(os.path.join(root, f)))

        if json_mode:
            print(json.dumps({"findings": all_findings, "total": len(all_findings)}, indent=2))
        else:
            print(f"🔍 Contrast Scan Results for '{target_path}':")
            if not all_findings:
                print("  ✓ Zero low-contrast color pairings detected.")
            else:
                for f in all_findings:
                    print(f"  ✗ {f['file']}:{f['line']} [{f['status']}] ratio={f['ratio']}:1 ({f['fg']} on {f['bg']})")
                    print(f"      {f['snippet']}")
        return 0 if not all_findings else 1

    # Single or paired color arguments
    tokens = []
    for a in args:
        if " on " in a.lower():
            parts = re.split(r"\s+on\s+", a, flags=re.IGNORECASE)
            tokens.extend([p.strip() for p in parts if p.strip()])
        else:
            tokens.append(a)

    if len(tokens) < 2:
        print("Error: provide two colors to compare (e.g. contrast_guard.py '#FFFFFF' '#1E293B')", file=sys.stderr)
        return 2

    c1, c2 = tokens[0], tokens[1]
    try:
        res = evaluate_contrast(c1, c2)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2

    if json_mode:
        print(json.dumps(res, indent=2))
    else:
        status_symbol = "✓" if res["wcag_aa_normal"] else ("⚠️" if res["wcag_aa_large"] else "✗")
        print(f"\n{status_symbol} Contrast Evaluation: {res['color1']} on {res['color2']}")
        print(f"   Contrast Ratio:       {res['ratio']}:1")
        print(f"   Normal Text (AA 4.5): {'PASS' if res['wcag_aa_normal'] else 'FAIL'}")
        print(f"   Normal Text (AAA 7.0):{'PASS' if res['wcag_aaa_normal'] else 'FAIL'}")
        print(f"   Large Text  (AA 3.0): {'PASS' if res['wcag_aa_large'] else 'FAIL'}")
        print(f"   Large Text  (AAA 4.5):{'PASS' if res['wcag_aaa_large'] else 'FAIL'}")
        print(f"   UI Graphic  (3.0:1):  {'PASS' if res['wcag_ui_component'] else 'FAIL'}")
        print(f"   Verdict:              {res['overall_status']}\n")

    return 0 if res["wcag_aa_normal"] else 1


if __name__ == "__main__":
    sys.exit(main())
