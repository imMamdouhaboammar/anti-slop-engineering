"""Independent fixture provenance and candidate identity checks."""

import hashlib
import json
import subprocess
import unittest

import test_design_integrity_guard as fixtures


class IndependentCITests(unittest.TestCase):
    def setUp(self):
        owner = fixtures.DesignIntegrityTests()
        owner.setUp()
        self.addCleanup(owner.doCleanups)
        owner.enable_v2()
        owner.record["schema_version"] = 3
        owner.seal()
        self.repo, self.outer, self.record, self.contract, self.key = (
            owner.repo,
            owner.outer,
            owner.record,
            owner.contract,
            owner.key,
        )
        self.cli = owner.cli
        self.fixture = self.outer / "fixture"
        self.fixture.mkdir()
        (self.fixture / "index.html").write_text("<main>Fixture</main>")
        self.build_key = self.outer / "builder"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-f", str(self.build_key)], check=True)
        self.receipt = self.outer / "build.json"
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "."], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.repo),
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
        self.head = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()
        self.build_record = {
            "schema_version": 1,
            "repository_id": self.record["repository_id"],
            "candidate_sha": self.head,
            "base_sha": self.head,
            "manifest_sha256": hashlib.sha256(self.contract.read_bytes()).hexdigest(),
            "files": {"index.html": hashlib.sha256((self.fixture / "index.html").read_bytes()).hexdigest()},
        }
        self.publish_build()

    def publish_build(self):
        self.receipt.write_text(json.dumps(self.build_record))
        signature = self.receipt.with_suffix(".json.sig")
        signature.unlink(missing_ok=True)
        subprocess.run(
            [
                "ssh-keygen",
                "-Y",
                "sign",
                "-f",
                str(self.build_key),
                "-n",
                "anti-slop-design-build-v1",
                str(self.receipt),
            ],
            check=True,
            capture_output=True,
        )

    def independent(self, expected=0, **overrides):
        args = {
            "--candidate": self.head,
            "--base": self.head,
            "--fixture-dir": str(self.fixture),
            "--build-receipt": str(self.receipt),
            "--build-key": str(self.build_key.with_suffix(".pub")),
        }
        args.update(overrides)
        return self.cli("ci-independent", "--preflight", *[v for pair in args.items() for v in pair], expected=expected)

    def test_independent_preflight_binds_exact_commit_and_fixture(self):
        report = self.independent()
        self.assertFalse(report["approved"])
        self.assertEqual(report["reason_code"], "UI_INDEPENDENT_PREFLIGHT")
        self.assertEqual(report["candidate_sha"], self.head)
        self.assertEqual(report["build_receipt_sha256"], hashlib.sha256(self.receipt.read_bytes()).hexdigest())

    def test_independent_rejects_wrong_commit(self):
        self.assertEqual(
            self.independent(expected=2, **{"--candidate": "0" * 40})["reason_code"], "UI_CANDIDATE_UNVERIFIED"
        )

    def test_independent_rejects_fixture_mutation_and_extra_file(self):
        path = self.fixture / "index.html"
        path.write_text("Changed")
        self.assertEqual(self.independent(expected=2)["reason_code"], "UI_BUILD_EVIDENCE_INVALID")
        path.write_text("<main>Fixture</main>")
        (self.fixture / "hidden.js").write_text("extra")
        self.assertEqual(self.independent(expected=2)["reason_code"], "UI_BUILD_EVIDENCE_INVALID")

    def test_independent_rejects_replay_and_tampered_receipt(self):
        self.build_record["candidate_sha"] = "1" * 40
        self.publish_build()
        self.assertEqual(self.independent(expected=2)["reason_code"], "UI_BUILD_EVIDENCE_INVALID")
        self.build_record["candidate_sha"] = self.head
        self.receipt.write_text(json.dumps(self.build_record))
        self.assertEqual(self.independent(expected=2)["reason_code"], "UI_BUILD_EVIDENCE_INVALID")

    def test_independent_rejects_owner_key_as_builder_key(self):
        self.assertEqual(
            self.independent(expected=2, **{"--build-key": str(self.key.with_suffix(".pub"))})["reason_code"],
            "UI_BUILD_EVIDENCE_INVALID",
        )


if __name__ == "__main__":
    unittest.main()
