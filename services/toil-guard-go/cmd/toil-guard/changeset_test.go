package main

import (
	"bytes"
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf8"
)

func TestEvidenceModeRejectsInvalidOptionCombinations(t *testing.T) {
	for _, args := range [][]string{
		{"--changeset", "worktree.json"},
		{"--index-changeset", "index.json"},
		{"--changeset=", "--index-changeset="},
		{"--changeset", "worktree.json", "--index-changeset", "index.json", "."},
	} {
		var out, stderr bytes.Buffer
		exit := executeAudit(args, &out, &stderr)
		if exit != 2 || out.Len() != 0 || !strings.Contains(stderr.String(), "both") {
			t.Errorf("invalid combination %v: exit=%d stdout=%q stderr=%q", args, exit, &out, &stderr)
		}
	}
}

func TestEvidenceModeValidatesScopeVersionAndBase(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)
	head := runEvidenceFixtureGit(t, dir, "rev-parse", "HEAD")
	documents := t.TempDir()
	if err := os.WriteFile(".gitignore", []byte("ignored.go\n"), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile("ignored.go", []byte("package main\n"), 0600); err != nil {
		t.Fatal(err)
	}
	empty := emptyEvidenceDocument("index", head)
	for _, tt := range []struct {
		name, body, want string
	}{
		{"version", strings.Replace(emptyEvidenceDocument("worktree", head), `"version":1`, `"version":2`, 1), "version"},
		{"base", emptyEvidenceDocument("worktree", strings.Repeat("0", 40)), "base"},
		{"wrong_snapshot", empty, "snapshot"},
		{"traversal", evidenceDocument(head, `{"text":"../outside.go","raw_hex":null}`), "repository-relative"},
		{"absolute", evidenceDocument(head, `{"text":"/outside.go","raw_hex":null}`), "repository-relative"},
		{"metadata", evidenceDocument(head, `{"text":".git/metadata.go","raw_hex":null}`), "repository-relative"},
		{"dual_representation", evidenceDocument(head, `{"text":"main.go","raw_hex":"ff"}`), "representation"},
		{"invalid_kind", strings.Replace(evidenceDocument(head, `{"text":"main.go","raw_hex":null}`), `"files":[]`, `"files":[{"status":"Z","new_path":{"text":"main.go"}}]`, 1), "status"},
		{"invalid_type", strings.Replace(evidenceDocument(head, `{"text":"main.go","raw_hex":null}`), `"files":[]`, `"files":[{"status":"M","old_path":{"text":"main.go"},"new_path":{"text":"main.go"},"new_mode":"000111"}]`, 1), "mode"},
		{"ignored_candidate", evidenceDocument(head, `{"text":"ignored.go","raw_hex":null}`), "non-ignored"},
		{"unexpected_commit", strings.Replace(evidenceDocument(head, `{"text":"main.go","raw_hex":null}`), `"target":null`, `"target":"some-commit"`, 1), "target"},
		{"trailing", evidenceDocument(head, `{"text":"main.go","raw_hex":null}`) + " {}", "trailing"},
	} {
		t.Run(tt.name, func(t *testing.T) {
			worktree := filepath.Join(documents, "worktree.json")
			index := filepath.Join(documents, "index.json")
			if err := os.WriteFile(worktree, []byte(tt.body), 0600); err != nil {
				t.Fatal(err)
			}
			if err := os.WriteFile(index, []byte(empty), 0600); err != nil {
				t.Fatal(err)
			}
			var out, stderr bytes.Buffer
			code := executeAudit([]string{"--changeset", worktree, "--index-changeset", index, "--format", "json"}, &out, &stderr)
			if code != 1 || out.Len() != 0 || !strings.Contains(stderr.String(), tt.want) {
				t.Fatalf("expected %q failure: exit=%d stdout=%q stderr=%q", tt.want, code, &out, &stderr)
			}
		})
	}
}

func emptyEvidenceDocument(snapshot, base string) string {
	return `{"version":1,"snapshot":"` + snapshot + `","base":"` + base + `","target":null,"files":[],"untracked":[]}`
}

func evidenceDocument(base, path string) string {
	return strings.Replace(emptyEvidenceDocument("worktree", base), `"untracked":[]`, `"untracked":[`+path+`]`, 1)
}

func runEvidenceFixtureGit(t *testing.T, dir string, args ...string) string {
	t.Helper()
	cmd := exec.Command("git", append([]string{"-C", dir}, args...)...)
	out, err := cmd.CombinedOutput()
	if err != nil {
		t.Fatalf("git %v: %v: %s", args, err, out)
	}
	return strings.TrimSpace(string(out))
}

func TestEvidenceModeEnforcesByteLimitsAndRawPaths(t *testing.T) {
	dir := initTempGitRepo(t)
	t.Chdir(dir)
	head := runEvidenceFixtureGit(t, dir, "rev-parse", "HEAD")
	docs := t.TempDir()
	worktree := filepath.Join(docs, "worktree.json")
	index := filepath.Join(docs, "index.json")
	body := evidenceDocument(head, `{"text":"main.go","raw_hex":null}`)
	empty := emptyEvidenceDocument("index", head)
	if err := os.WriteFile(index, []byte(empty), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(worktree, []byte(body+strings.Repeat(" ", maxEvidenceBytes)), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := collectChangeSetSources("HEAD", worktree, index); err == nil || !strings.Contains(err.Error(), "8 MiB") {
		t.Fatalf("oversized changeset accepted: %v", err)
	}
	if err := os.WriteFile(worktree, []byte(body), 0600); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile("main.go", bytes.Repeat([]byte{' '}, maxEvidenceFileBytes+1), 0600); err != nil {
		t.Fatal(err)
	}
	if _, err := collectChangeSetSources("HEAD", worktree, index); err == nil || !strings.Contains(err.Error(), "budget") {
		t.Fatalf("oversized source accepted: %v", err)
	}

	hexName := "ff2e676f"
	rawPath, err := changeSetPathValue(&changeSetPath{RawHex: hexName})
	if err != nil || rawPath != "\xff.go" || utf8.ValidString(rawPath) {
		t.Fatalf("raw path bytes were lost: %q %v", rawPath, err)
	}
}

func TestEvidenceModeMatchesDefaultOnRealGitProducer(t *testing.T) {
	producer := os.Getenv("GIT_CHANGESET_TEST_PRODUCER")
	if producer == "" {
		t.Skip("set GIT_CHANGESET_TEST_PRODUCER to pinned #144 git_changeset.py")
	}
	dir := initTempGitRepo(t)
	docs := t.TempDir()
	nested := filepath.Join(dir, "src")
	if err := os.Mkdir(nested, 0750); err != nil {
		t.Fatal(err)
	}

	write := func(path string, body []byte) {
		t.Helper()
		if err := os.WriteFile(filepath.Join(dir, path), body, 0600); err != nil {
			t.Fatal(err)
		}
	}
	write("src/old worker.go", []byte("package src\n\nfunc Worker() {\n\ttime.Sleep(5 * time.Second)\n}\n"))
	write("binary.go", []byte{0, 1})
	write("link.go", []byte{0, 2})
	write("reverted.go", []byte("package main\n"))
	write("deleted.go", []byte("package main\n"))
	write(".gitignore", []byte("ignored.go\n"))
	runGit(t, dir, "add", "-A")
	runGit(t, dir, "commit", "-m", "track change-set fixture")
	runGit(t, dir, "mv", "src/old worker.go", "src/café worker.go")
	runGit(t, dir, "rm", "deleted.go")
	write("main.go", []byte("package main\n\nfunc main() { /* edited */ }\n"))
	write("staged.go", []byte("package main\n\nfunc Added() {}\n"))
	write("reverted.go", []byte("package main\n// staged only\n"))
	runGit(t, dir, "add", "staged.go", "reverted.go")
	write("reverted.go", []byte("package main\n"))
	replaced := filepath.Join(dir, "replaced")
	if err := os.Mkdir(replaced, 0750); err != nil {
		t.Fatal(err)
	}
	write("replaced/staged.go", []byte("package main\n"))
	runGit(t, dir, "add", "replaced/staged.go")
	if err := os.Remove(filepath.Join(replaced, "staged.go")); err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(replaced); err != nil {
		t.Fatal(err)
	}
	write("replaced", []byte("replacement worktree file\n"))
	write("staged then removed.go", []byte("package main\n"))
	runGit(t, dir, "add", "staged then removed.go")
	if err := os.Remove(filepath.Join(dir, "staged then removed.go")); err != nil {
		t.Fatal(err)
	}
	write("src/untracked\tfile.py", []byte("def worker():\n    sleep(9)\n"))
	write("ignored.go", []byte("package main\n"))
	write("binary.go", []byte{0, 3})
	if err := os.Remove(filepath.Join(dir, "link.go")); err != nil {
		t.Fatal(err)
	}
	if err := os.Symlink("main.go", filepath.Join(dir, "link.go")); err != nil {
		t.Fatal(err)
	}
	runGit(t, dir, "add", "link.go")

	for _, snapshot := range []string{"worktree", "index"} {
		cmd := exec.Command("python3", producer, "--repo", dir, "--base", "HEAD", "--snapshot", snapshot)
		out, err := cmd.Output()
		if err != nil {
			t.Fatalf("produce %s payload: %v", snapshot, err)
		}
		if err := os.WriteFile(filepath.Join(docs, snapshot+".json"), out, 0600); err != nil {
			t.Fatal(err)
		}
	}
	type pathRecord struct {
		Text string `json:"text"`
	}
	type hunkRange struct {
		NewStart int `json:"new_start"`
		NewCount int `json:"new_count"`
	}
	type fileRecord struct {
		Status  string      `json:"status"`
		OldPath *pathRecord `json:"old_path"`
		NewPath *pathRecord `json:"new_path"`
		Hunks   []hunkRange `json:"hunks"`
	}
	type producerDocument struct {
		Files []fileRecord `json:"files"`
	}
	documents := map[string]producerDocument{}
	for _, snapshot := range []string{"worktree", "index"} {
		data, err := os.ReadFile(filepath.Join(docs, snapshot+".json"))
		if err != nil {
			t.Fatal(err)
		}
		var document producerDocument
		if err := json.Unmarshal(data, &document); err != nil {
			t.Fatalf("parse %s payload: %v", snapshot, err)
		}
		documents[snapshot] = document
	}
	recordFor := func(snapshot, newPath string) *fileRecord {
		for i := range documents[snapshot].Files {
			record := &documents[snapshot].Files[i]
			if record.NewPath != nil && record.NewPath.Text == newPath {
				return record
			}
		}
		return nil
	}
	// The staged rename crosses a space and a non-ASCII name. Both snapshots
	// must carry it as one R record preserving the old and new paths, with no
	// hunks: the rename is pure, so identity travels in the paths alone.
	for _, snapshot := range []string{"worktree", "index"} {
		rename := recordFor(snapshot, "src/café worker.go")
		if rename == nil || rename.Status != "R" || rename.OldPath == nil ||
			rename.OldPath.Text != "src/old worker.go" || len(rename.Hunks) != 0 {
			t.Fatalf("%s snapshot lost the staged rename: %+v", snapshot, rename)
		}
	}
	// Snapshot selection: the index record sees the staged edit to
	// reverted.go (new line 2) that the worktree record no longer sees,
	// while the worktree record sees the unstaged main.go edit (line 3)
	// that the index record never sees.
	staged := recordFor("index", "reverted.go")
	if staged == nil || staged.Status != "M" || len(staged.Hunks) != 1 ||
		staged.Hunks[0].NewStart != 2 || staged.Hunks[0].NewCount != 1 ||
		recordFor("worktree", "reverted.go") != nil {
		t.Fatalf("index snapshot lost the staged range: %+v", staged)
	}
	unstaged := recordFor("worktree", "main.go")
	if unstaged == nil || unstaged.Status != "M" || len(unstaged.Hunks) != 1 ||
		unstaged.Hunks[0].NewStart != 3 || unstaged.Hunks[0].NewCount != 1 ||
		recordFor("index", "main.go") != nil {
		t.Fatalf("worktree snapshot lost the unstaged range: %+v", unstaged)
	}
	// Source-unavailable control: the index record lists a staged file whose
	// source was removed from the worktree. It stays filename-only evidence:
	// neither audit mode may fabricate a finding for it (asserted below).
	if gone := recordFor("index", "staged then removed.go"); gone == nil || gone.Status != "A" {
		t.Fatalf("index snapshot lost the removed-source record: %+v", gone)
	}
	t.Chdir(nested)

	var normal, normalized, stderr bytes.Buffer
	normalCode := executeAudit([]string{"--format", "json"}, &normal, &stderr)
	if stderr.Len() != 0 {
		t.Fatal(&stderr)
	}
	normalizedCode := executeAudit([]string{"--format", "json", "--changeset", filepath.Join(docs, "worktree.json"),
		"--index-changeset", filepath.Join(docs, "index.json")}, &normalized, &stderr)
	if normalCode != 1 || normalizedCode != normalCode || stderr.Len() != 0 || !bytes.Equal(normal.Bytes(), normalized.Bytes()) {
		t.Fatalf("default and normalized audits differ: normal=%d/%s normalized=%d/%s stderr=%s",
			normalCode, &normal, normalizedCode, &normalized, &stderr)
	}
	var report struct {
		Findings []struct {
			File     string `json:"file"`
			Line     int    `json:"line"`
			Code     string `json:"code"`
			Severity string `json:"severity"`
		} `json:"findings"`
		SLI struct {
			TotalFiles int `json:"total_files"`
		} `json:"sli"`
	}
	if err := json.Unmarshal(normalized.Bytes(), &report); err != nil {
		t.Fatal(err)
	}
	// Shared rule identity (tests/fixtures/engine-parity/contracts.json):
	// canonical rule blind_sleep, catalog SRE-07 in scripts/rule_registry.py;
	// the Go audit emits it as SRE-SCALE-SLEEP with severity BLOCKER. The
	// byte-equal reports above prove the default and changeset-fed paths
	// agree; these assertions pin which rule matched, on which path, at
	// which line, so a dropped or misattributed finding fails here. The
	// first finding is the renamed file: the sleep survived the rename and
	// is reported under the new path, never the old one.
	if report.SLI.TotalFiles != 5 || len(report.Findings) != 2 ||
		report.Findings[0].File != "src/café worker.go" || report.Findings[0].Line != 4 ||
		report.Findings[0].Code != "SRE-SCALE-SLEEP" || report.Findings[0].Severity != "BLOCKER" ||
		report.Findings[1].File != "src/untracked\tfile.py" || report.Findings[1].Line != 2 ||
		report.Findings[1].Code != "SRE-SCALE-SLEEP" || report.Findings[1].Severity != "BLOCKER" {
		t.Fatalf("unexpected candidate or finding set: %+v", report)
	}
	for _, finding := range report.Findings {
		if finding.File == "staged then removed.go" {
			t.Fatalf("finding fabricated for unavailable source: %+v", finding)
		}
	}
}
