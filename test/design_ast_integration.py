"""Opt-in signed v3 tests using installed, lockfile-pinned AST parsers."""

import hashlib
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import test_design_integrity_guard as fixtures


class AstContractTests(fixtures.DesignIntegrityTests):
    def setUp(self):
        super().setUp()
        self.enable_v2()
        self.record["schema_version"] = 3
        self.seal()

    def check_text(self, name, source, expected=None):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        report = self.cli("check", name, expected=2 if expected else 0)
        self.assertEqual(report["reason_code"], expected or "UI_CONTRACT_VERIFIED")

    def test_v3_jsx_parser_handles_text_comments_and_dynamic_branches(self):
        self.check_text(
            "App.tsx",
            'const text = "<Fake className=red>"; export const App = () => <Button className={true ? "flex" : "gap-2"} />;',
        )
        self.check_text("App.tsx", '<Button className={flag ? "flex" : "bg-purple-500"} />', "UI_UNAPPROVED_UTILITY")
        self.check_text("App.tsx", "<Button className={value} />", "UI_STYLE_UNVERIFIED")
        self.check_text("App.tsx", "<Button {...props} />", "UI_STYLE_UNVERIFIED")
        self.check_text("App.tsx", "<Unknown />", "UI_UNAPPROVED_COMPONENT")
        self.check_text("App.tsx", '<Button className="flex"', "UI_SOURCE_PARSE_FAILED")

    def test_v3_css_parser_catches_nested_and_escaped_declarations(self):
        self.check_text("app.css", "@media (width > 300px) { .x { color: var(--color-text); } }")
        self.check_text("app.css", r".x { c\6flor: red; }", "UI_UNAPPROVED_TOKEN")
        self.check_text("app.css", ".x { border: 1px solid red; }", "UI_UNAPPROVED_TOKEN")
        self.check_text("app.css", ".x { background: linear-gradient(red, blue); }", "UI_UNAPPROVED_TOKEN")
        self.check_text("app.css", ".x { color: var(--color-text, red); }", "UI_UNAPPROVED_TOKEN")
        self.check_text("app.css", '@import "external.css";', "UI_STYLE_UNVERIFIED")

    def test_v3_html_parser_normalizes_attribute_case_and_entities(self):
        self.check_text("popup.html", '<button DATA-DESIGN-COMPONENT=Button CLASS="fl&#101;x">Go</button>')
        self.check_text("popup.html", '<button STYLE="color:red">Go</button>', "UI_STYLE_UNVERIFIED")
        self.check_text("popup.html", "<button class=bg-purple-500>Go</button>", "UI_UNAPPROVED_UTILITY")
        self.check_text("popup.html", "<style>.x{color:red}</style>", "UI_UNAPPROVED_TOKEN")

    def test_v3_javascript_dom_sinks_are_not_silently_ignored(self):
        self.check_text("render.ts", "const count = 3;")
        for source in (
            'el.style.color = "red";',
            'el.classList.add("red");',
            'el.setAttribute("class", "red");',
            'el["innerHTML"] = html;',
            'React.createElement("div", {className: "red"});',
        ):
            with self.subTest(source=source):
                self.check_text("render.ts", source, "UI_STYLE_UNVERIFIED")

    def test_v3_unsupported_source_needs_signed_artifact_or_external_exemption(self):
        self.check_text("App.vue", "<template><div/></template>", "UI_IMPACT_UNKNOWN")
        self.check_text("server/health.py", "print('ok')")
        path = self.repo / "theme.scss"
        path.write_text(".x { color: red; }")
        self.record["artifacts"]["theme.scss"] = hashlib.sha256(path.read_bytes()).hexdigest()
        self.seal()
        self.assertEqual(self.cli("check", "theme.scss")["decision"], "allow")

    def test_v3_unapproved_inspection_lists_each_file_without_signing(self):
        (self.repo / "good.tsx").write_text('<Button className="flex" />')
        (self.repo / "bad.css").write_text(".x {color: red;}")
        report = self.cli(
            "inspect",
            "--file",
            ".anti-slop/design/contract.json",
            "--policy-file",
            ".anti-slop/design/policy.json",
            "good.tsx",
            "bad.css",
            expected=2,
        )
        self.assertFalse(report["approved"])
        self.assertEqual(report["summary"], {"checked": 2, "passed": 1, "blocked": 1})
        self.assertEqual(report["findings"][0]["path"], "bad.css")
        self.assertEqual(report["findings"][0]["reason_code"], "UI_UNAPPROVED_TOKEN")

    def test_v3_missing_parser_fails_closed(self):
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
        from design_integrity_guard import DesignRejection, ast_result

        with patch("design_integrity_guard.shutil.which", return_value=None):
            with self.assertRaises(DesignRejection) as error:
                ast_result("app.css", ".x {color: red;}", self.record, {})
        self.assertEqual(error.exception.code, "UI_PARSER_UNAVAILABLE")

    def test_v3_adversarial_source_rejections(self):
        cases = [
            ("app.css", ".x{border-radius:999px}", "UI_UNAPPROVED_TOKEN"),
            ("app.css", ".x{border-start-start-radius:999px}", "UI_UNAPPROVED_TOKEN"),
            ("app.css", ".x{width:991px}", "UI_UNAPPROVED_TOKEN"),
            ("app.css", ".x{transform:scale(4)}", "UI_UNAPPROVED_TOKEN"),
            ("app.css", ".x{background-image:element(#other)}", "UI_UNAPPROVED_TOKEN"),
            ("App.tsx", '<svg><path d="M0 0L1 1" /></svg>', "UI_STYLE_UNVERIFIED"),
            ("App.tsx", '<link rel="stylesheet" href="https://example.invalid/theme.css" />', "UI_STYLE_UNVERIFIED"),
            ("App.tsx", '<div STYLE="color:red" />', "UI_STYLE_UNVERIFIED"),
            ("app.html", '<link rel="stylesheet" href=" https://example.invalid/theme.css">', "UI_STYLE_UNVERIFIED"),
            ("app.html", '<svg><path d="M0 0L1 1"/></svg>', "UI_STYLE_UNVERIFIED"),
            ("app.ts", 'el["st" + "yle"].color = "red";', "UI_STYLE_UNVERIFIED"),
            ("app.ts", 'const {style} = el; style.color = "red";', "UI_STYLE_UNVERIFIED"),
            ("app.ts", 'const obj = {["class" + "Name"]: "bad"};', "UI_STYLE_UNVERIFIED"),
        ]
        for name, source, code in cases:
            with self.subTest(source=source):
                self.check_text(name, source, code)

    def test_v3_adversarial_valid_changes(self):
        cases = [
            ("app.css", ".x{display:flex; color:var(--color-text); width:100%; height:auto}"),
            ("App.tsx", '<Button className={active ? "flex" : "gap-2"}>Save</Button>'),
            ("app.html", '<button class="flex">Save</button>'),
            ("app.ts", "const totals = {count: 1}; const next = totals.count + 1;"),
        ]
        for name, source in cases:
            with self.subTest(source=source):
                self.check_text(name, source)

    def test_v3_ci_rejects_dirty_or_hidden_candidate_state(self):
        path = self.repo / "app.ts"
        path.write_text("const count = 1;")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)

        def git(*args):
            subprocess.run(["git", "-C", str(self.repo), *args], check=True)

        git("add", ".")
        git("-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "base")
        path.write_text("const count = 2;")
        for mode in ("dirty", "assume-unchanged", "skip-worktree"):
            with self.subTest(mode=mode):
                if mode != "dirty":
                    git("update-index", "--" + mode, "app.ts")
                report = self.cli("ci", "--base", "HEAD", "--origin", "http://127.0.0.1:1", expected=2)
                self.assertEqual(report["reason_code"], "UI_CANDIDATE_UNVERIFIED")
                if mode != "dirty":
                    git("update-index", "--no-" + mode, "app.ts")

    def test_v3_inspection_reports_unsafe_path_per_file(self):
        (self.repo / "ok.ts").write_text("const count = 1;")
        (self.repo / "alias.ts").symlink_to(self.repo / "ok.ts")
        report = self.cli(
            "inspect",
            "--file",
            ".anti-slop/design/contract.json",
            "--policy-file",
            ".anti-slop/design/policy.json",
            "alias.ts",
            "ok.ts",
            expected=2,
        )
        self.assertEqual(report["summary"], {"checked": 2, "passed": 1, "blocked": 1})
        self.assertEqual(report["findings"], [{"path": "alias.ts", "reason_code": "UI_IMPACT_UNKNOWN"}])

    def test_v3_explicit_non_ui_data_module_exemption(self):
        path = self.repo / "api/client.ts"
        path.parent.mkdir()
        path.write_text('const response = {style: "formal"};')
        self.assertEqual(self.cli("check", "api/client.ts", expected=2)["reason_code"], "UI_STYLE_UNVERIFIED")
        trust = json.loads(self.trust.read_text())
        trust["non_ui_paths"].append("api/client.ts")
        self.trust.write_text(json.dumps(trust))
        self.assertEqual(self.cli("check", "api/client.ts")["decision"], "allow")
        (path.parent / "other.ts").write_bytes(path.read_bytes())
        self.assertEqual(self.cli("check", "api/other.ts", expected=2)["reason_code"], "UI_STYLE_UNVERIFIED")
        (self.repo / "theme.css").write_text(".x{color:red}")
        trust["non_ui_paths"].append("theme.css")
        self.trust.write_text(json.dumps(trust))
        self.assertEqual(self.cli("check", "theme.css", expected=2)["reason_code"], "UI_UNAPPROVED_TOKEN")


if __name__ == "__main__":
    suite = unittest.TestSuite(
        AstContractTests(name)
        for name in unittest.defaultTestLoader.getTestCaseNames(AstContractTests)
        if name.startswith("test_v3_")
    )
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    sys.exit(not result.wasSuccessful())
