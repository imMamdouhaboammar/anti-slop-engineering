#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Install and evaluate opt-in Claude Code project hooks."""
import argparse
import json
import os
import stat
import sys
import tempfile
import time
import warnings
from contextlib import ExitStack
from pathlib import Path

if not __package__:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.exec_guard import (
    SessionStateManager,
    _hook_targets,
    _load_hook_policy,
    evaluate_hook_event,
    read_hook_object,
    validate_hook_event,
)

from scripts.safe_install import SYSTEM_SYMLINKS, _open_instruction_parent_posix

PHASES = {"PreToolUse": "pre_tool", "PostToolUse": "post_tool"}
TOOLS = {"Read": "read", "Edit": "write", "Write": "write"}
MATCHER = "Read|Edit|Write"
HOOK_PATH = str(Path(__file__).resolve())
ERROR_MESSAGE = "invalid Claude hook event or local policy"
CHECKPOINT_BYTES = 64 * 1024
CHECKPOINT_ATTEMPT_BUDGET = 3
CHECKPOINT_LOCK_TIMEOUT = 0.25
CHECKPOINT_STATE_FILE = "checkpoint-state.json"
CHECKPOINT_AUDIT_FILE = "checkpoint-audit.jsonl"
CHECKPOINT_OVERRIDE_FILE = "checkpoint-override.json"
CHECKPOINT_OVERRIDE_HINT = ".anti-slop/checkpoint-override.json"


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


def read_local_source(project, source):
    system_root = Path(source.anchor, *source.parts[1:2])
    if system_root in SYSTEM_SYMLINKS:
        source = system_root.resolve() / source.relative_to(system_root)
    if ".." in source.parts or not source.is_relative_to(project):
        raise ValueError("Expected a regular local source file")
    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with ExitStack() as stack:
        parent = _open_instruction_parent_posix(stack, source, dir_flags)
        descriptor = os.open(source.name, file_flags, dir_fd=parent)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise ValueError("Expected a regular local source file")
            return stream.read(CHECKPOINT_BYTES + 1)


def python_checkpoint(project, target):
    """Check one local file without running it, changing it, or exposing its contents."""
    return _python_checkpoint_outcome(project, target)[1]


def _python_checkpoint_outcome(project, target):
    """Classify the checkpoint result as error, skip, ok, or not applicable."""
    source = Path(target)
    if source.suffix not in (".py", ".pyi"):
        return "na", None

    try:
        content = read_local_source(project, source)
    except (AttributeError, OSError, ValueError, RuntimeError):
        return "skip", "Python syntax check skipped: could not read a project-local regular file."
    if len(content) > CHECKPOINT_BYTES:
        return "skip", "Python syntax check skipped: source exceeds 64 KiB."

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            compile(content, "<post-write checkpoint>", "exec", dont_inherit=True)
    except SyntaxError as exc:
        return "error", f"Python syntax error at line {exc.lineno or 1}. Correct the file, then run its focused tests."
    except (ValueError, RecursionError, OverflowError):
        return "skip", "Python syntax check skipped: the local compiler could not process this file."
    return "ok", None


def _checkpoint_state_dir(project):
    return project / ".anti-slop"


def _canonical_checkpoint_target(project, target):
    if not isinstance(target, str) or not target:
        return None
    try:
        return _hook_targets({"target_paths": [target]}, project)[0]
    except (OSError, ValueError, RuntimeError):
        return None


def _read_checkpoint_record(path):
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    with os.fdopen(os.open(path, flags), "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise OSError("Checkpoint records must be regular files")
        return read_hook_object(stream)


def _load_checkpoint_state(state_dir):
    if state_dir.is_symlink():
        raise OSError("Checkpoint state must be local")
    try:
        return _read_checkpoint_record(state_dir / CHECKPOINT_STATE_FILE)
    except (FileNotFoundError, ValueError):
        return {}


def _save_checkpoint_state(state_dir, state):
    state_dir.mkdir(parents=True, exist_ok=True)
    if state_dir.is_symlink():
        raise ValueError("Checkpoint state directory must be local")
    descriptor, temp = tempfile.mkstemp(prefix="checkpoint-state-", dir=state_dir)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(state, stream, indent=2)
        os.replace(temp, state_dir / CHECKPOINT_STATE_FILE)
    finally:
        Path(temp).unlink(missing_ok=True)


def _audit_checkpoint(state_dir, event, session_id, target, **fields):
    path = state_dir / CHECKPOINT_AUDIT_FILE
    if state_dir.is_symlink() or path.is_symlink():
        raise ValueError("Checkpoint audit log must be local")
    entry = {"event": event, "session_id": session_id, "target": target, "at": time.time()}
    entry.update(fields)
    flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK
    fd = os.open(path, flags, 0o600)
    with os.fdopen(fd, "a", encoding="utf-8") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Checkpoint audit log must be a regular file")
        stream.write(json.dumps(entry) + "\n")


def _checkpoint_failures(state, key):
    entry = state.get(key)
    count = entry.get("failures") if isinstance(entry, dict) else None
    return count if type(count) is int and 0 <= count <= CHECKPOINT_ATTEMPT_BUDGET else 0


def _record_checkpoint_outcome(project, session_id, target, kind):
    """Track consecutive post-write syntax failures per session and target.

    Returns True when this failure exhausts the attempt budget. Tracking is
    best-effort: any state problem degrades to the stateless checkpoint.
    """
    if kind not in ("error", "ok"):
        return False
    canonical = _canonical_checkpoint_target(project, target)
    if not canonical:
        return False
    state_dir = _checkpoint_state_dir(project)
    key = f"{session_id}\n{canonical}"
    try:
        manager = SessionStateManager(state_dir)
        with manager.exclusive_lock(timeout_seconds=CHECKPOINT_LOCK_TIMEOUT):
            state = _load_checkpoint_state(state_dir)
            if kind == "ok":
                if key in state:
                    del state[key]
                    _save_checkpoint_state(state_dir, state)
                    _audit_checkpoint(state_dir, "cleared", session_id, canonical)
                return False
            failures = min(_checkpoint_failures(state, key) + 1, CHECKPOINT_ATTEMPT_BUDGET)
            state[key] = {"failures": failures}
            _save_checkpoint_state(state_dir, state)
            _audit_checkpoint(state_dir, "failure", session_id, canonical, failures=failures)
            if failures >= CHECKPOINT_ATTEMPT_BUDGET:
                _audit_checkpoint(state_dir, "exhausted", session_id, canonical, failures=failures)
                return True
            return False
    except (AttributeError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return False


def _checkpoint_denial(project, session_id, target):
    """Return a pre-write denial message when the attempt budget is spent.

    A matching operator override in the state directory is consumed once,
    audited, and clears the budget. Any state problem degrades to no denial.
    """
    canonical = _canonical_checkpoint_target(project, target)
    if not canonical:
        return None
    state_dir = _checkpoint_state_dir(project)
    key = f"{session_id}\n{canonical}"
    try:
        manager = SessionStateManager(state_dir)
        with manager.exclusive_lock(timeout_seconds=CHECKPOINT_LOCK_TIMEOUT):
            state = _load_checkpoint_state(state_dir)
            failures = _checkpoint_failures(state, key)
            if failures < CHECKPOINT_ATTEMPT_BUDGET:
                return None
            override_path = state_dir / CHECKPOINT_OVERRIDE_FILE
            override = None
            if override_path.is_file() and not override_path.is_symlink():
                try:
                    override = _read_checkpoint_record(override_path)
                except ValueError:
                    override = None
            override_target = (
                _canonical_checkpoint_target(project, override.get("target"))
                if isinstance(override, dict) else None
            )
            reason = override.get("reason") if isinstance(override, dict) else None
            if (
                isinstance(reason, str) and reason.strip()
                and override.get("session_id") == session_id
                and override_target == canonical
            ):
                override_path.unlink()
                del state[key]
                _save_checkpoint_state(state_dir, state)
                _audit_checkpoint(state_dir, "override_applied", session_id, canonical,
                                  reason=reason.strip())
                return None
            _audit_checkpoint(state_dir, "pre_write_denied", session_id, canonical,
                              failures=failures)
            return (
                "Checkpoint attempt budget exhausted for this file in this session after "
                f"{failures} failed post-write syntax checks. This write has not happened. "
                "Correct the file outside the agent, or record an audited override in "
                f"{CHECKPOINT_OVERRIDE_HINT}, before retrying."
            )
    except (AttributeError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return None


def evaluate_native_event(project, event, phase, session_id=None):
    state = _load_hook_policy(SessionStateManager(project / ".anti-slop"))
    policy = evaluate_hook_event(event, state, project)
    if event["operation"] != "write" or policy["reason_code"] != "WITHIN_CONTRACT":
        return translate_policy(policy, phase)
    target = event["target_paths"][0]
    track_attempts = bool(session_id) and state["contract"]["level"] == "guard"
    if phase == "PreToolUse" and track_attempts:
        denial = _checkpoint_denial(project, session_id, target)
        if denial:
            return translate_policy({"decision": "block", "message": denial}, phase)
    elif phase == "PostToolUse":
        kind, message = _python_checkpoint_outcome(project, target)
        exhausted = track_attempts and _record_checkpoint_outcome(
            project, session_id, target, kind)
        if message and exhausted:
            message += (
                f" Checkpoint attempt budget exhausted ({CHECKPOINT_ATTEMPT_BUDGET} failed "
                "checks). Further writes to this file in this session will be denied until a "
                "corrected write is recorded or an audited override is filed at "
                f"{CHECKPOINT_OVERRIDE_HINT}."
            )
        if message:
            return translate_policy({"decision": "warn", "message": message}, phase)
    return translate_policy(policy, phase)


def evaluate(project, phase):
    try:
        payload = read_hook_object(sys.stdin.buffer)
        event = normalize_event(payload, phase, project)
        session_id = payload.get("session_id") if isinstance(payload, dict) else None
        if not isinstance(session_id, str) or not session_id or len(session_id) > 128:
            session_id = None
        result = {} if event is None else evaluate_native_event(project, event, phase, session_id)
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


def edit_hooks(settings, groups_by_phase, own_handler, install):
    hooks = settings.get("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError("Hook settings must be an object")
    changed = False
    for phase, expected in groups_by_phase.items():
        groups = hooks.get(phase, [])
        if not isinstance(groups, list) or any(not isinstance(group, dict) for group in groups):
            raise ValueError("Hook groups must be objects")
        known = []
        for group in groups:
            handlers = group.get("hooks")
            if not isinstance(handlers, list):
                raise ValueError("Hook group requires a handler list")
            if any(own_handler(item) for item in handlers):
                known.append(group)
        if known and known != [expected]:
            raise ValueError("Existing Anti-Slop hook was modified. Restore or remove it in settings.")
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


def configure_hooks(path, groups, own_handler, install, dry_run, consent):
    if not dry_run and not consent:
        raise ValueError("Use --dry-run to inspect changes or --yes to apply them.")
    if path.parent.is_symlink() or path.is_symlink():
        raise ValueError("Claude settings must be local")
    initial_stat, settings = read_settings(path)
    changed = edit_hooks(settings, groups, own_handler, install)
    status = "unchanged"
    if changed and dry_run:
        status = "would_change"
    elif changed:
        write_settings(path, initial_stat, settings)
        status = "changed"
    return {"status": status, "settings": str(path)}


def configure(project, install, dry_run, consent):
    def owns_handler(item):
        args = item.get("args") if isinstance(item, dict) else None
        return isinstance(args, list) and args[:1] == [HOOK_PATH]

    groups = {phase: managed_group(project, phase) for phase in PHASES}
    result = configure_hooks(
        project / ".claude" / "settings.local.json", groups, owns_handler, install, dry_run, consent,
    )
    result["tools"] = list(TOOLS)
    print(json.dumps(result))
    return 0


def run_hook_cli(description, evaluate, configure):
    parser = argparse.ArgumentParser(description=description)
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
        print(f"Hook configuration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(run_hook_cli(__doc__, evaluate, configure))
