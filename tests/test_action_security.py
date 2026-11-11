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
            report = scripts / "pr_boundary_guard.py"
            report.write_text(
                "import json,sys\n"
                "args=sys.argv\n"
                "print(json.dumps({'findings': [], 'pr_metadata': "
                "{'title': args[args.index('--pr-title')+1]}}))\n",
                encoding="utf-8",
            )
            for script in ("audit_runner.py", "honeypot_trap_guard.py", "comment_budget_guard.py"):
                (scripts / script).write_text(
                    'print("{\\\"findings\\\": []}")\n', encoding="utf-8"
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
            pr_text = (workspace / "pr_boundary_result.json").read_text()
            self.assertTrue(pr_text.strip(), result.stdout + result.stderr)
            pr_result = json.loads(pr_text)
            self.assertEqual(pr_result["pr_metadata"]["title"], title)

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
            for overrides in (
                {"AUDIT_BASE": "--upload-pack=bad"},
                {"PR_BODY_FILE": "../outside.md"},
                {"TEMPLATE_FILE": "/etc/passwd"},
                {"FAIL_ON_BLOCKER": "$(touch invalid-boolean)"},
            ):
                with self.subTest(overrides=overrides):
                    result = subprocess.run(
                        ["bash", "-eo", "pipefail", "-c", shell], cwd=workspace,
                        env={**env, **overrides}, text=True, capture_output=True,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertFalse((workspace / "invalid-boolean").exists())


if __name__ == "__main__":
    unittest.main()
