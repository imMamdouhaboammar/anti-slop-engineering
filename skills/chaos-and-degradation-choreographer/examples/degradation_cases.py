import unittest


def fallback_decision(critical, dependency_status, fallback_valid, remaining_slots):
    if dependency_status == "healthy":
        return "normal"
    if critical:
        return "pending"
    if not fallback_valid:
        return "unavailable"
    return "degraded" if remaining_slots > 0 else "shed"


def recovery_decision(probe_result, attempts, attempt_limit):
    if probe_result == "healthy":
        return "reopen-gradually"
    if attempts >= attempt_limit:
        return "stop"
    return "keep-circuit-open"


class DegradationCases(unittest.TestCase):
    def test_cache_loss_sheds_above_origin_budget(self):
        self.assertEqual(fallback_decision(False, "timeout", True, 1), "degraded")
        self.assertEqual(fallback_decision(False, "timeout", True, 0), "shed")

    def test_payment_timeout_stays_pending(self):
        self.assertEqual(fallback_decision(True, "timeout", True, 1), "pending")

    def test_invalid_fallback_is_unavailable(self):
        self.assertEqual(fallback_decision(False, "timeout", False, 1), "unavailable")

    def test_failed_probes_stop_at_budget_and_success_restores_gradually(self):
        self.assertEqual(recovery_decision("timeout", 1, 2), "keep-circuit-open")
        self.assertEqual(recovery_decision("timeout", 2, 2), "stop")
        self.assertEqual(recovery_decision("healthy", 1, 2), "reopen-gradually")
        self.assertEqual(fallback_decision(False, "healthy", False, 0), "normal")


if __name__ == "__main__":
    unittest.main()
