#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""
Hook Engine Reference Implementation (Python Standard Library >= 3.9)

Implements:
- Safe argument passing without shell interpolation
- Bounded timeout management via subprocess.run
- Stdin payload piping & stdout JSON-RPC response parsing
- Fail-closed security gates with structured error handling
"""

import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class HookDefinition:
    def __init__(
        self,
        name: str,
        matcher: str,
        command: List[str],
        timeout_ms: int = 3000,
        on_failure: str = "deny",
    ):
        self.name = name
        self.matcher = re.compile(matcher)
        self.command = command
        self.timeout_sec = timeout_ms / 1000.0
        self.on_failure = on_failure.lower()


class HookEngine:
    def __init__(self, config_path: Optional[Path] = None):
        self.hooks: Dict[str, List[HookDefinition]] = {}
        if config_path and config_path.is_file():
            self.load_config(config_path)

    def load_config(self, config_path: Path) -> None:
        raw = json.loads(config_path.read_text(encoding="utf-8"))
        for event, hook_list in raw.get("hooks", {}).items():
            defs = []
            for item in hook_list:
                cmd_parts = item["command"] if isinstance(item["command"], list) else item["command"].split()
                defs.append(
                    HookDefinition(
                        name=item["name"],
                        matcher=item.get("matcher", ".*"),
                        command=cmd_parts,
                        timeout_ms=item.get("timeout_ms", 3000),
                        on_failure=item.get("on_failure", "deny"),
                    )
                )
            self.hooks[event] = defs

    def dispatch_pre_hook(self, event: str, payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Executes pre-hooks. Returns (True, None) if allowed, or (False, explanation) if denied.
        """
        tool_name = payload.get("tool_name", "")
        cwd = payload.get("cwd", ".")
        registered = self.hooks.get(event, [])

        for hook in registered:
            if not hook.matcher.search(tool_name):
                continue

            allowed, reason = self._execute_single_hook(hook, payload, cwd)
            if not allowed:
                return False, reason

        return True, None

    def _execute_single_hook(
        self, hook: HookDefinition, payload: Dict[str, Any], cwd: str
    ) -> Tuple[bool, Optional[str]]:
        input_bytes = (json.dumps(payload) + "\n").encode("utf-8")

        try:
            res = subprocess.run(
                hook.command,
                input=input_bytes,
                capture_output=True,
                cwd=cwd,
                timeout=hook.timeout_sec,
                check=False,
            )
        except subprocess.TimeoutExpired:
            sys.stderr.write(f"[Hook:{hook.name}] Timed out after {hook.timeout_sec}s\n")
            if hook.on_failure == "deny":
                return False, f"Hook {hook.name} timed out after {hook.timeout_sec}s."
            return True, None
        except Exception as e:
            sys.stderr.write(f"[Hook:{hook.name}] Execution failed: {e}\n")
            if hook.on_failure == "deny":
                return False, f"Hook {hook.name} failed to execute: {e}"
            return True, None

        if res.stderr:
            sys.stderr.write(f"[Hook:{hook.name}] {res.stderr.decode('utf-8', errors='ignore')}\n")

        if res.returncode != 0:
            if hook.on_failure == "deny":
                return False, f"Hook {hook.name} exited with non-zero status {res.returncode}."
            return True, None

        # Parse JSON response
        try:
            verdict = json.loads(res.stdout.decode("utf-8", errors="ignore").strip())
            if verdict.get("decision") == "deny":
                return False, verdict.get("explanation", f"Blocked by hook {hook.name}.")
        except Exception as e:
            sys.stderr.write(f"[Hook:{hook.name}] Non-JSON stdout or parse warning: {e}\n")

        return True, None


if __name__ == "__main__":
    print("HookEngine ready for integration into CLI and runtime tool suites.")
