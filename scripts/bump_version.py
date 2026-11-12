#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Bump version across repository manifests, documentation, and native services."""

import argparse
import datetime
import hashlib
import json
import pathlib
import shlex
import shutil
import sre_compile
import subprocess
import sys

ATTESTATION_REL_PATH = ".fable/heal-attestation.json"
CARGO_LOCK_REL_PATH = "services/anti-slop-rust/Cargo.lock"


class GitCommandError(RuntimeError):
    """Raised when a Git command fails or release preconditions are violated."""


def format_git_error(command, returncode, stdout="", stderr=""):
    """Format an actionable Git failure message with the exact command."""
    detail = stderr.strip() or stdout.strip() or f"exit code {returncode}"
    return f"Git command failed (exit {returncode}): {shlex.join(list(command))}\n{detail}"

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
    {
        "file": "scripts/diff_guard.py",
        "pattern": sre_compile.compile(r"(__version__\s*=\s*)'[^']+'"),
        "replacement": r"\g<1>'{version}'",
    },
    {
        "file": "scripts/sre_guard.py",
        "pattern": sre_compile.compile(r"(__version__\s*=\s*)'[^']+'"),
        "replacement": r"\g<1>'{version}'",
    },
    {
        "file": ".codex-plugin/plugin.json",
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
    attestation_path = pathlib.Path(root_dir) / ATTESTATION_REL_PATH
    if not attestation_path.is_file():
        return False
    try:
        data = json.loads(attestation_path.read_text(encoding="utf-8"))
        file_hashes = data.get("file_hashes")
        if not isinstance(file_hashes, dict) or "package.json" not in file_hashes:
            return False
        new_hash = hashlib.sha256(new_pkg_content.encode("utf-8")).hexdigest()
        if file_hashes["package.json"] == new_hash:
            return False
        file_hashes["package.json"] = new_hash
        attestation_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        return True
    except (OSError, ValueError) as err:
        print(f"Warning: failed to update {ATTESTATION_REL_PATH}: {err}", file=sys.stderr)
        return False


def sync_cargo_lock(root_dir):
    """Synchronize Cargo.lock if cargo is available and return True when Cargo.lock changed."""
    cargo_bin = shutil.which("cargo")
    cargo_toml = pathlib.Path(root_dir) / "services" / "anti-slop-rust" / "Cargo.toml"
    cargo_lock = pathlib.Path(root_dir) / CARGO_LOCK_REL_PATH
    if not cargo_bin or not cargo_toml.is_file():
        return False
    before_bytes = cargo_lock.read_bytes() if cargo_lock.is_file() else None
    subprocess.run(
        [cargo_bin, "check", "--manifest-path", str(cargo_toml)],
        capture_output=True,
        check=False,
    )
    after_bytes = cargo_lock.read_bytes() if cargo_lock.is_file() else None
    return after_bytes is not None and after_bytes != before_bytes


def bump_repository_version(root_dir, bump_type, release_date=None, dry_run=False, depth=0, max_depth=100):
    """Perform version bump across all registered repository manifests."""
    if depth > max_depth:
        raise ValueError("Maximum depth exceeded")
    root = pathlib.Path(root_dir).resolve()
    current_ver = read_current_version(root)
    next_ver = compute_next_version(current_ver, bump_type)
    rel_date = release_date or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d")

    results = []
    original_contents = {}
    file_contents = {}

    for target in MANIFEST_TARGETS:
        rel_path = target["file"]
        file_path = root / rel_path
        if not file_path.is_file():
            results.append({"file": rel_path, "status": "skipped_missing"})
            continue

        if rel_path not in original_contents:
            original_contents[rel_path] = file_path.read_text(encoding="utf-8")
        content = file_contents.get(rel_path, original_contents[rel_path])

        repl_str = target["replacement"].format(version=next_ver, release_date=rel_date)
        new_content, updated = apply_target_update(target["pattern"], repl_str, content)

        if updated:
            file_contents[rel_path] = new_content
            results.append({"file": rel_path, "status": "updated"})
        else:
            results.append({"file": rel_path, "status": "pattern_not_found"})

    modified_files = []
    if not dry_run:
        for rel_path, content in file_contents.items():
            if content != original_contents[rel_path]:
                (root / rel_path).write_text(content, encoding="utf-8")
                modified_files.append(rel_path)

        if "package.json" in file_contents and update_attestation_hash(root, file_contents["package.json"]):
            modified_files.append(ATTESTATION_REL_PATH)

        if sync_cargo_lock(root):
            modified_files.append(CARGO_LOCK_REL_PATH)

    return {
        "previous_version": current_ver,
        "new_version": next_ver,
        "release_date": rel_date,
        "dry_run": dry_run,
        "updated_files": list(dict.fromkeys(r["file"] for r in results if r["status"] == "updated")),
        "modified_files": list(dict.fromkeys(modified_files)),
        "details": results,
    }


def run_git(repo_dir, git_args, check=True):
    """Execute a git command scoped to repo_dir and raise GitCommandError on failure."""
    command = ["git", "-C", str(repo_dir), *git_args]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as err:
        raise GitCommandError(format_git_error(command, 127, stderr=str(err))) from err
    if check and proc.returncode != 0:
        raise GitCommandError(format_git_error(command, proc.returncode, proc.stdout, proc.stderr))
    return proc


def parse_git_status(porcelain_z):
    """Parse `git status --porcelain=v1 -z` output into structured status entries."""
    entries = []
    tokens = porcelain_z.split("\0")
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        idx += 1
        if not token or len(token) < 4:
            continue
        index_code = token[0]
        worktree_code = token[1]
        path = token[3:]
        if index_code in ("R", "C") and idx < len(tokens):
            idx += 1
        entries.append(
            {
                "path": path,
                "staged": index_code not in (" ", "?"),
                "unstaged": worktree_code not in (" ", "?"),
                "untracked": index_code == "?" and worktree_code == "?",
            }
        )
    return entries


def candidate_release_paths():
    """Return all repository-relative paths that a version bump may modify."""
    paths = {target["file"] for target in MANIFEST_TARGETS}
    paths.add(ATTESTATION_REL_PATH)
    paths.add(CARGO_LOCK_REL_PATH)
    return paths


def preflight_git_release(repo_dir, target_version, git_commit=False, git_tag=False):
    """Verify repository state before mutating files for a Git release."""
    run_git(repo_dir, ["rev-parse", "--is-inside-work-tree"])

    if git_commit:
        status_proc = run_git(repo_dir, ["status", "--porcelain=v1", "-z"])
        entries = parse_git_status(status_proc.stdout)
        staged = sorted(entry["path"] for entry in entries if entry["staged"])
        if staged:
            raise ValueError(f"Refusing --git-commit: preexisting staged changes in index: {', '.join(staged)}")

        targets = candidate_release_paths()
        dirty_targets = sorted(entry["path"] for entry in entries if entry["path"] in targets and entry["unstaged"])
        if dirty_targets:
            raise ValueError(
                f"Refusing --git-commit: preexisting uncommitted changes in release target files: {', '.join(dirty_targets)}"
            )

    if git_tag:
        tag_name = f"v{target_version}"
        tag_ref = f"refs/tags/{tag_name}"
        proc = run_git(repo_dir, ["rev-parse", "-q", "--verify", tag_ref], check=False)
        if proc.returncode == 0:
            raise ValueError(f"Refusing --git-tag: release tag '{tag_name}' already exists")
        if proc.returncode != 1:
            cmd = ["git", "-C", str(repo_dir), "rev-parse", "-q", "--verify", tag_ref]
            raise GitCommandError(format_git_error(cmd, proc.returncode, proc.stdout, proc.stderr))


def is_stageable_path(repo_dir, rel_path):
    """Return True if rel_path is tracked or not ignored by Git."""
    tracked = run_git(repo_dir, ["ls-files", "--error-unmatch", "--", rel_path], check=False)
    if tracked.returncode == 0:
        return True
    ignored = run_git(repo_dir, ["check-ignore", "-q", "--", rel_path], check=False)
    return ignored.returncode != 0


def commit_release_changes(repo_dir, version, modified_files):
    """Selectively stage modified release files and create the release commit."""
    stageable = [path for path in modified_files if is_stageable_path(repo_dir, path)]
    if not stageable:
        raise ValueError("No tracked or non-ignored version files were modified to commit.")

    run_git(repo_dir, ["add", "--", *stageable])

    staged_proc = run_git(repo_dir, ["diff", "--cached", "--name-only", "-z"])
    staged_paths = {path for path in staged_proc.stdout.split("\0") if path}
    unexpected = sorted(staged_paths - set(stageable))
    if unexpected:
        raise ValueError(f"Refusing commit: unexpected staged files detected: {', '.join(unexpected)}")
    if not staged_paths:
        raise ValueError("No staged changes remained after selective staging.")

    run_git(repo_dir, ["commit", "-m", f"chore(release): v{version}"])
    sha_proc = run_git(repo_dir, ["rev-parse", "--verify", "HEAD"])
    return sha_proc.stdout.strip(), sorted(staged_paths)


def create_release_tag(repo_dir, version):
    """Create and verify an annotated release tag."""
    tag_name = f"v{version}"
    run_git(repo_dir, ["tag", "-a", tag_name, "-m", f"Release {tag_name}"])
    run_git(repo_dir, ["rev-parse", "--verify", f"refs/tags/{tag_name}"])
    return tag_name


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

    root = pathlib.Path(args.repo).resolve()
    report = None
    commit_sha = None

    try:
        if (args.git_commit or args.git_tag) and not args.dry_run:
            target_ver = compute_next_version(read_current_version(root), args.bump)
            preflight_git_release(root, target_ver, git_commit=args.git_commit, git_tag=args.git_tag)

        report = bump_repository_version(
            root_dir=root,
            bump_type=args.bump,
            release_date=args.date,
            dry_run=args.dry_run,
        )

        if args.git_commit and not args.dry_run:
            commit_sha, staged_files = commit_release_changes(root, report["new_version"], report["modified_files"])
            report["commit_sha"] = commit_sha
            report["staged_files"] = staged_files

        if args.git_tag and not args.dry_run:
            report["tag"] = create_release_tag(root, report["new_version"])
    except (ValueError, FileNotFoundError, GitCommandError) as err:
        print(f"Error: {err}", file=sys.stderr)
        if report and report.get("modified_files"):
            print(
                f"Partial filesystem changes remain in working tree: {', '.join(report['modified_files'])}",
                file=sys.stderr,
            )
        if commit_sha:
            print(f"Release commit was created before subsequent Git failure: {commit_sha}", file=sys.stderr)
        return 1

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
