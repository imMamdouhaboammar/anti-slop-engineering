import os
import json
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
            if calls == 3:
                raise OSError("interrupted swap")
            return original_replace(source, target)

        with patch.object(safe_install.os, "replace", side_effect=fail_once):
            with self.assertRaisesRegex(OSError, "interrupted swap"):
                self.install()
        self.assertEqual((self.dest / "SKILL.md").read_text(), "original\n")
        self.assertEqual(self.install()["updated"], ["SKILL.md"])

    def test_rejects_dangling_managed_inventory_symlink(self):
        self.install()
        outside = self.dest.parent / "external-inventory.json"
        (self.dest / safe_install.MANIFEST).unlink()
        (self.dest / safe_install.MANIFEST).symlink_to(outside)
        (self.source / "SKILL.md").write_text("new release\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory.*symbolic link"):
            self.install()
        self.assertFalse(outside.exists())

    def test_rejects_staged_symlink_ancestor_without_external_write(self):
        self.install()
        nested = self.source / "nested"
        nested.mkdir()
        (nested / "new.md").write_text("managed data", encoding="utf-8")
        outside = self.dest.parent / "external"
        outside.mkdir()
        original_copytree = safe_install.shutil.copytree

        def inject_symlink(src, dst, **kwargs):
            result = original_copytree(src, dst, **kwargs)
            (Path(dst) / "nested").symlink_to(outside, target_is_directory=True)
            return result

        with patch.object(safe_install.shutil, "copytree", side_effect=inject_symlink):
            with self.assertRaisesRegex(ValueError, "Symbolic link"):
                self.install()
        self.assertFalse((outside / "new.md").exists())

    def test_detects_user_edit_during_staging_and_preserves_it(self):
        self.install()
        (self.source / "SKILL.md").write_text("new release\n", encoding="utf-8")
        original_copytree = safe_install.shutil.copytree

        def edit_during_stage(src, dst, **kwargs):
            result = original_copytree(src, dst, **kwargs)
            (self.dest / "SKILL.md").write_text("edited during update\n", encoding="utf-8")
            return result

        with patch.object(safe_install.shutil, "copytree", side_effect=edit_during_stage):
            with self.assertRaisesRegex(OSError, "changed during installation"):
                self.install()
        self.assertEqual((self.dest / "SKILL.md").read_text(), "edited during update\n")

    def test_recovers_previous_install_after_interrupted_rename(self):
        self.install()
        backup = self.dest.parent / ".skill.backup-interrupted"
        os.replace(self.dest, backup)
        result = self.install()
        self.assertEqual(result["recovered"], str(self.dest))
        self.assertEqual((self.dest / "SKILL.md").read_text(), "original\n")

    def test_recovers_interrupted_update_when_older_backups_exist(self):
        self.install()
        (self.source / "SKILL.md").write_text("second release\n", encoding="utf-8")
        self.install()
        (self.source / "SKILL.md").write_text("third release\n", encoding="utf-8")
        previous = self.dest.parent / ".skill.backup-current-swap"
        journal = self.dest.parent / ".skill.swap.json"
        journal.write_text(json.dumps({"backup": previous.name}), encoding="utf-8")
        os.replace(self.dest, previous)
        result = self.install()
        self.assertEqual(result["recovered"], str(self.dest))
        self.assertFalse(journal.exists())
        self.assertEqual((self.dest / "SKILL.md").read_text(), "third release\n")

    def test_rejects_symlinked_destination_and_path_traversal(self):
        outside = self.dest.parent / "outside"
        outside.mkdir(parents=True)
        self.dest.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "Symbolic link"):
            self.install()
        with self.assertRaisesRegex(ValueError, "without traversal"):
            safe_install.install_tree(self.source, self.dest.parent / ".." / "escape")
        self.assertEqual(list(outside.iterdir()), [])

    def test_instruction_writer_requires_unchanged_content(self):
        entry = self.dest.parent / "AGENTS.md"
        entry.parent.mkdir(parents=True)
        entry.write_text("original\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed during installation"):
            safe_install.write_instruction(entry, b"replacement\n", "absent")
        self.assertEqual(entry.read_text(), "original\n")
        safe_install.write_instruction(entry, b"replacement\n", safe_install.digest(b"original\n"))
        self.assertEqual(entry.read_text(), "replacement\n")

    def test_instruction_writer_rejects_parent_symlink_without_external_write(self):
        outside = self.dest.parent / "outside"
        outside.mkdir(parents=True)
        (outside / "AGENTS.md").write_text("owner data\n", encoding="utf-8")
        link = self.dest.parent / "agent"
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symbolic link"):
            safe_install.write_instruction(link / "AGENTS.md", b"injected\n", safe_install.digest(b"owner data\n"))
        self.assertEqual((outside / "AGENTS.md").read_text(), "owner data\n")

    def test_new_instruction_file_is_private_and_existing_mode_is_preserved(self):
        entry = self.dest.parent / "AGENTS.md"
        entry.parent.mkdir(parents=True)
        safe_install.write_instruction(entry, b"private instructions\n", "absent")
        self.assertEqual(stat.S_IMODE(entry.stat().st_mode) & 0o077, 0)
        entry.chmod(0o644)
        safe_install.write_instruction(entry, b"revised\n", safe_install.digest(b"private instructions\n"))
        self.assertEqual(stat.S_IMODE(entry.stat().st_mode), 0o644)

    def test_preserves_source_executable_permissions(self):
        executable = self.source / "bin" / "cli.js"
        executable.parent.mkdir()
        executable.write_text("#!/usr/bin/env node\n", encoding="utf-8")
        executable.chmod(0o755)
        self.install()
        self.assertTrue((self.dest / "bin" / "cli.js").stat().st_mode & stat.S_IXUSR)

    def test_project_local_install_excludes_its_own_destination(self):
        local = self.source / ".agents" / "skills" / "anti-slop-engineering"
        first = safe_install.install_tree(self.source, local)
        second = safe_install.install_tree(self.source, local)
        self.assertEqual(first["installed"], ["SKILL.md"])
        self.assertEqual(second["skipped"], ["SKILL.md"])
        self.assertFalse((local / ".agents").exists())


if __name__ == "__main__":
    unittest.main()
