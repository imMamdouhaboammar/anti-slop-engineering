#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Chromatic Saturation Drift & OKLCH Category Reflex Guard.

Zero-dependency standard-library implementation of sRGB <-> OKLab <-> OKLCH color
transformations. Detects cheerful saturation drift (oversaturating muted/analog palettes),
background lightness drift against committed targets, and category reflex traps
(warm-cream band, purple-blue gradient defaults, dark-mode inertia).

Usage:
    python3 scripts/chroma_drift_guard.py --scan src/ --target-l 0.55
    python3 scripts/chroma_drift_guard.py --color "#7b6b63" --target-c 0.04 --max-delta 0.02
    python3 scripts/chroma_drift_guard.py --file record.json --json
    python3 scripts/chroma_drift_guard.py --selftest
"""

import argparse
import datetime
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCAN_EXTENSIONS = {".css", ".scss", ".jsx", ".tsx", ".vue", ".svelte", ".html", ".js", ".ts"}
SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".next", "out"}


def srgb_to_linear(c: float) -> float:
    """Convert sRGB 0..1 to linear RGB."""
    return c / 12.92 if c <= 0.04045 else math.pow((c + 0.055) / 1.055, 2.4)


def rgb_to_oklch(r_byte: int, g_byte: int, b_byte: int) -> Tuple[float, float, float]:
    """Convert sRGB bytes (0-255) to CIE OKLCH (L in 0..1, C >= 0, H in 0..360)."""
    r_lin = srgb_to_linear(r_byte / 255.0)
    g_lin = srgb_to_linear(g_byte / 255.0)
    b_lin = srgb_to_linear(b_byte / 255.0)

    # Approximate cone responses
    l = 0.4122214708 * r_lin + 0.5363325363 * g_lin + 0.0514459929 * b_lin
    m = 0.2119034982 * r_lin + 0.6806995451 * g_lin + 0.1073969566 * b_lin
    s = 0.0883024619 * r_lin + 0.2817188376 * g_lin + 0.6299787005 * b_lin

    l_ = math.pow(l, 1.0 / 3.0) if l > 0 else 0.0
    m_ = math.pow(m, 1.0 / 3.0) if m > 0 else 0.0
    s_ = math.pow(s, 1.0 / 3.0) if s > 0 else 0.0

    # OKLab components
    L = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
    a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
    b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

    C = math.sqrt(a * a + b * b)
    H_rad = math.atan2(b, a)
    H = math.degrees(H_rad) % 360.0

    return (max(0.0, min(1.0, L)), max(0.0, C), H)


def parse_color_token(token: str) -> Optional[Tuple[float, float, float]]:
    """Parse color representation into OKLCH (L, C, H)."""
    t = token.strip()

    # oklch(L C H [/ alpha])
    m_ok = re.match(r"^oklch\(\s*([\d.]+%?)\s+([\d.]+)\s+([\d.]+)", t, re.I)
    if m_ok:
        l_str = m_ok.group(1)
        L = float(l_str.rstrip("%")) / 100.0 if l_str.endswith("%") else float(l_str)
        C = float(m_ok.group(2))
        H = float(m_ok.group(3)) % 360.0
        return (max(0.0, min(1.0, L)), max(0.0, C), H)

    # hex (#rgb or #rrggbb or #rrggbbaa)
    m_hex = re.match(r"^#([0-9a-fA-F]{3,8})$", t)
    if m_hex:
        h = m_hex.group(1)
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h[:3])
        elif len(h) >= 6:
            h = h[:6]
        else:
            return None
        r = int(h[0:2], 16)
        g = int(h[2:4], 16)
        b = int(h[4:6], 16)
        return rgb_to_oklch(r, g, b)

    # rgb / rgba
    m_rgb = re.match(r"^rgba?\(\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*[,\s]\s*([\d.]+)", t, re.I)
    if m_rgb:
        r = int(float(m_rgb.group(1)))
        g = int(float(m_rgb.group(2)))
        b = int(float(m_rgb.group(3)))
        return rgb_to_oklch(r, g, b)

    return None


def is_cream_reflex(lch: Tuple[float, float, float]) -> bool:
    """Detect saturated AI warm-cream default: L in 0.84..0.97, C < 0.06, H in 40..100."""
    L, C, H = lch
    return 0.84 <= L <= 0.97 and C < 0.06 and 40.0 <= H <= 100.0


def is_purple_blue_gradient(stops: List[Tuple[float, float, float]]) -> bool:
    """Detect AI default purple-blue gradient: >=2 non-gray stops with H in 250..290."""
    ai_stops = [s for s in stops if s[1] >= 0.04 and 250.0 <= s[2] <= 290.0]
    return len(ai_stops) >= 2


def scan_file_for_chroma(
    file_path: Path,
    bg_lightnesses: List[float],
    chromas: List[float],
    reflex_violations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Scan file for color declarations, gradients, and reflex patterns."""
    findings: List[Dict[str, Any]] = []
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return findings

    lines = content.splitlines()

    for idx, line in enumerate(lines, 1):
        # Background color declarations
        bg_m = re.search(r"background(?:-color)?\s*:\s*([^;\n}]+)", line, re.I)
        if bg_m:
            val = bg_m.group(1).strip()
            lch = parse_color_token(val)
            if lch:
                L, C, H = lch
                bg_lightnesses.append(L)
                chromas.append(C)
                if is_cream_reflex(lch):
                    reflex_violations.append({
                        "band": "CREAM_BAND_REFLEX",
                        "color": val,
                        "file": str(file_path),
                        "line": idx,
                    })
                    findings.append({
                        "id": f"CHROMA-CREAM-{idx}",
                        "file": str(file_path),
                        "line": idx,
                        "class": "CREAM_BAND_REFLEX",
                        "severity": "WARNING",
                        "evidence": f"Background '{val}' falls into the warm-cream AI default band (L={L:.2f}, C={C:.3f}, H={H:.0f}°).",
                        "recommendation": "Use a deliberate saturated brand surface or true neutral; express warmth via accent and type.",
                    })

        # Gradients
        grad_matches = re.finditer(r"(?:linear|radial|conic)-gradient\s*\(([^)]+)\)", line, re.I)
        for gm in grad_matches:
            body = gm.group(1)
            # Find colors inside gradient body
            stops: List[Tuple[float, float, float]] = []
            for token in re.finditer(r"#[0-9a-fA-F]{3,8}|oklch\([^)]+\)|rgba?\([^)]+\)", body):
                stop_lch = parse_color_token(token.group(0))
                if stop_lch:
                    stops.append(stop_lch)
            if is_purple_blue_gradient(stops):
                reflex_violations.append({
                    "band": "PURPLE_BLUE_GRADIENT_REFLEX",
                    "color": gm.group(0)[:60],
                    "file": str(file_path),
                    "line": idx,
                })
                findings.append({
                    "id": f"CHROMA-GRAD-{idx}",
                    "file": str(file_path),
                    "line": idx,
                    "class": "PURPLE_BLUE_GRADIENT_REFLEX",
                    "severity": "BLOCKING",
                    "evidence": f"Gradient has >=2 stops in purple-blue AI band (H in 250-290°): {gm.group(0)[:60]}",
                    "recommendation": "Commit to one brand hue family or use solid surfaces.",
                })

    return findings


def evaluate_chroma_drift(
    target_path: Path,
    target_l: Optional[float],
    target_c: Optional[float],
    max_delta: float = 0.03,
    tolerance_l: float = 0.12,
) -> Dict[str, Any]:
    """Execute chromatic drift and color space evaluation."""
    bg_lightnesses: List[float] = []
    chromas: List[float] = []
    reflex_violations: List[Dict[str, Any]] = []
    all_findings: List[Dict[str, Any]] = []

    if target_path.is_file():
        # Check if it's a pre-existing JSON record
        try:
            record_data = json.loads(target_path.read_text(encoding="utf-8"))
            if isinstance(record_data, dict) and "actual_mean_lightness" in record_data:
                return validate_chroma_record(record_data)
        except Exception:
            pass
        files_to_scan = [target_path]
    else:
        files_to_scan = []
        for root, dirs, files in os.walk(target_path):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                if Path(f).suffix.lower() in SCAN_EXTENSIONS:
                    files_to_scan.append(Path(root) / f)

    for fpath in files_to_scan:
        all_findings.extend(scan_file_for_chroma(fpath, bg_lightnesses, chromas, reflex_violations))

    mean_l = sum(bg_lightnesses) / len(bg_lightnesses) if bg_lightnesses else 0.5
    mean_c = sum(chromas) / len(chromas) if chromas else 0.0

    l_delta = abs(mean_l - target_l) if target_l is not None else 0.0
    c_delta = abs(mean_c - target_c) if target_c is not None else 0.0

    # 1. Cheerful drift check
    if target_c is not None and c_delta > max_delta:
        all_findings.append({
            "id": "CHROMA-CHEERFUL-DRIFT",
            "file": str(target_path),
            "line": 1,
            "class": "CHEERFUL_DRIFT",
            "severity": "BLOCKING",
            "evidence": f"Actual chroma {mean_c:.4f} exceeds target {target_c:.4f} by delta {c_delta:.4f} > {max_delta}.",
            "recommendation": "Reduce color saturation to honor committed muted/analog palette contract.",
        })

    # 2. Lightness drift check
    if target_l is not None and l_delta > tolerance_l:
        all_findings.append({
            "id": "CHROMA-LIGHTNESS-DRIFT",
            "file": str(target_path),
            "line": 1,
            "class": "LIGHTNESS_DRIFT",
            "severity": "BLOCKING",
            "evidence": f"Actual mean background lightness {mean_l:.4f} drifted from target {target_l:.4f} by delta {l_delta:.4f} > {tolerance_l}.",
            "recommendation": "Re-anchor surface background lightness to committed value in commit sheet.",
        })

    # 3. Unjustified dark mode check (mean L < 0.15 without explicit target_l <= 0.20)
    if mean_l < 0.15 and (target_l is None or target_l > 0.20):
        all_findings.append({
            "id": "CHROMA-DARK-MODE-INERTIA",
            "file": str(target_path),
            "line": 1,
            "class": "UNJUSTIFIED_DARK_MODE_REFLEX",
            "severity": "WARNING",
            "evidence": f"Mean background lightness is near-black (L={mean_l:.3f}) without committed dark theme contract.",
            "recommendation": "Justify dark mode with a concrete physical scene in the commit-sheet.",
        })

    verdict = "PROCEED"
    if any(f["severity"] == "BLOCKING" for f in all_findings):
        verdict = "REJECT"
    elif all_findings:
        verdict = "WARNING"

    result: Dict[str, Any] = {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "actual_mean_lightness": round(mean_l, 4),
        "actual_mean_chroma": round(mean_c, 4),
        "reflex_band_violations": reflex_violations,
        "findings_count": len(all_findings),
        "findings": all_findings,
    }

    if target_l is not None:
        result["target_lightness"] = round(target_l, 4)
        result["lightness_delta"] = round(l_delta, 4)
    if target_c is not None:
        result["target_chroma"] = round(target_c, 4)
        result["chroma_delta"] = round(c_delta, 4)

    return result


def validate_chroma_record(data: Dict[str, Any]) -> Dict[str, Any]:
    """Validate pre-existing chroma record JSON."""
    findings = data.get("findings", [])
    has_blocking = any(f.get("severity") == "BLOCKING" for f in findings)
    data["verdict"] = "REJECT" if has_blocking else ("WARNING" if findings else "PROCEED")
    data["findings_count"] = len(findings)
    return data


def run_selftest() -> None:
    """Validate color conversion math with known references."""
    # Black
    l, c, h = rgb_to_oklch(0, 0, 0)
    assert abs(l - 0.0) < 0.01 and abs(c - 0.0) < 0.01, f"Black failed: {l}, {c}, {h}"
    # White
    l, c, h = rgb_to_oklch(255, 255, 255)
    assert abs(l - 1.0) < 0.01 and abs(c - 0.0) < 0.01, f"White failed: {l}, {c}, {h}"
    # Parsers
    p1 = parse_color_token("#ffffff")
    assert p1 is not None and abs(p1[0] - 1.0) < 0.01
    p2 = parse_color_token("oklch(0.58 0.19 35)")
    assert p2 is not None and abs(p2[0] - 0.58) < 0.01 and abs(p2[1] - 0.19) < 0.01
    print("PASS: Chroma drift guard selftest green.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Chromatic Saturation Drift & OKLCH Category Reflex Guard."
    )
    parser.add_argument("--scan", type=str, default=".", help="Directory or file to scan")
    parser.add_argument("--file", type=str, help="Validate pre-existing chroma drift record JSON")
    parser.add_argument("--color", type=str, help="Single color string to evaluate (hex or oklch)")
    parser.add_argument("--target-l", type=float, help="Target mean background lightness (0.0 to 1.0)")
    parser.add_argument("--target-c", type=float, help="Target mean chroma (e.g. 0.04)")
    parser.add_argument("--max-delta", type=float, default=0.03, help="Max permissible chroma delta")
    parser.add_argument("--tolerance", type=float, default=0.12, help="Max permissible lightness delta")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Fail with code 2 on warnings")
    parser.add_argument("--selftest", action="store_true", help="Run built-in color math tests")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    if args.color:
        lch = parse_color_token(args.color)
        if not lch:
            print(f"Error: Unable to parse color '{args.color}'", file=sys.stderr)
            return 1
        L, C, H = lch
        print(f"Color: {args.color} -> OKLCH(L={L:.4f}, C={C:.4f}, H={H:.1f}°)")
        if is_cream_reflex(lch):
            print("WARNING: Color falls in warm-cream reflex band.")
        return 0

    target_path = Path(args.file if args.file else args.scan).resolve()
    if not target_path.exists():
        print(f"Error: Target path does not exist: {target_path}", file=sys.stderr)
        return 1

    report = evaluate_chroma_drift(
        target_path,
        target_l=args.target_l,
        target_c=args.target_c,
        max_delta=args.max_delta,
        tolerance_l=args.tolerance,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Chroma Drift Guard Verdict: {report['verdict']}")
        print(f"Actual Mean Lightness: {report['actual_mean_lightness']}")
        print(f"Actual Mean Chroma: {report['actual_mean_chroma']}")
        print(f"Total Findings: {report['findings_count']}")
        for f in report["findings"]:
            print(f"  [{f['severity']}] {f['class']}: {f['evidence']}")
            print(f"      Fix: {f['recommendation']}")

    if report["verdict"] == "REJECT" or (args.strict and report["verdict"] == "WARNING"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
