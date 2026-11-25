#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install and evaluate opt-in Antigravity project hooks for write_file and edit_file."""

import json
import os
import shlex
import sys
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.claude_hooks import (
    PHASES,
    read_settings,
    run_hook_cli,
    write_settings,
)
from scripts.exec_guard import (
    SessionStateManager,
    _load_hook_policy,
    evaluate_hook_event,
    read_hook_object,
    validate_hook_event,
)

HOOK_PATH = str(Path(__file__).resolve())
HOOK_NAME = "anti-slop"
TOOLS = ("write_file", "edit_file")
MATCHER = "write_file|edit_file"
ERROR_MESSAGE = "Anti-Slop could not evaluate the Antigravity file action."


def normalize_event(payload, phase, project):
    """Normalize an Antigravity PreToolUse/PostToolUse payload into a hook event."""
    if payload.get("hookEventName") != phase:
        raise ValueError("Unexpected Antigravity hook phase")
    tool_call = payload.get("toolCall")
    if not isinstance(tool_call, dict):
        raise ValueError("Expected Antigravity toolCall object")
    tool = tool_call.get("name")
    if not isinstance(tool, str) or not tool:
        raise ValueError("Missing Antigravity tool name")
    if tool not in TOOLS:
        return None
    cwd = payload.get("cwd")
    args = tool_call.get("args")
    target = args.get("Path") if isinstance(args, dict) else None
    if not isinstance(cwd, str) or not isinstance(target, str) or not target.strip():
        raise ValueError("Antigravity file action requires a working directory and Path")
    native_cwd = Path(cwd)
    if not native_cwd.is_absolute() or not native_cwd.resolve().is_relative_to(project):
        raise ValueError("Antigravity working directory is outside the registered project")
    if not Path(target).is_absolute():
        target = str(native_cwd / target)
    correlation_id = tool_call.get("id") or payload.get("conversationId")
    event = {
        "schema_version": 1,
        "agent": "antigravity",
        "phase": PHASES[phase],
        "tool": tool,
        "operation": "write",
        "target_paths": [target],
        "payload_trust": "untrusted",
        "correlation_id": correlation_id,
    }
    validate_hook_event(event)
    return event


def translate_policy(result, phase):
    """Translate an exec_guard decision into an Antigravity hook response."""
    effect, message = result["decision"], result["message"]
    if effect == "allow" or phase == "PostToolUse":
        return {}
    if effect == "warn":
        return {"decision": "ask", "reason": message}
    return {"decision": "deny", "reason": message}


def evaluate(project, phase):
    """Evaluate stdin hook payload against the armed project policy."""
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


def expected_hook_entry(project):
    """Build the expected Antigravity hooks.json entry for this project."""
    entry = {}
    for phase in PHASES:
        command = shlex.join([sys.executable, HOOK_PATH, "evaluate", "--project", str(project), "--phase", phase])
        entry[phase] = [{
            "matcher": MATCHER,
            "hooks": [{"type": "command", "command": command, "timeout": 5}],
        }]
    return entry


def configure(project, install, dry_run, consent):
    """Install or uninstall the Antigravity .agents/hooks.json entry."""
    if os.name != "posix":
        raise ValueError("Antigravity hook installation is supported on POSIX hosts.")
    if not dry_run and not consent:
        raise ValueError("Use --dry-run to inspect changes or --yes to apply them.")
    settings_path = project / ".agents" / "hooks.json"
    if settings_path.parent.is_symlink() or settings_path.is_symlink():
        raise ValueError("Antigravity hooks settings must be local")
    initial_stat, settings = read_settings(settings_path)
    expected = expected_hook_entry(project)
    changed = False
    if HOOK_NAME in settings:
        if settings[HOOK_NAME] != expected:
            raise ValueError("Existing Anti-Slop hook was modified. Restore or remove it in settings.")
        if not install:
            del settings[HOOK_NAME]
            changed = True
    elif install:
        settings[HOOK_NAME] = expected
        changed = True
    status = "unchanged"
    if changed and dry_run:
        status = "would_change"
    elif changed:
        write_settings(settings_path, initial_stat, settings)
        status = "changed"
    print(json.dumps({
        "status": status,
        "settings": str(settings_path),
        "tools": list(TOOLS),
        "requires_host_hook_trust": False,
    }))
    return 0


if __name__ == "__main__":
    sys.exit(run_hook_cli(__doc__, evaluate, configure))
