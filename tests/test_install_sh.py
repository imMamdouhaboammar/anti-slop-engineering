import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
NODE_DIRECTORY = str(Path(shutil.which("node")).parent) if shutil.which("node") else "/usr/bin"
SAFE_PATH = f"{NODE_DIRECTORY}:/usr/bin:/bin"


class BashInstallerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def install(self):
        return subprocess.run(
            ["bash", str(REPO / "install.sh")],
            cwd=self.home,
            env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
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
        env = {**os.environ, "HOME": str(self.home / "home"), "PATH": SAFE_PATH}
        for _ in range(2):
            result = subprocess.run(["bash", "install.sh", "--project"], cwd=source,
                                    env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("No executable CLI target", result.stderr)
        local = source / ".agents/skills/anti-slop-engineering"
        self.assertEqual((local / "SKILL.md").read_text(), "fixture\n")
        self.assertFalse((local / ".agents").exists())
        self.assertFalse((self.home / "home/.local/bin/anti-slop-engineering").exists())

    def test_bundled_module_conflicts_are_printed_as_readable_paths(self):
        source = self.home / "fixture"
        (source / "scripts").mkdir(parents=True)
        module = source / "skills/decision-guard"
        module.mkdir(parents=True)
        shutil.copy2(REPO / "install.sh", source / "install.sh")
        shutil.copy2(REPO / "scripts/safe_install.py", source / "scripts/safe_install.py")
        (source / "SKILL.md").write_text("core\n", encoding="utf-8")
        (module / "SKILL.md").write_text("module v1\n", encoding="utf-8")
        env = {**os.environ, "HOME": str(self.home / "home"), "PATH": "/usr/bin:/bin"}

        def install_fixture():
            return subprocess.run(["bash", "install.sh"], cwd=source, env=env,
                                  capture_output=True, text=True)

        self.assertEqual(install_fixture().returncode, 0)
        installed = Path(env["HOME"]) / ".agents/skills/decision-guard/SKILL.md"
        installed.write_text("user edit\n", encoding="utf-8")
        (module / "SKILL.md").write_text("module v2\n", encoding="utf-8")
        result = install_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Conflicts retained: SKILL.md", result.stdout)
        self.assertEqual(installed.read_text(), "user edit\n")

    def test_universal_only_install_creates_executable_cli_links(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        cli = self.home / ".agents/skills/anti-slop-engineering/bin/cli.js"
        for name in ("anti-slop-engineering", "diff-guard", "sre-guard", "rust-guard", "toil-guard"):
            link = self.home / ".local/bin" / name
            self.assertTrue(link.is_symlink(), f"Missing {link}")
            self.assertEqual(link.resolve(), cli)
            self.assertTrue(os.access(link, os.X_OK))
        primary = self.home / ".local/bin/anti-slop-engineering"
        self.assertEqual(subprocess.run([str(primary), "--help"], capture_output=True).returncode, 0)

    def test_codex_install_links_to_existing_codex_cli(self):
        (self.home / ".codex").mkdir()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.home / ".local/bin/anti-slop-engineering"
        self.assertEqual(link.resolve(), self.home / ".codex/skills/anti-slop-engineering/bin/cli.js")

    def test_multi_agent_install_uses_verified_gemini_cli(self):
        (self.home / ".gemini").mkdir()
        (self.home / ".codex").mkdir()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.home / ".local/bin/anti-slop-engineering"
        self.assertEqual(link.resolve(), self.home / ".gemini/config/skills/anti-slop-engineering/bin/cli.js")

    def test_existing_user_owned_links_are_preserved(self):
        bin_dir = self.home / ".local/bin"
        bin_dir.mkdir(parents=True)
        external = self.home / "custom-tool"
        external.write_text("keep this\n", encoding="utf-8")
        (bin_dir / "anti-slop-engineering").symlink_to(external)
        (bin_dir / "diff-guard").write_text("my guard\n", encoding="utf-8")
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((bin_dir / "anti-slop-engineering").resolve(), external)
        self.assertEqual((bin_dir / "diff-guard").read_text(), "my guard\n")
        self.assertIn("conflict", result.stdout.lower())
        self.assertTrue((bin_dir / "sre-guard").is_symlink())

    def test_repeated_install_preserves_existing_valid_links(self):
        self.assertEqual(self.install().returncode, 0)
        link = self.home / ".local/bin/anti-slop-engineering"
        first = link.lstat().st_ino
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(link.lstat().st_ino, first)

    def test_non_executable_cli_never_becomes_a_link_target(self):
        source = self.home / "incomplete-source"
        (source / "scripts").mkdir(parents=True)
        (source / "bin").mkdir()
        shutil.copy2(REPO / "install.sh", source / "install.sh")
        shutil.copy2(REPO / "scripts/safe_install.py", source / "scripts/safe_install.py")
        (source / "SKILL.md").write_text("fixture\n", encoding="utf-8")
        (source / "bin/cli.js").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (source / "bin/cli.js").chmod(0o755)
        result = subprocess.run(["bash", "install.sh"], cwd=source,
                                env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
                                capture_output=True, text=True)
        self.assertIn("No executable CLI target", result.stderr)
        self.assertFalse((self.home / ".local/bin/anti-slop-engineering").exists())

    def test_symlinked_cli_directory_is_never_written_through(self):
        outside = self.home / "other-bin"
        outside.mkdir()
        (self.home / ".local").symlink_to(outside, target_is_directory=True)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symbolic link", result.stderr.lower())
        self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
