import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]


class BashInstallerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def install(self):
        return subprocess.run(
            ["bash", str(REPO / "install.sh")],
            cwd=self.home,
            env={**os.environ, "HOME": str(self.home), "PATH": "/usr/bin:/bin"},
            text=True,
            capture_output=True,
        )

    def test_repeat_install_keeps_user_skill_edits(self):
        first = self.install()
        self.assertEqual(first.returncode, 0, first.stderr)
        skill = self.home / ".agents/skills/anti-slop-engineering"
        self.assertTrue((skill / "SKILL.md").is_file())
        (skill / "SKILL.md").write_text("# my customization\n", encoding="utf-8")
        (skill / "my-notes.md").write_text("personal reference\n", encoding="utf-8")

        second = self.install()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual((skill / "SKILL.md").read_text(), "# my customization\n")
        self.assertEqual((skill / "my-notes.md").read_text(), "personal reference\n")


if __name__ == "__main__":
    unittest.main()
