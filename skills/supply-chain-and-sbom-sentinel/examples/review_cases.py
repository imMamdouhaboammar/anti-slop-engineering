import unittest


def classify_review(coordinate, approved_coordinate, digest, approved_digest, hook_review):
    if approved_coordinate is not None and coordinate != approved_coordinate:
        return "suspicious"
    if digest is not None and approved_digest is not None and digest != approved_digest:
        return "suspicious"
    if hook_review == "prohibited":
        return "suspicious"
    if approved_coordinate is None or digest is None or approved_digest is None or hook_review != "clear":
        return "unknown"
    return "verified"


class ReviewCases(unittest.TestCase):
    def test_offline_review_cases(self):
        cases = (
            ("typo", "widget-parse", "widget-parser", "digest-a", "digest-a", "clear", "suspicious"),
            ("postinstall", "widget-parser", "widget-parser", "digest-a", "digest-a", "prohibited", "suspicious"),
            ("approved", "widget-parser", "widget-parser", "digest-a", "digest-a", "clear", "verified"),
            ("offline", "widget-parser", "widget-parser", None, "digest-a", "unknown", "unknown"),
            ("pinned image", "containers/widget", "containers/widget", "digest-b", "digest-a", "clear", "suspicious"),
        )
        for name, coordinate, approved, digest, approved_digest, hook, expected in cases:
            with self.subTest(name=name):
                self.assertEqual(classify_review(coordinate, approved, digest, approved_digest, hook), expected)


if __name__ == "__main__":
    unittest.main()
