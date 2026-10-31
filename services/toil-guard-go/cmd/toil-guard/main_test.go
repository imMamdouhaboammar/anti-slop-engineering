package main

import (
    "os"
    "path/filepath"
    "testing"
)

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
