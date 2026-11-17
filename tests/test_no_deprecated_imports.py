import pathlib
import subprocess
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = [
    "scripts/bump_version.py",
    "scripts/diff_guard.py",
    "scripts/forensic_hunter.py",
    "scripts/sre_guard.py",
]


class NoDeprecatedImportsTests(unittest.TestCase):
    def test_scripts_import_without_deprecation_warnings(self):
        for script in SCRIPTS:
            with self.subTest(script=script):
                result = subprocess.run(
                    [sys.executable, "-W", "error::DeprecationWarning", str(ROOT / script), "--help"],
                    text=True,
                    capture_output=True,
                )
                self.assertEqual(result.returncode, 0, f"{script} failed under -W error::DeprecationWarning:\n{result.stderr}")


if __name__ == "__main__":
    unittest.main()
