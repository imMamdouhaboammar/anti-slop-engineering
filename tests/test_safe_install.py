import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import safe_install


class SafeFileInstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = root / "source"
        self.dest = root / "target" / "skill"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("original\n", encoding="utf-8")

    def install(self):
        return safe_install.install_tree(self.source, self.dest)

    def test_fresh_install_and_idempotent_reinstall(self):
        first = self.install()
        self.assertEqual(first["installed"], ["SKILL.md"])
        self.assertEqual((self.dest / "SKILL.md").read_text(), "original\n")
        second = self.install()
        self.assertEqual(second["updated"], [])
        self.assertEqual(second["skipped"], ["SKILL.md"])
        self.assertIsNone(second["backup"])

    def test_managed_file_updates_when_unchanged_by_user(self):
        self.install()
        (self.source / "SKILL.md").write_text("new release\n", encoding="utf-8")
        result = self.install()
        self.assertEqual(result["updated"], ["SKILL.md"])
        self.assertEqual((self.dest / "SKILL.md").read_text(), "new release\n")
        self.assertTrue(Path(result["backup"]).exists())

    def test_modified_file_and_extra_file_are_preserved(self):
        self.install()
        (self.dest / "SKILL.md").write_text("local edit\n", encoding="utf-8")
        (self.dest / "private.md").write_text("my notes\n", encoding="utf-8")
        (self.source / "SKILL.md").write_text("new release\n", encoding="utf-8")
        result = self.install()
        self.assertEqual(result["conflicted"], ["SKILL.md"])
        self.assertEqual(result["preserved"], ["private.md"])
        self.assertEqual((self.dest / "SKILL.md").read_text(), "local edit\n")
        self.assertEqual((self.dest / "private.md").read_text(), "my notes\n")

    def test_failed_stage_copy_keeps_installed_content(self):
        self.install()
        (self.source / "SKILL.md").write_text("changed\n", encoding="utf-8")
        with patch.object(safe_install.shutil, "copytree", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                self.install()
        self.assertEqual((self.dest / "SKILL.md").read_text(), "original\n")

    def test_interrupted_swap_rolls_back_then_retries(self):
        self.install()
        (self.source / "SKILL.md").write_text("changed\n", encoding="utf-8")
        original_replace = safe_install.os.replace
        calls = 0

        def fail_once(source, target):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("interrupted swap")
            return original_replace(source, target)

        with patch.object(safe_install.os, "replace", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "interrupted swap"):
                self.install()
        self.assertEqual((self.dest / "SKILL.md").read_text(), "original\n")
        self.assertEqual(self.install()["updated"], ["SKILL.md"])

    def test_recovers_previous_install_after_interrupted_rename(self):
        self.install()
        backup = self.dest.parent / ".skill.backup-interrupted"
        os.replace(self.dest, backup)
        result = self.install()
        self.assertEqual(result["recovered"], str(self.dest))
        self.assertEqual((self.dest / "SKILL.md").read_text(), "original\n")

    def test_rejects_symlinked_destination_and_path_traversal(self):
        outside = self.dest.parent / "outside"
        outside.mkdir(parents=True)
        self.dest.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symbolic link"):
            self.install()
        with self.assertRaisesRegex(ValueError, "without traversal"):
            safe_install.install_tree(self.source, self.dest.parent / ".." / "escape")
        self.assertEqual(list(outside.iterdir()), [])

    def test_preserves_source_executable_permissions(self):
        executable = self.source / "bin" / "cli.js"
        executable.parent.mkdir()
        executable.write_text("#!/usr/bin/env node\n", encoding="utf-8")
        executable.chmod(0o755)
        self.install()
        self.assertTrue((self.dest / "bin" / "cli.js").stat().st_mode & stat.S_IXUSR)


if __name__ == "__main__":
    unittest.main()
