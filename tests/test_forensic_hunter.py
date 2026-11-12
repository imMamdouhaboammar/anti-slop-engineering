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

    def test_arc01_false_positive_regressions(self) -> None:
        # Exact bin/cli.js:496 error logger false positive case
        cli_lines = [
            (496, "console.error(`Error: update script not found at ${updateOxlintScript}`);"),
        ]
        findings = forensic_hunter.scan_lines("bin/cli.js", cli_lines)
        arc01_findings = [f for f in findings if f.code == "ARC-01"]
        self.assertEqual(len(arc01_findings), 0, f"False positive ARC-01 on bin/cli.js:496: {arc01_findings}")

        # Non-SQL loggers, error messages, and exceptions
        logger_lines = [
            (10, "console.log(`Updated ${count} records successfully`);"),
            (11, 'logger.info(f"Selected item {item_id} for user {user_id}")'),
            (12, 'log.Printf("Insert operation completed for user: %s", username)'),
            (13, 'print(f"Delete operation finished for file: {file_path}")'),
            (14, 'throw new Error(`Failed to update service config: ${cfg}`);'),
            (15, 'raise ValueError(f"Cannot select unsupported option {opt}")'),
        ]
        findings = forensic_hunter.scan_lines("service.ts", logger_lines)
        arc01_findings = [f for f in findings if f.code == "ARC-01"]
        self.assertEqual(len(arc01_findings), 0, f"False positive ARC-01 on loggers: {arc01_findings}")

        # UI copy, HTML, and JSX templates
        ui_lines = [
            (20, "<button>Delete ${item.name}</button>"),
            (21, "<span>Select an option from ${categoryName}</span>"),
            (22, "<h1>Update user profile for ${user.name}</h1>"),
            (23, "const tooltip = `Insert new comment for ${author}`;"),
            (24, "toast.success(`Updated ${itemName} successfully`);"),
        ]
        findings = forensic_hunter.scan_lines("Component.tsx", ui_lines)
        arc01_findings = [f for f in findings if f.code == "ARC-01"]
        self.assertEqual(len(arc01_findings), 0, f"False positive ARC-01 on UI copy: {arc01_findings}")

        # Documentation and comments containing SQL examples
        doc_lines = [
            (30, "// Note: run UPDATE users SET name = 'foo' where id = ${id}"),
            (31, "/* SELECT * FROM users WHERE id = ${id} */"),
            (32, '"""Example query: SELECT * FROM table WHERE id = %s"""'),
            (33, "* @example SELECT * FROM accounts WHERE id = ${id}"),
        ]
        findings = forensic_hunter.scan_lines("docs.py", doc_lines)
        arc01_findings = [f for f in findings if f.code == "ARC-01"]
        self.assertEqual(len(arc01_findings), 0, f"False positive ARC-01 on docs/comments: {arc01_findings}")

        # Mixed-case command names, file paths, and prose
        prose_lines = [
            (40, "const updateOxlintScript = path.join(dir, 'update.sh');"),
            (41, "const selectMenuCommand = `run-select --target ${target}`;"),
            (42, "const deleteUserHandler = `delete-user-job:${jobId}`;"),
            (43, "const updateUrl = `https://api.example.com/v1/update/${userId}`;"),
            (44, "const msg = `select one of the following: ${items.join(', ')}`;"),
        ]
        findings = forensic_hunter.scan_lines("handler.ts", prose_lines)
        arc01_findings = [f for f in findings if f.code == "ARC-01"]
        self.assertEqual(len(arc01_findings), 0, f"False positive ARC-01 on mixed-case command names: {arc01_findings}")

    def test_arc01_positive_execution_sinks_critical(self) -> None:
        # Real query execution sinks with interpolated dynamic SQL
        sink_cases = [
            (1, "await db.query(`SELECT * FROM users WHERE id = ${userId}`);", "service.ts"),
            (2, 'pool.query("SELECT * FROM accounts WHERE email = \'" + email + "\'");', "db.js"),
            (3, "client.query(`UPDATE users SET name = '${name}' WHERE id = ${id}`);", "user.ts"),
            (4, "conn.query(`DELETE FROM sessions WHERE token = '${token}'`);", "auth.js"),
            (5, "db.execute(`INSERT INTO audit_log (action) VALUES ('${action}')`);", "log.ts"),
            (6, "sql.raw(`SELECT * FROM ${table} WHERE id = ${id}`);", "query.ts"),
            (7, "prisma.$queryRawUnsafe(`SELECT * FROM users WHERE role = '${role}'`);", "prisma.ts"),
            (8, 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")', "repo.py"),
            (9, 'cursor.execute("SELECT * FROM users WHERE name = \'%s\'" % name)', "repo.py"),
            (10, 'session.execute(f"UPDATE accounts SET balance = {amount} WHERE id = {acc_id}")', "repo.py"),
            (11, 'db.Query(fmt.Sprintf("SELECT * FROM users WHERE email = \'%s\'", email))', "db.go"),
            (12, 'sqlx::query(&format!("SELECT * FROM users WHERE id = {}", user_id));', "db.rs"),
        ]
        for line_no, raw_line, filename in sink_cases:
            findings = forensic_hunter.scan_lines(filename, [(line_no, raw_line)])
            arc01_findings = [f for f in findings if f.code == "ARC-01"]
            self.assertEqual(len(arc01_findings), 1, f"Expected 1 ARC-01 finding for: {raw_line}")
            self.assertEqual(arc01_findings[0].severity, "CRITICAL", f"Expected CRITICAL for sink: {raw_line}")

    def test_arc01_multi_line_query_and_sink_critical(self) -> None:
        # Multi-line: variable assigned dynamic SQL, then passed to execution sink
        py_lines = [
            'sql = f"SELECT * FROM users WHERE id = {user_id}"',
            'cursor.execute(sql)',
        ]
        findings = forensic_hunter.scan_lines("repo.py", list(enumerate(py_lines, start=1)), full_file_lines=py_lines)
        arc01_findings = [f for f in findings if f.code == "ARC-01"]
        self.assertEqual(len(arc01_findings), 1)
        self.assertEqual(arc01_findings[0].severity, "CRITICAL")
        self.assertEqual(arc01_findings[0].line, 1)

        ts_lines = [
            'const query = `SELECT * FROM accounts WHERE id = ${accountId}`;',
            'const result = await db.query(query);',
        ]
        findings_ts = forensic_hunter.scan_lines("repo.ts", list(enumerate(ts_lines, start=1)), full_file_lines=ts_lines)
        arc01_ts = [f for f in findings_ts if f.code == "ARC-01"]
        self.assertEqual(len(arc01_ts), 1)
        self.assertEqual(arc01_ts[0].severity, "CRITICAL")
        self.assertEqual(arc01_ts[0].line, 1)

    def test_arc01_unverified_query_building_high_candidate(self) -> None:
        # Credible SQL query construction without verified execution sink -> HIGH candidate for review
        lines = [
            (1, 'query = "SELECT * FROM users WHERE id = " + user_id'),
        ]
        findings = forensic_hunter.scan_lines("query.py", lines)
        arc01_findings = [f for f in findings if f.code == "ARC-01"]
        self.assertEqual(len(arc01_findings), 1)
        self.assertEqual(arc01_findings[0].severity, "HIGH")
        self.assertIn("unverified", arc01_findings[0].title.lower())

    def test_cli_scan_bin_cli_js_not_flagged(self) -> None:
        out = io.StringIO()
        with redirect_stdout(out):
            code = forensic_hunter.main(["--files", "bin/cli.js", "--fail-on-critical", "--json"])
        self.assertEqual(code, 0)
        data = json.loads(out.getvalue())
        self.assertEqual(data["counts"]["CRITICAL"], 0)
        arc01_findings = [f for f in data["findings"] if f["code"] == "ARC-01"]
        self.assertEqual(len(arc01_findings), 0, f"Unexpected ARC-01 findings on bin/cli.js: {arc01_findings}")


if __name__ == "__main__":
    unittest.main()
