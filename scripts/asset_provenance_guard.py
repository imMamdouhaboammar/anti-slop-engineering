#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Asset Sourcing & License Provenance Ledger Guard.

Enforces cryptographic SHA-256 asset integrity, explicit open-source license
provenance (CC0, MIT, SIL OFL, Apache 2.0), and prevents unverified external
CDN hotlinks or copyright-unverified media in shipping builds.

Usage:
    python3 scripts/asset_provenance_guard.py --scan assets/
    python3 scripts/asset_provenance_guard.py --ledger .anti-slop/asset-ledger.jsonl
    python3 scripts/asset_provenance_guard.py --record-missing --scan public/
    python3 scripts/asset_provenance_guard.py --selftest
"""

import argparse
import datetime
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

APPROVED_LICENSES = {
    "cc0",
    "cc0-1.0",
    "mit",
    "ofl-1.1",
    "sil ofl",
    "apache-2.0",
    "bsd-2-clause",
    "bsd-3-clause",
    "public domain",
    "proprietary-licensed",
    "hand-authored",
}

ASSET_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".webp", ".avif", ".svg", ".gif",
    ".gltf", ".glb", ".hdr", ".exr",
    ".mp3", ".wav", ".ogg", ".aac",
    ".mp4", ".webm",
    ".woff", ".woff2", ".ttf", ".otf",
}

SKIP_DIRS = {"node_modules", "dist", "build", ".git", ".next", "out"}


def calculate_sha256(file_path: Path) -> str:
    """Compute hex SHA-256 digest of file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def load_asset_ledger(ledger_path: Path) -> Dict[str, Dict[str, Any]]:
    """Load ledger entries mapped by relative asset path."""
    ledger: Dict[str, Dict[str, Any]] = {}
    if not ledger_path.exists():
        return ledger

    try:
        content = ledger_path.read_text(encoding="utf-8")
        if ledger_path.suffix.lower() == ".json":
            raw = json.loads(content)
            if isinstance(raw, list):
                for item in raw:
                    p = item.get("path")
                    if p: ledger[p] = item
            elif isinstance(raw, dict):
                assets = raw.get("assets", {})
                if isinstance(assets, dict):
                    ledger = assets
                elif isinstance(assets, list):
                    for item in assets:
                        p = item.get("path")
                        if p: ledger[p] = item
        else:
            # JSON Lines format (.jsonl)
            for line in content.splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                item = json.loads(line)
                p = item.get("path")
                if p: ledger[p] = item
    except Exception:
        pass
    return ledger


def save_asset_ledger(ledger_path: Path, ledger: Dict[str, Dict[str, Any]]) -> None:
    """Persist ledger to disk in JSONL format."""
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "w", encoding="utf-8") as f:
        for item in sorted(ledger.values(), key=lambda x: x.get("path", "")):
            f.write(json.dumps(item) + "\n")


def scan_source_for_unverified_hotlinks(
    root_path: Path,
) -> List[Dict[str, Any]]:
    """Scan source code for unverified external CDN hotlinks."""
    findings: List[Dict[str, Any]] = []
    source_exts = {".html", ".jsx", ".tsx", ".vue", ".svelte", ".css", ".js", ".ts"}

    # Banned third-party hotlink domains that risk broken builds or copyright leaks
    hotlink_pattern = re.compile(
        r"""(?:src|href|url)\s*[:=(]\s*['"](https?://(?:images\.unsplash\.com|cdn\.jsdelivr\.net|unpkg\.com|cdnjs\.cloudflare\.com|i\.pinimg\.com)[^'"]+)['"]""",
        re.I,
    )

    for root, dirs, files in os.walk(root_path):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for f in files:
            p = Path(root) / f
            if p.suffix.lower() in source_exts:
                try:
                    text = p.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                for idx, line in enumerate(text.splitlines(), 1):
                    m = hotlink_pattern.search(line)
                    if m:
                        url = m.group(1)
                        findings.append({
                            "id": f"ASSET-HOTLINK-{idx}",
                            "file": str(p),
                            "line": idx,
                            "class": "UNVERIFIED_CDN_HOTLINK",
                            "severity": "WARNING",
                            "evidence": f"Found external unversioned CDN hotlink: {url[:80]}",
                            "recommendation": "Download asset locally, record provenance in asset ledger, and bundle with build.",
                        })
    return findings


def evaluate_asset_provenance(
    scan_dir: Path,
    ledger_file: Path,
    record_missing: bool = False,
) -> Dict[str, Any]:
    """Execute complete asset provenance and license ledger audit."""
    findings: List[Dict[str, Any]] = []
    ledger = load_asset_ledger(ledger_file)
    discovered_assets: List[Path] = []

    if scan_dir.is_file():
        # Could be pre-existing JSON record
        try:
            record_data = json.loads(scan_dir.read_text(encoding="utf-8"))
            if isinstance(record_data, dict) and "verified_clean_assets_count" in record_data:
                findings = record_data.get("findings", [])
                has_blocking = any(f.get("severity") == "BLOCKING" for f in findings)
                record_data["verdict"] = "REJECT" if has_blocking else ("WARNING" if findings else "PROCEED")
                record_data["findings_count"] = len(findings)
                return record_data
        except Exception:
            pass
        if scan_dir.suffix.lower() in ASSET_EXTENSIONS:
            discovered_assets = [scan_dir]
    else:
        for root, dirs, files in os.walk(scan_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for f in files:
                ext = Path(f).suffix.lower()
                if ext in ASSET_EXTENSIONS:
                    discovered_assets.append(Path(root) / f)

    scanned_count = len(discovered_assets)
    verified_clean_count = 0
    unverified_count = 0

    base_dir = scan_dir.parent if scan_dir.is_file() else scan_dir

    for asset_path in discovered_assets:
        try:
            rel_path = str(asset_path.relative_to(base_dir))
        except ValueError:
            rel_path = asset_path.name

        sha = calculate_sha256(asset_path)
        ledger_entry = ledger.get(rel_path) or ledger.get(asset_path.name)

        if not ledger_entry:
            unverified_count += 1
            if record_missing:
                # Auto-record as hand-authored template
                ledger[rel_path] = {
                    "path": rel_path,
                    "sha256": sha,
                    "source_url": "local://authored",
                    "license": "Hand-Authored",
                    "attribution": "Repository Author",
                    "added_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                }
                verified_clean_count += 1
            else:
                findings.append({
                    "id": f"ASSET-UNRECORDED-{len(findings) + 1}",
                    "file": str(asset_path),
                    "line": 1,
                    "class": "MISSING_PROVENANCE_RECORD",
                    "severity": "BLOCKING",
                    "evidence": f"Asset '{rel_path}' has no entry in provenance ledger ({ledger_file}).",
                    "recommendation": f"Add provenance entry to {ledger_file} with SHA-256 {sha[:16]} and approved license.",
                })
        else:
            # 1. SHA-256 match
            expected_sha = ledger_entry.get("sha256", "")
            if expected_sha and expected_sha != sha:
                unverified_count += 1
                findings.append({
                    "id": f"ASSET-HASH-MISMATCH-{len(findings) + 1}",
                    "file": str(asset_path),
                    "line": 1,
                    "class": "HASH_MISMATCH",
                    "severity": "BLOCKING",
                    "evidence": f"Asset '{rel_path}' SHA-256 {sha[:16]} does not match ledger hash {expected_sha[:16]}.",
                    "recommendation": "Verify asset integrity and update ledger hash if asset modification was intentional.",
                })
                continue

            # 2. Approved license check
            lic = str(ledger_entry.get("license", "")).lower().strip()
            if lic not in APPROVED_LICENSES:
                unverified_count += 1
                findings.append({
                    "id": f"ASSET-BAD-LICENSE-{len(findings) + 1}",
                    "file": str(asset_path),
                    "line": 1,
                    "class": "UNAPPROVED_LICENSE",
                    "severity": "BLOCKING",
                    "evidence": f"Asset '{rel_path}' has unapproved license '{lic}'.",
                    "recommendation": f"Replace asset with permissible license: {', '.join(sorted(list(APPROVED_LICENSES)))}",
                })
                continue

            verified_clean_count += 1

    if record_missing and unverified_count > 0:
        save_asset_ledger(ledger_file, ledger)

    # Check for hotlinks in repository source
    hotlink_findings = scan_source_for_unverified_hotlinks(scan_dir if scan_dir.is_dir() else scan_dir.parent)
    findings.extend(hotlink_findings)

    verdict = "PROCEED"
    if any(f["severity"] == "BLOCKING" for f in findings):
        verdict = "REJECT"
    elif findings:
        verdict = "WARNING"

    return {
        "schema_version": "1.0.0",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "ledger_file": str(ledger_file),
        "scanned_assets_count": scanned_count,
        "verified_clean_assets_count": verified_clean_count,
        "unverified_assets_count": unverified_count,
        "findings_count": len(findings),
        "findings": findings,
    }


def run_selftest() -> None:
    """Validate asset provenance assertions."""
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        tmp_dir = Path(td)
        tmp_ledger = tmp_dir / "test_asset_ledger.jsonl"
        tmp_asset = tmp_dir / "test_asset.png"
        tmp_asset.write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01")
        sha = calculate_sha256(tmp_asset)

        tmp_ledger.write_text(json.dumps({
            "path": "test_asset.png",
            "sha256": sha,
            "source_url": "https://polyhaven.com/a/test",
            "license": "CC0",
            "attribution": "Poly Haven"
        }) + "\n", encoding="utf-8")

        report = evaluate_asset_provenance(tmp_asset, tmp_ledger)
        assert report["verdict"] == "PROCEED", f"Expected PROCEED, got: {report}"
        assert report["verified_clean_assets_count"] == 1
        print("PASS: Asset provenance guard selftest green.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Asset Sourcing & License Provenance Ledger Guard."
    )
    parser.add_argument("--scan", type=str, default="assets", help="Asset directory or file to scan")
    parser.add_argument("--ledger", type=str, default=".anti-slop/asset-ledger.jsonl", help="Path to asset ledger")
    parser.add_argument("--record-missing", action="store_true", help="Auto-record unlisted assets as Hand-Authored")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--strict", action="store_true", help="Fail with code 2 on warnings")
    parser.add_argument("--selftest", action="store_true", help="Run built-in tests")
    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    scan_path = Path(args.scan).resolve()
    ledger_path = Path(args.ledger).resolve()

    if not scan_path.exists():
        print(f"Error: Scan path does not exist: {scan_path}", file=sys.stderr)
        return 1

    report = evaluate_asset_provenance(scan_path, ledger_path, record_missing=args.record_missing)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Asset Provenance Guard Verdict: {report['verdict']}")
        print(f"Scanned Assets: {report['scanned_assets_count']}")
        print(f"Verified Clean: {report['verified_clean_assets_count']}")
        print(f"Unverified / Discrepant: {report['unverified_assets_count']}")
        print(f"Total Findings: {report['findings_count']}")
        for f in report["findings"][:10]:
            print(f"  [{f['severity']}] {f['class']}: {f['evidence']}")
            print(f"      Fix: {f['recommendation']}")

    if report["verdict"] == "REJECT" or (args.strict and report["verdict"] == "WARNING"):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
