# SPDX-License-Identifier: MIT
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts.git_changeset import collect_changes, path_record


REPO_ROOT = Path(__file__).resolve().parents[1]


class ChangeSetTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory()
        self.addCleanup(workspace.cleanup)
        self.repo = Path(workspace.name)
        (self.repo / "src").mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "fixture@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.git("config", "core.filemode", "true")
        for name in ("rename.txt", "mode.txt", "delete.txt", "type.txt"):
            (self.repo / name).write_text("alpha\nbeta\ngamma\n", encoding="utf-8")
        (self.repo / "delete.txt").write_text("distinct removed content\n", encoding="utf-8")
        (self.repo / "tool.bin").write_bytes(b"\x00\x01")
        self.git("add", "--", ".")
        self.git("commit", "-qm", "fixture base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.repo), *args], text=True)

    def test_each_snapshot_has_an_explicit_target(self):
        path = self.repo / "stage.py"
        path.write_text("value = 1\n", encoding="utf-8")
        self.git("add", "--", "stage.py")
        self.git("commit", "-qm", "added file")
        head = self.git("rev-parse", "HEAD").strip()
        path.write_text("value = 1\nvalue = 2\n", encoding="utf-8")
        self.git("add", "--", "stage.py")
        path.write_text("value = 1\nvalue = 2\nvalue = 3\n", encoding="utf-8")
        (self.repo / "new.py").write_text("simple = True\n", encoding="utf-8")
        self.assertEqual(collect_changes(self.repo, head, "index")["files"][0]["added"], 1)
        worktree = collect_changes(self.repo, head, "worktree")
        self.assertEqual(worktree["files"][0]["added"], 2)
        self.assertEqual(worktree["untracked"], [{"text": "new.py", "raw_hex": None}])
        committed = collect_changes(self.repo, self.base, "commit", head)
        self.assertEqual(committed["target"], head)
        self.assertEqual(committed["files"][0]["status"], "A")
        self.assertEqual(committed["untracked"], [])
        self.assertEqual(json.loads(json.dumps(committed))["version"], 1)

    def test_git_reports_paths_and_metadata_without_reading_source_files(self):
        name = 'café "quoted"\tfile.py'
        self.git("config", "core.quotePath", "true")
        self.git("config", "diff.noprefix", "true")
        self.git("config", "diff.interHunkContext", "5")
        self.git("mv", "rename.txt", name)
        (self.repo / name).write_text("alpha\nbeta\ngamma\nvalue = 4\n", encoding="utf-8")
        (self.repo / "delete.txt").unlink()
        (self.repo / "mode.txt").chmod(0o755)
        (self.repo / "tool.bin").write_bytes(b"\x00\x02")
        (self.repo / "type.txt").unlink()
        (self.repo / "type.txt").symlink_to("mode.txt")
        files = collect_changes(self.repo, "HEAD", "worktree")["files"]
        by_status = {item["status"]: item for item in files if item["status"] != "M"}
        rename = by_status["R"]
        self.assertEqual(rename["old_path"]["text"], "rename.txt")
        self.assertEqual(rename["new_path"]["text"], name)
        self.assertEqual(rename["hunks"], [{"old_start": 3, "old_count": 0, "new_start": 4, "new_count": 1}])
        self.assertIsNone(by_status["D"]["new_path"])
        self.assertEqual([(h["old_count"], h["new_count"]) for h in by_status["T"]["hunks"]], [(3, 0), (0, 1)])
        by_path = {item["new_path"]["text"]: item for item in files if item["new_path"]}
        self.assertEqual(by_path["mode.txt"]["new_mode"], "100755")
        self.assertEqual(by_path["mode.txt"]["hunks"], [])
        self.assertTrue(by_path["tool.bin"]["binary"])
        self.assertIsNone(by_path["tool.bin"]["added"])

    def test_undecodable_names_retain_bytes_when_filesystem_supports_them(self):
        raw_name = b"file-\xff.py"
        path = os.fsencode(self.repo) + b"/" + raw_name
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_WRONLY, 0o600)
        except OSError:
            self.assertEqual(path_record(raw_name), {"text": None, "raw_hex": raw_name.hex()})
        else:
            os.close(descriptor)
            self.assertEqual(collect_changes(self.repo, "HEAD", "worktree")["untracked"],
                             [{"text": None, "raw_hex": raw_name.hex()}])

    def test_git_diff_attributes_only_new_lines_for_quoted_paths(self):
        self.git("config", "diff.noprefix", "true")
        self.git("config", "diff.interHunkContext", "2")
        name = 'src/café with tab\t.py'
        source = self.repo / name
        source.write_text("import time\nfirst = 1\ntime.sleep(2)\nlast = 3\n", encoding="utf-8")
        self.git("add", "--", name)
        self.git("commit", "-qm", "initial audited source")
        source.write_text("import time\nfirst = 2\ntime.sleep(2)\ntime.sleep(4)\n", encoding="utf-8")
        result = subprocess.check_output([
            "python3", str(REPO_ROOT / "scripts" / "sre_guard.py"),
            "--repo", str(self.repo), "--base", "HEAD", "--json",
        ], text=True)
        report = json.loads(result)
        self.assertEqual(report["summary"]["scanned_files"], 1)
        self.assertEqual(
            [(finding["line"], finding["in_active_diff"]) for finding in report["findings"]
             if finding["id"] == "SCALE_SLEEP_BAND_AID"],
            [(3, False), (4, True)],
        )

    def test_standalone_producer_outputs_json_only(self):
        script = str(REPO_ROOT / "scripts" / "git_changeset.py")
        command = [sys.executable, "-S", script, "--repo", str(self.repo), "--base", "HEAD"]
        result = subprocess.run(command + ["--snapshot", "index"], capture_output=True, text=True, check=True)
        self.assertEqual(result.stderr, "")
        self.assertEqual(json.loads(result.stdout), collect_changes(self.repo, "HEAD", "index"))
        bad_result = subprocess.run(
            command + ["--snapshot", "commit"], capture_output=True, text=True, check=False,
        )
        self.assertEqual(bad_result.returncode, 1)
        self.assertEqual(bad_result.stdout, "")
        self.assertIn("target is required", bad_result.stderr)

    def test_portable_diff_uses_exact_quoted_path_and_line(self):
        name = "src/café with space.py"
        source = self.repo / name
        source.write_text("value = 1\n", encoding="utf-8")
        self.git("add", "--", name)
        self.git("commit", "-qm", "tracked file")
        source.write_text("value = 1\ntry: pass\nexcept Exception: pass\n", encoding="utf-8")
        result = subprocess.check_output([
            sys.executable, "-S", str(REPO_ROOT / "scripts" / "diff_guard.py"),
            "--repo", str(self.repo), "--base", "HEAD", "--json",
        ], text=True)
        report = json.loads(result)
        self.assertEqual(report["summary"]["changed_files"], 1)
        self.assertIn((name, 3), [
            (item["file"], item["line"]) for item in report["findings"]
            if item["id"] == "ERROR_SWALLOW_CANDIDATE"
        ])

    def test_invalid_mode_and_revision_fail_explicitly(self):
        with self.assertRaises(ValueError):
            collect_changes(self.repo, "HEAD", "commit")
        with self.assertRaises(RuntimeError):
            collect_changes(self.repo, "--not-a-ref", "worktree")
