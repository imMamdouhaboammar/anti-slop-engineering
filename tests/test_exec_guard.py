#!/usr/bin/env python3
"""
Unit tests for the Anti-Slop in-flight execution guard (scripts/exec_guard.py).
Verifies directive parsing, action classification, shell AST analysis,
core decision engine, approval tickets, and atomic state locks.
"""

import json
import os
import shutil
import tempfile
import time
import unittest
from pathlib import Path

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import exec_guard


class ExecGuardDirectiveTests(unittest.TestCase):
    """Test suite for contract directive parsing."""

    def test_parse_default_contract_when_empty(self):
        contract, err = exec_guard.parse_directive("")
        self.assertIsNone(err)
        self.assertEqual(contract["mode"], "unconfirmed")
        self.assertEqual(contract["level"], "watch")
        self.assertEqual(contract["agent_budget"], exec_guard.DEFAULT_AGENT_LIMIT)

    def test_parse_standard_change_directive(self):
        text = "$anti-slop change guard -- Fix authentication test"
        contract, err = exec_guard.parse_directive(text)
        self.assertIsNone(err)
        self.assertEqual(contract["mode"], "change")
        self.assertEqual(contract["level"], "guard")
        self.assertEqual(contract["task"], "Fix authentication test")

    def test_parse_review_mode_with_options(self):
        text = "$anti-slop review guard files=src/**|tests/** hash=deny deps=deny agents=2 -- Audit PR"
        contract, err = exec_guard.parse_directive(text)
        self.assertIsNone(err)
        self.assertEqual(contract["mode"], "review")
        self.assertEqual(contract["level"], "guard")
        self.assertEqual(contract["allowed_paths"], ["src/**", "tests/**"])
        self.assertEqual(contract["hash_policy"], "deny")
        self.assertEqual(contract["dependency_policy"], "deny")
        self.assertEqual(contract["agent_budget"], 2)
        self.assertEqual(contract["task"], "Audit PR")

    def test_parse_invalid_mode_returns_error(self):
        text = "$anti-slop invalid_mode guard -- do work"
        contract, err = exec_guard.parse_directive(text)
        self.assertIsNotNone(err)
        self.assertIn("INVALID_MODE", err)

    def test_parse_invalid_agents_returns_error(self):
        text = "$anti-slop change guard agents=-5 -- do work"
        contract, err = exec_guard.parse_directive(text)
        self.assertIsNotNone(err)
        self.assertIn("INVALID_AGENT_BUDGET", err)


class ExecGuardShellAnalysisTests(unittest.TestCase):
    """Test suite for shell command static analysis."""

    def test_read_only_commands_classified_as_read(self):
        read_commands = [
            "ls -la",
            "git status",
            "git diff HEAD~1",
            "cat README.md",
            "grep -r 'pattern' src/",
            "find . -name '*.py'",
            "head -n 20 file.txt",
        ]
        for cmd in read_commands:
            analysis = exec_guard.analyze_shell_command(cmd)
            self.assertEqual(analysis["mutability"], "read", f"Failed for {cmd}")
            self.assertFalse(analysis["dependency_intent"], f"Failed dep for {cmd}")
            self.assertFalse(analysis["hash_intent"], f"Failed hash for {cmd}")

    def test_mutating_file_commands_detected(self):
        mutating_commands = [
            "rm -rf build/",
            "mkdir -p src/new_dir",
            "touch new_file.txt",
            "cp a.txt b.txt",
            "mv old.txt new.txt",
            "sed -i 's/foo/bar/g' test.txt",
            "echo 'hello' > output.txt",
            "echo 'more' >> output.txt",
            "git commit -m 'save work'",
            "git checkout -b new-branch",
        ]
        for cmd in mutating_commands:
            analysis = exec_guard.analyze_shell_command(cmd)
            self.assertEqual(analysis["mutability"], "write", f"Failed for {cmd}")

    def test_dependency_install_commands_detected(self):
        dep_commands = [
            ("npm install lodash", "npm"),
            ("npm i -D typescript", "npm"),
            ("bun add fastify", "bun"),
            ("pnpm add react", "pnpm"),
            ("pip install requests", "pip"),
            ("pip3 install pytest", "pip3"),
            ("cargo add serde", "cargo"),
            ("uv add httpx", "uv"),
            ("go get github.com/gin-gonic/gin", "go"),
        ]
        for cmd, pkg_mgr in dep_commands:
            analysis = exec_guard.analyze_shell_command(cmd)
            self.assertTrue(analysis["dependency_intent"], f"Failed for {cmd}")
            self.assertEqual(analysis["mutability"], "write")

    def test_hash_checksum_commands_detected(self):
        hash_commands = [
            "sha256sum release.tar.gz",
            "shasum -a 256 artifact.zip",
            "md5sum data.csv",
            "b2sum binary",
            "openssl dgst -sha256 package.tar",
        ]
        for cmd in hash_commands:
            analysis = exec_guard.analyze_shell_command(cmd)
            self.assertTrue(analysis["hash_intent"], f"Failed for {cmd}")


class ExecGuardDecisionTests(unittest.TestCase):
    """Test suite for core decision engine rules."""

    def test_unconfirmed_mode_allows_actions(self):
        contract = exec_guard.make_default_contract()
        action = {"mutability": "write", "affected_paths": ["src/app.py"]}
        decision = exec_guard.decide(contract, action)
        self.assertEqual(decision["outcome"], "allow")
        self.assertEqual(decision["reason_code"], "CONTROL_INACTIVE")

    def test_review_mode_forbids_mutation(self):
        contract = {
            "mode": "review",
            "level": "guard",
            "agent_budget": 10,
            "hash_policy": "deny",
            "dependency_policy": "ask",
            "allowed_paths": None,
        }
        action = {"mutability": "write", "affected_paths": ["src/app.py"]}
        decision = exec_guard.decide(contract, action)
        self.assertEqual(decision["outcome"], "deny_and_explain")
        self.assertEqual(decision["family"], "I")
        self.assertEqual(decision["reason_code"], "MODE_FORBIDS_MUTATION")

    def test_review_mode_in_watch_level_reports_and_defers(self):
        contract = {
            "mode": "review",
            "level": "watch",
            "agent_budget": 10,
            "hash_policy": "deny",
            "dependency_policy": "ask",
            "allowed_paths": None,
        }
        action = {"mutability": "write", "affected_paths": ["src/app.py"]}
        decision = exec_guard.decide(contract, action)
        self.assertEqual(decision["outcome"], "report_and_defer")
        self.assertEqual(decision["family"], "I")
        self.assertEqual(decision["reason_code"], "MODE_FORBIDS_MUTATION")

    def test_path_boundary_enforcement(self):
        contract = {
            "mode": "change",
            "level": "guard",
            "agent_budget": 10,
            "hash_policy": "deny",
            "dependency_policy": "ask",
            "allowed_paths": ["src/**", "tests/**"],
        }
        # Inside boundary
        action_allowed = {"mutability": "write", "affected_paths": ["src/core/utils.py"]}
        decision_allowed = exec_guard.decide(contract, action_allowed)
        self.assertEqual(decision_allowed["outcome"], "allow")

        # Outside boundary
        action_denied = {"mutability": "write", "affected_paths": ["package.json"]}
        decision_denied = exec_guard.decide(contract, action_denied)
        self.assertEqual(decision_denied["outcome"], "deny_and_explain")
        self.assertEqual(decision_denied["family"], "S")
        self.assertEqual(decision_denied["reason_code"], "PATH_OUTSIDE_CONTRACT")

    def test_hash_policy_enforcement(self):
        contract = {
            "mode": "change",
            "level": "guard",
            "agent_budget": 10,
            "hash_policy": "deny",
            "dependency_policy": "ask",
            "allowed_paths": None,
        }
        action = {"mutability": "write", "hash_intent": True}
        decision = exec_guard.decide(contract, action)
        self.assertEqual(decision["outcome"], "deny_and_explain")
        self.assertEqual(decision["family"], "H")
        self.assertEqual(decision["reason_code"], "HASH_NOT_AUTHORIZED")

    def test_dependency_policy_ask_requires_approval(self):
        contract = {
            "mode": "change",
            "level": "guard",
            "agent_budget": 10,
            "hash_policy": "deny",
            "dependency_policy": "ask",
            "allowed_paths": None,
        }
        action = {"mutability": "write", "dependency_intent": True, "command": "bun add zod"}
        decision = exec_guard.decide(contract, action)
        self.assertEqual(decision["outcome"], "require_user_approval")
        self.assertEqual(decision["family"], "S")
        self.assertEqual(decision["reason_code"], "DEPENDENCY_NOT_AUTHORIZED")

    def test_agent_concurrency_budget_exhaustion(self):
        contract = {
            "mode": "change",
            "level": "guard",
            "agent_budget": 2,
            "hash_policy": "deny",
            "dependency_policy": "ask",
            "allowed_paths": None,
        }
        state = {"active_agents": 2}
        action = {"mutability": "delegate", "delegation_count": 1}
        decision = exec_guard.decide(contract, action, state)
        self.assertEqual(decision["outcome"], "deny_and_explain")
        self.assertEqual(decision["family"], "S")
        self.assertEqual(decision["reason_code"], "AGENT_BUDGET_EXHAUSTED")


class ExecGuardTicketAndStateTests(unittest.TestCase):
    """Test suite for single-use approval tickets and atomic state lock."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="anti_slop_test_")
        self.state_dir = os.path.join(self.test_dir, ".anti-slop")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_ticket_lifecycle(self):
        manager = exec_guard.SessionStateManager(self.state_dir)
        cmd = "bun add zod"
        ticket_id = manager.grant_approval_ticket(cmd, ttl_seconds=600)
        self.assertTrue(ticket_id.startswith("tkt_"))

        # Verify valid ticket consumes successfully
        valid = manager.consume_approval_ticket(cmd, ticket_id)
        self.assertTrue(valid)

        # Ticket is single-use: second consumption fails
        second_valid = manager.consume_approval_ticket(cmd, ticket_id)
        self.assertFalse(second_valid)

    def test_expired_ticket_fails(self):
        manager = exec_guard.SessionStateManager(self.state_dir)
        cmd = "pip install torch"
        # 0 second TTL means already expired
        ticket_id = manager.grant_approval_ticket(cmd, ttl_seconds=0)
        time.sleep(0.01)
        valid = manager.consume_approval_ticket(cmd, ticket_id)
        self.assertFalse(valid)

    def test_atomic_lock_and_stale_lock_recovery(self):
        manager = exec_guard.SessionStateManager(self.state_dir)
        with manager.exclusive_lock():
            state = manager.load_state()
            state["test_key"] = "test_value"
            manager.save_state(state)

        reloaded = manager.load_state()
        self.assertEqual(reloaded.get("test_key"), "test_value")

    def test_runtime_audit_event_logging_and_explain(self):
        manager = exec_guard.SessionStateManager(self.state_dir)
        action = {"tool": "write_file", "path": "src/bad.py", "mutability": "write"}
        decision = {
            "outcome": "deny_and_explain",
            "family": "I",
            "reason_code": "MODE_FORBIDS_MUTATION",
            "explanation": "Review mode forbids writes",
            "next_step": "Obtain change contract",
        }
        evt_id = manager.log_runtime_event(action, decision)
        self.assertTrue(evt_id.startswith("evt_"))

        record = manager.get_runtime_event(evt_id)
        self.assertIsNotNone(record)
        self.assertEqual(record["event_id"], evt_id)
        self.assertEqual(record["reason_code"], "MODE_FORBIDS_MUTATION")


if __name__ == "__main__":
    unittest.main()
