"""Real Chromium integration tests (run explicitly with Playwright installed)."""

import sys
import os
import hashlib
import json
import threading
import subprocess
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
import unittest
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from design_runtime import inspect_page, screenshot_digest, compare_screenshot
from design_policy import PolicyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import test_design_integrity_guard as fixtures

CHANNEL = os.environ.get("DESIGN_TEST_BROWSER", "chrome")

HTML = """<!doctype html><html lang="en" dir="ltr"><head>
<style>body{margin:0;background:white}main{display:flex;gap:8px;padding:16px}
button{width:100px;height:36px;color:rgb(32,32,32);background:rgb(255,255,255)}
button:focus-visible{outline:2px solid black}</style></head>
<body><main data-design-surface="settings" data-design-state="ready">
<button id="save" data-design-component="Button">Save</button>
<button id="cancel" data-design-component="Button">Cancel</button>
</main></body></html>"""

MANIFEST = {"tokens": {"--color-text": "#202020"}, "components": ["Button"]}
POLICY = {"allowed_classes": []}
SCENARIO = {
    "surface": "settings",
    "state": "ready",
    "direction": "ltr",
    "components": {"Button": [2, 2]},
    "checks": {
        "min_target": 24,
        "no_horizontal_overflow": True,
        "align": [{"selectors": ["#save", "#cancel"], "edge": "top", "epsilon": 0.5}],
        "no_overlap": [["#save", "#cancel"]],
        "computed": [{"selector": "#save", "property": "color", "token": "--color-text"}],
        "contrast": [{"foreground": "#save", "background": "#save", "minimum": 4.5}],
        "keyboard": ["#save", "#cancel"],
    },
}


class BrowserContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pw = sync_playwright().start()
        cls.addClassCleanup(cls.pw.stop)
        cls.browser = cls.pw.chromium.launch(channel=CHANNEL, headless=True)
        cls.addClassCleanup(cls.browser.close)

    def setUp(self):
        self.context = self.browser.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1)
        self.addCleanup(self.context.close)
        self.page = self.context.new_page()

    def test_valid_layout_and_screenshot(self):
        self.page.set_content(HTML)
        inspect_page(self.page, SCENARIO, MANIFEST, POLICY)
        first = screenshot_digest(self.page)
        self.assertEqual(len(first), 64)
        compare_screenshot(self.page, first)
        self.page.set_content(HTML.replace("Save</button>", "Submit</button>"))
        with self.assertRaises(PolicyError) as err:
            compare_screenshot(self.page, first)
        self.assertEqual(err.exception.code, "UI_VISUAL_DRIFT")

    def test_real_dom_rejects_regressions(self):
        for markup, code in (
            (HTML.replace('data-design-state="ready"', 'data-design-state="loading"'), "UI_REQUIRED_STATE_MISSING"),
            (
                HTML.replace('data-design-component="Button"', 'data-design-component="Mystery"', 1),
                "UI_UNAPPROVED_COMPONENT",
            ),
            (HTML.replace("height:36px", "height:12px"), "UI_ACCESSIBILITY_FAILED"),
            (HTML.replace("rgb(32,32,32)", "rgb(255,255,255)"), "UI_COMPUTED_STYLE_MISMATCH"),
            (HTML.replace("gap:8px", "gap:8px;width:1000px"), "UI_GEOMETRY_INVARIANT_FAILED"),
            (HTML.replace('id="save"', 'id="save" class="invented"'), "UI_UNAPPROVED_UTILITY"),
        ):
            with self.subTest(code=code):
                self.page.set_content(markup)
                with self.assertRaises(PolicyError) as err:
                    inspect_page(self.page, SCENARIO, MANIFEST, POLICY)
                self.assertEqual(err.exception.code, code)

    def test_adversarial_component_visibility_and_scope(self):
        for markup in (
            HTML.replace('id="save"', 'id="save" style="opacity:0"'),
            HTML.replace("</main></body>", "</body>").replace('<button id="cancel"', '</main><button id="cancel"'),
            HTML.replace("</main>", '<iframe srcdoc="<button>Other</button>"></iframe></main>'),
        ):
            with self.subTest(markup=markup):
                self.page.set_content(markup)
                with self.assertRaises(PolicyError):
                    inspect_page(self.page, SCENARIO, MANIFEST, POLICY)

    def test_adversarial_invisible_focus_indicator(self):
        from design_runtime import inspect_keyboard

        self.page.set_content(
            HTML.replace("outline:2px solid black", "outline:2px solid transparent;box-shadow:0 0 0 transparent")
        )
        with self.assertRaises(PolicyError):
            inspect_keyboard(self.page, ["#save"])

    def test_signed_cli_pipeline_and_ci(self):
        fixture = fixtures.DesignIntegrityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.enable_v2()
        page = fixture.repo / "settings.html"
        page.write_text(HTML)
        baseline = ".anti-slop/design/baselines/settings.png"
        scenario = dict(SCENARIO, id="settings-mobile", path="/settings.html", viewport=[390, 844], baseline=baseline)
        policy = dict(
            POLICY,
            schema_version=1,
            scenarios=[scenario],
            browser={"channel": CHANNEL, "version": self.browser.version},
        )
        policy_path = fixture.design / "policy.json"
        policy_path.write_text(json.dumps(policy))
        fixture.record["artifacts"][".anti-slop/design/policy.json"] = hashlib.sha256(
            policy_path.read_bytes()
        ).hexdigest()
        fixture.seal()
        handler = partial(SimpleHTTPRequestHandler, directory=str(fixture.repo))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_port}"
        output = fixture.outer / "capture"
        receipt = fixture.cli("capture", "--origin", origin, "--output", str(output))
        self.assertFalse(receipt["approved"])
        signed_baseline = fixture.repo / baseline
        signed_baseline.write_bytes((output / "settings-mobile.png").read_bytes())
        fixture.record["artifacts"][baseline] = hashlib.sha256(signed_baseline.read_bytes()).hexdigest()
        fixture.seal()
        report = fixture.cli("runtime", "--origin", origin)
        self.assertEqual(report["reason_code"], "UI_RUNTIME_VERIFIED")
        subprocess.run(["git", "init", "-q", str(fixture.repo)], check=True)
        subprocess.run(["git", "-C", str(fixture.repo), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(fixture.repo),
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
        self.assertEqual(fixture.cli("ci", "--base", "HEAD", "--origin", origin)["reason_code"], "UI_RUNTIME_VERIFIED")
        page.write_text(HTML.replace("Save</button>", "Submit</button>"))
        self.assertEqual(
            fixture.cli("ci", "--base", "HEAD", "--origin", origin, expected=2)["reason_code"], "UI_VISUAL_DRIFT"
        )

    def test_builder_capture_review_and_signed_v3_runtime(self):
        fixture = fixtures.DesignIntegrityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        proposals = fixture.design / "proposals"
        proposals.mkdir()
        (fixture.repo / "settings.html").write_text(HTML)
        (fixture.repo / "tokens.json").write_text(
            json.dumps({"space": {"$type": "dimension", "$value": {"value": 16, "unit": "px"}}})
        )
        checks = dict(
            SCENARIO["checks"], computed=[{"selector": "main", "property": "padding-top", "token": "--space"}]
        )
        scenario = dict(SCENARIO, id="settings-mobile", path="/settings.html", viewport=[390, 844], checks=checks)
        spec = {
            "schema_version": 1,
            "repository_id": fixture.record["repository_id"],
            "token_file": "tokens.json",
            "components": ["Button"],
            "surfaces": ["settings"],
            "allowed_classes": [],
            "browser": {"channel": CHANNEL, "version": self.browser.version},
            "artifacts": [],
            "scenarios": [scenario],
        }
        (proposals / "input.json").write_text(json.dumps(spec))
        base = ".anti-slop/design/proposals/"
        draft = fixture.cli("build", "--file", base + "input.json", "--output", base + "draft")
        self.assertEqual(draft["state"], "DRAFT")
        handler = partial(SimpleHTTPRequestHandler, directory=str(fixture.repo))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        origin = f"http://127.0.0.1:{server.server_port}"
        capture = fixture.outer / "builder-capture"
        captured = fixture.cli(
            "capture",
            "--origin",
            origin,
            "--output",
            str(capture),
            "--file",
            base + "draft/candidate.json",
            "--policy-file",
            base + "draft/policy.json",
        )
        self.assertFalse(captured["approved"])
        review = fixture.cli(
            "build", "--file", base + "input.json", "--output", base + "review", "--capture-dir", str(capture)
        )
        self.assertEqual(review["state"], "READY_FOR_REVIEW")
        self.assertFalse(review["approved"])
        self.assertEqual(fixture.cli("verify", expected=2)["reason_code"], "UI_CONTRACT_MISSING")
        # This test represents independent approval using an ephemeral fixture key.
        package = proposals / "review"
        (fixture.design / "policy.json").write_bytes((package / "policy.json").read_bytes())
        (fixture.design / "baselines").mkdir()
        (fixture.design / "baselines/settings-mobile.png").write_bytes((package / "settings-mobile.png").read_bytes())
        fixture.contract.write_bytes((package / "candidate.json").read_bytes())
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(fixture.key), "-n", "anti-slop-design-v1", str(fixture.contract)],
            check=True,
            capture_output=True,
        )
        fixture.publish_trust()
        self.assertEqual(fixture.cli("runtime", "--origin", origin)["reason_code"], "UI_RUNTIME_VERIFIED")

    def test_independent_ci_signed_fixture_and_commit(self):
        fixture = fixtures.DesignIntegrityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.enable_v2()
        fixture.record["schema_version"] = 3
        bundle = fixture.outer / "bundle"
        bundle.mkdir()
        (bundle / "settings.html").write_text(HTML)
        baseline = ".anti-slop/design/baselines/settings.png"
        scenario = dict(SCENARIO, id="settings-mobile", path="/settings.html", viewport=[390, 844], baseline=baseline)
        policy = dict(
            POLICY,
            schema_version=1,
            scenarios=[scenario],
            browser={"channel": CHANNEL, "version": self.browser.version},
        )
        policy_path = fixture.design / "policy.json"
        policy_path.write_text(json.dumps(policy))
        fixture.record["artifacts"][".anti-slop/design/policy.json"] = hashlib.sha256(
            policy_path.read_bytes()
        ).hexdigest()
        fixture.seal()
        handler = partial(SimpleHTTPRequestHandler, directory=str(bundle))
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        output = fixture.outer / "capture"
        fixture.cli("capture", "--origin", f"http://127.0.0.1:{server.server_port}", "--output", str(output))
        image = (output / "settings-mobile.png").read_bytes()
        (fixture.repo / baseline).write_bytes(image)
        fixture.record["artifacts"][baseline] = hashlib.sha256(image).hexdigest()
        fixture.seal()
        subprocess.run(["git", "init", "-q", str(fixture.repo)], check=True)
        subprocess.run(["git", "-C", str(fixture.repo), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(fixture.repo),
                "-c",
                "user.name=Test",
                "-c",
                "user.email=test@example.com",
                "commit",
                "-qm",
                "candidate",
            ],
            check=True,
        )
        head = subprocess.check_output(["git", "-C", str(fixture.repo), "rev-parse", "HEAD"], text=True).strip()
        build_key = fixture.outer / "build-key"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(build_key)], check=True)
        record = {
            "schema_version": 1,
            "repository_id": fixture.record["repository_id"],
            "candidate_sha": head,
            "base_sha": head,
            "manifest_sha256": hashlib.sha256(fixture.contract.read_bytes()).hexdigest(),
            "files": {"settings.html": hashlib.sha256((bundle / "settings.html").read_bytes()).hexdigest()},
        }
        receipt = fixture.outer / "build.json"
        receipt.write_text(json.dumps(record))
        subprocess.run(
            ["ssh-keygen", "-Y", "sign", "-f", str(build_key), "-n", "anti-slop-design-build-v1", str(receipt)],
            check=True,
            capture_output=True,
        )
        args = (
            "ci-independent",
            "--candidate",
            head,
            "--base",
            head,
            "--fixture-dir",
            str(bundle),
            "--build-receipt",
            str(receipt),
            "--build-key",
            str(build_key.with_suffix(".pub")),
        )
        report = fixture.cli(*args)
        self.assertTrue(report["approved"])
        self.assertEqual(report["candidate_sha"], head)
        self.assertEqual(report["reason_code"], "UI_RUNTIME_VERIFIED")
        (bundle / "settings.html").write_text(HTML.replace("Save</button>", "Changed</button>"))
        self.assertEqual(fixture.cli(*args, expected=2)["reason_code"], "UI_BUILD_EVIDENCE_INVALID")


if __name__ == "__main__":
    unittest.main()
