"""Browser extension integration: local, unpacked, least-privilege MV3 fixtures only."""

import base64
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from design_extension import validate_extension, run_extension_scenarios
from design_policy import PolicyError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
import test_design_integrity_guard as fixtures


class ExtensionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        self.extension = self.root / "extension"
        self.extension.mkdir()
        # Public SPKI test identity; no secret key required.
        import subprocess

        public = subprocess.run(
            ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048"],
            capture_output=True,
            check=True,
        ).stdout
        der = subprocess.run(
            ["openssl", "pkey", "-pubout", "-outform", "DER"], input=public, capture_output=True, check=True
        ).stdout
        self.ext_id = (
            hashlib.sha256(der).hexdigest()[:32].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))
        )
        self.metadata = {
            "manifest_version": 3,
            "name": "Design guard test fixture",
            "version": "1.0.0",
            "key": base64.b64encode(der).decode(),
            "permissions": ["sidePanel"],
            "action": {"default_popup": "popup.html"},
            "side_panel": {"default_path": "side.html"},
            "options_ui": {"page": "options.html", "open_in_tab": True},
        }
        self.scenarios = []
        for surface, name, width in (
            ("popup", "popup.html", 320),
            ("side-panel", "side.html", 360),
            ("options", "options.html", 800),
        ):
            (self.extension / name).write_text(
                '<!doctype html><html dir="ltr"><body><main data-design-surface="'
                + surface
                + '" data-design-state="ready"><button data-design-component="Button" style="width:100px;height:32px">OK</button></main></body></html>'
            )
            self.scenarios.append(
                {
                    "id": surface,
                    "surface": surface,
                    "path": "/" + name,
                    "viewport": [width, 500],
                    "direction": "ltr",
                    "state": "ready",
                    "components": {"Button": [1, 1]},
                    "baseline": surface + ".png",
                    "checks": {
                        "min_target": 24,
                        "no_horizontal_overflow": True,
                        "align": [],
                        "no_overlap": [],
                        "computed": [],
                    },
                }
            )
        self.write_manifest()
        self.policy = {
            "extension": {"id": self.ext_id},
            "scenarios": self.scenarios,
            "allowed_classes": [],
            "browser": {"channel": "chromium", "version": "test"},
        }

    def write_manifest(self):
        (self.extension / "manifest.json").write_text(json.dumps(self.metadata))

    def test_extension_metadata_rejects_missing_surface_wrong_path_and_permissions(self):
        self.assertEqual(validate_extension(self.extension, self.policy), self.ext_id)
        for key, value in (
            ("host_permissions", ["<all_urls>"]),
            ("background", {"service_worker": "worker.js"}),
            ("permissions", ["tabs"]),
        ):
            with self.subTest(key=key):
                previous = self.metadata.get(key)
                self.metadata[key] = value
                self.write_manifest()
                with self.assertRaises(PolicyError):
                    validate_extension(self.extension, self.policy)
                if previous is None:
                    self.metadata.pop(key)
                else:
                    self.metadata[key] = previous
        self.write_manifest()
        self.scenarios[0]["path"] = "/other.html"
        with self.assertRaises(PolicyError):
            validate_extension(self.extension, self.policy)

    def test_actual_extension_pages_and_visual_drift(self):
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chromium", headless=True)
            self.policy["browser"]["version"] = browser.version
            browser.close()
        manifest = {"components": ["Button"], "tokens": {}, "artifacts": {}}
        output = self.root / "capture"
        output.mkdir()
        receipts = run_extension_scenarios(self.extension, manifest, self.policy, output)
        self.assertEqual([r["status"] for r in receipts], ["pass"] * 3, receipts)
        for scenario, receipt in zip(self.scenarios, receipts):
            manifest["artifacts"][scenario["baseline"]] = receipt["sha256"]
        self.assertTrue(
            all(r["status"] == "pass" for r in run_extension_scenarios(self.extension, manifest, self.policy))
        )
        path = self.extension / "side.html"
        path.write_text(path.read_text().replace(">OK<", ">No<"))
        receipts = run_extension_scenarios(self.extension, manifest, self.policy)
        self.assertEqual(receipts[-1]["reason_code"], "UI_VISUAL_DRIFT")

    def test_signed_extension_cli_transport(self):
        import subprocess
        from playwright.sync_api import sync_playwright

        fixture = fixtures.DesignIntegrityTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        fixture.record["schema_version"] = 3
        fixture.record["surfaces"] = [s["surface"] for s in self.scenarios]
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel="chromium", headless=True)
            self.policy["browser"]["version"] = browser.version
            browser.close()
        policy = dict(self.policy, schema_version=1)
        baseline_dir = fixture.design / "baselines"
        baseline_dir.mkdir()
        for scenario in self.scenarios:
            scenario["baseline"] = ".anti-slop/design/baselines/" + scenario["id"] + ".png"
            fixture.record["artifacts"][scenario["baseline"]] = "0" * 64
        path = fixture.design / "policy.json"
        path.write_text(json.dumps(policy))
        fixture.record["artifacts"][".anti-slop/design/policy.json"] = hashlib.sha256(path.read_bytes()).hexdigest()
        fixture.contract.write_text(json.dumps(fixture.record))
        output = self.root / "signed-capture"
        capture = fixture.cli("capture", "--extension-dir", str(self.extension), "--output", str(output))
        self.assertFalse(capture["approved"])
        for scenario in self.scenarios:
            image = (output / (scenario["id"] + ".png")).read_bytes()
            (fixture.repo / scenario["baseline"]).write_bytes(image)
            fixture.record["artifacts"][scenario["baseline"]] = hashlib.sha256(image).hexdigest()
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
                "base",
            ],
            check=True,
        )
        report = fixture.cli("ci", "--base", "HEAD", "--extension-dir", str(self.extension))
        self.assertEqual(report["reason_code"], "UI_RUNTIME_VERIFIED")
        self.assertEqual(len(report["scenarios"]), 3)
        self.assertEqual(report["candidate_sha"], report["base_sha"])
        self.assertEqual(len(report["candidate_sha"]), 40)
        self.assertEqual(
            fixture.cli("runtime", "--origin", "http://127.0.0.1:4173", expected=2)["reason_code"], "UI_POLICY_INVALID"
        )


if __name__ == "__main__":
    unittest.main()
