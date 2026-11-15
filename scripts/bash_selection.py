#!/usr/bin/env python3
"""Record completed Bash project skill installations."""

import hashlib
import json
import os
import re
import stat
import sys
from pathlib import Path

from safe_install import write_instruction

CORE = "anti-slop-engineering"
PROJECT_AGENTS = ["antigravity", "amp", "copilot", "kimi", "deepseek"]


def previous_selection(manifest):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        descriptor = os.open(manifest, flags)
    except FileNotFoundError:
        return [], "absent"
    with os.fdopen(descriptor, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ValueError("Expected a regular installer selection manifest")
        content = handle.read()
    state = json.loads(content)
    if not isinstance(state, dict) or state.get("format") != 1 or not isinstance(state.get("skills"), list):
        raise ValueError("Expected an installer selection in format 1")
    return state["skills"], hashlib.sha256(content).hexdigest()


def record_selection(project_skills, version_file, requested):
    manifest = project_skills / ".anti-slop-selection.json"
    previous, expected_hash = previous_selection(manifest)
    version = json.loads(version_file.read_text(encoding="utf-8")).get("version")
    if not isinstance(version, str) or not version:
        raise ValueError("Expected a package version")
    selected = {}
    for skill in [CORE, *previous, *requested]:
        if not isinstance(skill, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]*", skill):
            raise ValueError("Selection contains a malformed skill identifier")
        entry = project_skills / skill / "SKILL.md"
        if entry.is_file() and not entry.is_symlink() and not entry.parent.is_symlink():
            selected[skill] = None
    if CORE not in selected:
        raise ValueError("Required core skill entrypoint is absent")
    data = {"format": 1, "version": version, "scope": "project", "agents": PROJECT_AGENTS,
            "skills": list(selected)}
    write_instruction(manifest, (json.dumps(data, indent=2) + "\n").encode(), expected_hash)


if __name__ == "__main__":
    try:
        record_selection(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3:])
    except (OSError, ValueError) as exc:
        print(f"Installer error: {exc}", file=sys.stderr)
        sys.exit(2)
