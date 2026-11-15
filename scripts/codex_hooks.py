#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install and evaluate opt-in Codex project hooks for apply_patch."""
import argparse
import json
import os
import shlex
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.claude_hooks import PHASES, configure_hooks, translate_policy
from scripts.exec_guard import (
    HOOK_EVENT_MAX_PATH_LENGTH,
    HOOK_EVENT_MAX_PATHS,
    SessionStateManager,
    _load_hook_policy,
    evaluate_hook_event,
    read_hook_object,
    validate_hook_event,
)

HOOK_PATH = str(Path(__file__).resolve())
MATCHER = "apply_patch"
PATCH_FILE_HEADERS = ("*** Add File: ", "*** Delete File: ", "*** Update File: ")
PATCH_MOVE_HEADER = "*** Move to: "
ERROR_MESSAGE = "Anti-Slop could not verify the Codex file action."


def patch_paths(patch):
    if not isinstance(patch, str):
        raise ValueError("Expected Codex tool input patch")
    lines = patch.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    if len(lines) < 3 or lines[0] != "*** Begin Patch" or lines[-1] != "*** End Patch":
        raise ValueError("Expected a Codex apply_patch envelope")
    targets = []
    for line in lines[1:-1]:
        for marker in (*PATCH_FILE_HEADERS, PATCH_MOVE_HEADER):
            if line.startswith(marker):
                path = line[len(marker):]
                if not 0 < len(path) <= HOOK_EVENT_MAX_PATH_LENGTH or path != path.strip():
                    raise ValueError("Invalid Codex patch target")
                if len(targets) >= HOOK_EVENT_MAX_PATHS:
                    raise ValueError("Too many Codex patch targets")
                targets.append(path)
                break
        else:
            if line.startswith("*** ") and line != "*** End of File":
                raise ValueError("Unknown Codex patch header")
    if not targets:
        raise ValueError("Codex patch did not expose target paths")
    return targets


def normalize_event(payload, phase, project):
    if payload.get("hook_event_name") != phase or payload.get("tool_name") != MATCHER:
        raise ValueError("Unexpected Codex hook event")
    cwd = payload.get("cwd")
    if not isinstance(cwd, str):
        raise ValueError("Expected Codex working directory")
    native_cwd = Path(cwd)
    if not native_cwd.is_absolute() or not native_cwd.resolve().is_relative_to(project):
        raise ValueError("Codex working directory is outside the project")
    tool_input = payload.get("tool_input")
    paths = patch_paths(tool_input.get("command") if isinstance(tool_input, dict) else None)
    event = {
        "schema_version": 1, "agent": "codex", "phase": PHASES[phase],
        "tool": MATCHER, "operation": "write", "target_paths": [str(native_cwd / path) for path in paths],
        "payload_trust": "untrusted", "correlation_id": payload.get("tool_use_id"),
    }
    validate_hook_event(event)
    return event


def evaluate(project, phase):
    try:
        event = normalize_event(read_hook_object(sys.stdin.buffer), phase, project)
        decision = evaluate_hook_event(event, _load_hook_policy(SessionStateManager(project / ".anti-slop")), project)
        result = translate_policy(decision, phase)
    except (OSError, ValueError, RuntimeError):
        result = translate_policy({"decision": "block" if phase == "PreToolUse" else "warn", "message": ERROR_MESSAGE}, phase)
    print(json.dumps(result))
    return 0


def configure(project, install, dry_run, consent):
    if os.name != "posix":
        raise ValueError("Codex hook installation is supported on POSIX hosts.")

    def owns_handler(item):
        command = item.get("command") if isinstance(item, dict) else None
        if not isinstance(command, str):
            return False
        try:
            return HOOK_PATH in shlex.split(command)
        except ValueError:
            return False

    groups = {}
    for phase in PHASES:
        command = shlex.join([sys.executable, HOOK_PATH, "evaluate", "--project", str(project), "--phase", phase])
        groups[phase] = {"matcher": MATCHER, "hooks": [{"type": "command", "command": command, "timeout": 5}]}
    result = configure_hooks(project / ".codex" / "hooks.json", groups, owns_handler, install, dry_run, consent)
    result["tools"] = [MATCHER]
    result["requires_host_hook_trust"] = True
    print(json.dumps(result))
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for command in ("install", "uninstall"):
        config = commands.add_parser(command)
        config.add_argument("--project", type=Path, default=Path.cwd())
        config.add_argument("--dry-run", action="store_true")
        config.add_argument("--yes", action="store_true")
    evaluate_parser = commands.add_parser("evaluate")
    evaluate_parser.add_argument("--project", type=Path, required=True)
    evaluate_parser.add_argument("--phase", choices=PHASES, required=True)
    args = parser.parse_args()

    try:
        project = args.project.resolve(strict=True)
        if not project.is_dir():
            raise ValueError("Expected a local project directory")
        if args.command == "evaluate":
            return evaluate(project, args.phase)
        return configure(project, args.command == "install", args.dry_run, args.yes)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"Codex hook configuration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
