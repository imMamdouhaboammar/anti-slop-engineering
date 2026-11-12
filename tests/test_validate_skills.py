import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import validate_skills

REPO_ROOT = Path(__file__).resolve().parent.parent


class ValidateSkillsTests(unittest.TestCase):
    def _build_fixture_repo(self, root: Path, skills: dict[str, str], agents_md: str) -> None:
        (root / "bin").mkdir(parents=True, exist_ok=True)
        (root / "bin" / "cli.js").write_text(
            'if (cmd === "check") {}\nif (cmd === "audit") {}\n',
            encoding="utf-8",
        )
        (root / "scripts").mkdir(parents=True, exist_ok=True)
        (root / "scripts" / "real_guard.py").write_text("print('ok')\n", encoding="utf-8")
        (root / "AGENTS.md").write_text(agents_md, encoding="utf-8")
        for name, content in skills.items():
            skill_dir = root / "skills" / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(content, encoding="utf-8")

    def test_repository_skills_and_agents_pointers_pass_clean_checkout(self):
        report = validate_skills.validate_repository(REPO_ROOT, strict_cli=False)
        self.assertTrue(report["ok"], report["errors"])
        self.assertEqual(report["skills_checked"], 39)
        self.assertEqual(report["errors"], [])

    def test_single_file_skill_without_optional_directories_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build_fixture_repo(
                root,
                skills={
                    "lean-skill": (
                        "---\n"
                        "name: lean-skill\n"
                        "description: Single-file skill without scripts or references.\n"
                        "---\n\n"
                        "# Lean Skill\n"
                        "Run `npx anti-slop-engineering check --base HEAD`.\n"
                    )
                },
                agents_md="- `lean-skill`: `skills/lean-skill/SKILL.md`\n",
            )
            report = validate_skills.validate_repository(root, strict_cli=True)
            self.assertTrue(report["ok"], report["errors"])
            self.assertEqual(report["skills_checked"], 1)

    def test_rejects_broken_agents_pointer_to_untracked_dot_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build_fixture_repo(
                root,
                skills={
                    "demo-skill": "---\nname: demo-skill\ndescription: Valid skill.\n---\n"
                },
                agents_md="- `demo-skill`: `.agents/skills/demo-skill/SKILL.md`\n",
            )
            report = validate_skills.validate_repository(root, strict_cli=True)
            self.assertFalse(report["ok"])
            self.assertTrue(
                any(".agents/skills/demo-skill/SKILL.md" in err for err in report["errors"]),
                report["errors"],
            )

    def test_rejects_missing_or_mismatched_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build_fixture_repo(
                root,
                skills={
                    "alpha-skill": "---\nname: wrong-name\ndescription: Mismatched.\n---\n",
                    "beta-skill": "---\nname: beta-skill\n---\n# Missing description\n",
                },
                agents_md="",
            )
            report = validate_skills.validate_repository(root)
            self.assertFalse(report["ok"])
            joined = "\n".join(report["errors"])
            self.assertIn("does not match directory 'alpha-skill'", joined)
            self.assertIn("missing frontmatter 'description'", joined)

    def test_rejects_broken_markdown_link_and_missing_script(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build_fixture_repo(
                root,
                skills={
                    "broken-links": (
                        "---\n"
                        "name: broken-links\n"
                        "description: Skill with broken pointer and missing script.\n"
                        "---\n"
                        "See [Contract](references/missing.md) and run `python3 scripts/missing_guard.py`.\n"
                    )
                },
                agents_md="",
            )
            report = validate_skills.validate_repository(root)
            self.assertFalse(report["ok"])
            joined = "\n".join(report["errors"])
            self.assertIn("references/missing.md", joined)
            self.assertIn("scripts/missing_guard.py", joined)

    def test_strict_cli_flags_unrouted_command_and_cli_json_output_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._build_fixture_repo(
                root,
                skills={
                    "unrouted-skill": (
                        "---\n"
                        "name: unrouted-skill\n"
                        "description: Advertises an unrouted CLI command.\n"
                        "---\n"
                        "Run `npx anti-slop-engineering nonexistent-cmd audit record.json`.\n"
                    )
                },
                agents_md="",
            )
            non_strict = validate_skills.validate_repository(root, strict_cli=False)
            self.assertTrue(non_strict["ok"])
            self.assertEqual(len(non_strict["missing_cli_handlers"]), 1)

            strict_proc = subprocess.run(
                [sys.executable, str(REPO_ROOT / "scripts" / "validate_skills.py"), "--repo", str(root), "--strict-cli", "--json"],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(strict_proc.returncode, 1)
            payload = json.loads(strict_proc.stdout)
            self.assertFalse(payload["ok"])
            self.assertTrue(any("nonexistent-cmd" in err for err in payload["errors"]))


if __name__ == "__main__":
    unittest.main()
