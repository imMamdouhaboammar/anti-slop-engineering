import unittest
from scripts.sre_guard import normalize_line


class NormalizationTests(unittest.TestCase):
    def test_mapping_entry_is_not_dropped(self):
        self.assertEqual(normalize_line('"role": "admin"'), '"role": "admin"')

    def test_standalone_string_is_ignored(self):
        self.assertEqual(normalize_line('"standalone",'), "")


if __name__ == "__main__":
    unittest.main()
