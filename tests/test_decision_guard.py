import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "decision_guard.py"


def architecture_packet():
    """Return a valid baseline architecture decision packet for testing."""
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
    """Run the decision guard script against a serialized packet in a temporary file."""
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
        """Verify that a complete architecture packet passes validation with pause action."""
        result, output = audit(architecture_packet())
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")
        self.assertTrue(output["machine_check_only"])
        self.assertEqual(output["decision_action"], "pause")

    def test_architecture_requires_independent_axis_comparison(self):
        """Verify that architecture decisions require at least one decision axis."""
        packet = architecture_packet()
        packet["decision_axes"] = []
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MISSING_DECISION_AXES", [item["code"] for item in output["findings"]])

    def test_architecture_must_include_future_stress_scenario(self):
        """Verify that architecture decisions require current and future horizon scenarios."""
        packet = architecture_packet()
        packet["horizons"] = packet["horizons"][:1]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MISSING_FUTURE_SCENARIO", [item["code"] for item in output["findings"]])

    def test_direct_answer_requires_override_for_indirect_execution(self):
        """Verify that finding a direct answer requires an explicit handling override to proceed."""
        packet = architecture_packet()
        packet["direct_check"] = {
            "status": "found", "source": "Existing API", "finding": "Value is exposed as a first-class field"
        }
        packet["decision"]["action"] = "proceed"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("DIRECT_PATH_OVERRIDE_REQUIRED", [item["code"] for item in output["findings"]])

    def test_unknown_direct_answer_blocks_proceed_but_allows_pause(self):
        """Verify that an unresolved direct path blocks proceed but permits pausing."""
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
        """Verify that direct observation allows an investigation to cleanly conclude with stop."""
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
        """Verify that unparseable JSON input exits with error code 1."""
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
        """Verify that investigations cannot mark direct check as not applicable."""
        packet = architecture_packet()
        packet["kind"] = "investigation"
        packet["direct_check"]["status"] = "not_applicable"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("DIRECT_CHECK_SKIPPED", [item["code"] for item in output["findings"]])

    def test_only_inferred_evidence_cannot_support_proceed(self):
        """Verify that proceeding requires at least one observed or derived evidence item."""
        packet = architecture_packet()
        packet["evidence"][0]["level"] = "inferred"
        packet["decision"]["action"] = "proceed"
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("NO_GROUNDED_EVIDENCE", [item["code"] for item in output["findings"]])

    def test_non_string_enum_values_produce_findings_without_type_error(self):
        """Verify that non-string enum values emit validation findings without crashing."""
        packet = architecture_packet()
        packet["evidence"][0]["level"] = 123
        packet["direct_check"]["status"] = {}
        packet["assumptions"][0]["state"] = None
        packet["decision"]["action"] = True
        packet["horizons"][0]["stage"] = ["now"]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIsNotNone(output)
        codes = [item["code"] for item in output["findings"]]
        self.assertIn("INVALID_EVIDENCE", codes)
        self.assertIn("MISSING_DIRECT_CHECK", codes)
        self.assertIn("INVALID_ASSUMPTION", codes)
        self.assertIn("MISSING_DECISION", codes)
        self.assertIn("INVALID_HORIZONS", codes)

        packet_bad_kind = architecture_packet()
        packet_bad_kind["kind"] = []
        result_kind, output_kind = audit(packet_bad_kind)
        self.assertEqual(result_kind.returncode, 2)
        codes_kind = [item["code"] for item in output_kind["findings"]]
        self.assertIn("INVALID_KIND", codes_kind)

    def test_architecture_alternatives_require_distinct_names(self):
        """Verify that architecture alternatives must have distinct names."""
        packet = architecture_packet()
        packet["alternatives"] = [
            {"name": "VPS + Postgres", "benefit": "Low cost", "risk": "Single node", "reversal": "Export"},
            {"name": "VPS + Postgres", "benefit": "Low cost", "risk": "Single node", "reversal": "Export"},
        ]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("MISSING_ALTERNATIVES", [item["code"] for item in output["findings"]])

    def test_architecture_single_candidate_with_constraint_rationale(self):
        """Verify that single candidate with constraint rationale satisfies validation."""
        packet = architecture_packet()
        packet["decision_axes"] = [
            {
                "name": "database",
                "considered": ["On-prem Postgres"],
                "selected": "On-prem Postgres",
                "single_candidate": True,
                "constraint_rationale": "Legal compliance strictly mandates on-premises data residency.",
            }
        ]
        packet["alternatives"] = [
            {"name": "On-prem Postgres", "benefit": "Meets compliance", "risk": "Hardware maintenance", "reversal": "Export data"}
        ]
        packet["single_candidate"] = True
        packet["constraint_rationale"] = "Hardware security mandate excludes multi-tenant cloud options."
        result, output = audit(packet)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(output["record_status"], "complete")

    def test_architecture_single_candidate_without_constraint_rationale_fails(self):
        """Verify that a single candidate axis without constraint rationale fails validation."""
        packet = architecture_packet()
        packet["decision_axes"] = [
            {
                "name": "database",
                "considered": ["On-prem Postgres"],
                "selected": "On-prem Postgres",
            }
        ]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("INVALID_DECISION_AXIS", [item["code"] for item in output["findings"]])

    def test_architecture_two_active_candidates_with_rationale_fails_single_candidate_branch(self):
        """Verify that two active candidates with a rationale cannot bypass the two-candidate check."""
        packet = architecture_packet()
        packet["decision_axes"] = [
            {
                "name": "database",
                "considered": ["On-prem Postgres", "Cloud SQL"],
                "selected": "On-prem Postgres",
                "constraint_rationale": "Hardware security preference.",
            }
        ]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("INVALID_DECISION_AXIS", [item["code"] for item in output["findings"]])

    def test_architecture_eliminated_candidates_do_not_count_toward_credible_options(self):
        """Verify that eliminated candidates do not satisfy the minimum alternative requirement."""
        packet = architecture_packet()
        packet["decision_axes"] = [
            {
                "name": "database",
                "considered": ["On-prem Postgres", "Cloud SQL"],
                "eliminated": ["Cloud SQL"],
                "selected": "On-prem Postgres",
            }
        ]
        result, output = audit(packet)
        self.assertEqual(result.returncode, 2)
        self.assertIn("INVALID_DECISION_AXIS", [item["code"] for item in output["findings"]])


if __name__ == "__main__":
    unittest.main()
