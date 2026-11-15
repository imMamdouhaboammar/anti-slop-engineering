# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Optional diff scan hooks supplied explicitly by the caller."""
import json
import os
import pathlib
import subprocess
import sys

HOOK_EVENTS = ("pre_scan", "post_scan")
HOOK_TIMEOUT = 5


def load_hooks(directory, root):
    directory = pathlib.Path(directory)
    if not directory.is_absolute():
        raise ValueError("--hooks-dir requires an absolute path.")

    try:
        resolved = directory.resolve(strict=True)
    except FileNotFoundError as exc:
        raise ValueError("--hooks-dir must point to an existing directory.") from exc
    except OSError as exc:
        raise ValueError(f"Could not resolve --hooks-dir: {exc.strerror}") from exc
    root = pathlib.Path(root).resolve()
    if directory.is_relative_to(root) or resolved.is_relative_to(root) or directory != resolved:
        raise ValueError("--hooks-dir must be a canonical path outside the scanned repository.")
    if not directory.is_dir():
        raise ValueError("--hooks-dir must point to an existing directory.")

    hooks = {}
    for event_type in HOOK_EVENTS:
        source = directory / f"{event_type}.py"
        if source.is_symlink() or (source.exists() and not source.is_file()):
            raise ValueError(f"{source.name} must be a regular file in --hooks-dir.")
        if source.is_file():
            hooks[event_type] = source
    if not hooks:
        raise ValueError("--hooks-dir contains neither pre_scan.py nor post_scan.py.")
    return hooks


def run_hook(source, event_type, root, base, payload):
    if source is None:
        return

    event = {"event_type": event_type, "repo": root, "base": base, "payload": payload}
    env = {name: os.environ[name] for name in ("SystemRoot",) if name in os.environ}
    try:
        process = subprocess.run(
            [sys.executable, "-I", "-B", str(source)],
            cwd=source.parent,
            env=env,
            input=json.dumps(event),
            text=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=HOOK_TIMEOUT,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{source.name} timed out after {HOOK_TIMEOUT} seconds.") from exc
    except OSError as exc:
        raise RuntimeError(f"Could not start {source.name}: {exc.strerror}") from exc
    if process.returncode:
        raise RuntimeError(f"{source.name} exited with code {process.returncode}.")
