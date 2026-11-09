#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Deterministic packager and validator for OpenAI/Codex plugin submission archives."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

FIXED_TIME = (1980, 1, 1, 0, 0, 0)
MAX_ARCHIVE = 100 * 1024 * 1024
CATEGORIES = {
    "Productivity", "Creativity", "Developer Tools", "Business & Operations",
    "Data & Analytics", "Communication", "Education & Research", "Security",
    "Finance", "Healthcare", "Travel", "Entertainment", "Other",
}
REQUIRED_ROOT_DOCS = [
    "README.md", "LICENSE", "PRIVACY.md", "TERMS.md", "SUPPORT.md", "SECURITY.md"
]


def _validate_image_asset(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"image asset missing: {path}")
    if path.suffix.lower() == ".svg":
        tree = ET.parse(path)
        root = tree.getroot()
        tag = root.tag.split("}")[-1].lower()
        if tag != "svg":
            raise ValueError(f"root element must be <svg>: {path}")
        vb = root.attrib.get("viewBox") or root.attrib.get("viewbox")
        if not vb:
            raise ValueError(f"SVG must declare viewBox: {path}")
        parts = [float(p) for p in vb.replace(",", " ").split() if p]
        if len(parts) != 4 or parts[2] != parts[3] or parts[2] < 48:
            raise ValueError(f"SVG must be square and >=48x48: {path}")
    else:
        raise ValueError(f"unsupported asset format: {path}")


def validate_plugin(root_dir: Path) -> dict:
    root = root_dir.expanduser().resolve()
    manifest_path = root / ".codex-plugin" / "plugin.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing manifest: {manifest_path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    name = manifest.get("name")
    version = manifest.get("version")
    if not name or not isinstance(name, str):
        raise ValueError("manifest name is required")
    if not version or not isinstance(version, str):
        raise ValueError("manifest version is required")

    interface = manifest.get("interface", {})
    if not isinstance(interface, dict):
        raise ValueError("manifest interface must be an object")

    for field, limit in [("displayName", 30), ("shortDescription", 30), ("longDescription", 4000), ("developerName", 80)]:
        val = interface.get(field)
        if not val or not isinstance(val, str) or len(val) > limit:
            raise ValueError(f"interface.{field} required and must be <={limit} chars")

    cat = interface.get("category")
    if cat not in CATEGORIES:
        raise ValueError(f"invalid interface.category: {cat}")

    for img_field in ["composerIcon", "logo"]:
        rel = interface.get(img_field)
        if not rel or not isinstance(rel, str):
            raise ValueError(f"interface.{img_field} is required")
        img_path = root / rel.lstrip("./")
        _validate_image_asset(img_path)

    skills_dir = root / "skills"
    if not skills_dir.is_dir():
        raise ValueError("manifest skills directory missing: ./skills/")

    discovered_skills = []
    for item in sorted(skills_dir.iterdir()):
        if not item.is_dir() or item.name.startswith("."):
            continue
        skill_file = item / "SKILL.md"
        if not skill_file.is_file():
            raise ValueError(f"skill missing SKILL.md: {item.name}")
        content = skill_file.read_text(encoding="utf-8")
        if not content.startswith("---\n"):
            raise ValueError(f"SKILL.md missing YAML frontmatter: {item.name}")
        end_fm = content.find("\n---", 4)
        if end_fm == -1:
            raise ValueError(f"SKILL.md unclosed YAML frontmatter: {item.name}")
        body = content[end_fm + 4:].strip()
        if not body:
            raise ValueError(f"SKILL.md empty body: {item.name}")
        discovered_skills.append(item.name)

    for doc_name in REQUIRED_ROOT_DOCS:
        doc_path = root / doc_name
        if not doc_path.is_file():
            raise ValueError(f"missing required root document: {doc_name}")
        text = doc_path.read_text(encoding="utf-8", errors="ignore")
        if "/Users/" in text or "/home/" in text:
            raise ValueError(f"forbidden absolute path found in {doc_name}")

    return {
        "ok": True,
        "name": name,
        "version": version,
        "skills": discovered_skills,
        "interface": interface.get("displayName"),
    }


def _collect_files(root: Path) -> tuple[list[str], list[str]]:
    files: list[str] = []
    directories: set[str] = set()
    for current, dirs, names in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for d in sorted(dirs):
            if d.startswith(".") and d != ".codex-plugin":
                continue
            dir_rel = (current_path / d).relative_to(root).as_posix() + "/"
            directories.add(dir_rel)
        for f in sorted(names):
            if f in {".DS_Store", "Thumbs.db"} or f.endswith((".pyc", ".pyo")):
                continue
            file_rel = (current_path / f).relative_to(root).as_posix()
            files.append(file_rel)
            parts = file_rel.split("/")[:-1]
            for i in range(1, len(parts) + 1):
                directories.add("/".join(parts[:i]) + "/")
    return sorted(directories), sorted(files)


def build_archive(plugin_root: str, output_path: str) -> dict:
    root = Path(plugin_root).expanduser().resolve()
    output = Path(output_path).expanduser().resolve()
    if output == root or root in output.parents:
        raise ValueError("output ZIP must live outside the plugin root")

    report = validate_plugin(root)
    directories, files = _collect_files(root)

    output.parent.mkdir(parents=True, exist_ok=True)
    temp_zip = output.with_name(output.name + ".tmp")
    try:
        with zipfile.ZipFile(temp_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for d in directories:
                info = zipfile.ZipInfo(d, FIXED_TIME)
                info.create_system = 3
                info.external_attr = (stat.S_IFDIR | 0o755) << 16
                archive.writestr(info, b"")
            for f in files:
                f_path = root.joinpath(*f.split("/"))
                info = zipfile.ZipInfo(f, FIXED_TIME)
                info.create_system = 3
                info.compress_type = zipfile.ZIP_DEFLATED
                mode = 0o755 if (f_path.stat().st_mode & stat.S_IXUSR) else 0o644
                info.external_attr = (stat.S_IFREG | mode) << 16
                archive.writestr(info, f_path.read_bytes(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

        if temp_zip.stat().st_size > MAX_ARCHIVE:
            raise ValueError(f"archive exceeds 100MB limit: {temp_zip.stat().st_size}")
        temp_zip.replace(output)
    finally:
        if temp_zip.exists():
            temp_zip.unlink()

    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return {
        "ok": True,
        "name": report["name"],
        "version": report["version"],
        "skills": len(report["skills"]),
        "entries": len(directories) + len(files),
        "bytes": output.stat().st_size,
        "outputPath": str(output),
        "sha256": digest,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plugin_root")
    parser.add_argument("output_zip")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        res = build_archive(args.plugin_root, args.output_zip)
    except Exception as exc:
        if args.json:
            print(json.dumps({"ok": False, "errors": [str(exc)]}, indent=2))
        else:
            print(f"package_plugin: FAIL: {exc}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(res, indent=2))
    else:
        print(f"package_plugin: PASS {res['name']} {res['version']} sha256={res['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
