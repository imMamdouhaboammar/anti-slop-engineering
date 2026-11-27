#!/usr/bin/env python3
"""
Anti-Slop In-Flight Execution Guard (exec_guard.py).
Intercepts and evaluates agent tool actions, shell commands, file modifications,
and subagent delegations against an explicit task contract in real time.

Complies with standard library Python (>=3.9) without external dependencies.
Adheres to KISS (nesting <= 4, functions <= 80 lines), DRY, YAGNI, and SRE scale invariants.
"""

import argparse
import fnmatch
import hashlib
import json
import os
import random
import re
import shlex
import stat
import string
import sys
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

DEFAULT_AGENT_LIMIT = 9007199254740991
DEFAULT_TICKET_TTL = 600

VALID_MODES = {"change", "review", "answer", "monitor", "unconfirmed"}
VALID_LEVELS = {"guard", "watch", "off"}
VALID_HASH_POLICIES = {"deny", "ask", "allow"}
VALID_DEP_POLICIES = {"deny", "ask", "allow"}

REASON_CODES = {
    "CONTROL_INACTIVE": "No confirmed enforcing contract is active.",
    "WITHIN_CONTRACT": "The action is within the active task contract.",
    "MODE_FORBIDS_MUTATION": "The active task mode does not authorize repository mutations.",
    "MUTABILITY_UNPROVEN": "The proposed action is not proven read-only under a non-mutating mode.",
    "PATH_OUTSIDE_CONTRACT": "The action targets files outside the declared file boundary.",
    "WRITE_PATH_UNPROVEN": "The target path cannot be proven inside the declared file boundary.",
    "HASH_NOT_AUTHORIZED": "The action introduces unapproved cryptographic hashing or checksums.",
    "DEPENDENCY_NOT_AUTHORIZED": "The action introduces dependencies without authorization.",
    "AGENT_BUDGET_EXHAUSTED": "The concurrent subagent delegation budget has been exhausted.",
    "RECOVERY_READ_ONLY": "Operating in read-only recovery mode due to state protection.",
    "ENV_INSPECTION_REQUIRES_APPROVAL": "The action reads environment variables or an environment file.",
    "SHELL_COMMAND_REQUIRES_APPROVAL": "The shell syntax does not identify a single environment operation.",
    "LOCK_DAMAGED": "The session lock is damaged and requires administrative remediation.",
}


def make_default_contract():
    """Construct a default unconfirmed task contract."""
    return {
        "mode": "unconfirmed",
        "level": "watch",
        "agent_budget": DEFAULT_AGENT_LIMIT,
        "hash_policy": "deny",
        "dependency_policy": "ask",
        "allowed_paths": None,
        "task": "",
    }


def parse_directive(text):
    """
    Parse a task directive string into a structured contract.
    Format: $anti-slop [mode] [level] [files=...] [hash=...] [deps=...] [agents=N] -- [task]
    """
    if not text or not text.strip():
        return make_default_contract(), None

    stripped = text.strip()
    if not stripped.startswith("$anti-slop") and not stripped.startswith("/anti-slop"):
        return make_default_contract(), None

    head, task = _split_directive_head_task(stripped)
    tokens = head.split()
    contract = make_default_contract()
    contract["task"] = task.strip()

    mode_set = False
    level_set = False
    for token in tokens[1:]:
        if "=" in token:
            key, val = token.split("=", 1)
            err = _apply_contract_option(contract, key.strip(), val.strip())
            if err:
                return contract, err
        elif token in VALID_MODES:
            contract["mode"] = token
            mode_set = True
        elif token in VALID_LEVELS:
            contract["level"] = token
            level_set = True
        elif not mode_set:
            return contract, f"INVALID_MODE: Unknown mode '{token}'. Must be one of {sorted(VALID_MODES)}"
        elif not level_set:
            return contract, f"INVALID_LEVEL: Unknown level '{token}'. Must be one of {sorted(VALID_LEVELS)}"
        else:
            return contract, f"INVALID_DIRECTIVE_TOKEN: Unrecognized token '{token}'"

    return contract, None


def _split_directive_head_task(stripped):
    """Split head directive from trailing task specification."""
    if " -- " in stripped:
        return stripped.split(" -- ", 1)
    if ": " in stripped:
        return stripped.split(": ", 1)
    parts = stripped.split("\n", 1)
    return parts[0], parts[1] if len(parts) > 1 else ""


def _apply_contract_option(contract, key, val):
    """Apply a key-value option to the contract dictionary."""
    if key == "files":
        contract["allowed_paths"] = [p.strip() for p in val.split("|") if p.strip()]
        return None
    if key == "hash":
        if val not in VALID_HASH_POLICIES:
            return f"INVALID_HASH_POLICY: Value must be one of {sorted(VALID_HASH_POLICIES)}"
        contract["hash_policy"] = val
        return None
    if key == "deps":
        if val not in VALID_DEP_POLICIES:
            return f"INVALID_DEP_POLICY: Value must be one of {sorted(VALID_DEP_POLICIES)}"
        contract["dependency_policy"] = val
        return None
    if key == "agents":
        return _parse_agent_budget(contract, val)
    return f"INVALID_DIRECTIVE_OPTION: Unknown option key '{key}'"


def _parse_agent_budget(contract, val):
    """Parse and validate non-negative integer agent budget."""
    try:
        budget = int(val)
        if budget < 0:
            return "INVALID_AGENT_BUDGET: Agent budget must be a non-negative integer"
        contract["agent_budget"] = budget
        return None
    except ValueError:
        return "INVALID_AGENT_BUDGET: Agent budget must be an integer"


def analyze_shell_command(cmd_str):
    """Statically inspect shell commands for contract-relevant actions."""
    raw = (cmd_str or "").strip()
    analysis = {
        "mutability": "read", "dependency_intent": False, "hash_intent": False,
        "shell_approval_reason": None, "reason": "empty",
    }
    if not raw:
        return analysis
    try:
        tokens = shlex.split(raw)
    except ValueError:
        analysis.update(mutability="unknown", reason="unparseable_syntax")
        if raw.split(maxsplit=1)[0].rsplit("/", 1)[-1] == "env":
            analysis["shell_approval_reason"] = "SHELL_COMMAND_REQUIRES_APPROVAL"
        return analysis

    analysis["reason"] = "analyzed_tokens"
    if ">" in raw:
        analysis.update(mutability="write", reason="redirection")
    elif tokens and tokens[0].rsplit("/", 1)[-1] != "env":
        _apply_existing_shell_rules(analysis, tokens)

    # Look for environment actions at literal command heads; the general shell
    # decision above continues to use its existing argument and redirection rules.
    for segment in _shell_commands(raw):
        wrapped_command, approval_reason = _environment_command(segment)
        if approval_reason:
            analysis["shell_approval_reason"] = analysis["shell_approval_reason"] or approval_reason
        if wrapped_command:
            _apply_existing_shell_rules(analysis, wrapped_command)
    return analysis


def _apply_existing_shell_rules(analysis, tokens):
    dependency_intent = _detect_package_manager_intent(tokens)
    analysis["dependency_intent"] |= dependency_intent
    analysis["hash_intent"] |= _detect_hashing_intent(tokens)
    if dependency_intent or _detect_mutating_command(tokens):
        analysis["mutability"] = "write"


def _shell_commands(raw):
    # Consume literal quoting and escapes before recognizing separators.
    segments = []
    start = 0
    for symbol in re.finditer(r"""\\.|'[^']*'|"(?:\\.|[^"\\])*"|[;&|\n]+""", raw):
        if symbol[0][0] not in ";&|\n":
            continue
        segments.append(raw[start:symbol.start()])
        start = symbol.end()
    segments.append(raw[start:])
    return [tokens for segment in segments if (tokens := shlex.split(segment))]


def _environment_command(tokens):
    """Resolve literal env overrides and recognize direct inspection commands."""
    wrapped = False
    command = tokens[0].rsplit("/", 1)[-1]
    if command == "env":
        index = 2 if tokens[1:2] == ["--"] else 1
        while index < len(tokens) and re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*=", tokens[index]):
            index += 1
        if index == len(tokens):
            return [], "ENV_INSPECTION_REQUIRES_APPROVAL"
        tokens = tokens[index:]
        command = tokens[0].rsplit("/", 1)[-1]
        if command == "env" or command.startswith("-"):
            return [], "SHELL_COMMAND_REQUIRES_APPROVAL"
        wrapped = True
    if _inspects_environment(command, tokens[1:]):
        return [], "ENV_INSPECTION_REQUIRES_APPROVAL"
    return ([command, *tokens[1:]] if wrapped else []), None


def _inspects_environment(command, args):
    if command == "printenv" or (command in {"export", "set"} and args in ([], ["-p"])):
        return True
    if command not in {"cat", "head", "tail", "more", "less", "grep", "source", "."}:
        return False
    names = (arg.rsplit("/", 1)[-1] for arg in args)
    return any(name == ".env" or name.startswith(".env.") for name in names)


def _detect_package_manager_intent(tokens):
    """Check if tokens execute a package installation command."""
    joined = " ".join(tokens)
    patterns = [
        r"\b(?:npm|pnpm|yarn|bun)\s+(?:install|i|add)\b",
        r"\b(?:pip|pip3)\s+install\b",
        r"\bpython[0-9.]*\s+-m\s+pip\s+install\b",
        r"\bcargo\s+(?:add|install)\b",
        r"\buv\s+(?:add|pip\s+install)\b",
        r"\bgo\s+(?:get|install)\b",
        r"\b(?:brew|apt|apt-get|pacman)\s+install\b",
    ]
    return any(re.search(pat, joined) for pat in patterns)


def _detect_hashing_intent(tokens):
    """Check if tokens invoke checksum or cryptographic hash generators."""
    hash_bins = {"sha256sum", "shasum", "md5sum", "b2sum", "sha1sum", "sha512sum"}
    if tokens[0] in hash_bins:
        return True
    joined = " ".join(tokens)
    return bool(re.search(r"\bopenssl\s+dgst\b", joined))


def _detect_mutating_command(tokens):
    """Check if tokens represent filesystem or git mutation commands."""
    cmd = tokens[0]
    mutating_bins = {
        "rm", "mv", "cp", "mkdir", "touch", "chmod", "chown",
        "sed", "awk", "truncate", "dd", "tar", "unzip",
    }
    if cmd in mutating_bins:
        if cmd == "sed" and "-i" not in tokens and "--in-place" not in tokens:
            return False
        return True

    if cmd == "git" and len(tokens) > 1:
        mutating_git = {
            "commit", "merge", "rebase", "checkout", "switch",
            "push", "pull", "reset", "clean", "apply", "revert", "tag"
        }
        return tokens[1] in mutating_git

    return False


def classify_tool_action(tool_name, tool_args):
    """Normalize agent tool call arguments into a standard action descriptor."""
    name = str(tool_name).lower()
    args = tool_args if isinstance(tool_args, dict) else {}

    if name in {"write_file", "edit_file", "delete_file", "patch", "apply_patch"}:
        path = args.get("Path") or args.get("path") or args.get("target") or ""
        return _make_action(name, "write", [str(path)] if path else [])

    if name in {"read_file", "search_files", "list_dir", "web_search", "search_web"}:
        path = args.get("Path") or args.get("path") or ""
        return _make_action(name, "read", [str(path)] if path else [])

    if name in {"invoke_subagent", "delegate_task", "agent"}:
        count = args.get("count", 1)
        action = _make_action(name, "delegate", [])
        action["delegation_count"] = count if isinstance(count, int) else 1
        return action

    if name in {"run_command", "terminal", "bash", "execute_command"}:
        cmd = args.get("CommandLine") or args.get("command") or args.get("cmd") or ""
        shell_res = analyze_shell_command(cmd)
        action = _make_action(name, shell_res["mutability"], [])
        action["command"] = cmd
        action["hash_intent"] = shell_res["hash_intent"]
        action["dependency_intent"] = shell_res["dependency_intent"]
        if shell_res["shell_approval_reason"]:
            action["shell_approval_reason"] = shell_res["shell_approval_reason"]
        return action

    return _make_action(name, "unknown", [])


def _make_action(tool_name, mutability, affected_paths):
    """Construct standard action dictionary."""
    return {
        "tool": tool_name,
        "mutability": mutability,
        "affected_paths": affected_paths,
        "hash_intent": False,
        "dependency_intent": False,
    }


def normalize_path(path_str, cwd=None, depth=0, max_depth=100):
    """Normalize file paths for consistent cross-platform boundary checks."""
    if depth > max_depth or not path_str:
        return ""
    cleaned = str(path_str).replace("\\", "/").strip()
    p = Path(cleaned)
    if p.is_absolute() and cwd:
        try:
            rel = p.relative_to(Path(cwd))
            return str(rel).replace("\\", "/")
        except ValueError:
            return cleaned
    return cleaned[2:] if cleaned.startswith("./") else cleaned


def path_allowed(target_path, allowed_patterns, cwd=None, depth=0, max_depth=100):
    """Verify if a normalized target path matches any allowed glob patterns (fail-closed)."""
    if depth > max_depth:
        return False
    if allowed_patterns is None:
        return True
    if not allowed_patterns:
        return False
    norm_target = normalize_path(target_path, cwd, depth=depth + 1, max_depth=max_depth)
    if not norm_target:
        return False
    for pat in allowed_patterns:
        norm_pat = normalize_path(pat, cwd, depth=depth + 1, max_depth=max_depth)
        if norm_pat == "**":
            return True
        if norm_pat.endswith("/**"):
            base = norm_pat[:-3]
            if norm_target == base or norm_target.startswith(base + "/"):
                return True
        if fnmatch.fnmatch(norm_target, norm_pat):
            return True
    return False


def controlled_outcome(level, enforced="deny_and_explain"):
    """Compute decision outcome based on contract enforcement level."""
    if level == "watch":
        return "report_and_defer"
    return enforced


def decide(contract, action, state=None, depth=0, max_depth=100):
    """
    Host-independent decision engine. Evaluates (contract, action, state) -> Decision.
    """
    if depth > max_depth:
        return _make_decision("deny_and_explain", "S", "MAX_DEPTH_EXCEEDED", "Evaluation depth exceeded", None)

    mode = contract.get("mode", "unconfirmed")
    level = contract.get("level", "watch")
    state = state or {}

    if level == "off" or mode == "unconfirmed":
        return _make_decision("allow", None, "CONTROL_INACTIVE", REASON_CODES["CONTROL_INACTIVE"], None)

    storage_decision = _check_storage_error(state, action)
    if storage_decision:
        return storage_decision

    ro_decision = _check_read_only_mode(mode, level, action)
    if ro_decision:
        return ro_decision

    reachability_decision = _check_reachability(action)
    if reachability_decision:
        return reachability_decision

    hash_decision = _check_hash_policy(contract, level, action)
    if hash_decision:
        return hash_decision

    path_decision = _check_path_boundary(contract, level, action)
    if path_decision:
        return path_decision

    dep_decision = _check_dependency_policy(contract, level, action)
    if dep_decision:
        return dep_decision

    approval_reason = action.get("shell_approval_reason")
    if approval_reason:
        return _make_decision(
            controlled_outcome(level, "require_user_approval"), "S",
            approval_reason, REASON_CODES[approval_reason],
            "Use an explicit command or request approval for this action.",
        )

    delegation_decision = _check_delegation_budget(contract, level, action, state)
    if delegation_decision:
        return delegation_decision

    return _make_decision("allow", None, "WITHIN_CONTRACT", REASON_CODES["WITHIN_CONTRACT"], None)


def _check_storage_error(state, action):
    """Check if state storage is in damaged/recovery condition."""
    err = state.get("storage_error")
    if not err:
        return None
    if action.get("mutability") == "read":
        return _make_decision("allow", None, "RECOVERY_READ_ONLY", REASON_CODES["RECOVERY_READ_ONLY"], None)
    is_lock = err.get("code") == "LOCK_DAMAGED"
    return _make_decision(
        "deny_and_explain", "I",
        "LOCK_DAMAGED" if is_lock else "STATE_DAMAGED",
        err.get("message", "Damaged session state"),
        "Isolate damaged lock or restore valid state before continuing."
    )


def _check_read_only_mode(mode, level, action):
    """Enforce read-only constraint for review, answer, and monitor modes."""
    if mode not in {"review", "answer", "monitor"}:
        return None
    mut = action.get("mutability")
    if mut == "write":
        return _make_decision(
            controlled_outcome(level), "I", "MODE_FORBIDS_MUTATION",
            f"Task mode '{mode}' does not authorize repository mutations.",
            "Report findings, use read-only actions, or request an explicit change contract."
        )
    if mut == "unknown":
        return _make_decision(
            controlled_outcome(level, "require_user_approval"), "I", "MUTABILITY_UNPROVEN",
            f"The proposed action is not proven read-only under '{mode}' mode.",
            "Use an explicitly read-only command or request an explicit change contract."
        )
    return None


def _check_reachability(action):
    """Check if action proposes hypothetical hardening for unreachable states."""
    if action.get("reachability") == "unreachable":
        return _make_decision(
            "report_and_defer", "H", "HYPOTHETICAL_UNREACHABLE",
            "The proposed hardening has no supported reachable input or deployed state.",
            "Defer it unless project evidence establishes reachability."
        )
    return None


def _evaluate_policy_outcome(policy, level, depth=0, max_depth=100):
    """Evaluate whether a policy allows, or requires approval vs denial (depth bounded)."""
    if depth > max_depth:
        return "deny_and_explain"
    if policy == "allow":
        return None
    req_approval = policy == "ask"
    return controlled_outcome(level, "require_user_approval" if req_approval else "deny_and_explain")


def _enforce_named_policy(policy, level, family, reason_code, message, remediation, depth=0, max_depth=100):
    """Enforce a policy returning a decision if denied/approval required, else None."""
    if depth > max_depth:
        return _make_decision("deny_and_explain", family, "MAX_DEPTH_EXCEEDED", "Depth exceeded", None)
    outcome = _evaluate_policy_outcome(policy, level, depth=depth + 1, max_depth=max_depth)
    if not outcome:
        return None
    return _make_decision(outcome, family, reason_code, message, remediation)


def _check_hash_policy(contract, level, action):
    """Enforce hashing and checksum generation policy."""
    if not action.get("hash_intent"):
        return None
    policy = contract.get("hash_policy", "deny")
    return _enforce_named_policy(
        policy, level, "H", "HASH_NOT_AUTHORIZED",
        f"Action introduces hashing while hash policy is '{policy}'.",
        "Use direct alternatives or obtain hash=allow authority."
    )


def _check_path_boundary(contract, level, action):
    """Enforce declared path boundary constraints on file writes."""
    allowed = contract.get("allowed_paths")
    if allowed is None:
        return None
    affected = action.get("affected_paths", [])
    if action.get("mutability") in {"write", "unknown"} and not affected and "**" not in allowed:
        return _make_decision(
            controlled_outcome(level, "require_user_approval"), "S", "WRITE_PATH_UNPROVEN",
            "Action may write through a tool whose target path is unproven inside file boundary.",
            "Specify target paths explicitly or expand contract file boundary."
        )
    outside = [p for p in affected if not path_allowed(p, allowed, action.get("cwd"))]
    if outside:
        return _make_decision(
            controlled_outcome(level), "S", "PATH_OUTSIDE_CONTRACT",
            f"Action writes outside declared file boundary: {', '.join(outside)}.",
            "Restrict writes to declared paths or obtain an expanded boundary."
        )
    return None


def _check_dependency_policy(contract, level, action):
    """Enforce dependency installation authorization."""
    if not action.get("dependency_intent"):
        return None
    policy = contract.get("dependency_policy", "ask")
    return _enforce_named_policy(
        policy, level, "S", "DEPENDENCY_NOT_AUTHORIZED",
        f"Action introduces dependencies while dependency policy is '{policy}'.",
        "Use existing stack dependencies or obtain approval for new packages."
    )


def _check_delegation_budget(contract, level, action, state):
    """Enforce active subagent concurrency limit."""
    if action.get("mutability") != "delegate":
        return None
    budget = contract.get("agent_budget", DEFAULT_AGENT_LIMIT)
    active = state.get("active_agents", 0)
    requested = action.get("delegation_count", 1)
    if active + requested > budget:
        return _make_decision(
            controlled_outcome(level), "S", "AGENT_BUDGET_EXHAUSTED",
            f"Session allows {budget} concurrent subagents ({active} active), requested {requested}.",
            "Wait for active delegations to complete or increase agents=N budget."
        )
    return None


def _make_decision(outcome, family, reason_code, explanation, next_step):
    """Construct a decision response payload."""
    return {
        "outcome": outcome,
        "family": family,
        "reason_code": reason_code,
        "explanation": explanation,
        "next_step": next_step,
    }


def _match_event_in_line(line, event_id):
    """Extract and parse event if line matches event_id."""
    stripped = line.strip()
    if not stripped or event_id not in stripped:
        return None
    try:
        record = json.loads(stripped)
        return record if record.get("event_id") == event_id else None
    except json.JSONDecodeError as err:
        sys.stderr.write(f"[WARN] Failed to parse event JSONL: {err}\n")
        return None


class SessionStateManager:
    """Manages persistent session contracts, atomic locks, tickets, and audit trails."""

    def __init__(self, state_dir=None):
        self.state_dir = Path(state_dir) if state_dir else Path(".anti-slop")
        self.lock_dir = self.state_dir / ".lock"
        self.state_file = self.state_dir / "state.json"
        self.events_file = self.state_dir / "events.jsonl"
        self.tickets_dir = self.state_dir / "tickets"

    def _ensure_dirs(self, depth=0, max_depth=10):
        """Ensure state and ticket directories exist with bounded depth."""
        if depth > max_depth:
            raise RecursionError("Max directory creation depth exceeded")
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.tickets_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def exclusive_lock(self, timeout_seconds=5.0):
        """Acquire directory lock with exponential backoff and stale lock reclamation."""
        self._ensure_dirs()
        deadline = time.time() + timeout_seconds
        backoff = 0.01

        acquired = False
        while time.time() < deadline:
            acquired = self._try_create_lock()
            if acquired:
                break
            if self._reclaim_stale_lock():
                continue
            jitter = random.uniform(0.5, 1.5)
            time.sleep(backoff * jitter)
            backoff = min(backoff * 1.5, 0.25)

        if not acquired:
            raise TimeoutError(f"Could not acquire lock {self.lock_dir} within {timeout_seconds}s")

        try:
            yield
        finally:
            self._release_lock()

    def _try_create_lock(self):
        """Attempt atomic creation of the lock directory and owner metadata."""
        try:
            os.mkdir(str(self.lock_dir))
            owner_file = self.lock_dir / "owner.json"
            owner_data = {"pid": os.getpid(), "created_at": time.time()}
            owner_file.write_text(json.dumps(owner_data))
            return True
        except FileExistsError:
            return False

    def _reclaim_stale_lock(self):
        """Check if lock holder is dead. Reclaim if dead, return True if reclaimed."""
        owner_file = self.lock_dir / "owner.json"
        if not owner_file.exists():
            return False
        try:
            data = json.loads(owner_file.read_text())
            pid = data.get("pid")
            if not pid:
                return False
            os.kill(pid, 0)
            return False
        except (OSError, ProcessLookupError):
            self._release_lock()
            return True
        except Exception as ex:
            sys.stderr.write(f"[WARN] Error inspecting lock owner: {ex}\n")
            return False

    def _release_lock(self):
        """Remove lock directory and owner file."""
        owner_file = self.lock_dir / "owner.json"
        try:
            if owner_file.exists():
                owner_file.unlink()
            if self.lock_dir.exists():
                os.rmdir(str(self.lock_dir))
        except OSError as ex:
            sys.stderr.write(f"[WARN] Lock directory removal error: {ex}\n")

    def load_state(self):
        """Load session state from disk with safe fallback."""
        if not self.state_file.exists():
            return {"contract": make_default_contract(), "active_agents": 0}
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except Exception as ex:
            return {
                "contract": make_default_contract(),
                "active_agents": 0,
                "storage_error": {"code": "STATE_DAMAGED", "message": str(ex)},
            }

    def save_state(self, state):
        """Atomically persist state via temporary file."""
        self._ensure_dirs()
        tmp_file = self.state_dir / f"state_{uuid.uuid4().hex[:8]}.tmp"
        tmp_file.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp_file.replace(self.state_file)

    def grant_approval_ticket(self, command, ttl_seconds=DEFAULT_TICKET_TTL):
        """Generate a one-time approval ticket for an intercepted action."""
        self._ensure_dirs()
        ticket_id = f"tkt_{uuid.uuid4().hex[:12]}"
        cmd_hash = hashlib.sha256(command.strip().encode("utf-8")).hexdigest()
        ticket_data = {
            "ticket_id": ticket_id,
            "cmd_hash": cmd_hash,
            "command": command.strip(),
            "expires_at": time.time() + ttl_seconds,
            "consumed": False,
        }
        ticket_path = self.tickets_dir / f"{ticket_id}.json"
        ticket_path.write_text(json.dumps(ticket_data), encoding="utf-8")
        return ticket_id

    def consume_approval_ticket(self, command, ticket_id):
        """Verify and atomically consume a single-use approval ticket."""
        ticket_path = self.tickets_dir / f"{ticket_id}.json"
        if not ticket_path.exists():
            return False
        try:
            data = json.loads(ticket_path.read_text(encoding="utf-8"))
            if data.get("consumed"):
                return False
            if time.time() > data.get("expires_at", 0):
                ticket_path.unlink()
                return False
            cmd_hash = hashlib.sha256(command.strip().encode("utf-8")).hexdigest()
            if data.get("cmd_hash") != cmd_hash:
                return False
            data["consumed"] = True
            ticket_path.unlink()
            return True
        except Exception as ex:
            sys.stderr.write(f"[WARN] Error consuming approval ticket: {ex}\n")
            return False

    def log_runtime_event(self, action, decision):
        """Append decision record to events.jsonl audit trail."""
        self._ensure_dirs()
        event_id = f"evt_{uuid.uuid4().hex[:12]}"
        record = {
            "event_id": event_id,
            "timestamp": time.time(),
            "action": action,
            "outcome": decision["outcome"],
            "family": decision["family"],
            "reason_code": decision["reason_code"],
            "explanation": decision["explanation"],
            "next_step": decision["next_step"],
        }
        with open(self.events_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return event_id

    def get_runtime_event(self, event_id):
        """Find an event record by event_id in events.jsonl."""
        if not self.events_file.exists():
            return None
        lines = self.events_file.read_text(encoding="utf-8").splitlines()
        for line in lines:
            match = _match_event_in_line(line, event_id)
            if match:
                return match
        return None


def _handle_parse_prompt(manager, args):
    """Handle parse-prompt CLI invocation."""
    contract, err = parse_directive(args.text)
    if err:
        print(json.dumps({"status": "error", "message": err}))
        sys.exit(1)
    with manager.exclusive_lock():
        state = manager.load_state()
        state["contract"] = contract
        manager.save_state(state)
    print(json.dumps({"status": "ok", "contract": contract}, indent=2))


def _handle_check_action(manager, args):
    """Handle check-action CLI invocation."""
    try:
        tool_args = json.loads(args.args)
    except json.JSONDecodeError as ex:
        print(json.dumps({"outcome": "deny_and_explain", "reason_code": "INVALID_ARG_JSON", "explanation": str(ex)}))
        sys.exit(1)

    action = classify_tool_action(args.tool, tool_args)
    with manager.exclusive_lock():
        state = manager.load_state()
        contract = state.get("contract", make_default_contract())

        if args.ticket and action.get("command"):
            if manager.consume_approval_ticket(action["command"], args.ticket):
                print(json.dumps({
                    "outcome": "allow",
                    "family": None,
                    "reason_code": "TICKET_APPROVED",
                    "explanation": f"Action approved via one-time ticket {args.ticket}.",
                }, indent=2))
                sys.exit(0)

        decision = decide(contract, action, state)
        evt_id = manager.log_runtime_event(action, decision)
        decision["event_id"] = evt_id
        print(json.dumps(decision, indent=2))
        sys.exit(0 if decision["outcome"] == "allow" else 2)



HOOK_EVENT_MAX_BYTES = 64 * 1024
HOOK_EVENT_MAX_PATHS = 32
HOOK_EVENT_MAX_PATH_LENGTH = 1024
HOOK_EVENT_FIELDS = {
    "schema_version", "agent", "phase", "tool", "operation", "target_paths",
    "payload_trust", "correlation_id",
}
HOOK_ID_CHARACTERS = frozenset(string.ascii_letters + string.digits + "_.:-")
HOOK_EFFECTS = {
    "allow": "allow",
    "report_and_defer": "warn",
    "deny_and_explain": "block",
    "require_user_approval": "block",
}
HOOK_MESSAGES = {
    "INVALID_HOOK_EVENT": "The hook received an invalid or unsupported event.",
    "STATE_DAMAGED": "The local action contract could not be read or validated.",
    "TARGET_OUTSIDE_WORKSPACE": "A tool target is outside the configured workspace.",
    "TARGET_UNAVAILABLE": "The hook could not resolve a tool target.",
    "POLICY_UNAVAILABLE": "The hook could not evaluate the local action contract.",
}


def _unique_hook_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON field")
        result[key] = value
    return result


def read_hook_object(stream):
    raw = stream.read(HOOK_EVENT_MAX_BYTES + 1)
    if len(raw) > HOOK_EVENT_MAX_BYTES:
        raise ValueError("Hook JSON exceeds its byte limit")
    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_hook_object)
    except RecursionError as exc:
        raise ValueError("Hook JSON nesting exceeds decoder capacity") from exc
    if not isinstance(value, dict):
        raise ValueError("Hook JSON requires an object")
    return value


def _valid_hook_paths(paths):
    return len(paths) <= HOOK_EVENT_MAX_PATHS and all(
        isinstance(path, str) and 0 < len(path) <= HOOK_EVENT_MAX_PATH_LENGTH
        and path.strip() and "\x00" not in path for path in paths
    )


def validate_hook_event(event):
    if set(event) != HOOK_EVENT_FIELDS or type(event["schema_version"]) is not int or event["schema_version"] != 1:
        raise ValueError("Unsupported hook event fields or version")
    for field in ("agent", "tool", "correlation_id"):
        value = event[field]
        if not isinstance(value, str) or not 0 < len(value) <= 128 or not HOOK_ID_CHARACTERS.issuperset(value):
            raise ValueError("Invalid hook identifier")
    if event["phase"] not in ("pre_tool", "post_tool") or event["operation"] not in ("read", "write", "unknown"):
        raise ValueError("Unknown hook phase or operation")
    if event["payload_trust"] != "untrusted":
        raise ValueError("Unsupported payload trust level")
    paths = event["target_paths"]
    if not isinstance(paths, list) or not _valid_hook_paths(paths):
        raise ValueError("Invalid target paths")
    if event["operation"] != "unknown" and not paths:
        raise ValueError("A structured file operation requires a target path")


def _validate_hook_policy(state):
    contract = state.get("contract", make_default_contract())
    if not isinstance(contract, dict):
        raise ValueError("Invalid contract")
    for field, allowed in (
        ("mode", VALID_MODES), ("level", VALID_LEVELS),
        ("hash_policy", VALID_HASH_POLICIES), ("dependency_policy", VALID_DEP_POLICIES),
    ):
        value = contract.get(field)
        if not isinstance(value, str) or value not in allowed:
            raise ValueError("Invalid contract option")
    paths = contract.get("allowed_paths")
    if paths is not None and (not isinstance(paths, list) or not _valid_hook_paths(paths)):
        raise ValueError("Invalid contract path patterns")
    return contract


def _load_hook_policy(manager):
    if manager.state_dir.is_symlink() or manager.state_file.is_symlink():
        raise ValueError("Hook state must be local")
    try:
        flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        fd = os.open(manager.state_file, flags)
    except FileNotFoundError:
        return {}
    with os.fdopen(fd, "rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise ValueError("Hook state must be a regular file")
        return read_hook_object(stream)


def _hook_result(event, decision, reason_code):
    if decision == "block" and event.get("phase") == "post_tool":
        decision = "warn"
    message = REASON_CODES.get(reason_code) or HOOK_MESSAGES.get(reason_code, HOOK_MESSAGES["POLICY_UNAVAILABLE"])
    return {
        "schema_version": 1,
        "correlation_id": event.get("correlation_id"),
        "decision": decision,
        "reason_code": reason_code,
        "message": message,
    }


def _hook_targets(event, workspace):
    paths = []
    for target in event["target_paths"]:
        resolved = (workspace / target).resolve()
        relative = resolved.relative_to(workspace)
        # The legacy matcher normalizes backslashes and trims spaces. Keep
        # paths it cannot represent outside its authorization input.
        relative_path = relative.as_posix()
        if relative_path != relative_path.strip() or chr(92) in relative_path:
            raise OSError("Target cannot be represented by the path policy")
        paths.append(relative_path)
    return paths


def evaluate_hook_event(event, state, workspace):
    """Evaluate one validated event without changing policy, tickets, or logs."""
    if state.get("storage_error"):
        return _hook_result(event, "error", "STATE_DAMAGED")
    contract = _validate_hook_policy(state)
    operation = event["operation"]
    if "ANTI_SLOP_DESIGN_TRUST" in os.environ:
        if str(Path(__file__).resolve().parents[1]) not in sys.path:
            sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from scripts.design_integrity_guard import check_mutation
        normalized_targets = [
            Path(item).as_posix() if isinstance(item, str) else item
            for item in event["target_paths"]
        ]
        design = check_mutation(
            workspace.resolve(), os.environ["ANTI_SLOP_DESIGN_TRUST"], operation, normalized_targets,
            pre_tool=event["phase"] == "pre_tool",
        )
        if design["decision"] == "block":
            response = _hook_result(event, "block", design["reason_code"])
            response["message"] = design["message"]
            return response
    if contract["level"] == "off" or contract["mode"] == "unconfirmed":
        return _hook_result(event, "allow", "CONTROL_INACTIVE")

    try:
        paths = _hook_targets(event, workspace)
    except ValueError:
        effect = "warn" if contract["level"] == "watch" else "block"
        return _hook_result(event, effect, "TARGET_OUTSIDE_WORKSPACE")
    except (OSError, RuntimeError):
        return _hook_result(event, "error", "TARGET_UNAVAILABLE")
    action = _make_action(event["tool"], operation, paths)
    policy = decide(contract, action, state)
    effect = HOOK_EFFECTS.get(policy["outcome"], "error")
    return _hook_result(event, effect, policy["reason_code"])


def _handle_hook_event(manager, workspace):
    try:
        event = read_hook_object(sys.stdin.buffer)
        validate_hook_event(event)
    except (OSError, ValueError):
        result = _hook_result({}, "error", "INVALID_HOOK_EVENT")
    else:
        try:
            result = evaluate_hook_event(event, _load_hook_policy(manager), workspace)
        except (OSError, ValueError):
            result = _hook_result(event, "error", "STATE_DAMAGED")
    print(json.dumps(result))
    return {"allow": 0, "warn": 0, "block": 2, "error": 1}[result["decision"]]


def main():
    """Command-line interface entry point."""
    parser = argparse.ArgumentParser(description="Anti-Slop In-Flight Action Guard")
    subparsers = parser.add_subparsers(dest="command", required=True)

    p_prompt = subparsers.add_parser("parse-prompt", help="Parse prompt directive and arm session contract")
    p_prompt.add_argument("text", help="Prompt text containing directive")

    p_check = subparsers.add_parser("check-action", help="Evaluate a proposed tool action")
    p_check.add_argument("--tool", required=True, help="Tool name")
    p_check.add_argument("--args", required=True, help="Tool arguments JSON string")
    p_check.add_argument("--ticket", default=None, help="Approval ticket ID if previously granted")

    subparsers.add_parser("hook-event", help="Evaluate one normalized hook event from stdin")

    p_grant = subparsers.add_parser("grant-ticket", help="Grant a single-use approval ticket")
    p_grant.add_argument("cmd", help="Exact command string to approve")
    p_grant.add_argument("--ttl", type=int, default=DEFAULT_TICKET_TTL, help="TTL in seconds")

    subparsers.add_parser("status", help="Inspect active contract and session metrics")

    p_exp = subparsers.add_parser("explain", help="Explain a specific decision event")
    p_exp.add_argument("event_id", help="Event ID (evt_...)")

    args = parser.parse_args()
    manager = SessionStateManager()

    if args.command == "parse-prompt":
        _handle_parse_prompt(manager, args)
    elif args.command == "check-action":
        _handle_check_action(manager, args)
    elif args.command == "hook-event":
        sys.exit(_handle_hook_event(manager, Path.cwd()))
    elif args.command == "grant-ticket":
        ticket_id = manager.grant_approval_ticket(args.cmd, args.ttl)
        print(json.dumps({"ticket_id": ticket_id, "command": args.cmd, "ttl": args.ttl}, indent=2))
    elif args.command == "status":
        print(json.dumps(manager.load_state(), indent=2))
    elif args.command == "explain":
        record = manager.get_runtime_event(args.event_id)
        if not record:
            print(json.dumps({"error": f"Event {args.event_id} not found"}))
            sys.exit(1)
        print(json.dumps(record, indent=2))


if __name__ == "__main__":
    main()
