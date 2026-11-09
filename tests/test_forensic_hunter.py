#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from unittest.mock import patch

from scripts import forensic_hunter


class ForensicHunterTests(unittest.TestCase):
    def test_matches_file_target(self) -> None:
        rule_docker = forensic_hunter.TrapRule(
            code="DCK-01",
            stack="docker",
            severity="CRITICAL",
            pattern=forensic_hunter.sre_compile.compile(r"FROM"),
            title="Docker rule",
            impact="impact",
            remedy="remedy",
            file_names=("Dockerfile", "Containerfile"),
            file_extensions=(".dockerfile",),
        )
        self.assertTrue(forensic_hunter.matches_file_target(rule_docker, "Dockerfile"))
        self.assertTrue(forensic_hunter.matches_file_target(rule_docker, "path/to/Dockerfile"))
        self.assertTrue(forensic_hunter.matches_file_target(rule_docker, "app.dockerfile"))
        self.assertFalse(forensic_hunter.matches_file_target(rule_docker, "server.ts"))

    def test_docker_traps(self) -> None:
        lines = [
            (1, "FROM node:latest"),
            (2, 'CMD npm start'),
            (3, "ARG PRIVATE_KEY_SECRET=xyz"),
            (4, "RUN curl https://example.com/install.sh | bash"),
        ]
        findings = forensic_hunter.scan_lines("Dockerfile", lines)
        codes = {f.code for f in findings}
        self.assertIn("DCK-01", codes)
        self.assertIn("DCK-02", codes)
        self.assertIn("DCK-03", codes)
        self.assertIn("DCK-04", codes)

    def test_k8s_traps_and_manifest_limits(self) -> None:
        lines = [
            (1, "apiVersion: apps/v1"),
            (2, "kind: Deployment"),
            (3, "spec:"),
            (4, "  template:"),
            (5, "    spec:"),
            (6, "      hostNetwork: true"),
            (7, "      containers:"),
            (8, "      - name: web"),
            (9, "        image: web:latest"),
            (10, "        securityContext:"),
            (11, "          allowPrivilegeEscalation: true"),
        ]
        full_lines = [line for _, line in lines]
        findings = forensic_hunter.scan_lines("deploy.yaml", lines, full_file_lines=full_lines)
        codes = {f.code for f in findings}
        self.assertIn("K8S-01", codes)
        self.assertIn("K8S-02", codes)
        self.assertIn("K8S-03", codes)
        self.assertIn("K8S-04", codes)  # Missing resources.limits
        self.assertIn("K8S-05", codes)  # Missing runAsNonRoot

    def test_python_traps(self) -> None:
        lines = [
            (1, "def compute_items(items=[]):"),
            (2, "    try:"),
            (3, "        res = pickle.loads(b'data')"),
            (4, "    except: pass"),
            (5, "async def background():"),
            (6, "    asyncio.create_task(do_work())"),
            (7, "    subprocess.run('ls', shell=True)"),
            (8, "    requests.get('https://example.com')"),
        ]
        findings = forensic_hunter.scan_lines("service.py", lines)
        codes = {f.code for f in findings}
        self.assertIn("PY-01", codes)
        self.assertIn("PY-02", codes)
        self.assertIn("PY-03", codes)
        self.assertIn("PY-04", codes)
        self.assertIn("PY-05", codes)
        self.assertIn("PY-06", codes)

    def test_typescript_and_bun_traps(self) -> None:
        lines = [
            (1, "const data = raw as any;"),
            (2, "items.forEach(async (item) => { await process(item); });"),
            (3, "await Promise.all(users.map(async (u) => fetchUser(u)));"),
            (4, "try { doSomething(); } catch {}"),
            (5, "Bun.spawn(['sh', '-c', `cat ${path}`]);"),
            (6, "Bun.serve({ fetch() { return new Response('ok'); } });"),
        ]
        findings = forensic_hunter.scan_lines("server.ts", lines)
        codes = {f.code for f in findings}
        self.assertIn("TS-01", codes)
        self.assertIn("TS-02", codes)
        self.assertIn("TS-03", codes)
        self.assertIn("TS-04", codes)
        self.assertIn("BUN-01", codes)
        self.assertIn("BUN-02", codes)

    def test_react_traps(self) -> None:
        lines = [
            (1, "return items.map((item, index) => <Item key={index} />);"),
            (2, "<div dangerouslySetInnerHTML={{ __html: untrustedHtml }} />"),
            (3, "<p>Mock data: pending backend implementation</p>"),
        ]
        findings = forensic_hunter.scan_lines("Component.tsx", lines)
        codes = {f.code for f in findings}
        self.assertIn("RCT-01", codes)
        self.assertIn("RCT-02", codes)
        self.assertIn("RCT-03", codes)

    def test_rust_traps(self) -> None:
        lines = [
            (1, "let val = option.unwrap();"),
            (2, "unsafe { *ptr = 42; }"),
            (3, "std::thread::sleep(std::time::Duration::from_secs(1));"),
            (4, "let (tx, rx) = mpsc::unbounded_channel();"),
        ]
        findings = forensic_hunter.scan_lines("main.rs", lines)
        codes = {f.code for f in findings}
        self.assertIn("RS-01", codes)
        self.assertIn("RS-02", codes)
        self.assertIn("RS-03", codes)
        self.assertIn("RS-04", codes)

    def test_golang_traps(self) -> None:
        lines = [
            (1, "_ = db.Exec(query)"),
            (2, "resp, err := http.Get(url)"),
            (3, "go func() { work() }()"),
        ]
        findings = forensic_hunter.scan_lines("handler.go", lines)
        codes = {f.code for f in findings}
        self.assertIn("GO-01", codes)
        self.assertIn("GO-02", codes)
        self.assertIn("GO-03", codes)

    def test_shell_traps(self) -> None:
        lines = [
            (1, "#!/usr/bin/env bash"),
            (2, "rm -rf $TARGET_DIR/"),
        ]
        full_lines = [line for _, line in lines]
        findings = forensic_hunter.scan_lines("deploy.sh", lines, full_file_lines=full_lines)
        codes = {f.code for f in findings}
        self.assertIn("SH-01", codes)
        self.assertIn("SH-02", codes)  # Missing set -euo pipefail

    def test_architecture_traps(self) -> None:
        lines = [
            (1, 'query = "SELECT * FROM users WHERE id = " + user_id'),
            (2, 'SELECT * FROM transactions;'),
            (3, 'const secret = process.env.API_KEY || "secret";'),
        ]
        findings = forensic_hunter.scan_lines("query.py", lines)
        codes = {f.code for f in findings}
        self.assertIn("ARC-01", codes)
        self.assertIn("ARC-02", codes)
        self.assertIn("ARC-03", codes)

    def test_stack_filter(self) -> None:
        lines = [
            (1, "def fn(x=[]): pass"),
            (2, "const x = val as any;"),
        ]
        findings_py_only = forensic_hunter.scan_lines("file.py", lines, allowed_stacks={"python"})
        self.assertEqual(len(findings_py_only), 1)
        self.assertEqual(findings_py_only[0].code, "PY-01")

    def test_cli_file_scan_with_json_and_exit_codes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            clean_file = os.path.join(tmpdir, "clean.py")
            with open(clean_file, "w", encoding="utf-8") as f:
                f.write("def safe_fn(items=None):\n    pass\n")

            out = io.StringIO()
            with redirect_stdout(out):
                code = forensic_hunter.main(["--files", clean_file, "--json"])
            self.assertEqual(code, 0)
            data = json.loads(out.getvalue())
            self.assertEqual(data["verdict"], "FORTIFIED (PASS)")
            self.assertEqual(data["total_findings"], 0)

            trap_file = os.path.join(tmpdir, "trap.py")
            with open(trap_file, "w", encoding="utf-8") as f:
                f.write("def bad_fn(items=[]):\n    pass\n")

            out_trap = io.StringIO()
            with redirect_stdout(out_trap):
                code_crit = forensic_hunter.main(["--files", trap_file, "--fail-on-critical", "--json"])
            self.assertEqual(code_crit, 2)
            data_crit = json.loads(out_trap.getvalue())
            self.assertEqual(data_crit["verdict"], "COMPROMISED (BLOCK)")
            self.assertEqual(data_crit["counts"]["CRITICAL"], 1)

    def test_cli_parse_git_diff_failure(self) -> None:
        with patch("subprocess.run") as mock_run:
            mock_run.return_value.returncode = 128
            mock_run.return_value.stderr = "fatal: bad revision"
            with self.assertRaises(RuntimeError):
                forensic_hunter.parse_git_diff("nonexistent-ref")


if __name__ == "__main__":
    unittest.main()
