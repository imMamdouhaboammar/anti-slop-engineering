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
        import pty

        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        self.master, slave = pty.openpty()
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


if __name__ == "__main__":
    unittest.main()
