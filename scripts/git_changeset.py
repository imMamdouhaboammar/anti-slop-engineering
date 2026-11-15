# SPDX-License-Identifier: MIT
"""Collect versioned file-change evidence directly from Git."""
import codecs
import os
import subprocess
from collections import defaultdict

STATUS = b"ACDMRTUXB"


def git(repo, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0")
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args], capture_output=True, env=env, timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise RuntimeError(f"Git could not collect file changes: {error}") from error
    if completed.returncode:
        detail = completed.stderr.decode("utf-8", "replace").strip()
        raise RuntimeError(detail or f"Git exited {completed.returncode}")
    return completed.stdout


def path_record(raw):
    if raw is None:
        return None
    try:
        return {"text": raw.decode("utf-8"), "raw_hex": None}
    except UnicodeDecodeError:
        return {"text": None, "raw_hex": raw.hex()}


def raw_records(data):
    records = {}
    counts = {}
    fields = iter(data.split(b"\0"))
    for token in fields:
        if not token:
            continue
        if token.startswith(b":"):
            old_mode, new_mode, _, _, status = token[1:].split(b" ")
            if not status or status[0] not in STATUS or (len(status) > 1 and not status[1:].isdigit()):
                raise ValueError("Unexpected Git path status")
            first = next(fields)
            second = next(fields) if status.startswith((b"R", b"C")) else first
            old = None if status.startswith(b"A") else first
            new = None if status.startswith(b"D") else second
            key = (first, second)
            records[key] = {
                "status": chr(status[0]),
                "score": int(status[1:]) if len(status) > 1 else None,
                "old_path": path_record(old),
                "new_path": path_record(new),
                "old_mode": None if old_mode == b"000000" else old_mode.decode("ascii"),
                "new_mode": None if new_mode == b"000000" else new_mode.decode("ascii"),
            }
        else:
            added, deleted, first = token.split(b"\t", 2)
            second = first
            if not first:
                first, second = next(fields), next(fields)
            counts[(first, second)] = (
                (None, None) if added == deleted == b"-" else (int(added), int(deleted))
            )
    if records.keys() != counts.keys():
        raise ValueError("Git raw and numstat file records differ")
    return records, counts


def patch_path(token, prefix):
    token = token.removesuffix(b"\t")
    if token == b"/dev/null":
        return None
    if token.startswith(b'"') and token.endswith(b'"'):
        token = codecs.escape_decode(token[1:-1])[0]
    if not token.startswith(prefix) or len(token) == 2:
        raise ValueError("Unexpected Git patch path prefix")
    return token[2:]


def line_range(token, prefix):
    if not token.startswith(prefix):
        raise ValueError("Unexpected Git patch side")
    start, separator, count = token[1:].partition(b",")
    return int(start), int(count) if separator else 1


def patch_ranges(patch):
    ranges = defaultdict(list)
    old = new = None
    header = False
    for line in patch.split(b"\n"):
        if line.startswith(b"diff --git "):
            old = new = None
            header = True
        elif header and line.startswith(b"--- "):
            old = patch_path(line[4:], b"a/")
        elif header and line.startswith(b"+++ "):
            new = patch_path(line[4:], b"b/")
        elif line.startswith(b"@@ "):
            header = False
            _, old_range, new_range, tail = line.split(b" ", 3)
            if not tail.startswith(b"@@") or (old is None and new is None):
                raise ValueError("Unexpected Git patch range")
            old_start, old_count = line_range(old_range, b"-")
            new_start, new_count = line_range(new_range, b"+")
            key = (old if old is not None else new, new if new is not None else old)
            ranges[key].append({
                "old_start": old_start, "old_count": old_count,
                "new_start": new_start, "new_count": new_count,
            })
    return ranges


def repository_root(repo):
    return os.fsdecode(git(repo, "rev-parse", "--show-toplevel").removesuffix(b"\n"))


def collect_changes(repo, base, snapshot="worktree", target=None):
    """Collect from the repository root resolved by the caller."""
    if snapshot not in {"worktree", "index", "commit"} or (snapshot == "commit") != bool(target):
        raise ValueError("A target is required only for the commit snapshot")
    base_id = git(repo, "rev-parse", "--verify", "--end-of-options", f"{base}^{{commit}}").strip().decode("ascii")
    target_id = None
    if target:
        target_id = git(repo, "rev-parse", "--verify", "--end-of-options", f"{target}^{{commit}}").strip().decode("ascii")

    options = [
        "--raw", "--numstat", "-z", "--patch", "--no-ext-diff", "--no-textconv",
        "--no-color", "--no-relative", "--find-renames", "--src-prefix=a/", "--dst-prefix=b/",
        "--unified=0", "--inter-hunk-context=0", "--submodule=short",
        "--output-indicator-new=+", "--output-indicator-old=-", "--output-indicator-context= ",
    ]
    if snapshot == "index":
        result = git(repo, "diff", *options, "--cached", base_id, "--")
    elif target_id:
        result = git(repo, "diff", *options, base_id, target_id, "--")
    else:
        result = git(repo, "diff", *options, base_id, "--")
    data, _, patch = result.partition(b"\0\0")
    try:
        records, counts = raw_records(data)
        ranges = patch_ranges(patch)
    except (StopIteration, ValueError) as error:
        raise RuntimeError("Git produced an invalid change set") from error
    if ranges.keys() - records.keys():
        raise RuntimeError("Git patch ranges could not be attributed to file changes")
    for key, record in records.items():
        added, deleted = counts[key]
        record.update(added=added, deleted=deleted, binary=added is None, hunks=ranges.get(key, []))
    untracked = []
    if snapshot == "worktree":
        paths = git(repo, "ls-files", "--others", "--exclude-standard", "-z")
        untracked = [path_record(path) for path in paths.split(b"\0") if path]
    return {
        "version": 1,
        "snapshot": snapshot,
        "base": base_id,
        "target": target_id,
        "files": list(records.values()),
        "untracked": untracked,
    }
