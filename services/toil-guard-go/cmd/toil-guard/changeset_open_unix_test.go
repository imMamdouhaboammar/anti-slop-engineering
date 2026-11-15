//go:build unix

package main

import (
	"errors"
	"os"
	"path/filepath"
	"syscall"
	"testing"
)

func TestEvidenceOpenCannotBlockOnConcurrentFIFOReplacement(t *testing.T) {
	path := filepath.Join(t.TempDir(), "evidence.json")
	if err := os.WriteFile(path, []byte("{}"), 0600); err != nil {
		t.Fatal(err)
	}
	info, err := os.Lstat(path)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.Remove(path); err != nil {
		t.Fatal(err)
	}
	if err := syscall.Mkfifo(path, 0600); err != nil {
		t.Fatal(err)
	}

	data, err := readRegularEvidence(path, info, maxEvidenceBytes, os.OpenFile)
	if len(data) != 0 || !errors.Is(err, errEvidenceFileChanged) {
		t.Fatalf("expected descriptor validation failure, got data=%q err=%v", data, err)
	}
}
