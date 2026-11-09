#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Stage, validate, and build deterministic release archive for OpenAI/Codex plugins."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SURFACE = [
    Path(".codex-plugin"),
    Path("assets"),
    Path("skills"),
    Path("README.md"),
    Path("LICENSE"),
    Path("PRIVACY.md"),
    Path("TERMS.md"),
    Path("SUPPORT.md"),
    Path("SECURITY.md"),
]


def stage_plugin(destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    for rel in SURFACE:
        source = ROOT / rel
        target = destination / rel
        if source.is_dir():
            shutil.copytree(
                source,
                target,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", ".DS_Store"),
            )
        elif source.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
        else:
            raise FileNotFoundError(f"missing release surface member: {rel}")
    return destination


def _safe_extract(archive: Path, destination: Path) -> None:
    with zipfile.ZipFile(archive) as zf:
        for member in zf.infolist():
            target_path = (destination / member.filename).resolve()
            if not target_path.is_relative_to(destination.resolve()):
                raise RuntimeError(f"Zip slip detected: {member.filename}")
            zf.extract(member, destination)


def build(out_dir: Path) -> dict:
    manifest_file = ROOT / ".codex-plugin/plugin.json"
    if not manifest_file.exists():
        raise FileNotFoundError(f"missing manifest: {manifest_file}")
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    name = manifest["name"]
    version = manifest["version"]
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / f"{name}-{version}.zip"

    packager = ROOT / "scripts/package_plugin.py"

    with tempfile.TemporaryDirectory(prefix="plugin-release-") as temp:
        stage = stage_plugin(Path(temp) / "plugin")
        proc = subprocess.run(
            [sys.executable, str(packager), str(stage), str(archive), "--json"],
            text=True,
            capture_output=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout)
        package_report = json.loads(proc.stdout)

        extract = Path(temp) / "extract"
        _safe_extract(archive, extract)

    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    if digest != package_report["sha256"]:
        raise RuntimeError("packager SHA256 does not match final archive digest")

    sums = out_dir / "SHA256SUMS"
    sums.write_text(f"{digest}  {archive.name}\n", encoding="utf-8")

    return {
        "ok": True,
        "name": name,
        "version": version,
        "archive": str(archive),
        "sha256": digest,
        "checksums": str(sums),
        "bytes": archive.stat().st_size,
        "entries": package_report["entries"],
        "skills": package_report["skills"],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="dist")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        report = build(Path(args.out_dir).expanduser().resolve())
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2, sort_keys=True))
        else:
            print(f"build_plugin_release: FAIL: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(
            f"build_plugin_release: PASS {report['name']} {report['version']} "
            f"skills={report['skills']} sha256={report['sha256']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
