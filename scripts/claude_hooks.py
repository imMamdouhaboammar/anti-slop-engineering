#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install and evaluate opt-in Claude Code project hooks."""
import argparse
import json
import os
import stat
import sys
import tempfile
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.exec_guard import (
    SessionStateManager,
    _load_hook_policy,
    evaluate_hook_event,
    read_hook_object,
    validate_hook_event,
)

PHASES = {"PreToolUse": "pre_tool", "PostToolUse": "post_tool"}
TOOLS = {"Read": "read", "Edit": "write", "Write": "write"}
MATCHER = "Read|Edit|Write"
HOOK_PATH = str(Path(__file__).resolve())
ERROR_MESSAGE = "invalid Claude hook event or local policy"


def normalize_event(payload, phase, project):
    if payload.get("hook_event_name") != phase:
        raise ValueError("Unexpected Claude hook phase")
    tool = payload.get("tool_name")
    if not isinstance(tool, str):
        raise ValueError("Expected Claude tool name")
    if tool not in TOOLS:
        return None
    tool_input = payload.get("tool_input")
    location = payload.get("cwd")
    target = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(location, str) or not isinstance(target, str) or not target:
        raise ValueError("Expected Claude project and file path")
    native_cwd = Path(location)
    if not native_cwd.is_absolute() or not native_cwd.resolve().is_relative_to(project):
        raise ValueError("Unexpected Claude working directory")
    if not Path(target).is_absolute():
        target = str(native_cwd / target)
    event = {
        "schema_version": 1, "agent": "claude-code",
        "phase": PHASES[phase], "tool": tool, "operation": TOOLS[tool],
        "target_paths": [target], "payload_trust": "untrusted", "correlation_id": payload.get("tool_use_id"),
    }
    validate_hook_event(event)
    return event


def translate_policy(result, phase):
    effect = result["decision"]
    message = result["message"]
    if effect == "allow":
        return {}
    if effect == "block" and phase == "PreToolUse":
        return {"hookSpecificOutput": {
            "hookEventName": phase, "permissionDecision": "deny", "permissionDecisionReason": message,
        }}
    if effect == "warn":
        return {"hookSpecificOutput": {"hookEventName": phase, "additionalContext": message}}
    raise ValueError("Hook policy returned an error")


def evaluate(project, phase):
    try:
        event = normalize_event(read_hook_object(sys.stdin.buffer), phase, project)
        result = {} if event is None else translate_policy(
            evaluate_hook_event(event, _load_hook_policy(SessionStateManager(project / ".anti-slop")), project),
            phase,
        )
    except (OSError, ValueError, RuntimeError):
        print(ERROR_MESSAGE, file=sys.stderr)
        return 1
    print(json.dumps(result))
    return 0


def managed_group(project, phase):
    runner = {
        "type": "command",
        "command": str(Path(sys.executable).absolute()),
        "args": [HOOK_PATH, "evaluate", "--project", str(project), "--phase", phase],
        "timeout": 5,
    }
    if phase == "PreToolUse":
        runner["onFailure"] = "block"
    return {"matcher": MATCHER, "hooks": [runner]}


def owns_hook_path(item):
    if not isinstance(item, dict):
        return False
    args = item.get("args")
    return isinstance(args, list) and args[:1] == [HOOK_PATH]


def edit_hooks(settings, project, install):
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Claude hooks settings must be an object")
    changed = False
    for phase in PHASES:
        groups = hooks.get(phase, [])
        if not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups):
            raise ValueError("Claude hook groups must be objects")
        expected = managed_group(project, phase)
        known = []
        for group in groups:
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                raise ValueError("Claude hook group requires a handler list")
            if any(owns_hook_path(item) for item in handlers):
                known.append(group)
        if known and known != [expected]:
            raise ValueError("Existing Anti-Slop Claude hook was modified. Restore or remove it in settings.")
        if install and not known:
            hooks[phase] = [*groups, expected]
            changed = True
        elif not install and known:
            remaining = [group for group in groups if group != expected]
            if remaining:
                hooks[phase] = remaining
            else:
                del hooks[phase]
            changed = True
    if hooks:
        settings["hooks"] = hooks
    elif "hooks" in settings and changed:
        del settings["hooks"]
    return changed


def read_settings(settings_path):
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(settings_path, flags)
    except FileNotFoundError:
        return None, {}
    with os.fdopen(fd, "rb") as stream:
        file_stat = os.fstat(stream.fileno())
        if not stat.S_ISREG(file_stat.st_mode):
            raise ValueError("Claude settings must be a regular local file")
        data = read_hook_object(stream)
    return file_stat, data


def settings_identity(file_stat):
    if file_stat is None:
        return None
    return (file_stat.st_dev, file_stat.st_ino, file_stat.st_mtime_ns, file_stat.st_size)


def write_settings(path, initial_stat, contents):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    if path.parent.is_symlink():
        raise ValueError("Claude settings directory must be local")
    descriptor, temp = tempfile.mkstemp(prefix=".anti-slop-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(contents, handle, indent=2)
            handle.write("\n")
        os.chmod(temp, 0o600 if initial_stat is None else stat.S_IMODE(initial_stat.st_mode))
        try:
            current_stat = path.lstat()
        except FileNotFoundError:
            current_stat = None
        if settings_identity(current_stat) != settings_identity(initial_stat):
            raise ValueError("Claude settings changed during update. Retry with a new dry run.")
        os.replace(temp, path)
    finally:
        Path(temp).unlink(missing_ok=True)


def configure(project, install, dry_run, consent):
    if not dry_run and not consent:
        raise ValueError("Use --dry-run to inspect changes or --yes to apply them.")
    path = project / ".claude" / "settings.local.json"
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("Claude settings must be local")
    initial_stat, settings = read_settings(path)
    changed = edit_hooks(settings, project, install)
    status = "unchanged"
    if changed and dry_run:
        status = "would_change"
    elif changed:
        write_settings(path, initial_stat, settings)
        status = "changed"
    print(json.dumps({"status": status, "settings": str(path), "tools": list(TOOLS)}))
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
        print(f"Claude hook configuration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
