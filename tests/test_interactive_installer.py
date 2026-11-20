import os
import select
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "posix" and shutil.which("node"), "PTY and Node are required")
class InteractiveInstallerTests(unittest.TestCase):
    def setUp(self):
        import fcntl
        import pty
        import struct
        import termios

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 42, 0, 0))
        self.process = subprocess.Popen(
            [shutil.which("node"), str(REPO / "scripts/installer.mjs"), "--agent=codex"],
            stdin=slave, stdout=slave, stderr=slave, cwd=self.project,
            env={**os.environ, "HOME": str(self.project), "CI": "", "NO_COLOR": "1"},
        )
        os.close(slave)
        self.addCleanup(self.cleanup_child)

    def cleanup_child(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        os.close(self.master)

    def read_until(self, phrase, seconds=8):
        output = bytearray()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            readable, _, _ = select.select([self.master], [], [], 0.2)
            if not readable:
                continue
            try:
                chunk = os.read(self.master, 8192)
            except OSError:
                break
            if not chunk:
                break
            output.extend(chunk)
            if phrase.encode() in output:
                return output.decode(errors="replace")
        self.fail(f"Expected interactive prompt {phrase!r}; output: {output.decode(errors='replace')[:500]}")

    def test_core_only_setup_supports_back_and_confirmation(self):
        self.read_until("Core only")
        os.write(self.master, b"2\n")
        self.read_until("Select optional plugins")
        os.write(self.master, b"b\n")
        self.read_until("Core only")
        os.write(self.master, b"1\n")
        self.read_until("Confirm installation")
        os.write(self.master, b"y\n")
        self.assertEqual(self.process.wait(timeout=15), 0)
        self.assertTrue((self.project / ".codex/skills/anti-slop-engineering/SKILL.md").exists())
        self.assertFalse((self.project / ".codex/skills/decision-guard").exists())

    def test_eof_cancels_without_mutating_project(self):
        self.read_until("Core only")
        os.write(self.master, b"\x04")
        self.assertNotEqual(self.process.wait(timeout=8), 0)
        self.assertFalse((self.project / ".codex").exists())

    def test_declined_confirmation_does_not_install_anything(self):
        self.read_until("Core only")
        os.write(self.master, b"3\n")
        self.read_until("Confirm installation")
        os.write(self.master, b"n\n")
        self.assertNotEqual(self.process.wait(timeout=8), 0)
        self.assertFalse((self.project / ".codex").exists())

    def test_small_terminal_displays_optional_descriptions_and_supports_empty_selection(self):
        self.read_until("Core only")
        os.write(self.master, b"2\n")
        listing = self.read_until("Plugins (comma-separated")
        self.assertIn("decision-guard", listing)
        for line in listing.splitlines():
            if line.startswith("  ") and not line.startswith("  Target:"):
                self.assertLessEqual(len(line), 42, line)
        os.write(self.master, b"\n")
        self.read_until("Confirm installation")
        os.write(self.master, b"y\n")
        self.assertEqual(self.process.wait(timeout=15), 0)
        self.assertFalse((self.project / ".codex/skills/decision-guard").exists())

    def test_custom_selection_installs_multiple_plugins_with_core(self):
        self.read_until("Core only")
        os.write(self.master, b"2\n")
        self.read_until("Plugins (comma-separated")
        os.write(self.master, b"decision-guard,root-fix-gate\n")
        self.read_until("Confirm installation")
        os.write(self.master, b"y\n")
        self.assertEqual(self.process.wait(timeout=15), 0)
        root = self.project / ".codex/skills"
        for module in ("anti-slop-engineering", "decision-guard", "root-fix-gate"):
            self.assertTrue((root / module / "SKILL.md").is_file(), module)
        self.assertFalse((root / "future-scale-gate").exists())

    def test_user_can_change_agent_scope_before_confirmation(self):
        self.read_until("Core only")
        os.write(self.master, b"t\n")
        self.read_until("Agent IDs")
        os.write(self.master, b"codex\n")
        self.read_until("Scope")
        os.write(self.master, b"global\n")
        self.read_until("Core only")
        os.write(self.master, b"1\n")
        self.read_until("Confirm installation")
        os.write(self.master, b"y\n")
        self.assertEqual(self.process.wait(timeout=15), 0)
        self.assertTrue((self.project / ".agents/skills/anti-slop-engineering/SKILL.md").exists())
        self.assertFalse((self.project / ".codex").exists())

    def test_interactive_role_preset_selection(self):
        self.read_until("Choose installation:")
        os.write(self.master, b"p\n")
        self.read_until("Choose role preset")
        os.write(self.master, b"1\n")
        self.read_until("Confirm installation")
        os.write(self.master, b"y\n")
        self.assertEqual(self.process.wait(timeout=15), 0)
        root = self.project / ".codex/skills"
        self.assertTrue((root / "anti-slop-engineering/SKILL.md").is_file())
        self.assertTrue((root / "decision-guard/SKILL.md").is_file())
        self.assertTrue((root / "paranoid-principal-architect/SKILL.md").is_file())
        self.assertFalse((root / "apple-craft-and-interaction-physics").exists())

    def test_interactive_domain_pack_selection(self):
        self.read_until("Choose installation:")
        os.write(self.master, b"g\n")
        self.read_until("Domain pack [1-7")
        os.write(self.master, b"1\n")
        self.read_until("Confirm installation")
        os.write(self.master, b"y\n")
        self.assertEqual(self.process.wait(timeout=15), 0)
        root = self.project / ".codex/skills"
        self.assertTrue((root / "anti-slop-engineering/SKILL.md").is_file())
        self.assertTrue((root / "decision-guard/SKILL.md").is_file())
        self.assertTrue((root / "reduction-guard/SKILL.md").is_file())

    def test_explicit_selection_does_not_prompt_when_stdin_is_terminal(self):
        import json
        import pty

        master, slave = pty.openpty()
        try:
            proc = subprocess.run(
                [shutil.which("node"), str(REPO / "scripts/installer.mjs"), "--selection-only",
                 "--agent=codex", "--skills=decision-guard"],
                stdin=slave, stdout=subprocess.PIPE, stderr=slave, cwd=self.project,
                env={**os.environ, "HOME": str(self.project), "CI": "", "NO_COLOR": "1"},
                timeout=5,
            )
            self.assertEqual(proc.returncode, 0)
            self.assertEqual(json.loads(proc.stdout)["skills"], ["anti-slop-engineering", "decision-guard"])
            self.assertFalse((self.project / ".codex").exists())
        finally:
            os.close(slave)
            os.close(master)

    def test_piped_stdin_selection_only_reads_from_tty(self):
        import fcntl
        import json
        import pty
        import struct
        import termios

        master, slave = pty.openpty()
        slave_name = os.ttyname(slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        proc = subprocess.Popen(
            [shutil.which("node"), str(REPO / "scripts/installer.mjs"), "--selection-only", "--scope=project"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=slave, cwd=self.project,
            env={**os.environ, "HOME": str(self.project), "CI": "", "NO_COLOR": "1", "ANTI_SLOP_TTY_PATH": slave_name},
        )
        os.close(slave)
        try:
            output = bytearray()
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    output.extend(chunk)
                    if b"Choose installation" in output:
                        break
            self.assertIn(b"Choose installation", output)
            os.write(master, b"1\n")
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    output.extend(chunk)
                    if b"Confirm installation" in output:
                        break
            self.assertIn(b"Confirm installation", output)
            os.write(master, b"y\n")
            stdout_data, _ = proc.communicate(timeout=8)
            self.assertEqual(proc.returncode, 0)
            data = json.loads(stdout_data.decode())
            self.assertEqual(data["skills"], ["anti-slop-engineering"])
        finally:
            os.close(master)

    def test_piped_stdin_selection_only_cancel_exits_130(self):
        import fcntl
        import pty
        import struct
        import termios

        master, slave = pty.openpty()
        slave_name = os.ttyname(slave)
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        proc = subprocess.Popen(
            [shutil.which("node"), str(REPO / "scripts/installer.mjs"), "--selection-only", "--scope=project"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=slave, cwd=self.project,
            env={**os.environ, "HOME": str(self.project), "CI": "", "NO_COLOR": "1", "ANTI_SLOP_TTY_PATH": slave_name},
        )
        os.close(slave)
        try:
            output = bytearray()
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                r, _, _ = select.select([master], [], [], 0.2)
                if r:
                    chunk = os.read(master, 1024)
                    if not chunk:
                        break
                    output.extend(chunk)
                    if b"Choose installation" in output:
                        break
            os.write(master, b"q\n")
            proc.communicate(timeout=8)
            self.assertEqual(proc.returncode, 130)
        finally:
            os.close(master)

    def test_headless_selection_only_defaults_without_tty(self):
        import json
        proc = subprocess.run(
            [shutil.which("node"), str(REPO / "scripts/installer.mjs"), "--selection-only", "--scope=project"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, cwd=self.project,
            env={**os.environ, "HOME": str(self.project), "CI": "", "NO_COLOR": "1"},
            timeout=5,
        )
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout.decode())
        self.assertEqual(data["skills"], ["anti-slop-engineering"])


@unittest.skipUnless(os.name == "posix" and shutil.which("node"), "PTY and Node are required")
class InteractiveEnforcementTests(unittest.TestCase):
    def setUp(self):
        import fcntl
        import pty
        import struct
        import termios

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        hooks = self.project / ".codex" / "hooks.json"
        hooks.parent.mkdir(parents=True)
        self.settings_bytes = b'{"hooks": {"custom": true}}\n'
        hooks.write_bytes(self.settings_bytes)
        self.master, slave = pty.openpty()
        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))
        self.process = subprocess.Popen(
            [shutil.which("node"), str(REPO / "scripts/installer.mjs"),
             "--agent=codex", "--enforcement=advisory"],
            stdin=slave, stdout=slave, stderr=slave, cwd=self.project,
            env={**os.environ, "HOME": str(self.project), "CI": "", "NO_COLOR": "1"},
        )
        os.close(slave)
        self.addCleanup(self.cleanup_child)

    def cleanup_child(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        os.close(self.master)

    def read_until(self, phrase, seconds=8):
        output = bytearray()
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            readable, _, _ = select.select([self.master], [], [], 0.2)
            if not readable:
                continue
            try:
                chunk = os.read(self.master, 8192)
            except OSError:
                break
            if not chunk:
                break
            output.extend(chunk)
            if phrase.encode() in output:
                return output.decode(errors="replace")
        self.fail(f"Expected interactive prompt {phrase!r}; output: {output.decode(errors='replace')[:500]}")

    def test_plan_shows_enforcement_capability_and_preserves_existing_settings(self):
        self.read_until("Core only")
        os.write(self.master, b"1\n")
        plan = self.read_until("Confirm installation")
        self.assertIn(".codex/hooks.json", plan)
        self.assertIn("Codex project hook trust", plan)
        self.assertIn("advisory", plan)
        self.assertIn("review watch", plan)
        os.write(self.master, b"y\n")
        self.assertEqual(self.process.wait(timeout=15), 0)
        self.assertEqual((self.project / ".codex" / "hooks.json").read_bytes(), self.settings_bytes)
        self.assertTrue((self.project / ".codex/skills/anti-slop-engineering/SKILL.md").exists())


@unittest.skipUnless(os.name == "posix" and shutil.which("node"), "Node is required")
class PresetInstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)

    def run_installer(self, *args, check=True):
        cmd = [shutil.which("node"), str(REPO / "scripts/installer.mjs"), "--agent=codex", *args]
        return subprocess.run(
            cmd,
            cwd=self.project,
            capture_output=True,
            text=True,
            check=check,
            env={**os.environ, "HOME": str(self.project), "CI": "1", "NO_COLOR": "1"},
        )

    def test_preset_minimal_installs_core_only(self):
        result = self.run_installer("--preset=minimal")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.project / ".codex/skills/anti-slop-engineering/SKILL.md").exists())
        self.assertFalse((self.project / ".codex/skills/decision-guard").exists())

    def test_preset_backend_installs_backend_skills(self):
        result = self.run_installer("--preset=backend")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.project / ".codex/skills/anti-slop-engineering/SKILL.md").exists())
        self.assertTrue((self.project / ".codex/skills/decision-guard/SKILL.md").exists())
        self.assertTrue((self.project / ".codex/skills/paranoid-principal-architect/SKILL.md").exists())
        self.assertFalse((self.project / ".codex/skills/apple-craft-and-interaction-physics").exists())

    def test_preset_frontend_installs_frontend_skills(self):
        result = self.run_installer("--preset=frontend")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.project / ".codex/skills/anti-slop-engineering/SKILL.md").exists())
        self.assertTrue((self.project / ".codex/skills/apple-craft-and-interaction-physics/SKILL.md").exists())
        self.assertTrue((self.project / ".codex/skills/styleseed-guard/SKILL.md").exists())
        self.assertFalse((self.project / ".codex/skills/zero-downtime-migration-gate").exists())

    def test_preset_domain_pack(self):
        result = self.run_installer("--preset=core-decisions")
        self.assertEqual(result.returncode, 0)
        self.assertTrue((self.project / ".codex/skills/anti-slop-engineering/SKILL.md").exists())
        self.assertTrue((self.project / ".codex/skills/decision-guard/SKILL.md").exists())
        self.assertTrue((self.project / ".codex/skills/reduction-guard/SKILL.md").exists())

    def test_invalid_preset_fails_with_clear_error(self):
        result = self.run_installer("--preset=invalid_foo", check=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid preset", result.stderr.lower())


if __name__ == "__main__":
    unittest.main()
