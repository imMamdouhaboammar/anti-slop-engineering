from decimal import Decimal
import unittest


class CostCases(unittest.TestCase):
    def test_six_attempts_bound_cost_under_two_branch_fanout(self):
        observed_attempts = ("a:1", "a:2", "b:1", "b:2")
        maximum_attempts, rate = 2 * 3, Decimal("0.05")
        self.assertLessEqual(len(observed_attempts), maximum_attempts)
        self.assertEqual(len(observed_attempts) * rate, Decimal("0.20"))
        self.assertEqual(maximum_attempts * rate, Decimal("0.30"))

    def test_missing_limit_and_price_remain_unknown(self):
        rate = Decimal("0.05")
        cases = (
            ("unbounded attempts", 4, None, rate, Decimal("0.20"), None),
            ("unknown rate", 4, 6, None, None, None),
        )
        for name, observed, maximum, unit_rate, expected_total, expected_ceiling in cases:
            with self.subTest(name=name):
                total = observed * unit_rate if unit_rate is not None else None
                ceiling = maximum * unit_rate if maximum is not None and unit_rate is not None else None
                self.assertEqual(total, expected_total)
                self.assertEqual(ceiling, expected_ceiling)


if __name__ == "__main__":
    unittest.main()
