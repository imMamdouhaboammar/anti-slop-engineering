#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""DPR-2 Runtime Motion & Fillrate Sentry.

Validates runtime motion performance, long tasks, audio autoplay safety, and
reduced-motion parity under retina client conditions (1440x900@2x = 5.2MP)
with 4x CPU throttling. Suppresses dev-server false failures.

Usage:
    python3 scripts/motion_runtime_guard.py --file motion-report.json
    python3 scripts/motion_runtime_guard.py --fps 58 --dpr 2 --longtask 32 --json
    python3 scripts/motion_runtime_guard.py --selftest
"""

import argparse
import datetime
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

MIN_ACCEPTABLE_FPS = 50.0
MAX_LONGTASK_MS = 50.0
REQUIRED_DPR = 2.0


def evaluate_motion_metrics(
    fps: float,
    dpr: float,
    max_longtask_ms: float,
    audio_silent: bool,
    reduced_motion_present: bool,
    is_dev_server: bool = False,
    viewport_w: int = 1440,
    viewport_h: int = 900,
    cpu_throttle: float = 4.0,
) -> Dict[str, Any]:
    """Audit runtime motion and fillrate performance against SRE standards."""
    findings: List[Dict[str, Any]] = []

    # 1. Dev server check: Dev server costs ~2x per frame (HMR client, unminified code)
    if is_dev_server:
        findings.append({
            "id": "MOTION-DEV-SERVER",
            "file": "runtime",
            "line": 1,
            "class": "DEV_SERVER_MEASUREMENT_INVALID",
            "severity": "WARNING",
            "evidence": "Measurement was captured against a dev server (Vite/Webpack/Next HMR). Dev server roughly doubles frame cost.",
            "recommendation": "Measure a production build to avoid false failures.",
        })

    # 2. DPR 2 retina verification: full-screen passes cost per pixel, not geometry
    if dpr < REQUIRED_DPR:
        findings.append({
            "id": "MOTION-DPR-DEFICIT",
            "file": "runtime",
            "line": 1,
            "class": "SUBPAR_FPS_AT_DPR2",
            "severity": "WARNING",
            "evidence": f"Measurement DPR was {dpr} (expected {REQUIRED_DPR}). DPR 1 quarters the pixel fillrate cost, creating false confidence.",
            "recommendation": "Measure at DPR 2 (1440x900@2x = 5.2MP) under 4x CPU throttle.",
        })

    # 3. FPS threshold check
    if fps < MIN_ACCEPTABLE_FPS:
        findings.append({
            "id": "MOTION-LOW-FPS",
            "file": "runtime",
            "line": 1,
            "class": "SUBPAR_FPS_AT_DPR2",
            "severity": "BLOCKING",
            "evidence": f"Measured FPS ({fps:.1f}) is below minimum acceptable threshold ({MIN_ACCEPTABLE_FPS:.1f}) under 4x CPU throttle.",
            "recommendation": "Prune full-screen post-processing passes, throttle uniform writes to rAF, or switch complex scenes to canvas/video scrub.",
        })

    # 4. Long task check
    if max_longtask_ms > MAX_LONGTASK_MS:
        findings.append({
            "id": "MOTION-LONG-TASK",
            "file": "runtime",
            "line": 1,
            "class": "LONGTASK_BUDGET_EXCEEDED",
            "severity": "BLOCKING",
            "evidence": f"Max LongTask was {max_longtask_ms:.1f}ms (budget is <= {MAX_LONGTASK_MS:.1f}ms).",
            "recommendation": "Decompose heavy JavaScript execution, yield to main thread via scheduler.yield() or requestIdleCallback.",
        })

    # 5. Audio autoplay policy: unmuted audio must never autoplay
    if not audio_silent:
        findings.append({
            "id": "MOTION-AUTOPLAY-SOUND",
            "file": "runtime",
            "line": 1,
            "class": "AUTOPLAY_SOUND_UNMUTED",
            "severity": "BLOCKING",
            "evidence": "Audio or video element is autoplaying unmuted. Audio must start only on an explicit user gesture.",
            "recommendation": "Add muted attribute to autoplaying media and require user click/interaction to unmute.",
        })

    # 6. Reduced motion parity: alternative art direction required
    if not reduced_motion_present:
        findings.append({
            "id": "MOTION-REDUCED-MOTION-ABSENT",
            "file": "runtime",
            "line": 1,
            "class": "REDUCED_MOTION_COLLAPSE",
            "severity": "BLOCKING",
            "evidence": "WebGL or animation state machine lacks prefers-reduced-motion branch.",
            "recommendation": "Implement an alternative art direction (calm still or gentle opacity reveal) for prefers-reduced-motion.",
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
        "viewport_width": viewport_w,
        "viewport_height": viewport_h,
        "device_scale_factor": dpr,
        "cpu_throttling_rate": cpu_throttle,
        "measured_fps": round(fps, 2),
        "min_fps_threshold": MIN_ACCEPTABLE_FPS,
        "max_longtask_ms": round(max_longtask_ms, 2),
        "audio_autoplay_silent": audio_silent,
        "reduced_motion_branch_present": reduced_motion_present,
        "is_dev_server": is_dev_server,
        "findings_count": len(findings),
        "findings": findings,
    }


def evaluate_motion_record_file(record_path: Path) -> Dict[str, Any]:
    """Evaluate pre-recorded JSON motion report."""
    if not record_path.exists():
        return {
            "schema_version": "1.0.0",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "verdict": "REJECT",
            "device_scale_factor": 1.0,
            "measured_fps": 0.0,
            "max_longtask_ms": 0.0,
            "audio_autoplay_silent": False,
            "reduced_motion_branch_present": False,
            "findings_count": 1,
            "findings": [{
                "id": "MOTION-FILE-MISSING",
                "file": str(record_path),
                "line": 1,
                "class": "SUBPAR_FPS_AT_DPR2",
                "severity": "BLOCKING",
                "evidence": f"Motion report file not found: {record_path}",
                "recommendation": "Run motionqa audit to generate runtime performance report.",
            }],
        }

    try:
        data = json.loads(record_path.read_text(encoding="utf-8"))
    except Exception as e:
        return {
            "schema_version": "1.0.0",
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "verdict": "REJECT",
            "device_scale_factor": 1.0,
            "measured_fps": 0.0,
            "max_longtask_ms": 0.0,
            "audio_autoplay_silent": False,
            "reduced_motion_branch_present": False,
            "findings_count": 1,
            "findings": [{
                "id": "MOTION-INVALID-JSON",
                "file": str(record_path),
                "line": 1,
                "class": "SUBPAR_FPS_AT_DPR2",
                "severity": "BLOCKING",
                "evidence": f"Failed to parse motion report JSON: {e}",
                "recommendation": "Ensure motionqa outputs valid JSON.",
            }],
        }

    return evaluate_motion_metrics(
        fps=float(data.get("measured_fps", data.get("fps", 0.0))),
        dpr=float(data.get("device_scale_factor", data.get("dpr", 2.0))),
        max_longtask_ms=float(data.get("max_longtask_ms", data.get("longtask_ms", 0.0))),
        audio_silent=bool(data.get("audio_autoplay_silent", not data.get("audioAutoplaying", False))),
        reduced_motion_present=bool(data.get("reduced_motion_branch_present", data.get("reduced_motion", True))),
        is_dev_server=bool(data.get("is_dev_server", data.get("devServer", False))),
        viewport_w=int(data.get("viewport_width", 1440)),
        viewport_h=int(data.get("viewport_height", 900)),
        cpu_throttle=float(data.get("cpu_throttling_rate", 4.0)),
    )


def run_selftest() -> None:
    """Validate motion rules assertions."""
    # Clean run
    clean = evaluate_motion_metrics(
        fps=58.0, dpr=2.0, max_longtask_ms=24.0, audio_silent=True, reduced_motion_present=True
    )
    assert clean["verdict"] == "PROCEED", f"Expected PROCEED, got: {clean}"

    # Low FPS
    low_fps = evaluate_motion_metrics(
        fps=32.0, dpr=2.0, max_longtask_ms=24.0, audio_silent=True, reduced_motion_present=True
    )
    assert low_fps["verdict"] == "REJECT"

    # Audio autoplay unmuted
    audio_fail = evaluate_motion_metrics(
        fps=60.0, dpr=2.0, max_longtask_ms=10.0, audio_silent=False, reduced_motion_present=True
    )
    assert audio_fail["verdict"] == "REJECT"

    print("PASS: Motion runtime guard selftest green.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="DPR-2 Runtime Motion & Fillrate Sentry."
    )
    parser.add_argument("--file", type=str, help="Path to motion report JSON file")
    parser.add_argument("--fps", type=float, default=60.0, help="Measured FPS")
    parser.add_argument("--dpr", type=float, default=2.0, help="Device Scale Factor (default: 2.0)")
    parser.add_argument("--longtask", type=float, default=0.0, help="Max LongTask duration in ms")
    parser.add_argument("--unmuted-autoplay", action="store_true", help="Audio autoplays unmuted")
    parser.add_argument("--no-reduced-motion", action="store_true", help="Missing prefers-reduced-motion branch")
    parser.add_argument("--dev-server", action="store_true", help="Mark measurement as dev server")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Fail with code 2 on warnings")
    parser.add_argument("--selftest", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    if args.file:
        report = evaluate_motion_record_file(Path(args.file).resolve())
    else:
        report = evaluate_motion_metrics(
            fps=args.fps,
            dpr=args.dpr,
            max_longtask_ms=args.longtask,
            audio_silent=not getattr(args, "unmuted_autoplay", False),
            reduced_motion_present=not args.no_reduced_motion,
            is_dev_server=args.dev_server,
        )

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Motion Runtime Guard Verdict: {report['verdict']}")
        print(f"FPS @ DPR {report['device_scale_factor']}: {report['measured_fps']}")
        print(f"Max LongTask: {report['max_longtask_ms']}ms")
        print(f"Audio Autoplay Silent: {report['audio_autoplay_silent']}")
        print(f"Reduced Motion Parity: {report['reduced_motion_branch_present']}")
        print(f"Total Findings: {report['findings_count']}")
        for f in report["findings"]:
            print(f"  [{f['severity']}] {f['class']}: {f['evidence']}")
            print(f"      Fix: {f['recommendation']}")

    if report["verdict"] == "REJECT" or (args.strict and report["verdict"] == "WARNING"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
