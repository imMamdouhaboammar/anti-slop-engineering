package main

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"slices"
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

func TestExecuteAuditCollectsUntrackedFileEvenWhenDiffExists(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)

	// 1. Modify tracked file main.go
	if err := os.WriteFile(filepath.Join(dir, "main.go"), []byte("package main\n\nfunc main() {\n\t// clean edit\n}\n"), 0600); err != nil {
		t.Fatal(err)
	}

	// 2. Create untracked bad file
	untracked := filepath.Join(dir, "untracked_bad.go")
	if err := os.WriteFile(untracked, []byte("package main\n\nfunc Bad() {\n\ttime.Sleep(5 * time.Second)\n}\n"), 0600); err != nil {
		t.Fatal(err)
	}

	var stdout, stderr bytes.Buffer
	code := executeAudit([]string{"--format", "json", "--base", "HEAD"}, &stdout, &stderr)
	if code == 0 {
		t.Fatalf("expected non-zero exit when untracked file contains blocker alongside diff, got 0")
	}
	var report model.AuditReport
	if err := json.Unmarshal(stdout.Bytes(), &report); err != nil {
		t.Fatalf("invalid JSON output: %v\n%s", err, stdout.String())
	}
	if report.SLI.Status != "BLOCKED" {
		t.Fatalf("expected BLOCKED status, got %+v", report)
	}
	foundSleep := false
	for _, f := range report.Findings {
		if f.Code == "SRE-SCALE-SLEEP" {
			foundSleep = true
			break
		}
	}
	if !foundSleep {
		t.Fatalf("expected SRE-SCALE-SLEEP finding from untracked file, got %+v", report.Findings)
	}
}

func TestCollectAuditFilesEnumeratesGitPathsFromNestedDirectory(t *testing.T) {
	dir := initTempGitRepo(t)
	nested := filepath.Join(dir, "src")
	if err := os.Mkdir(nested, 0750); err != nil {
		t.Fatal(err)
	}

	write := func(path, body string) {
		t.Helper()
		if err := os.WriteFile(filepath.Join(dir, path), []byte(body), 0600); err != nil {
			t.Fatal(err)
		}
	}
	const renamedSource = "package src\n\nfunc Worker() {}\n"
	write("src/old worker.go", renamedSource)
	write("deleted.go", "package main\n")
	write("reverted.go", "package main\n")
	write(".gitignore", "ignored.go\n")
	runGit(t, dir, "add", "-A")
	runGit(t, dir, "commit", "-m", "add tracked fixtures")

	const renamed = "src/café worker.go"
	const untracked = "src/ spaced\tworker.go"
	write("main.go", "package main\n\nfunc main() { /* edited */ }\n")
	write("staged.go", "package main\n\nfunc Added() {}\n")
	write(untracked, "package src\n\nfunc Untracked() {}\n")
	write("ignored.go", "package main\n")
	runGit(t, dir, "mv", "src/old worker.go", renamed)
	runGit(t, dir, "rm", "deleted.go")
	runGit(t, dir, "add", "staged.go")
	write("reverted.go", "package main\n// staged edit\n")
	runGit(t, dir, "add", "reverted.go")
	write("reverted.go", "package main\n")
	write("staged then removed.go", "package main\n")
	runGit(t, dir, "add", "staged then removed.go")
	if err := os.Remove(filepath.Join(dir, "staged then removed.go")); err != nil {
		t.Fatal(err)
	}
	runGit(t, dir, "config", "diff.relative", "true")

	t.Chdir(nested)
	files, err := collectAuditFiles(nil, "HEAD")
	if err != nil {
		t.Fatal(err)
	}
	want := map[string]string{
		"main.go":     "package main\n\nfunc main() { /* edited */ }\n",
		"reverted.go": "package main\n",
		"staged.go":   "package main\n\nfunc Added() {}\n",
		renamed:       renamedSource,
		untracked:     "package src\n\nfunc Untracked() {}\n",
	}
	if len(files) != len(want) {
		t.Fatalf("expected %d candidate files, got %d: %v", len(want), len(files), files)
	}
	for name, content := range want {
		if got := files[name]; got != content {
			t.Errorf("%q: got %q, want %q", name, got, content)
		}
	}
}

func TestExecuteAuditUsesFullSourceAcrossCommittedHunks(t *testing.T) {
	dir := initTempGitRepo(t)
	const path = "café worker.go"
	sourcePath := filepath.Join(dir, path)
	before := "package main\r\n\r\nfunc First() {\r\n\twork()\r\n}\r\n" +
		strings.Repeat("\n", 10) + "func Second() {\n\twork()\n}\n"
	after := strings.ReplaceAll(before, "work()", "time.Sleep(5 * time.Second)")
	if err := os.WriteFile(sourcePath, []byte(before), 0600); err != nil {
		t.Fatal(err)
	}
	runGit(t, dir, "add", path)
	runGit(t, dir, "commit", "-m", "add mixed line ending fixture")
	if err := os.WriteFile(sourcePath, []byte(after), 0600); err != nil {
		t.Fatal(err)
	}
	runGit(t, dir, "add", path)
	runGit(t, dir, "commit", "-m", "edit two separated functions")
	t.Chdir(dir)

	files, err := collectAuditFiles(nil, "HEAD~1")
	if err != nil || len(files) != 1 || files[path] != after {
		t.Fatalf("expected full current source for %q, got files=%v err=%v", path, files, err)
	}

	var stdout, stderr bytes.Buffer
	code := executeAudit([]string{"--format", "json", "--base", "HEAD~1"}, &stdout, &stderr)
	var report model.AuditReport
	if code != 1 || stderr.Len() != 0 {
		t.Fatalf("expected a blocker report, got exit=%d stderr=%q", code, stderr.String())
	}
	if err := json.Unmarshal(stdout.Bytes(), &report); err != nil {
		t.Fatal(err)
	}
	var lines []int
	for _, finding := range report.Findings {
		if finding.Code == "SRE-SCALE-SLEEP" && finding.File == path {
			lines = append(lines, finding.Line)
		}
	}
	if len(lines) != 2 || lines[0] != 4 || lines[1] != 17 {
		t.Fatalf("expected findings at source lines 4 and 17, got %v", lines)
	}
}

func TestParseGitPathsRejectsMalformedNonEmptyOutput(t *testing.T) {
	for _, output := range []string{"missing terminator", "src/worker.go\x00\x00"} {
		if _, err := parseGitPaths(output); err == nil {
			t.Errorf("expected error for malformed path list %q", output)
		}
	}
}

func TestGoldenParityFixtures(t *testing.T) {
	fixturesDir, err := filepath.Abs(filepath.Join("..", "..", "..", "..", "tests", "fixtures", "engine-parity"))
	if err != nil {
		t.Fatal(err)
	}
	fixtures := []struct {
		name    string
		path    string
		before  string
		audited int
		blocked bool
	}{
		{name: "clean"},
		{
			name: "blocker_error_swallow", path: "src/worker.py", audited: 1, blocked: true,
			before: "def process_job(job):\n    return job.run()\n",
		},
		{
			name: "deletion_only", path: "src/legacy.py",
			before: "def deprecated():\n    return True\n\n",
		},
		{
			name: "renamed_file", path: "src/old_worker.py", audited: 1,
			before: "def run_task():\n    return 42\n",
		},
		{
			name: "whitespace_path", path: "src/my helper.py", audited: 1,
			before: "def greet():\n    pass\n",
		},
		{
			name: "non_ascii_path", path: "src/café_über.py", audited: 1,
			before: "def status():\n    pass\n",
		},
	}
	for _, fixture := range fixtures {
		t.Run(fixture.name, func(t *testing.T) {
			dir := initTempGitRepo(t)
			t.Chdir(dir)
			if fixture.path != "" {
				source := filepath.Join(dir, fixture.path)
				if err := os.MkdirAll(filepath.Dir(source), 0750); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(source, []byte(fixture.before), 0600); err != nil {
					t.Fatal(err)
				}
				runGit(t, dir, "add", "--", fixture.path)
				runGit(t, dir, "commit", "-m", "add parity fixture")
				runGit(t, dir, "apply", "--recount", "--", filepath.Join(fixturesDir, fixture.name+".diff"))
			}
			files, err := collectAuditFiles(nil, "HEAD")
			if err != nil || len(files) != fixture.audited {
				t.Fatalf("expected %d audited files, got files=%v err=%v", fixture.audited, files, err)
			}
			findings, sli := sre.AuditFiles(files)
			if (sli.Status == "BLOCKED") != fixture.blocked {
				t.Fatalf("unexpected SLI status %s with findings %v", sli.Status, findings)
			}
			if fixture.blocked {
				for _, finding := range findings {
					if finding.Code == "SRE-SCALE-SWALLOW" && finding.Severity == model.SeverityBlocker {
						return
					}
				}
				t.Fatalf("expected SRE-SCALE-SWALLOW blocker finding, got %+v", findings)
			}
		})
	}
}

func TestParseGitPathsDeterministicGeneratedInputs(t *testing.T) {
	paths := []string{
		"src/my file.go",
		"src/café.go",
		"src/tab\tworker.go",
		"src/line\nworker.go",
		"src/quote\"worker.go",
		"src/arrow -> worker.go",
	}
	var seed uint64 = 0x5EEDC0DE2026
	for range 1000 {
		var want []string
		for range 8 {
			seed = seed*6364136223846793005 + 1
			want = append(want, paths[(seed>>32)%uint64(len(paths))])
		}
		stream := strings.Join(want, "\x00")
		got, err := parseGitPaths(stream + "\x00")
		if err != nil || !slices.Equal(got, want) {
			t.Fatalf("path framing changed values: got=%q want=%q err=%v", got, want, err)
		}
		if _, err := parseGitPaths(stream); err == nil {
			t.Fatalf("expected error for unterminated path stream %q", stream)
		}
	}
}

func TestConcurrentAuditRace(t *testing.T) {
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
