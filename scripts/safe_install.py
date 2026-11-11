#!/usr/bin/env python3
"""Preserve installed skill files while applying verified package updates."""

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import tempfile
from pathlib import Path


MANIFEST = ".anti-slop-managed.json"
EXCLUDED = {".git", "node_modules", "target"}


def digest(content):
    return hashlib.sha256(content).hexdigest()


def validate_destination(source, destination):
    if not destination.is_absolute() or ".." in destination.parts:
        raise ValueError("Installation destination must be an absolute path without traversal")
    if destination == Path(destination.anchor) or destination.name in {"", ".", ".."}:
        raise ValueError("Refusing to install into a filesystem root")
    for parent in (destination, *destination.parents):
        if parent.is_symlink():
            raise ValueError(f"Symbolic link in installation destination: {parent}")
    resolved = destination.resolve()
    if resolved == source or resolved in source.parents:
        raise ValueError("Installation source and destination overlap")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"Installation destination is not a directory: {destination}")


def collect_source(source, destination, version=None):
    files = {}
    for current, directories, names in os.walk(source, followlinks=False):
        parent = Path(current)
        for name in list(directories):
            item = parent / name
            if (name in EXCLUDED or item == destination
                    or (parent == destination.parent and name.startswith(
                        (f".{destination.name}.backup-", f".{destination.name}.stage-"
                    )))):
                directories.remove(name)
            elif item.is_symlink():
                raise ValueError(f"Source directory is a symbolic link: {item}")
        for name in names:
            if name in EXCLUDED or name == MANIFEST:
                continue
            item = parent / name
            if item.is_symlink() or not item.is_file():
                raise ValueError(f"Unsupported source file type: {item}")
            files[item.relative_to(source).as_posix()] = (
                item.read_bytes(), stat.S_IMODE(item.stat().st_mode)
            )
    if version is not None:
        files["VERSION"] = ((version + "\n").encode(), 0o644)
    return files


def load_manifest(destination):
    path = destination / MANIFEST
    if not path.exists():
        return {}
    if path.is_symlink():
        raise ValueError(f"Managed inventory cannot be a symbolic link: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("format") != 1 or not isinstance(data.get("files"), dict):
        raise ValueError(f"Invalid managed inventory: {path}")
    for relative, checksum in data["files"].items():
        if (not isinstance(relative, str) or not relative or relative.startswith("/")
                or any(part in {"", ".", ".."} for part in relative.split("/"))
                or not isinstance(checksum, str) or len(checksum) != 64):
            raise ValueError(f"Invalid managed inventory entry: {relative!r}")
    return data["files"]


def recover_interrupted_swap(destination):
    if destination.exists():
        return None
    backups = list(destination.parent.glob(f".{destination.name}.backup-*"))
    if not backups:
        return None
    if len(backups) != 1 or backups[0].is_symlink() or not backups[0].is_dir():
        raise ValueError(f"Ambiguous installation recovery: {destination.parent}")
    os.replace(backups[0], destination)
    return str(destination)


def plan_files(source_files, destination, previous):
    results = {status: [] for status in ("installed", "updated", "preserved", "skipped", "conflicted")}
    managed = dict(previous)
    writes = {}
    for relative, (content, mode) in sorted(source_files.items()):
        dest = destination / relative
        incoming = digest(content)
        if dest.is_symlink() or any(parent.is_symlink() for parent in dest.parents if destination in parent.parents):
            raise ValueError(f"Symbolic link in managed file path: {dest}")
        if not dest.exists():
            results["installed"].append(relative)
            writes[relative] = (content, mode)
            managed[relative] = incoming
        elif not dest.is_file():
            results["conflicted"].append(relative)
        else:
            existing = digest(dest.read_bytes())
            if existing == incoming:
                results["skipped"].append(relative)
                managed[relative] = incoming
            elif previous.get(relative) == existing:
                results["updated"].append(relative)
                writes[relative] = (content, mode)
                managed[relative] = incoming
            else:
                results["conflicted"].append(relative)
    if destination.exists():
        for item in destination.rglob("*"):
            if item.is_file() or item.is_symlink():
                relative = item.relative_to(destination).as_posix()
                if relative != MANIFEST and relative not in source_files:
                    results["preserved"].append(relative)
    return results, writes, managed


def stage_install(destination, writes, managed):
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    backup = None
    try:
        if destination.exists():
            shutil.copytree(destination, stage, dirs_exist_ok=True, symlinks=True)
        for relative, (content, mode) in writes.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_symlink():
                raise ValueError(f"Symbolic link in staged file path: {target}")
            target.write_bytes(content)
            target.chmod(mode)
        (stage / MANIFEST).write_text(
            json.dumps({"format": 1, "files": managed}, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        for relative, (content, _) in writes.items():
            if digest((stage / relative).read_bytes()) != digest(content):
                raise OSError(f"Staged installation failed verification: {relative}")
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{destination.name}.backup-", dir=destination.parent))
            backup.rmdir()
            os.replace(destination, backup)
        try:
            os.replace(stage, destination)
        except OSError:
            if backup is not None:
                os.replace(backup, destination)
            raise
        return str(backup) if backup is not None else None
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def install_tree(source, destination, version=None):
    source = Path(source).resolve(strict=True)
    destination = Path(destination)
    if not source.is_dir():
        raise ValueError(f"Installation source is not a directory: {source}")
    validate_destination(source, destination)
    recovered = recover_interrupted_swap(destination)
    previous = load_manifest(destination)
    source_files = collect_source(source, destination, version)
    results, writes, managed = plan_files(source_files, destination, previous)
    backup = None
    if writes or managed != previous or not destination.exists():
        backup = stage_install(destination, writes, managed)
    return {**results, "destination": str(destination), "backup": backup, "recovered": recovered}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--dest", required=True)
    parser.add_argument("--version")
    options = parser.parse_args()
    try:
        print(json.dumps(install_tree(options.source, options.dest, options.version)))
    except (OSError, ValueError) as exc:
        print(f"Installer error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
