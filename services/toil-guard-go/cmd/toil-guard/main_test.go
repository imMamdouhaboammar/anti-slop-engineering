package main

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
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
