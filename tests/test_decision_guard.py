import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "decision_guard.py"


def architecture_packet():
    return {
        "kind": "architecture",
        "goal": "Run an authenticated SaaS with predictable operations.",
        "proposal": "Next.js on Vercel with hosted Postgres.",
        "evidence": [
            {"source": "Product brief, section 2", "finding": "Only the landing page is public", "level": "observed"}
        ],
        "direct_check": {
            "status": "not_found",
            "source": "Existing repository and deployment inventory",
            "finding": "No existing service satisfies the full requirement",
        },
        "assumptions": [
            {"claim": "The initial team can maintain a VPS", "state": "unverified", "basis": "Owner confirmation pending"}
        ],
        "decision_axes": [
            {"name": "frontend", "considered": ["Next.js", "TanStack Start", "Vite SPA"], "selected": "Vite SPA"},
            {"name": "hosting", "considered": ["VPS", "PaaS"], "selected": "VPS"},
            {"name": "database", "considered": ["Local Postgres", "Managed Postgres"], "selected": "Local Postgres"},
        ],
        "alternatives": [
            {"name": "VPS + local Postgres", "benefit": "Low fixed cost", "risk": "Single node", "reversal": "Move DB separately"},
            {"name": "PaaS + managed Postgres", "benefit": "Lower operational load", "risk": "Recurring service cost", "reversal": "Containerized export"},
        ],
        "horizons": [
            {"stage": "now", "scenario": "First 100 users", "consequence": "Simple deployment"},
            {"stage": "later", "scenario": "10x data growth and node outage", "consequence": "Recovery and migration costs"},
        ],
        "decision": {
            "action": "pause",
            "choice": "VPS + local Postgres",
            "reason": "Conditional on operations ownership and tested offsite restore",
            "invalidated_by": "No competent operator or unacceptable restore time",
        },
    }


def audit(packet):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "decision.json"
        path.write_text(json.dumps(packet), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "audit", str(path), "--json"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        return result, json.loads(result.stdout) if result.stdout else None


class DecisionGuardTests(unittest.TestCase):
    def test_complete_architecture_packet_is_structurally_valid_not_fact_certified(self):
        result, output = audit(architecture_packet())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")
        self.assertTrue(output["machine_check_only"])
        self.assertEqual(output["decision_action"], "pause")

    def test_architecture_requires_independent_axis_comparison(self):
        packet = architecture_packet()
        packet["decision_axes"] = []
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MISSING_DECISION_AXES", [item["code"] for item in output["findings"]])

    def test_architecture_must_include_future_stress_scenario(self):
        packet = architecture_packet()
        packet["horizons"] = packet["horizons"][:1]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MISSING_FUTURE_SCENARIO", [item["code"] for item in output["findings"]])

    def test_direct_answer_requires_override_for_indirect_execution(self):
        packet = architecture_packet()
        packet["direct_check"] = {
            "status": "found", "source": "Existing API", "finding": "Value is exposed as a first-class field"
        }
        packet["decision"]["action"] = "proceed"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("DIRECT_PATH_OVERRIDE_REQUIRED", [item["code"] for item in output["findings"]])

    def test_unknown_direct_answer_blocks_proceed_but_allows_pause(self):
        packet = architecture_packet()
        packet["direct_check"]["status"] = "unknown"
        packet["decision"]["action"] = "proceed"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("DIRECT_PATH_UNRESOLVED", [item["code"] for item in output["findings"]])
        packet["decision"]["action"] = "pause"
        result, _ = audit(packet)
        self.assertEqual(result.returncode, 0)

    def test_direct_observation_can_stop_unnecessary_investigation(self):
        packet = architecture_packet()
        packet["kind"] = "investigation"
        packet["decision_axes"] = []
        packet["alternatives"] = []
        packet["horizons"] = []
        packet["direct_check"]["status"] = "found"
        packet["decision"].update({"action": "stop", "choice": "Direct observation"})
        result, output = audit(packet)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")

    def test_malformed_json_exits_with_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text("{bad", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "audit", str(path), "--json"],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(result.returncode, 1)
            self.assertIn("Invalid JSON", result.stderr)

    def test_investigation_cannot_skip_direct_source_inventory(self):
        packet = architecture_packet()
        packet["kind"] = "investigation"
        packet["direct_check"]["status"] = "not_applicable"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("DIRECT_CHECK_SKIPPED", [item["code"] for item in output["findings"]])

    def test_only_inferred_evidence_cannot_support_proceed(self):
        packet = architecture_packet()
        packet["evidence"][0]["level"] = "inferred"
        packet["decision"]["action"] = "proceed"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("NO_GROUNDED_EVIDENCE", [item["code"] for item in output["findings"]])


if __name__ == "__main__":
    unittest.main()
