#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install and evaluate opt-in Gemini CLI project hooks for write_file."""

import json
import os
import shlex
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.claude_hooks import PHASES, configure_hooks, run_hook_cli
from scripts.exec_guard import (
    SessionStateManager,
    _load_hook_policy,
    evaluate_hook_event,
    read_hook_object,
    validate_hook_event,
)

HOOK_PATH = str(Path(__file__).resolve())
NATIVE_PHASES = {"PreToolUse": "BeforeTool", "PostToolUse": "AfterTool"}
TOOL = "write_file"
ERROR_MESSAGE = "Anti-Slop could not evaluate the Gemini file action."


def normalize_event(payload, phase, project):
    if payload.get("hook_event_name") != NATIVE_PHASES[phase]:
        raise ValueError("Unexpected Gemini hook phase")
    tool = payload.get("tool_name")
    if not isinstance(tool, str):
        raise ValueError("Missing Gemini tool name")
    if tool != TOOL:
        return None
    cwd = payload.get("cwd")
    tool_input = payload.get("tool_input")
    target = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(cwd, str) or not isinstance(target, str) or not target.strip():
        raise ValueError("Gemini file action requires a working directory and target")
    native_cwd = Path(cwd)
    if not native_cwd.is_absolute() or not native_cwd.resolve().is_relative_to(project):
        raise ValueError("Gemini working directory is outside the registered project")
    event = {
        "schema_version": 1, "agent": "gemini-cli", "phase": PHASES[phase], "tool": TOOL,
        "operation": "write", "target_paths": [str(native_cwd / target)],
        "payload_trust": "untrusted", "correlation_id": payload.get("session_id"),
    }
    validate_hook_event(event)
    return event


def translate_policy(result, phase):
    effect, message = result["decision"], result["message"]
    if effect == "allow":
        return {}
    if phase == "PostToolUse":
        return {"hookSpecificOutput": {"additionalContext": message}}
    if effect == "warn":
        return {"systemMessage": message}
    return {"decision": "deny", "reason": message}


def evaluate(project, phase):
    try:
        event = normalize_event(read_hook_object(sys.stdin.buffer), phase, project)
        result = {}
        if event is not None:
            state = _load_hook_policy(SessionStateManager(project / ".anti-slop"))
            result = translate_policy(evaluate_hook_event(event, state, project), phase)
    except (OSError, ValueError, RuntimeError):
        result = translate_policy({"decision": "error", "message": ERROR_MESSAGE}, phase)
    print(json.dumps(result))
    return 0


def owns_handler(item):
    command = item.get("command") if isinstance(item, dict) else None
    if not isinstance(command, str):
        return False
    try:
        return HOOK_PATH in shlex.split(command)
    except ValueError:
        return False


def configure(project, install, dry_run, consent):
    if os.name != "posix":
        raise ValueError("Gemini hook installation is supported on POSIX hosts.")
    groups = {}
    for phase, native in NATIVE_PHASES.items():
        command = shlex.join([sys.executable, HOOK_PATH, "evaluate", "--project", str(project), "--phase", phase])
        groups[native] = {
            "matcher": "^write_file$",
            "hooks": [{"type": "command", "command": command, "timeout": 5000}],
        }
    result = configure_hooks(project / ".gemini" / "settings.json", groups, owns_handler, install, dry_run, consent)
    result["tools"] = [TOOL]
    result["requires_host_hook_trust"] = True
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_cli(__doc__, evaluate, configure))
