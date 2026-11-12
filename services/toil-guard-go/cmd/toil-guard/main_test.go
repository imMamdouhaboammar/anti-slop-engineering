package main

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/sre"
)

func initTempGitRepo(t *testing.T) string {
	t.Helper()
	dir := t.TempDir()
	runGit(t, dir, "init")
	runGit(t, dir, "config", "user.email", "test@example.com")
	runGit(t, dir, "config", "user.name", "Test User")
	if err := os.WriteFile(filepath.Join(dir, "main.go"), []byte("package main\n\nfunc main() {}\n"), 0600); err != nil {
		t.Fatal(err)
	}
	runGit(t, dir, "add", "main.go")
	runGit(t, dir, "commit", "-m", "initial commit")
	return dir
}

func runGit(t *testing.T, dir string, args ...string) {
	t.Helper()
	cmd := exec.Command("git", append([]string{"-C", dir}, args...)...)
	if out, err := cmd.CombinedOutput(); err != nil {
		t.Fatalf("git %v failed: %v\n%s", args, err, string(out))
	}
}

func TestCollectAuditFilesCleanRepoReturnsEmptyMap(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)

	files, err := collectAuditFiles(nil, "HEAD")
	if err != nil {
		t.Fatalf("expected clean repository to succeed, got error: %v", err)
	}
	if len(files) != 0 {
		t.Fatalf("expected 0 changed files in clean repository, got %d (%v)", len(files), files)
	}
}

func TestCollectAuditFilesRejectsMissingTarget(t *testing.T) {
	if _, err := collectAuditFiles([]string{filepath.Join(t.TempDir(), "missing.go")}, "HEAD"); err == nil {
		t.Fatal("expected missing path error")
	}
}

func TestCollectAuditFilesRejectsEmptyDirectory(t *testing.T) {
	if _, err := collectAuditFiles([]string{t.TempDir()}, "HEAD"); err == nil {
		t.Fatal("expected empty audit error")
	}
}

func TestCollectAuditFilesReadsSourceFile(t *testing.T) {
	path := filepath.Join(t.TempDir(), "main.go")
	if err := os.WriteFile(path, []byte("package main\n"), 0600); err != nil {
		t.Fatal(err)
	}
	files, err := collectAuditFiles([]string{path}, "HEAD")
	if err != nil || len(files) != 1 || files[path] != "package main\n" {
		t.Fatalf("got files=%v err=%v", files, err)
	}
}

func TestCollectAuditFilesRejectsInvalidGitBase(t *testing.T) {
	if _, err := collectAuditFiles(nil, "nonexistent-revision-123"); err == nil {
		t.Fatal("expected git diff error")
	}
}

func TestExecuteAuditCleanRepositoryJSONAndText(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)

	var stdout, stderr bytes.Buffer
	code := executeAudit([]string{"--format", "json", "--base", "HEAD"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0 on clean repo, got %d (stderr=%q)", code, stderr.String())
	}
	if stderr.Len() != 0 {
		t.Fatalf("expected empty stderr on clean repo, got %q", stderr.String())
	}
	if !strings.Contains(stdout.String(), `"findings": []`) {
		t.Fatalf("expected empty JSON array for findings, got:\n%s", stdout.String())
	}

	var report model.AuditReport
	if err := json.Unmarshal(stdout.Bytes(), &report); err != nil {
		t.Fatalf("invalid JSON output: %v\n%s", err, stdout.String())
	}
	if report.Engine != "toil-guard-go" || report.SLI.Status != "PASSED" {
		t.Fatalf("unexpected report header/status: %+v", report)
	}
	if report.SLI.TotalFiles != 0 || report.SLI.TotalLines != 0 || report.SLI.ToilIncidents != 0 || report.SLI.ErrorBudgetLeft != 100.0 || len(report.Findings) != 0 {
		t.Fatalf("expected zero-file/zero-finding clean report, got: %+v", report)
	}

	stdout.Reset()
	stderr.Reset()
	code = executeAudit([]string{"--format", "text", "--base", "HEAD"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0 on clean repo text output, got %d (stderr=%q)", code, stderr.String())
	}
	if !strings.Contains(stdout.String(), "Status: PASSED") || !strings.Contains(stdout.String(), "Audited Files: 0 | Lines: 0") {
		t.Fatalf("unexpected clean text report:\n%s", stdout.String())
	}
}

func TestExecuteAuditNonAuditableOnlyChangesReportsZeroChanges(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)

	if err := os.WriteFile(filepath.Join(dir, "README.md"), []byte("# Docs\n"), 0600); err != nil {
		t.Fatal(err)
	}
	runGit(t, dir, "add", "README.md")

	var stdout, stderr bytes.Buffer
	code := executeAudit([]string{"--format", "json", "--base", "HEAD"}, &stdout, &stderr)
	if code != 0 {
		t.Fatalf("expected exit 0 when only non-auditable files changed, got %d (stderr=%q)", code, stderr.String())
	}
	var report model.AuditReport
	if err := json.Unmarshal(stdout.Bytes(), &report); err != nil {
		t.Fatalf("invalid JSON output: %v", err)
	}
	if report.SLI.TotalFiles != 0 || report.SLI.Status != "PASSED" || len(report.Findings) != 0 {
		t.Fatalf("expected zero auditable files, got: %+v", report)
	}
}

func TestExecuteAuditRejectsInvalidRefsAndNonGitDirs(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)

	for _, base := range []string{"nonexistent-ref", "--stat", ""} {
		var stdout, stderr bytes.Buffer
		code := executeAudit([]string{"--base", base}, &stdout, &stderr)
		if code == 0 {
			t.Fatalf("expected non-zero exit for invalid base %q, got 0", base)
		}
		if stderr.Len() == 0 {
			t.Fatalf("expected stderr message for invalid base %q", base)
		}
	}

	nonGitDir := t.TempDir()
	t.Chdir(nonGitDir)
	var stdout, stderr bytes.Buffer
	if code := executeAudit([]string{"--base", "HEAD"}, &stdout, &stderr); code == 0 {
		t.Fatal("expected non-zero exit outside git repository")
	}
}

func TestExecuteAuditRejectsMissingAndUnreadableExplicitPaths(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)

	var stdout, stderr bytes.Buffer
	missing := filepath.Join(dir, "does-not-exist.go")
	if code := executeAudit([]string{missing}, &stdout, &stderr); code == 0 {
		t.Fatalf("expected non-zero exit for missing explicit path %q", missing)
	}

	if os.Geteuid() != 0 {
		unreadable := filepath.Join(dir, "unreadable.go")
		if err := os.WriteFile(unreadable, []byte("package main\n"), 0000); err != nil {
			t.Fatal(err)
		}
		t.Cleanup(func() {
			_ = os.Chmod(unreadable, 0600)
		})
		stdout.Reset()
		stderr.Reset()
		if code := executeAudit([]string{unreadable}, &stdout, &stderr); code == 0 {
			t.Fatalf("expected non-zero exit for unreadable explicit path %q", unreadable)
		}
	}
}

func TestParseGitDiffRejectsMalformedNonEmptyOutput(t *testing.T) {
	if _, err := parseGitDiff("not a valid git diff\n+added line\n"); err == nil {
		t.Fatal("expected error for malformed diff without diff header")
	}
}

func TestExecuteAuditCollectsUntrackedFileInNestedDir(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)

	nestedDir := filepath.Join(dir, "src")
	if err := os.MkdirAll(nestedDir, 0750); err != nil {
		t.Fatal(err)
	}
	nestedFile := filepath.Join(nestedDir, "bad.go")
	if err := os.WriteFile(nestedFile, []byte("package src\n\nfunc Bad() {\n\ttime.Sleep(5 * time.Second)\n}\n"), 0600); err != nil {
		t.Fatal(err)
	}

	var stdout, stderr bytes.Buffer
	code := executeAudit([]string{"--format", "json", "--base", "HEAD"}, &stdout, &stderr)
	if code == 0 {
		t.Fatalf("expected non-zero exit for untracked nested blocker, got 0 (stdout=%s)", stdout.String())
	}
	var report model.AuditReport
	if err := json.Unmarshal(stdout.Bytes(), &report); err != nil {
		t.Fatalf("invalid JSON output: %v\n%s", err, stdout.String())
	}
	if report.SLI.TotalFiles != 1 || report.SLI.Status != "BLOCKED" || len(report.Findings) == 0 {
		t.Fatalf("expected 1 blocked nested file, got: %+v", report)
	}
}

func TestGoldenParityFixtures(t *testing.T) {
	fixturesDir := filepath.Join("..", "..", "..", "..", "tests", "fixtures", "engine-parity")

	cleanBytes, err := os.ReadFile(filepath.Join(fixturesDir, "clean.diff"))
	if err != nil {
		t.Fatalf("read clean.diff: %v", err)
	}
	cleanFiles, err := parseGitDiff(string(cleanBytes))
	if err != nil || len(cleanFiles) != 0 {
		t.Fatalf("expected empty map for clean.diff, got files=%v err=%v", cleanFiles, err)
	}

	blockerBytes, err := os.ReadFile(filepath.Join(fixturesDir, "blocker_error_swallow.diff"))
	if err != nil {
		t.Fatalf("read blocker_error_swallow.diff: %v", err)
	}
	blockerFiles, err := parseGitDiff(string(blockerBytes))
	if err != nil {
		t.Fatalf("parse blocker diff: %v", err)
	}
	findings, sli := sre.AuditFiles(blockerFiles)
	if sli.Status != "BLOCKED" {
		t.Fatalf("expected BLOCKED status for blocker fixture, got %+v", sli)
	}
	foundSwallow := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" && f.Severity == model.SeverityBlocker {
			foundSwallow = true
			break
		}
	}
	if !foundSwallow {
		t.Fatalf("expected SRE-SCALE-SWALLOW blocker finding, got %+v", findings)
	}

	for _, name := range []string{"deletion_only.diff", "renamed_file.diff", "whitespace_path.diff", "non_ascii_path.diff"} {
		raw, readErr := os.ReadFile(filepath.Join(fixturesDir, name))
		if readErr != nil {
			t.Fatalf("read %s: %v", name, readErr)
		}
		files, parseErr := parseGitDiff(string(raw))
		if parseErr != nil {
			t.Fatalf("parse %s failed: %v", name, parseErr)
		}
		_, fixtureSLI := sre.AuditFiles(files)
		if fixtureSLI.Status == "BLOCKED" {
			t.Fatalf("unexpected BLOCKED status for %s: %+v", name, fixtureSLI)
		}
	}
}

func TestParseGitDiffDeterministicFuzzAndConcurrentAuditRace(t *testing.T) {
	fragments := []string{
		"diff --git a/src/my file.go b/src/my file.go\n",
		"diff --git \"a/src/caf\\303\\251.go\" \"b/src/caf\\303\\251.go\"\n",
		"+++ b/src/my file.go\n",
		"+++ /dev/null\n",
		"@@ -1 +0,0 @@\n",
		"+func ok() {}\r\n",
		"+if err != nil {}\n",
		"+++not a header\n",
	}

	var seed uint64 = 0x5EEDC0DE2026
	for i := 0; i < 64; i++ {
		var sb strings.Builder
		for step := 0; step < 8; step++ {
			seed = seed*6364136223846793005 + 1
			sb.WriteString(fragments[(seed>>32)%uint64(len(fragments))])
		}
		files, err := parseGitDiff(sb.String())
		if err == nil {
			_, _ = sre.AuditFiles(files)
		}
	}

	sample := map[string]string{
		"a.go": "package a\nfunc A() { if err != nil {} }\n",
		"b.go": "package b\nfunc B() {}\n",
	}
	var wg sync.WaitGroup
	for g := 0; g < 8; g++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for iter := 0; iter < 10; iter++ {
				findings, sli := sre.AuditFiles(sample)
				if sli.Status != "BLOCKED" || len(findings) == 0 {
					t.Errorf("unexpected concurrent audit result: status=%s findings=%d", sli.Status, len(findings))
				}
			}
		}()
	}
	wg.Wait()
}
