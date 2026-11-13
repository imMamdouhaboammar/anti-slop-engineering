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


if __name__ == "__main__":
    unittest.main()
