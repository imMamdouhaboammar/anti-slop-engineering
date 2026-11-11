import json
import os
import re
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path


ACTION = Path(__file__).resolve().parents[1] / "action.yml"


def action_step():
    source = ACTION.read_text(encoding="utf-8")
    lines = source.splitlines()
    index = next(i for i, line in enumerate(lines) if line.strip() == "run: |")
    indent = len(lines[index]) - len(lines[index].lstrip())
    body = []
    for line in lines[index + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= indent:
            break
        body.append(line)
    return source, textwrap.dedent("\n".join(body))


class CompositeActionInputTests(unittest.TestCase):
    def test_caller_inputs_are_never_shell_source(self):
        _, shell = action_step()
        self.assertNotRegex(shell, r"\$\{\{\s*inputs\.")

    def test_adversarial_title_stays_literal(self):
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            marker = workspace / "unexpected-command"
            title = "fix: $(touch " + str(marker) + ")"
            fake_action = workspace / "action"
            scripts = fake_action / "scripts"
            scripts.mkdir(parents=True)
            (scripts / "audit_runner.py").write_text(
                "import json, os, sys\n"
                "def guard_commands(base='HEAD', canary_token='', **kwargs):\n"
                "    optional = {'invariant_steward_guard'}\n"
                "    if not canary_token: optional.add('honeypot_trap_guard')\n"
                "    return [(name, None if name in optional else ['python']) "
                "for name in os.environ['EXPECTED_GUARDS'].split(',')]\n"
                "if __name__ == '__main__':\n"
                "    title = sys.argv[sys.argv.index('--pr-title') + 1]\n"
                "    checks = {name: {'status': 'SKIPPED' if cmd is None else 'PASS', "
                "'applicable': cmd is not None, 'exit_code': None if cmd is None else 0, "
                "'findings_count': 0} for name, cmd in guard_commands()}\n"
                "    checks['pr_boundary_guard']['pr_metadata'] = {'title': title}\n"
                "    print(json.dumps({'status': 'PASS', 'total_findings': 0, "
                "'blockers_count': 0, 'findings': [], 'guards': checks}))\n",
                encoding="utf-8",
            )
            (scripts / "action_result.py").write_bytes(
                (ACTION.parent / "scripts" / "action_result.py").read_bytes()
            )
            subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-q", "--allow-empty", "-m", "fixture"],
                cwd=workspace, check=True,
            )
            source, shell = action_step()
            expressions = {
                "base": "HEAD",
                "pr-title": title,
                "pr-body-file": "",
                "template-file": ".github/pull_request_template.md",
                "canary-token": "",
                "fail-on-blocker": "false",
            }
            env = os.environ.copy()
            env.update({
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(workspace / "outputs"),
                "GITHUB_ACTION_PATH": str(fake_action),
                "ACTION_PATH": str(fake_action),
                "EXPECTED_GUARDS": ",".join((
                    "diff_guard", "sre_guard", "ast_slop_guard", "contrast_guard",
                    "comment_budget_guard", "pr_boundary_guard", "invariant_steward_guard",
                    "attention_guard", "system_drift_guard", "chroma_drift_guard",
                    "styleseed_guard", "honeypot_trap_guard",
                )),
            })
            for name, key in re.findall(r"(?m)^\s+([A-Z][A-Z_]+):\s*\$\{\{\s*inputs\.([\w-]+)\s*}}", source):
                env[name] = expressions[key]
            for key, value in expressions.items():
                shell = shell.replace("${{ inputs." + key + " }}", value)
            shell = shell.replace("${{ github.action_path }}", str(fake_action))
            result = subprocess.run(
                ["bash", "-eo", "pipefail", "-c", shell],
                cwd=workspace, env=env, text=True, capture_output=True,
            )
            self.assertFalse(marker.exists(), result.stderr)
            self.assertEqual(result.returncode, 0, result.stderr)
            report = json.loads((workspace / "audit_result.json").read_text())
            self.assertEqual(report["guards"]["pr_boundary_guard"]["pr_metadata"]["title"], title)

    def test_rejects_invalid_base_and_escaped_input_paths(self):
        _, shell = action_step()
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
            subprocess.run(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.com",
                 "commit", "-q", "--allow-empty", "-m", "fixture"],
                cwd=workspace, check=True,
            )
            env = os.environ.copy()
            env.update({
                "GITHUB_WORKSPACE": str(workspace),
                "GITHUB_OUTPUT": str(workspace / "outputs"),
                "ACTION_PATH": str(workspace / "action"),
                "AUDIT_BASE": "HEAD",
                "PR_TITLE": "",
                "PR_BODY_FILE": "",
                "TEMPLATE_FILE": "",
                "CANARY_TOKEN": "",
                "FAIL_ON_BLOCKER": "false",
            })
            for overrides, expected_exit, expected_error in (
                ({"AUDIT_BASE": "--upload-pack=bad"}, 2, "Invalid audit base revision"),
                ({"PR_BODY_FILE": "../outside.md"}, 1, "Input file path must stay inside"),
                ({"TEMPLATE_FILE": "/etc/passwd"}, 1, "Input file path must stay inside"),
                ({"FAIL_ON_BLOCKER": "$(touch invalid-boolean)"}, 2, "Invalid fail-on-blocker value"),
            ):
                with self.subTest(overrides=overrides):
                    result = subprocess.run(
                        ["bash", "-eo", "pipefail", "-c", shell], cwd=workspace,
                        env={**env, **overrides}, text=True, capture_output=True,
                    )
                    self.assertEqual(result.returncode, expected_exit, result.stderr)
                    self.assertIn(expected_error, result.stderr)
                    self.assertFalse((workspace / "invalid-boolean").exists())


if __name__ == "__main__":
    unittest.main()
