"""Contract builder acceptance tests, including approval boundaries."""

import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def png(width=390, height=844):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    pixels = (b"\0" + b"\xff\xff\xff" * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(pixels)) + chunk(b"IEND", b"")


class BuilderTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.outer = Path(temp.name).resolve()
        self.repo = self.outer / "repo"
        self.proposals = self.repo / ".anti-slop/design/proposals"
        self.proposals.mkdir(parents=True)
        for name in ("PRODUCT.md", "DESIGN.md"):
            (self.repo / name).write_text("Owner review required.\n")
        self.token_file = self.repo / "tokens.json"
        self.token_file.write_text(
            json.dumps(
                {
                    "spacing": {"$type": "dimension", "small": {"$value": {"value": 8, "unit": "px"}}},
                    "text": {"$type": "color", "$value": {"colorSpace": "srgb", "components": [0, 0, 0]}},
                }
            )
        )
        self.spec = {
            "schema_version": 1,
            "repository_id": "example/app",
            "token_file": "tokens.json",
            "components": ["Button"],
            "surfaces": ["settings"],
            "allowed_classes": ["flex"],
            "browser": {"channel": "chromium", "version": "145.0.7632.6"},
            "artifacts": [],
            "scenarios": [
                {
                    "id": "settings-mobile",
                    "surface": "settings",
                    "path": "/settings",
                    "viewport": [390, 844],
                    "direction": "ltr",
                    "state": "ready",
                    "components": {"Button": [1, 2]},
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
        self.input = self.proposals / "input.json"
        self.output = self.proposals / "draft"
        self.capture = self.outer / "capture"
        self.capture.mkdir()

    def cli(self, *args, expected=0):
        env = dict(os.environ)
        env.pop("ANTI_SLOP_DESIGN_TRUST", None)
        result = subprocess.run(
            [sys.executable, str(ROOT / "scripts/design_integrity_guard.py"), *args],
            cwd=self.repo,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def build(self, *args, expected=0):
        self.input.write_text(json.dumps(self.spec))
        return self.cli(
            "build",
            "--file",
            str(self.input.relative_to(self.repo)),
            "--output",
            str(self.output.relative_to(self.repo)),
            *args,
            expected=expected,
        )

    def test_draft_is_deterministic_and_unapproved(self):
        report = self.build()
        self.assertFalse(report["approved"])
        self.assertEqual(report["state"], "DRAFT")
        self.assertEqual(report["missing_baselines"], ["settings-mobile"])
        manifest = json.loads((self.output / "candidate.json").read_text())
        policy = (self.output / "policy.json").read_bytes()
        self.assertEqual(manifest["schema_version"], 3)
        self.assertEqual(manifest["tokens"]["--spacing-small"], "8px")
        self.assertEqual(manifest["artifacts"][".anti-slop/design/policy.json"], hashlib.sha256(policy).hexdigest())
        self.assertEqual(manifest["artifacts"][".anti-slop/design/baselines/settings-mobile.png"], "0" * 64)
        self.assertEqual(
            self.cli("validate", "--file", str((self.output / "candidate.json").relative_to(self.repo)))["decision"],
            "allow",
        )
        self.assertFalse((self.repo / ".anti-slop/design/contract.json").exists())
        self.assertFalse((self.repo / ".anti-slop/design/contract.json.sig").exists())
        first = (self.output / "candidate.json").read_bytes()
        self.output = self.proposals / "second"
        self.build()
        self.assertEqual(first, (self.output / "candidate.json").read_bytes())

    def test_capture_package_is_ready_for_review_not_approved(self):
        image = png()
        (self.capture / "settings-mobile.png").write_bytes(image)
        report = self.build("--capture-dir", str(self.capture))
        self.assertEqual(report["state"], "READY_FOR_REVIEW")
        self.assertFalse(report["approved"])
        manifest = json.loads((self.output / "candidate.json").read_text())
        self.assertEqual(
            manifest["artifacts"][".anti-slop/design/baselines/settings-mobile.png"], hashlib.sha256(image).hexdigest()
        )
        self.assertEqual((self.output / "settings-mobile.png").read_bytes(), image)
        self.assertEqual(self.cli("verify", expected=2)["reason_code"], "UI_TRUST_INVALID")

    def test_invalid_capture_and_incomplete_capture_are_rejected(self):
        for data in (b"not a png", png(320, 844)):
            with self.subTest(data=data[:16]):
                (self.capture / "settings-mobile.png").write_bytes(data)
                self.assertEqual(
                    self.build("--capture-dir", str(self.capture), expected=2)["reason_code"], "UI_BUILDER_INVALID"
                )
                self.assertFalse(self.output.exists())
        (self.capture / "settings-mobile.png").unlink()
        self.assertEqual(
            self.build("--capture-dir", str(self.capture), expected=2)["reason_code"], "UI_BUILDER_INVALID"
        )

    def test_rejects_missing_surface_and_unsafe_id(self):
        self.spec["surfaces"].append("other")
        self.assertEqual(self.build(expected=2)["reason_code"], "UI_POLICY_INVALID")
        self.assertFalse(self.output.exists())
        self.spec["surfaces"].pop()
        self.spec["scenarios"][0]["id"] = "../escape"
        self.assertEqual(self.build(expected=2)["reason_code"], "UI_BUILDER_INVALID")
        self.assertFalse(self.output.exists())

    def test_never_overwrites_existing_package_or_approved_paths(self):
        self.output.mkdir()
        sentinel = self.output / "candidate.json"
        sentinel.write_text("keep")
        self.assertEqual(self.build(expected=2)["reason_code"], "UI_BUILDER_INVALID")
        self.assertEqual(sentinel.read_text(), "keep")
        self.output = self.repo / ".anti-slop/design"
        self.assertEqual(self.build(expected=2)["reason_code"], "UI_BUILDER_INVALID")

    def test_builder_rejects_symlinks_and_protected_artifacts(self):
        self.spec["artifacts"] = [".anti-slop/design/contract.json"]
        self.assertEqual(self.build(expected=2)["reason_code"], "UI_BUILDER_INVALID")
        self.spec["artifacts"] = []
        self.token_file.unlink()
        external = self.outer / "outside.json"
        external.write_text("{}")
        self.token_file.symlink_to(external)
        self.assertEqual(self.build(expected=2)["reason_code"], "UI_BUILDER_INVALID")
        self.assertFalse(self.output.exists())

    def test_extra_capture_files_rejected(self):
        (self.capture / "settings-mobile.png").write_bytes(png())
        (self.capture / "other.png").write_bytes(png())
        self.assertEqual(
            self.build("--capture-dir", str(self.capture), expected=2)["reason_code"], "UI_BUILDER_INVALID"
        )
        self.assertFalse(self.output.exists())

    def test_rejects_truncated_png_with_matching_header(self):
        (self.capture / "settings-mobile.png").write_bytes(png()[:33])
        self.assertEqual(
            self.build("--capture-dir", str(self.capture), expected=2)["reason_code"], "UI_BUILDER_INVALID"
        )
        self.assertFalse(self.output.exists())

    def test_rejects_case_insensitive_scenario_filename_collision(self):
        another = dict(self.spec["scenarios"][0], id="Settings-Mobile")
        self.spec["scenarios"].append(another)
        self.assertEqual(self.build(expected=2)["reason_code"], "UI_BUILDER_INVALID")
        self.assertFalse(self.output.exists())

    def test_capture_rejects_policy_digest_mismatch_before_browser(self):
        self.build()
        policy_path = self.output / "policy.json"
        policy_path.write_bytes(policy_path.read_bytes() + b" ")
        report = self.cli(
            "capture",
            "--origin",
            "http://127.0.0.1:1",
            "--output",
            str(self.outer / "capture-new"),
            "--file",
            str((self.output / "candidate.json").relative_to(self.repo)),
            "--policy-file",
            str(policy_path.relative_to(self.repo)),
            expected=2,
        )
        self.assertEqual(report["reason_code"], "UI_ARTIFACT_DRIFT")
        self.assertFalse((self.outer / "capture-new").exists())


if __name__ == "__main__":
    unittest.main()
