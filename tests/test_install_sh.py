import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
_REAL_NODE = shutil.which("node")
HAS_NODE = _REAL_NODE is not None

# Create a clean, isolated directory containing only a symlink to node (if present)
# to avoid leaking host agent binaries (codex, claude, gemini) located in ~/.local/bin
# into SAFE_PATH during installer tests.
_ISOLATED_DIR = tempfile.TemporaryDirectory()
_ISOLATED_BIN = Path(_ISOLATED_DIR.name).resolve() / "bin"
_ISOLATED_BIN.mkdir(parents=True, exist_ok=True)
if HAS_NODE:
    (_ISOLATED_BIN / "node").symlink_to(_REAL_NODE)

SAFE_PATH = f"{_ISOLATED_BIN}:/usr/bin:/bin"


class BashInstallerSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name).resolve()

    def install(self):
        return subprocess.run(
            ["bash", str(REPO / "install.sh")],
            cwd=self.home,
            env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
            text=True,
            capture_output=True,
        )

    def test_repeat_install_keeps_user_skill_edits(self):
        """Verify repeated installation retains user edits to installed skill files."""
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

    def test_checkout_install_copies_only_tracked_files(self):
        source = self.home / "checkout"
        (source / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / "install.sh", source / "install.sh")
        shutil.copy2(REPO / "scripts/safe_install.py", source / "scripts/safe_install.py")
        (source / "SKILL.md").write_text("tracked skill\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=source, check=True)
        subprocess.run(["git", "add", "install.sh", "scripts/safe_install.py", "SKILL.md"], cwd=source, check=True)
        for relative in (".env", "openreview.config.json", ".fable/incidents/index.json", "local-notes.txt"):
            local = source / relative
            local.parent.mkdir(parents=True, exist_ok=True)
            local.write_text("local-only fixture\n", encoding="utf-8")

        (source / "local-link").symlink_to(source / "local-notes.txt")

        result = subprocess.run(
            ["bash", "install.sh"], cwd=source,
            env={**os.environ, "HOME": str(self.home / "agent-home"), "PATH": SAFE_PATH},
            text=True, capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        installed = self.home / "agent-home/.agents/skills/anti-slop-engineering"
        self.assertEqual((installed / "SKILL.md").read_text(encoding="utf-8"), "tracked skill\n")
        for relative in (".env", "openreview.config.json", ".fable", "local-notes.txt", "local-link"):
            with self.subTest(relative=relative):
                self.assertFalse((installed / relative).exists())

    def test_other_user_skills_remain_untouched(self):
        """Verify sibling skills in the destination directory are never modified or removed."""
        sibling = self.home / ".agents/skills/my-other-skill"
        sibling.mkdir(parents=True)
        (sibling / "SKILL.md").write_text("my own skill\n", encoding="utf-8")
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual(self.install().returncode, 0)
        self.assertEqual((sibling / "SKILL.md").read_text(), "my own skill\n")

    def test_reinstall_does_not_change_local_executable_modes(self):
        """Verify reinstalling does not override existing file permission modes."""
        self.assertEqual(self.install().returncode, 0)
        cli = self.home / ".agents/skills/anti-slop-engineering/bin/cli.js"
        cli.chmod(0o600)
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(stat.S_IMODE(cli.stat().st_mode), 0o600)

    def test_symlinked_destination_is_rejected_without_touching_target(self):
        """Verify symlinked destination directories are safely rejected."""
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
        """Verify --project install does not create nested recursive skill copies."""
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

    @unittest.skipUnless(HAS_NODE, "Node.js required for plugin catalog selection")
    def test_bundled_module_conflicts_are_printed_as_readable_paths(self):
        """Verify bundled sub-module conflicts report clean readable destination paths."""
        source = self.home / "fixture"
        (source / "scripts").mkdir(parents=True)
        module = source / "skills/decision-guard"
        module.mkdir(parents=True)
        shutil.copy2(REPO / "install.sh", source / "install.sh")
        shutil.copy2(REPO / "scripts/safe_install.py", source / "scripts/safe_install.py")
        shutil.copy2(REPO / "scripts/installer.mjs", source / "scripts/installer.mjs")
        (source / "SKILL.md").write_text("core\n", encoding="utf-8")
        (module / "SKILL.md").write_text(
            "---\nname: decision-guard\ndescription: Decision checks\n---\nmodule v1\n",
            encoding="utf-8",
        )
        env = {**os.environ, "HOME": str(self.home / "home"), "PATH": SAFE_PATH}

        def install_fixture():
            # Core-first is now the default; explicitly select this optional module.
            return subprocess.run(["bash", "install.sh", "--skills=all"], cwd=source, env=env,
                                  capture_output=True, text=True)

        first = install_fixture()
        self.assertEqual(first.returncode, 0, first.stderr)
        installed = Path(env["HOME"]) / ".agents/skills/decision-guard/SKILL.md"
        self.assertTrue(installed.is_file(), first.stdout + first.stderr)
        installed.write_text("user edit\n", encoding="utf-8")
        (module / "SKILL.md").write_text(
            "---\nname: decision-guard\ndescription: Decision checks\n---\nmodule v2\n",
            encoding="utf-8",
        )
        result = install_fixture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Conflicts retained: SKILL.md", result.stdout)
        self.assertEqual(installed.read_text(), "user edit\n")

    @unittest.skipUnless(HAS_NODE, "Node.js runtime required to execute bin/cli.js")
    def test_universal_only_install_creates_executable_cli_links(self):
        """End-to-end smoke test verifying universal install creates executable CLI symlinks."""
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        cli = self.home / ".agents/skills/anti-slop-engineering/bin/cli.js"
        for name in ("anti-slop-engineering", "diff-guard", "sre-guard", "rust-guard", "toil-guard", "exec-guard"):
            link = self.home / ".local/bin" / name
            self.assertTrue(link.is_symlink(), f"Missing {link}")
            self.assertEqual(link.resolve(), cli)
            self.assertTrue(os.access(link, os.X_OK))
        primary = self.home / ".local/bin/anti-slop-engineering"
        self.assertEqual(subprocess.run([str(primary), "--help"], capture_output=True).returncode, 0)

    def test_runtime_independent_cli_link_creation(self):
        """Verify CLI link creation and target resolution without requiring Node.js."""
        source = self.home / "standalone-source"
        (source / "scripts").mkdir(parents=True)
        (source / "bin").mkdir()
        shutil.copy2(REPO / "install.sh", source / "install.sh")
        shutil.copy2(REPO / "scripts/safe_install.py", source / "scripts/safe_install.py")
        (source / "SKILL.md").write_text("standalone\n", encoding="utf-8")
        cli_fixture = source / "bin/cli.js"
        cli_fixture.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        cli_fixture.chmod(0o755)
        result = subprocess.run(
            ["bash", "install.sh"],
            cwd=source,
            env={**os.environ, "HOME": str(self.home), "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        expected_cli = self.home / ".agents/skills/anti-slop-engineering/bin/cli.js"
        for name in ("anti-slop-engineering", "diff-guard", "sre-guard", "rust-guard", "toil-guard", "exec-guard"):
            link = self.home / ".local/bin" / name
            self.assertTrue(link.is_symlink(), f"Missing {link}")
            self.assertEqual(link.resolve(), expected_cli)
            self.assertTrue(os.access(link, os.X_OK))

    def test_install_without_executable_cli_skips_links_safely(self):
        """When no executable CLI target is found, skills install cleanly and links are skipped."""
        source = self.home / "no-cli-source"
        (source / "scripts").mkdir(parents=True)
        shutil.copy2(REPO / "install.sh", source / "install.sh")
        shutil.copy2(REPO / "scripts/safe_install.py", source / "scripts/safe_install.py")
        (source / "SKILL.md").write_text("no-cli\n", encoding="utf-8")
        result = subprocess.run(
            ["bash", "install.sh"],
            cwd=source,
            env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("No executable CLI target", result.stderr)
        self.assertFalse((self.home / ".local/bin/anti-slop-engineering").exists())

    @unittest.skipUnless(HAS_NODE, "Node.js runtime required to execute bin/cli.js")
    def test_codex_install_links_to_existing_codex_cli(self):
        """Verify installation prioritizes Codex CLI when Codex agent environment exists."""
        (self.home / ".codex").mkdir()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.home / ".local/bin/anti-slop-engineering"
        self.assertEqual(link.resolve(), self.home / ".codex/skills/anti-slop-engineering/bin/cli.js")

    @unittest.skipUnless(HAS_NODE, "Node.js runtime required to execute bin/cli.js")
    def test_multi_agent_install_uses_verified_gemini_cli(self):
        """Verify Gemini CLI target is prioritized over Codex in multi-agent installations."""
        (self.home / ".gemini").mkdir()
        (self.home / ".codex").mkdir()
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        link = self.home / ".local/bin/anti-slop-engineering"
        self.assertEqual(link.resolve(), self.home / ".gemini/config/skills/anti-slop-engineering/bin/cli.js")

    @unittest.skipUnless(HAS_NODE, "Node.js runtime required to execute bin/cli.js")
    def test_existing_user_owned_links_are_preserved(self):
        """Verify user-owned CLI links and files are preserved with conflict warnings."""
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

    @unittest.skipUnless(HAS_NODE, "Node.js runtime required to execute bin/cli.js")
    def test_repeated_install_preserves_existing_valid_links(self):
        """Verify idempotency of CLI link creation across multiple installation runs."""
        self.assertEqual(self.install().returncode, 0)
        link = self.home / ".local/bin/anti-slop-engineering"
        first = link.lstat().st_ino
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(link.lstat().st_ino, first)

    def test_non_executable_cli_never_becomes_a_link_target(self):
        """Verify non-executable or failing CLI candidate is rejected and produces no links."""
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
        """Verify symlinked ~/.local directory paths abort before writing any links."""
        outside = self.home / "other-bin"
        outside.mkdir()
        (self.home / ".local").symlink_to(outside, target_is_directory=True)
        result = self.install()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symbolic link", result.stderr.lower())
        self.assertEqual(list(outside.iterdir()), [])

    def test_default_bash_install_selects_only_core_skill(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        skills = self.home / ".agents/skills"
        self.assertTrue((skills / "anti-slop-engineering/SKILL.md").exists())
        self.assertFalse((skills / "decision-guard").exists())

    @unittest.skipUnless(HAS_NODE, "Node.js required for plugin catalog selection")
    def test_bash_accepts_any_catalog_plugin_and_does_not_install_unselected_ones(self):
        result = subprocess.run(
            ["bash", str(REPO / "install.sh"), "--skills=api-ergonomics-and-contract-governor"],
            cwd=self.home, env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        skills = self.home / ".agents/skills"
        self.assertTrue((skills / "anti-slop-engineering/SKILL.md").exists())
        self.assertTrue((skills / "api-ergonomics-and-contract-governor/SKILL.md").exists())
        self.assertFalse((skills / "decision-guard").exists())

    def test_bash_rejects_unknown_plugin_before_creating_targets(self):
        result = subprocess.run(
            ["bash", str(REPO / "install.sh"), "--skills=missing-plugin"],
            cwd=self.home, env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
            capture_output=True, text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.home / ".agents/skills/anti-slop-engineering").exists())

    def test_bash_dry_run_does_not_install_files_or_links(self):
        result = subprocess.run(
            ["bash", str(REPO / "install.sh"), "--skills=decision-guard", "--dry-run"],
            cwd=self.home, env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("decision-guard", result.stdout)
        self.assertFalse((self.home / ".agents").exists())
        self.assertFalse((self.home / ".local").exists())

    @unittest.skipUnless(HAS_NODE, "Node.js required for plugin catalog selection")
    def test_bash_all_installs_every_valid_catalog_skill(self):
        result = subprocess.run(
            ["bash", str(REPO / "install.sh"), "--skills=all"],
            cwd=self.home, env={**os.environ, "HOME": str(self.home), "PATH": SAFE_PATH},
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        for entry in (REPO / "skills").iterdir():
            if entry.is_dir() and (entry / "SKILL.md").is_file():
                self.assertTrue((self.home / ".agents/skills" / entry.name / "SKILL.md").is_file(), entry.name)

    def test_bash_core_flags_succeed_even_without_node(self):
        """Verify --skills=core and -s core succeed even without Node.js in PATH."""
        env = {**os.environ, "HOME": str(self.home), "PATH": "/usr/bin:/bin"}
        result = subprocess.run(
            ["bash", str(REPO / "install.sh"), "--skills=core"],
            cwd=self.home, env=env, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        skills = self.home / ".agents/skills"
        self.assertTrue((skills / "anti-slop-engineering/SKILL.md").exists())
        self.assertFalse((skills / "decision-guard").exists())


if __name__ == "__main__":
    unittest.main()
