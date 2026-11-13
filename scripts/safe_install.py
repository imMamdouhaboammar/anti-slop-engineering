#!/usr/bin/env python3
"""Preserve installed skill files while applying verified package updates."""

import argparse
from contextlib import ExitStack, suppress
import errno
import hashlib
import json
import os
import secrets
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
    if path.is_symlink():
        raise ValueError(f"Managed inventory cannot be a symbolic link: {path}")
    if not path.exists():
        return {}
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
    journal = destination.parent / f".{destination.name}.swap.json"
    if journal.is_symlink():
        raise ValueError(f"Symbolic link in recovery journal: {journal}")
    if journal.exists():
        state = json.loads(journal.read_text(encoding="utf-8"))
        name = state.get("backup") if isinstance(state, dict) else None
        if not isinstance(name, str) or not name.startswith(f".{destination.name}.backup-") or "/" in name or "\\" in name:
            raise ValueError(f"Invalid installation recovery journal: {journal}")
        backup = destination.parent / name
        if backup not in backups:
            raise ValueError(f"Missing installation recovery backup: {backup}")
    elif len(backups) == 1:
        backup = backups[0]
    else:
        raise ValueError(f"Ambiguous installation recovery: {destination.parent}")
    if backup.is_symlink() or not backup.is_dir():
        raise ValueError(f"Invalid installation recovery backup: {backup}")
    os.replace(backup, destination)
    if journal.exists():
        journal.unlink()
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
            if not item.is_file() and not item.is_symlink():
                continue
            relative = item.relative_to(destination).as_posix()
            if relative != MANIFEST and relative not in source_files:
                results["preserved"].append(relative)
    return results, writes, managed


def record_swap(destination, backup):
    journal = destination.parent / f".{destination.name}.swap.json"
    descriptor, name = tempfile.mkstemp(prefix=f".{destination.name}.journal-", dir=destination.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        temporary.write_text(json.dumps({"backup": backup.name}), encoding="utf-8")
        os.replace(temporary, journal)
    finally:
        if temporary.exists():
            temporary.unlink()


def snapshot_tree(root):
    """Fingerprint the active tree, including unmanaged files, before replacement."""
    if not root.exists():
        return None
    snapshot = {}
    for item in (root, *root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        metadata = item.lstat()
        if stat.S_ISLNK(metadata.st_mode):
            snapshot[relative] = ("link", os.readlink(item))
        elif stat.S_ISDIR(metadata.st_mode):
            snapshot[relative] = ("directory", stat.S_IMODE(metadata.st_mode))
        elif stat.S_ISREG(metadata.st_mode):
            snapshot[relative] = ("file", stat.S_IMODE(metadata.st_mode), digest(item.read_bytes()))
        else:
            snapshot[relative] = ("unsupported", metadata.st_mode)
    return snapshot


def write_staged_file(stage, relative, content, mode):
    """Write beneath a private staging directory without following nested links."""
    parts = Path(relative).parts
    if not parts or Path(relative).is_absolute() or any(part in (".", "..") for part in parts):
        raise ValueError(f"Invalid staged file path: {relative}")
    if os.name != "posix":
        target = stage / relative
        for ancestor in (target, *target.parents):
            if ancestor.is_symlink():
                raise ValueError(f"Symbolic link in staged file path: {relative}")
            if ancestor == stage:
                break
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_symlink():
            raise ValueError(f"Symbolic link in staged file path: {relative}")
        target.write_bytes(content)
        target.chmod(mode)
        return
    with ExitStack() as stack:
        directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, directory_fd)
        for component in parts[:-1]:
            with suppress(FileExistsError):
                os.mkdir(component, dir_fd=directory_fd)
            if stat.S_ISLNK(os.stat(component, dir_fd=directory_fd, follow_symlinks=False).st_mode):
                raise ValueError(f"Symbolic link in staged file path: {relative}")
            next_fd = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory_fd)
            stack.callback(os.close, next_fd)
            directory_fd = next_fd
        name = parts[-1]
        try:
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            metadata = None
        if metadata is not None and not stat.S_ISREG(metadata.st_mode):
            raise ValueError(f"Symbolic link or unsupported staged file: {relative}")
        file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, mode, dir_fd=directory_fd)
        with os.fdopen(file_fd, "wb") as output:
            output.write(content)
            output.flush()
            os.fchmod(output.fileno(), mode)


def stage_install(destination, writes, managed, original_snapshot):
    destination.parent.mkdir(parents=True, exist_ok=True)
    journal = destination.parent / f".{destination.name}.swap.json"
    if journal.is_symlink():
        raise ValueError(f"Symbolic link in installation journal: {journal}")
    stage = Path(tempfile.mkdtemp(prefix=f".{destination.name}.stage-", dir=destination.parent))
    backup = None
    try:
        if destination.exists():
            shutil.copytree(destination, stage, dirs_exist_ok=True, symlinks=True)
        for relative, (content, mode) in writes.items():
            write_staged_file(stage, relative, content, mode)
        write_staged_file(
            stage, MANIFEST,
            (json.dumps({"format": 1, "files": managed}, sort_keys=True, indent=2) + "\n").encode(),
            0o644,
        )
        for relative, (content, _) in writes.items():
            if digest((stage / relative).read_bytes()) != digest(content):
                raise OSError(f"Staged installation failed verification: {relative}")
        if snapshot_tree(destination) != original_snapshot:
            raise OSError(f"Installed files changed during installation: {destination}")
        if destination.exists():
            backup = Path(tempfile.mkdtemp(prefix=f".{destination.name}.backup-", dir=destination.parent))
            backup.rmdir()
            record_swap(destination, backup)
            os.replace(destination, backup)
            if snapshot_tree(backup) != original_snapshot:
                os.replace(backup, destination)
                raise OSError(f"Installed files changed during installation: {destination}")
        try:
            os.replace(stage, destination)
        except OSError:
            if backup is not None:
                os.replace(backup, destination)
            raise
        if journal.exists():
            journal.unlink()
        return str(backup) if backup is not None else None
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if destination.exists() and journal.exists():
            journal.unlink()


def prepared_paths(source, destination):
    source = Path(source).resolve(strict=True)
    destination = Path(destination)
    if not source.is_dir():
        raise ValueError(f"Installation source is not a directory: {source}")
    validate_destination(source, destination)
    return source, destination


def install_tree(source, destination, version=None):
    source, destination = prepared_paths(source, destination)
    recovered = recover_interrupted_swap(destination)
    previous = load_manifest(destination)
    original_snapshot = snapshot_tree(destination)
    source_files = collect_source(source, destination, version)
    results, writes, managed = plan_files(source_files, destination, previous)
    backup = None
    if writes or managed != previous or not destination.exists():
        backup = stage_install(destination, writes, managed, original_snapshot)
    return {**results, "destination": str(destination), "backup": backup, "recovered": recovered}


def write_instruction(entry, content, expected_hash):
    """Atomically replace an instruction file using a no-follow parent handle."""
    entry = Path(entry)
    if not entry.is_absolute() or ".." in entry.parts or entry.name in ("", ".", ".."):
        raise ValueError(f"Unsafe agent instruction path: {entry}")
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    with ExitStack() as stack:
        if os.name == "posix":
            directory_fd = os.open(entry.anchor, flags)
            stack.callback(os.close, directory_fd)
            for component in entry.parts[1:-1]:
                try:
                    next_fd = os.open(component, flags, dir_fd=directory_fd)
                except OSError as exc:
                    if exc.errno in (errno.ELOOP, errno.ENOTDIR):
                        raise ValueError(f"Unsafe symbolic link in agent instruction path: {entry}") from exc
                    raise
                stack.callback(os.close, next_fd)
                directory_fd = next_fd
            parent = None
        else:
            # Windows Python lacks dir_fd support; reject links at every existing ancestor.
            for ancestor in (entry, *entry.parents):
                if ancestor.is_symlink():
                    raise ValueError(f"Symbolic link in agent instruction path: {ancestor}")
            directory_fd = None
            parent = entry.parent

        open_args = {"dir_fd": directory_fd} if directory_fd is not None else {}
        current_mode = 0o600
        try:
            current_fd = os.open(entry.name if parent is None else entry, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0), **open_args)
        except FileNotFoundError:
            current_hash = "absent"
        else:
            with os.fdopen(current_fd, "rb") as existing:
                current_mode = stat.S_IMODE(os.fstat(existing.fileno()).st_mode)
                if not stat.S_ISREG(os.fstat(existing.fileno()).st_mode):
                    raise ValueError(f"Unsafe agent instruction file: {entry}")
                current_hash = digest(existing.read())
        if current_hash != expected_hash:
            raise ValueError(f"Agent instructions changed during installation: {entry}")

        temporary = f".{entry.name}.{secrets.token_hex(12)}.tmp"
        target = temporary if parent is None else parent / temporary
        created = False
        try:
            temporary_fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0), 0o600, **open_args)
            created = True
            with os.fdopen(temporary_fd, "wb") as output:
                output.write(content)
                output.flush()
                if hasattr(os, "fchmod"):
                    os.fchmod(output.fileno(), current_mode)
            if not hasattr(os, "fchmod"):
                os.chmod(target, current_mode)
            if directory_fd is not None:
                os.replace(temporary, entry.name, src_dir_fd=directory_fd, dst_dir_fd=directory_fd)
            else:
                os.replace(parent / temporary, entry)
        finally:
            if created:
                with suppress(FileNotFoundError):
                    os.unlink(target, **open_args)


def preview_tree(source, destination, version=None):
    source, destination = prepared_paths(source, destination)
    previous = load_manifest(destination)
    source_files = collect_source(source, destination, version)
    results, _, _ = plan_files(source_files, destination, previous)
    return {**results, "destination": str(destination), "backup": None, "recovered": None,
            "recovery_required": not destination.exists() and any(
                destination.parent.glob(f".{destination.name}.backup-*")
            )}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source")
    parser.add_argument("--dest")
    parser.add_argument("--version")
    parser.add_argument("--write-instruction")
    parser.add_argument("--expected-hash")
    parser.add_argument("--dry-run", action="store_true")
    options = parser.parse_args()
    try:
        if options.write_instruction is not None:
            if not options.expected_hash:
                parser.error("--write-instruction requires --expected-hash")
            write_instruction(options.write_instruction, sys.stdin.buffer.read(), options.expected_hash)
            return 0
        if not options.source or not options.dest:
            parser.error("--source and --dest are required for installation")
        operation = preview_tree if options.dry_run else install_tree
        print(json.dumps(operation(options.source, options.dest, options.version)))
    except (OSError, ValueError) as exc:
        print(f"Installer error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
