import os
import json
import stat
import subprocess
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
        root = Path(self.temp.name).resolve()
        self.source = root / "source"
        self.dest = root / "target" / "skill"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("original\n", encoding="utf-8")

    def install(self):
        return safe_install.install_tree(self.source, self.dest)


    def test_installed_skill_version_matches_version_file(self):
        (self.source / "SKILL.md").write_text(
            '---\nname: demo\nmetadata:\n  version: "0.0.1"\n---\nbody\n',
            encoding="utf-8")
        safe_install.install_tree(self.source, self.dest, version="9.9.9")
        installed = (self.dest / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn('version: "9.9.9"', installed)
        self.assertEqual(
            (self.dest / "VERSION").read_text(encoding="utf-8").strip(), "9.9.9")
        self.assertIn(
            'version: "0.0.1"',
            (self.source / "SKILL.md").read_text(encoding="utf-8"))

    def test_batch_preview_matches_single_plans_without_creating_destinations(self):
        other = self.dest.with_name("second")
        command = [sys.executable, str(Path(safe_install.__file__)), "--preview-batch"]
        result = subprocess.run(
            command,
            input=json.dumps([[str(self.source), str(target)] for target in (self.dest, other)]),
            text=True, capture_output=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout),
            [safe_install.preview_tree(self.source, target) for target in (self.dest, other)],
        )
        self.assertFalse(self.dest.parent.exists())

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

    def test_preview_reports_conflicts_without_modifying_disk(self):
        self.install()
        (self.dest / "SKILL.md").write_text("my local content\n", encoding="utf-8")
        (self.source / "SKILL.md").write_text("next release\n", encoding="utf-8")
        before = (self.dest / safe_install.MANIFEST).read_bytes()
        outcome = safe_install.preview_tree(self.source, self.dest)
        self.assertEqual(outcome["conflicted"], ["SKILL.md"])
        self.assertEqual((self.dest / "SKILL.md").read_text(), "my local content\n")
        self.assertEqual((self.dest / safe_install.MANIFEST).read_bytes(), before)
        self.assertEqual(list(self.dest.parent.glob(".skill.backup-*")), [])

    def test_write_staged_file_creates_restrictive_permissions(self):
        stage = Path(self.temp.name).resolve() / "staged"
        stage.mkdir()
        safe_install.write_staged_file(stage, "test.txt", b"secret\n", 0o644)
        target = stage / "test.txt"
        self.assertTrue(target.is_file())
        self.assertEqual(stat.S_IMODE(target.stat().st_mode) & 0o077, 0o044)

    def test_default_excluded_paths_prevent_skills_and_dev_directories_leakage(self):
        """Verify default exclusions prevent optional skills and dev-only folders from being installed."""
        (self.source / "skills" / "decision-guard").mkdir(parents=True)
        (self.source / "skills" / "decision-guard" / "SKILL.md").write_text("decision skill\n", encoding="utf-8")
        for dev_dir in ("tests", "test", "cases", "docs", ".github", "submission"):
            target_dir = self.source / dev_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "internal.txt").write_text("dev artifact\n", encoding="utf-8")

        result = self.install()
        self.assertIn("SKILL.md", result["installed"])
        self.assertFalse((self.dest / "skills").exists())
        self.assertFalse((self.dest / "skills" / "decision-guard").exists())
        for dev_dir in ("tests", "test", "cases", "docs", ".github", "submission"):
            self.assertFalse((self.dest / dev_dir).exists(), f"Dev directory {dev_dir} was leaked to destination")

    def test_custom_exclude_parameter_and_cli_flag_exclude_specified_paths(self):
        """Verify custom excludes argument filters out extra paths during installation."""
        (self.source / "extra").mkdir()
        (self.source / "extra" / "data.json").write_text("{}\n", encoding="utf-8")
        (self.source / "unwanted.md").write_text("skip me\n", encoding="utf-8")

        result = safe_install.install_tree(self.source, self.dest, excludes={"extra", "unwanted.md"})
        self.assertIn("SKILL.md", result["installed"])
        self.assertNotIn("extra/data.json", result["installed"])
        self.assertNotIn("unwanted.md", result["installed"])
        self.assertFalse((self.dest / "extra").exists())
        self.assertFalse((self.dest / "unwanted.md").exists())

    def test_optional_skill_installation_preserves_nested_assets(self):
        """Verify installing an individual optional skill copies its assets without interference from exclusions."""
        optional_source = Path(self.temp.name).resolve() / "optional-source"
        optional_dest = Path(self.temp.name).resolve() / "target" / "decision-guard"
        optional_source.mkdir()
        (optional_source / "SKILL.md").write_text("decision guard\n", encoding="utf-8")
        for sub in ("agents", "evals", "examples", "references", "usecases"):
            sub_dir = optional_source / sub
            sub_dir.mkdir()
            (sub_dir / "asset.txt").write_text(f"{sub} content\n", encoding="utf-8")

        result = safe_install.install_tree(optional_source, optional_dest)
        self.assertIn("SKILL.md", result["installed"])
        for sub in ("agents", "evals", "examples", "references", "usecases"):
            self.assertIn(f"{sub}/asset.txt", result["installed"])
            self.assertTrue((optional_dest / sub / "asset.txt").is_file())


if __name__ == "__main__":
    unittest.main()
