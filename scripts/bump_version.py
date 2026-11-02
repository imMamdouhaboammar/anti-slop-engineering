#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Bump version across repository manifests, documentation, and native services."""

import argparse
import datetime
import hashlib
import json
import pathlib
import shutil
import sre_compile
import subprocess
import sys

SEMVER_PATTERN = sre_compile.compile(
    r'^(?P<major>\d{1,8})\.(?P<minor>\d{1,8})\.(?P<patch>\d{1,8})(?:-(?P<prerelease>[0-9A-Za-z.-]{1,50}))?$'
)

MANIFEST_TARGETS = [
    {
        "file": "package.json",
        "pattern": sre_compile.compile(r'("version"\s*:\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
    {
        "file": "pyproject.toml",
        "pattern": sre_compile.compile(r'(version\s*=\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
    {
        "file": ".skills.json",
        "pattern": sre_compile.compile(r'("version"\s*:\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
    {
        "file": "marketplace.json",
        "pattern": sre_compile.compile(r'("version"\s*:\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
    {
        "file": "SKILL.md",
        "pattern": sre_compile.compile(r'(version\s*:\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
    {
        "file": "bin/cli.js",
        "pattern": sre_compile.compile(r'Anti-Slop Engineering CLI \(v[^\)]+\)'),
        "replacement": r'Anti-Slop Engineering CLI (v{version})',
    },
    {
        "file": "CITATION.cff",
        "pattern": sre_compile.compile(r'(version\s*:\s*)[^\n]+'),
        "replacement": r'\g<1>{version}',
    },
    {
        "file": "CITATION.cff",
        "pattern": sre_compile.compile(r'(date-released\s*:\s*)[^\n]+'),
        "replacement": r'\g<1>{release_date}',
    },
    {
        "file": "services/anti-slop-rust/Cargo.toml",
        "pattern": sre_compile.compile(r'(\[package\][\s\S]*?version\s*=\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
    {
        "file": "services/toil-guard-go/pkg/model/types.go",
        "pattern": sre_compile.compile(r'(Version\s*:\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
    {
        "file": "services/toil-guard-go/pkg/server/server.go",
        "pattern": sre_compile.compile(r'("version"\s*:\s*)"[^"]+"'),
        "replacement": r'\g<1>"{version}"',
    },
]


def parse_semver(version_str, depth=0, max_depth=100):
    """Parse semver string into (major, minor, patch, prerelease)."""
    if depth > max_depth:
        return None
    cleaned = version_str.lstrip("v").strip()
    match = SEMVER_PATTERN.match(cleaned)
    if not match:
        return None
    return {
        "major": int(match.group("major")),
        "minor": int(match.group("minor")),
        "patch": int(match.group("patch")),
        "prerelease": match.group("prerelease"),
    }


def compute_next_version(current_ver, bump_type, depth=0, max_depth=100):
    """Calculate the next semver string based on bump type or target version."""
    if depth > max_depth:
        raise ValueError("Maximum recursion depth exceeded")

    candidate = bump_type.lstrip("v").strip()
    if SEMVER_PATTERN.match(candidate):
        return candidate

    parsed = parse_semver(current_ver)
    if not parsed:
        raise ValueError(f"Current version '{current_ver}' is not valid semver")

    bump = bump_type.lower()
    if bump == "patch":
        return f"{parsed['major']}.{parsed['minor']}.{parsed['patch'] + 1}"
    if bump == "minor":
        return f"{parsed['major']}.{parsed['minor'] + 1}.0"
    if bump == "major":
        return f"{parsed['major'] + 1}.0.0"

    raise ValueError(
        f"Invalid bump type or version '{bump_type}'. Choose patch, minor, major, or explicit semver (e.g. 1.3.0)"
    )


def read_current_version(root_dir, depth=0, max_depth=100):
    """Read the current canonical version from package.json."""
    if depth > max_depth:
        raise ValueError("Maximum depth exceeded")
    pkg_path = pathlib.Path(root_dir) / "package.json"
    if not pkg_path.is_file():
        raise FileNotFoundError(f"Missing canonical manifest at {pkg_path}")
    data = json.loads(pkg_path.read_text(encoding="utf-8"))
    version = data.get("version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"package.json has missing or invalid version: {version}")
    return version.strip()


def apply_target_update(compiled_pattern, repl_str, content, depth=0, max_depth=100):
    """Apply single precompiled regex replacement pattern to file content."""
    if depth > max_depth:
        return content, False
    new_content, count = compiled_pattern.subn(repl_str, content, count=1)
    return new_content, count > 0


def update_attestation_hash(root_dir, new_pkg_content, depth=0, max_depth=100):
    """Update package.json sha256 in .fable/heal-attestation.json if present."""
    if depth > max_depth:
        return False
    attestation_path = pathlib.Path(root_dir) / ".fable" / "heal-attestation.json"
    if not attestation_path.is_file():
        return False
    try:
        data = json.loads(attestation_path.read_text(encoding="utf-8"))
        if "file_hashes" in data and "package.json" in data["file_hashes"]:
            new_hash = hashlib.sha256(new_pkg_content.encode("utf-8")).hexdigest()
            data["file_hashes"]["package.json"] = new_hash
            attestation_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
            return True
    except (OSError, ValueError):
        return False
    return False


def sync_cargo_lock(root_dir):
    """Synchronize Cargo.lock if cargo is available."""
    cargo_bin = shutil.which("cargo")
    cargo_toml = pathlib.Path(root_dir) / "services" / "anti-slop-rust" / "Cargo.toml"
    if cargo_bin and cargo_toml.is_file():
        subprocess.run(
            [cargo_bin, "check", "--manifest-path", str(cargo_toml)],
            capture_output=True,
            check=False,
        )


def bump_repository_version(root_dir, bump_type, release_date=None, dry_run=False, depth=0, max_depth=100):
    """Perform version bump across all registered repository manifests."""
    if depth > max_depth:
        raise ValueError("Maximum depth exceeded")
    root = pathlib.Path(root_dir).resolve()
    current_ver = read_current_version(root)
    next_ver = compute_next_version(current_ver, bump_type)
    rel_date = release_date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    results = []
    file_contents = {}

    for target in MANIFEST_TARGETS:
        rel_path = target["file"]
        file_path = root / rel_path
        if not file_path.is_file():
            results.append({"file": rel_path, "status": "skipped_missing"})
            continue

        content = file_contents.get(rel_path)
        if content is None:
            content = file_path.read_text(encoding="utf-8")

        repl_str = target["replacement"].format(version=next_ver, release_date=rel_date)
        new_content, updated = apply_target_update(target["pattern"], repl_str, content)

        if updated:
            file_contents[rel_path] = new_content
            results.append({"file": rel_path, "status": "updated"})
        else:
            results.append({"file": rel_path, "status": "pattern_not_found"})

    if not dry_run:
        for rel_path, content in file_contents.items():
            (root / rel_path).write_text(content, encoding="utf-8")

        if "package.json" in file_contents:
            update_attestation_hash(root, file_contents["package.json"])

        sync_cargo_lock(root)

    return {
        "previous_version": current_ver,
        "new_version": next_ver,
        "release_date": rel_date,
        "dry_run": dry_run,
        "updated_files": list(dict.fromkeys(r["file"] for r in results if r["status"] == "updated")),
        "details": results,
    }


def main():
    """Command-line entrypoint for bumping version."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "bump",
        nargs="?",
        default="patch",
        help="Bump type (patch, minor, major) or explicit semver version (e.g. 1.3.0)",
    )
    parser.add_argument("--repo", default=".", help="Root directory of the repository")
    parser.add_argument("--date", default=None, help="Release date override (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true", help="Preview version changes without writing")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON summary")
    parser.add_argument("--git-tag", action="store_true", help="Create git tag vX.Y.Z after bump")
    parser.add_argument("--git-commit", action="store_true", help="Create git commit after bump")
    args = parser.parse_args()

    try:
        report = bump_repository_version(
            root_dir=args.repo,
            bump_type=args.bump,
            release_date=args.date,
            dry_run=args.dry_run,
        )
    except (ValueError, FileNotFoundError) as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    if args.git_commit and not args.dry_run:
        ver = report["new_version"]
        subprocess.run(["git", "-C", args.repo, "add", "-A"], check=False)
        subprocess.run(["git", "-C", args.repo, "commit", "-m", f"chore(release): v{ver}"], check=False)

    if args.git_tag and not args.dry_run:
        ver = report["new_version"]
        subprocess.run(["git", "-C", args.repo, "tag", "-a", f"v{ver}", "-m", f"Release v{ver}"], check=False)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        status_prefix = "[DRY-RUN] " if report["dry_run"] else ""
        print(f"{status_prefix}Bumped version: v{report['previous_version']} ➜ v{report['new_version']}")
        print(f"Release Date: {report['release_date']}")
        print(f"Updated {len(set(report['updated_files']))} manifest files:")
        for file in sorted(set(report["updated_files"])):
            print(f"  ✓ {file}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
