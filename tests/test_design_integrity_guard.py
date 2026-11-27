import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DesignIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.outer = Path(self.tmp.name).resolve()
        self.repo = self.outer / "repo"
        self.design = self.repo / ".anti-slop/design"
        self.design.mkdir(parents=True)
        self.trust = self.outer / "trust.json"
        self.key = self.outer / "owner"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.key)], check=True)
        self.contract = self.design / "contract.json"
        self.signature = self.design / "contract.json.sig"
        self.env = dict(os.environ, ANTI_SLOP_DESIGN_TRUST=str(self.trust))
        self.record = {
            "schema_version": 1,
            "repository_id": "example/project",
            "tokens": {"--color-text": "#202020"},
            "components": ["Button"],
            "surfaces": ["settings"],
            "artifacts": {},
        }
        for name in ("PRODUCT.md", "DESIGN.md"):
            data = b"Approved design specification\n"
            (self.repo / name).write_bytes(data)
            self.record["artifacts"][name] = hashlib.sha256(data).hexdigest()
        self.publish_trust()

    def publish_trust(self):
        self.trust.write_text(
            json.dumps(
                {
                    "workspace": str(self.repo),
                    "repository_id": "example/project",
                    "manifest_sha256": hashlib.sha256(self.contract.read_bytes()).hexdigest()
                    if self.contract.exists()
                    else "0" * 64,
                    "public_key": self.key.with_suffix(".pub").read_text().split()[0]
                    + " "
                    + self.key.with_suffix(".pub").read_text().split()[1],
                    "non_ui_paths": ["server/health.py"],
                }
            )
        )

    def seal(self, key=None):
        self.contract.write_text(json.dumps(self.record))
        if self.signature.exists():
            self.signature.unlink()
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(key or self.key), "-n", "anti-slop-design-v1", str(self.contract)],
            check=True,
            capture_output=True,
        )
        self.publish_trust()

    def cli(self, *args, expected=0):
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/design_integrity_guard.py"), *args],
            cwd=self.repo,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def hook(self, operation, paths, phase="pre_tool"):
        event = {
            "schema_version": 1,
            "agent": "codex",
            "tool": "edit",
            "correlation_id": "test",
            "phase": phase,
            "operation": operation,
            "payload_trust": "untrusted",
            "target_paths": paths,
        }
        result = subprocess.run(
            ["python3", str(ROOT / "scripts/exec_guard.py"), "hook-event"],
            cwd=self.repo,
            env=self.env,
            input=json.dumps(event),
            capture_output=True,
            text=True,
        )
        return json.loads(result.stdout)

    def test_missing_contract_blocks_ui_but_not_explicit_backend(self):
        self.assertEqual(self.cli("check", "src/App.tsx", expected=2)["reason_code"], "UI_CONTRACT_MISSING")
        self.assertEqual(self.cli("check", "server/health.py")["reason_code"], "UI_NON_UI_PATHS")

    def test_valid_approval_allows_known_path(self):
        self.seal()
        self.assertEqual(self.cli("verify")["reason_code"], "UI_CONTRACT_VERIFIED")
        self.assertEqual(self.cli("check", "src/App.tsx")["reason_code"], "UI_CONTRACT_VERIFIED")

    def test_hash_rewrite_does_not_forge_signature(self):
        self.seal()
        self.record["tokens"]["--color-text"] = "#ff00ff"
        self.contract.write_text(json.dumps(self.record))
        self.publish_trust()
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_SIGNATURE_INVALID")

    def test_other_key_not_trusted(self):
        key = self.outer / "other"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(key)], check=True)
        self.seal(key)
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_SIGNATURE_INVALID")

    def test_manifest_pin_rejects_changed_bytes(self):
        self.seal()
        self.contract.write_bytes(self.contract.read_bytes() + b" ")
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_MANIFEST_NOT_APPROVED")

    def test_cross_repository_replay(self):
        self.record["repository_id"] = "other/project"
        self.seal()
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_REPOSITORY_MISMATCH")

    def test_empty_contract_is_not_valid(self):
        self.record["tokens"] = {}
        self.seal()
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_CONTRACT_INVALID")

    def test_artifact_drift(self):
        self.seal()
        (self.repo / "DESIGN.md").write_text("Unapproved")
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_ARTIFACT_DRIFT")

    def test_hook_denies_when_exec_control_inactive(self):
        self.assertEqual(self.hook("write", ["src/App.tsx"])["reason_code"], "UI_CONTRACT_MISSING")
        self.assertEqual(self.hook("read", ["src/App.tsx"])["decision"], "allow")
        self.assertEqual(self.hook("write", ["server/health.py"])["decision"], "allow")

    def test_hook_blocks_protected_and_unknown_mutations_even_after_seal(self):
        self.seal()
        self.assertEqual(self.hook("write", ["DESIGN.md"])["reason_code"], "UI_PROTECTED_PATH")
        self.assertEqual(self.hook("unknown", [])["reason_code"], "UI_IMPACT_UNKNOWN")
        self.assertEqual(self.hook("write", ["src/App.tsx"])["decision"], "allow")

    def test_symlink_cannot_hide_protected_target(self):
        self.seal()
        (self.repo / "server").mkdir()
        (self.repo / "server/health.py").symlink_to(self.repo / "DESIGN.md")
        self.assertEqual(self.hook("write", ["server/health.py"])["decision"], "block")

    def test_trust_inside_workspace_is_rejected(self):
        self.seal()
        path = self.repo / "trust.json"
        path.write_bytes(self.trust.read_bytes())
        self.env["ANTI_SLOP_DESIGN_TRUST"] = str(path)
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_TRUST_INVALID")

    def test_signed_artifact_cannot_be_excluded_as_backend(self):
        data = b"Approved artifact"
        (self.repo / "server").mkdir()
        (self.repo / "server/health.py").write_bytes(data)
        self.record["artifacts"]["server/health.py"] = hashlib.sha256(data).hexdigest()
        self.seal()
        self.assertEqual(self.hook("write", ["server/health.py"])["reason_code"], "UI_PROTECTED_PATH")

    def test_unapproved_protected_path_fails_diff_check(self):
        self.seal()
        self.assertEqual(self.cli("check", ".github/workflows/ci.yml", expected=2)["reason_code"], "UI_PROTECTED_PATH")

    def test_css_token_reference_and_override(self):
        self.seal()
        path = self.repo / "theme.css"
        path.write_text(".button { color: var(--color-text); }")
        self.assertEqual(self.cli("check", "theme.css")["reason_code"], "UI_CONTRACT_VERIFIED")
        path.write_text(".button { color: var(--invented); }")
        self.assertEqual(self.cli("check", "theme.css", expected=2)["reason_code"], "UI_UNAPPROVED_TOKEN")
        path.write_text(":root { --color-text: #ffffff; }")
        self.assertEqual(self.cli("check", "theme.css", expected=2)["reason_code"], "UI_UNAPPROVED_TOKEN")
        path.write_text(".button { color: #202020; }")
        self.assertEqual(self.cli("check", "theme.css", expected=2)["reason_code"], "UI_UNAPPROVED_TOKEN")

    def test_css_comments_and_approved_definition(self):
        self.seal()
        (self.repo / "theme.css").write_text("/* color: #abc; var(--unknown) */ :root { --color-text: #202020; }")
        self.assertEqual(self.cli("check", "theme.css")["reason_code"], "UI_CONTRACT_VERIFIED")

    def test_diff_includes_untracked_and_staged_paths(self):
        self.seal()
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
                "-c",
                "user.email=test@example.com",
                "-c",
                "user.name=Test",
                "commit",
                "-qm",
                "base",
            ],
            check=True,
        )
        self.assertEqual(self.cli("check", "--base", "HEAD")["decision"], "allow")
        (self.repo / "new.css").write_text(".x { color: #123456; }")
        self.assertEqual(self.cli("check", "--base", "HEAD", expected=2)["reason_code"], "UI_UNAPPROVED_TOKEN")
        subprocess.run(["git", "-C", str(self.repo), "add", "new.css"], check=True)
        self.assertEqual(self.cli("check", "--base", "HEAD", expected=2)["reason_code"], "UI_UNAPPROVED_TOKEN")
        (self.repo / "new.css").unlink()
        self.assertEqual(self.cli("check", "--base", "HEAD", expected=2)["reason_code"], "UI_IMPACT_UNKNOWN")

    def test_post_tool_warns_on_css_violation(self):
        self.seal()
        (self.repo / "theme.css").write_text(".button { color: var(--unknown); }")
        decision = self.hook("write", ["theme.css"], phase="post_tool")
        self.assertEqual(decision["decision"], "warn")
        self.assertEqual(decision["reason_code"], "UI_UNAPPROVED_TOKEN")

    def test_codex_and_claude_adapter_output(self):
        events = [
            (
                "codex_hooks.py",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "apply_patch",
                    "tool_use_id": "fixture-call",
                    "tool_input": {"command": "*** Begin Patch\n*** Add File: App.tsx\n+test\n*** End Patch\n"},
                    "cwd": str(self.repo),
                },
            ),
            (
                "claude_hooks.py",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Write",
                    "tool_use_id": "fixture-call",
                    "tool_input": {"file_path": str(self.repo / "App.tsx")},
                    "cwd": str(self.repo),
                },
            ),
        ]
        for script, payload in events:
            with self.subTest(script=script):
                proc = subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts" / script),
                        "evaluate",
                        "--project",
                        str(self.repo),
                        "--phase",
                        "PreToolUse",
                    ],
                    cwd=self.repo,
                    env=self.env,
                    input=json.dumps(payload),
                    text=True,
                    capture_output=True,
                    check=True,
                )
                result = json.loads(proc.stdout)["hookSpecificOutput"]
                self.assertEqual(result["permissionDecision"], "deny")
                self.assertIn("No approved manifest", result["permissionDecisionReason"])

    def test_discovery_is_unapproved_and_read_only(self):
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        (self.repo / "theme.css").write_text(":root { --text: #202020; --gap: 8px; }")
        output = self.cli("discover")
        self.assertEqual(output["state"], "DISCOVERED")
        self.assertFalse(output["approved"])
        self.assertEqual(output["sources"][0]["tokens"], {"--text": ["#202020"], "--gap": ["8px"]})
        self.assertFalse(self.contract.exists())
        self.assertFalse(self.signature.exists())

    def test_preview_is_not_approval(self):
        self.contract.write_text(json.dumps(self.record))
        output = self.cli("preview")
        self.assertFalse(output["approved"])
        self.assertIn("--color-text: #202020;", output["css"])
        self.assertFalse(self.signature.exists())

    def test_invalid_css_token_cannot_generate_preview(self):
        self.record["tokens"]["--color-text"] = "red; } body { display: none"
        self.contract.write_text(json.dumps(self.record))
        self.assertEqual(self.cli("preview", expected=2)["reason_code"], "UI_CONTRACT_INVALID")

    def test_proposal_preview_uses_unsealed_path(self):
        proposal = self.design / "proposals" / "candidate.json"
        proposal.parent.mkdir()
        proposal.write_text(json.dumps(self.record))
        output = self.cli("preview", "--file", ".anti-slop/design/proposals/candidate.json")
        self.assertFalse(output["approved"])
        self.assertIn("--color-text: #202020;", output["css"])
        self.assertFalse(self.contract.exists())

    def test_literal_color_and_spacing_are_not_token_consumption(self):
        self.record["tokens"]["--space-2"] = "8px"
        self.seal()
        path = self.repo / "theme.css"
        for css in (
            ".x { color: red; }",
            ".x { background-color: rgb(0, 0, 0); }",
            ".x { padding: 8px; }",
            ".x { font-family: Arial; }",
            ".x { color: var(--color-text, red); }",
        ):
            with self.subTest(css=css):
                path.write_text(css)
                self.assertEqual(self.cli("check", "theme.css", expected=2)["reason_code"], "UI_UNAPPROVED_TOKEN")
        path.write_text(".x { color: var(--color-text); padding: 0 var(--space-2); }")
        self.assertEqual(self.cli("check", "theme.css")["reason_code"], "UI_CONTRACT_VERIFIED")

    def test_proposals_are_editable_during_drift_but_cannot_be_signed(self):
        self.seal()
        (self.repo / "DESIGN.md").write_text("drift")
        self.assertEqual(self.hook("write", [".anti-slop/design/proposals/candidate.json"])["decision"], "allow")
        self.record["artifacts"][".anti-slop/design/proposals/candidate.json"] = "1" * 64
        self.seal()
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_CONTRACT_INVALID")

    def test_old_valid_signature_cannot_replay_after_new_pin(self):
        self.seal()
        old_data, old_sig = self.contract.read_bytes(), self.signature.read_bytes()
        self.record["tokens"]["--color-text"] = "#101010"
        self.seal()
        self.contract.write_bytes(old_data)
        self.signature.write_bytes(old_sig)
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_MANIFEST_NOT_APPROVED")

    def enable_v2(self):
        self.record["schema_version"] = 2
        policy = {
            "schema_version": 1,
            "allowed_classes": ["flex", "gap-2", "text-primary"],
            "browser": {"channel": "chrome", "version": "test-version"},
            "scenarios": [
                {
                    "id": "settings-mobile",
                    "surface": "settings",
                    "path": "/settings",
                    "viewport": [390, 844],
                    "direction": "ltr",
                    "state": "ready",
                    "components": {"Button": [1, 2]},
                    "baseline": ".anti-slop/design/baselines/settings.png",
                    "checks": {
                        "min_target": 24,
                        "no_horizontal_overflow": True,
                        "align": [],
                        "no_overlap": [],
                        "computed": [],
                    },
                }
            ],
        }
        path = self.design / "policy.json"
        path.write_text(json.dumps(policy))
        self.record["artifacts"][".anti-slop/design/policy.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
        baseline = self.design / "baselines/settings.png"
        baseline.parent.mkdir(exist_ok=True)
        baseline.write_bytes(b"synthetic baseline fixture")
        self.record["artifacts"][".anti-slop/design/baselines/settings.png"] = hashlib.sha256(
            baseline.read_bytes()
        ).hexdigest()
        self.seal()
        return policy

    def test_v2_requires_signed_policy(self):
        self.record["schema_version"] = 2
        self.seal()
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_CONTRACT_INVALID")

    def test_v2_blocks_unknown_component_and_utility(self):
        self.enable_v2()
        path = self.repo / "App.tsx"
        path.write_text('<Button className="flex gap-2" />')
        self.assertEqual(self.cli("check", "App.tsx")["decision"], "allow")
        path.write_text('<InventedCard className="flex" />')
        self.assertEqual(self.cli("check", "App.tsx", expected=2)["reason_code"], "UI_UNAPPROVED_COMPONENT")
        path.write_text('<Button className="bg-purple-500 p-[13px]" />')
        self.assertEqual(self.cli("check", "App.tsx", expected=2)["reason_code"], "UI_UNAPPROVED_UTILITY")

    def test_v2_blocks_inline_and_dynamic_style(self):
        self.enable_v2()
        path = self.repo / "App.tsx"
        for source in ('<Button style={{color: "red"}} />', "<Button className={computed} />"):
            with self.subTest(source=source):
                path.write_text(source)
                self.assertEqual(self.cli("check", "App.tsx", expected=2)["reason_code"], "UI_STYLE_UNVERIFIED")
        path.write_text('<Button className={"flex text-primary"} />')
        self.assertEqual(self.cli("check", "App.tsx")["decision"], "allow")

    def test_v2_policy_cannot_omit_surface_or_unsigned_baseline(self):
        policy = self.enable_v2()
        policy["scenarios"][0]["baseline"] = "unsigned.png"
        path = self.design / "policy.json"
        path.write_text(json.dumps(policy))
        self.record["artifacts"][".anti-slop/design/policy.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.seal()
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_POLICY_INVALID")

    def test_v2_html_class_and_component(self):
        self.enable_v2()
        path = self.repo / "settings.html"
        path.write_text('<button data-design-component="Button" class="flex">Save</button>')
        self.assertEqual(self.cli("check", "settings.html")["decision"], "allow")
        path.write_text('<button data-design-component="Mystery" class="flex">Save</button>')
        self.assertEqual(self.cli("check", "settings.html", expected=2)["reason_code"], "UI_UNAPPROVED_COMPONENT")

    def test_runtime_requires_v2_approval(self):
        self.seal()
        self.assertEqual(
            self.cli("runtime", "--origin", "http://127.0.0.1:43100", expected=2)["reason_code"], "UI_POLICY_INVALID"
        )

    def test_ci_does_not_accept_external_origin(self):
        self.enable_v2()
        self.assertEqual(
            self.cli("runtime", "--origin", "https://example.com", expected=2)["reason_code"],
            "UI_RENDER_EVIDENCE_MISSING",
        )

    def test_v2_rejects_unapproved_policy_mutation(self):
        self.enable_v2()
        path = self.design / "policy.json"
        path.write_text("{}")
        self.assertEqual(
            self.cli("runtime", "--origin", "http://127.0.0.1:43100", expected=2)["reason_code"], "UI_ARTIFACT_DRIFT"
        )

    def test_dtcg_import_is_unapproved_and_preserves_alias(self):
        path = self.repo / "tokens.json"
        path.write_text(
            json.dumps(
                {
                    "color": {
                        "$type": "color",
                        "ink": {"$value": {"colorSpace": "srgb", "components": [0, 0.125, 1], "alpha": 1}},
                        "text": {"$value": "{color.ink}"},
                    },
                    "spacing": {"small": {"$type": "dimension", "$value": {"value": 8, "unit": "px"}}},
                }
            )
        )
        report = self.cli("import", "--file", "tokens.json")
        self.assertFalse(report["approved"])
        self.assertEqual(
            report["tokens"],
            {"--color-ink": "color(srgb 0 0.125 1 / 1)", "--color-text": "var(--color-ink)", "--spacing-small": "8px"},
        )
        self.assertEqual(report["sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertFalse(self.contract.exists())

    def test_dtcg_import_rejects_cycles_and_normalization_collision(self):
        path = self.repo / "tokens.json"
        records = [
            {"a": {"$type": "number", "$value": "{b}"}, "b": {"$type": "number", "$value": "{a}"}},
            {"a-b": {"$type": "number", "$value": 1}, "a": {"b": {"$type": "number", "$value": 2}}},
            {"unknown": {"$type": "shadow", "$value": {"color": "black"}}},
        ]
        for record in records:
            with self.subTest(record=record):
                path.write_text(json.dumps(record))
                self.assertEqual(
                    self.cli("import", "--file", "tokens.json", expected=2)["reason_code"], "UI_REFERENCE_UNSUPPORTED"
                )

    def test_extension_transport_cannot_be_used_with_web_policy(self):
        self.enable_v2()
        self.assertEqual(
            self.cli("runtime", "--extension-dir", str(self.outer), expected=2)["reason_code"], "UI_POLICY_INVALID"
        )

    def test_extension_policy_requires_signed_identity_and_chromium(self):
        self.record["schema_version"] = 3
        policy = self.enable_v2()
        self.record["schema_version"] = 3
        policy["extension"] = {"id": "a" * 32}
        path = self.design / "policy.json"
        path.write_text(json.dumps(policy))
        self.record["artifacts"][".anti-slop/design/policy.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.seal()
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_POLICY_INVALID")

    def test_proposal_directory_does_not_exempt_executable_source(self):
        path = self.design / "proposals" / "bypass.css"
        path.parent.mkdir()
        path.write_text(".x{color:red}")
        self.assertEqual(self.hook("write", [str(path)])["decision"], "block")
        self.seal()
        self.assertEqual(self.cli("check", str(path), expected=2)["reason_code"], "UI_PROTECTED_PATH")

    def test_proposal_json_remains_editable(self):
        path = self.design / "proposals" / "candidate.json"
        path.parent.mkdir()
        path.write_text("{}")
        self.assertEqual(self.hook("write", [str(path)])["decision"], "allow")


if __name__ == "__main__":
    unittest.main()
