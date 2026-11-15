"""Verify a record's bounded Git evidence using local committed objects."""

import argparse
import hashlib
import os
import subprocess
from pathlib import Path, PurePosixPath


MAX_PATHS = 16
MAX_BLOB_BYTES = 1024 * 1024
DIFF_OPTIONS = (
    "--no-ext-diff", "--no-textconv", "--no-renames", "--no-color", "--no-relative",
    "--diff-algorithm=myers", "--no-indent-heuristic", "--src-prefix=a/", "--dst-prefix=b/", "--unified=3",
)


def audit_parser(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("command", choices=["audit"])
    parser.add_argument("record", type=Path)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--verify-evidence", action="store_true", help="Check committed evidence in the selected Git repository")
    parser.add_argument("--json", action="store_true")
    return parser


def _hex(value, lengths=(64,)):
    if not isinstance(value, str) or len(value) not in lengths:
        return False
    return all(character in "0123456789abcdef" for character in value)


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _git(repo, *args, check=True):
    # Local objects only, including when the repository is a partial clone.
    env = {name: value for name, value in os.environ.items() if not name.startswith("GIT_")}
    env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=os.devnull, GIT_NO_REPLACE_OBJECTS="1",
               GIT_NO_LAZY_FETCH="1", GIT_ALLOW_PROTOCOL="", LC_ALL="C")
    command = ["git", "-C", str(repo), "--literal-pathspecs", "-c", "core.quotePath=true",
               "-c", "core.attributesFile=" + os.devnull, "-c", "diff.submodule=short",
               "-c", "diff.wsErrorHighlight=new", "-c", "core.fsmonitor=false",
               "-c", "core.abbrev=12", "-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab"]
    command.extend(args)
    return subprocess.run(command, capture_output=True, check=check, env=env, timeout=5)


def _valid_path(value):
    if not isinstance(value, str) or not value or len(value) > 512 or "\\" in value or "\x00" in value:
        return False
    path = PurePosixPath(value)
    return value != "." and value == path.as_posix() and not path.is_absolute() and ".." not in path.parts


def _claim(evidence):
    if not isinstance(evidence, dict) or type(evidence.get("version")) is not int or evidence["version"] != 1:
        raise ValueError("Missing or unsupported repository_evidence version")
    base, head = evidence.get("base_commit"), evidence.get("head_commit")
    if not (_hex(base, (40, 64)) and _hex(head, (40, 64)) and base != head):
        raise ValueError("Use distinct full base and head commit IDs")
    paths = evidence.get("paths")
    if not isinstance(paths, list) or not 1 <= len(paths) <= MAX_PATHS:
        raise ValueError("Claim 1–16 changed regular paths")
    seen = set()
    for item in paths:
        if not isinstance(item, dict) or not _valid_path(item.get("path")):
            raise ValueError("Invalid repository-relative path")
        path = item["path"]
        if path in seen or not all(_hex(item.get(key)) for key in ("blob_sha256", "patch_sha256")):
            raise ValueError("Paths must be unique and carry valid blob and patch SHA-256 digests")
        seen.add(path)
    check = evidence.get("check")
    if not (isinstance(check, dict) and check.get("name") == "git_diff_check"
            and type(check.get("exit_code")) is int and check["exit_code"] == 0
            and set(check) == {"name", "exit_code", "stdout_sha256", "stderr_sha256"}
            and all(_hex(check.get(key)) for key in ("stdout_sha256", "stderr_sha256"))):
        raise ValueError("Expected a successful git_diff_check and digests for both output streams")
    return base, head, paths, check


def _blob_oid(repo, commit, path, required):
    raw = _git(repo, "ls-tree", "-z", commit, "--", path).stdout
    if not raw and not required:
        return None
    if raw.count(b"\x00") != 1 or b"\t" not in raw:
        raise ValueError("No regular committed file at a claimed path")
    entry, wire_path = raw[:-1].split(b"\t", 1)
    mode, kind, oid = entry.split()
    if wire_path != os.fsencode(path) or kind != b"blob" or mode not in {b"100644", b"100755"}:
        raise ValueError("Evidence paths must be regular committed files")
    oid = oid.decode("ascii")
    if int(_git(repo, "cat-file", "-s", oid).stdout) > MAX_BLOB_BYTES:
        raise ValueError("Evidence files are limited to 1 MiB per revision")
    return oid


def _verify_path(repo, base, head, claim):
    path = claim["path"]
    _blob_oid(repo, base, path, required=False)
    oid = _blob_oid(repo, head, path, required=True)
    blob = _git(repo, "cat-file", "blob", oid).stdout
    patch = _git(repo, "diff", *DIFF_OPTIONS, base, head, "--", path).stdout
    return {
        "path": path,
        "blob_matches": _sha256(blob) == claim["blob_sha256"],
        "patch_matches": bool(patch) and _sha256(patch) == claim["patch_sha256"],
    }


def attach_evidence(result, record, repo):
    result["record_valid"] = result["record_status"] == "complete"
    result["evidence_status"] = "inconclusive"
    result["evidence_scope"] = "Listed commit, file hashes, and scoped Git whitespace check"
    checks = {"paths": [], "diff_check": None}
    result["evidence_checks"] = checks
    if not result["record_valid"]:
        checks["reason"] = "Record is structurally incomplete"
        return
    try:
        base, head, paths, expected = _claim(record.get("repository_evidence"))
        for oid in (base, head):
            if _git(repo, "cat-file", "-t", oid).stdout.strip() != b"commit":
                raise ValueError("Evidence IDs must identify commit objects")
        if _git(repo, "rev-parse", "HEAD").stdout.decode().strip() != head:
            raise ValueError("Evidence head differs from the checkout; verify from a checkout of the stated commit")
        _git(repo, "merge-base", "--is-ancestor", base, head)
        checks["paths"] = [_verify_path(repo, base, head, item) for item in paths]
        observed = _git(repo, "diff", *DIFF_OPTIONS, "--check", base, head, "--",
                        *(item["path"] for item in paths), check=False)
    except ValueError as error:
        checks["reason"] = str(error)
        return
    except (OSError, subprocess.SubprocessError):
        checks["reason"] = "Required local Git evidence is unavailable"
        return

    diff = {
        "name": "git_diff_check",
        "exit_code": observed.returncode,
        "stdout_sha256": _sha256(observed.stdout),
        "stderr_sha256": _sha256(observed.stderr),
    }
    checks["diff_check"] = diff
    if diff == expected and all(item["blob_matches"] and item["patch_matches"] for item in checks["paths"]):
        result["evidence_status"] = "implementation_verified"
    else:
        checks["reason"] = "Recorded file or check evidence does not match the repository"


def exit_code(result, structural_code, as_json):
    if "evidence_status" in result and not as_json:
        print("Repository evidence: %s (%s)" % (result["evidence_status"], result["evidence_scope"]))
        reason = result["evidence_checks"].get("reason")
        if reason:
            print("  %s" % reason)
    if structural_code:
        return structural_code
    return 3 if result.get("evidence_status") == "inconclusive" else 0
