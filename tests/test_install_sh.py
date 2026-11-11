import os
import shutil
import stat
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

    def test_other_user_skills_remain_untouched(self):
        sibling = self.home / ".agents/skills/my-other-skill"
        sibling.mkdir(parents=True)
        (sibling / "SKILL.md").write_text("my own skill\n", encoding="utf-8")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((sibling / "SKILL.md").read_text(), "my own skill\n")

    def test_reinstall_does_not_change_local_executable_modes(self):
        self.assertEqual(self.install().returncode, 0)
        cli = self.home / ".agents/skills/anti-slop-engineering/bin/cli.js"
        cli.chmod(0o600)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(cli.stat().st_mode), 0o600)

    def test_symlinked_destination_is_rejected_without_touching_target(self):
        root = self.home / ".agents/skills"
        root.mkdir(parents=True)
        outside = self.home / "outside"
        outside.mkdir()
        (outside / "SKILL.md").write_text("leave me\n", encoding="utf-8")
        (root / "anti-slop-engineering").symlink_to(outside, target_is_directory=True)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Symbolic link", result.stderr)
        self.assertEqual((outside / "SKILL.md").read_text(), "leave me\n")

    def test_project_local_install_does_not_copy_itself_recursively(self):
        source = self.home / "source"
        (source / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / "install.sh", source / "install.sh")
        shutil.copy2(REPO / "scripts/safe_install.py", source / "scripts/safe_install.py")
        (source / "SKILL.md").write_text("fixture\n", encoding="utf-8")
        env = {**os.environ, "HOME": str(self.home / "home"), "PATH": "/usr/bin:/bin"}
        for _ in range(2):
            result = subprocess.run(["bash", "install.sh", "--project"], cwd=source,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        local = source / ".agents/skills/anti-slop-engineering"
        self.assertEqual((local / "SKILL.md").read_text(), "fixture\n")
        self.assertFalse((local / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
