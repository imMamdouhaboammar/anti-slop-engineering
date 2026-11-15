package main

import (
	"bytes"
	"context"
	"errors"
	"os"
	"path/filepath"
	"testing"
)

func TestRuntimeSandboxPreservesCancellation(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	if _, err := runSandboxedRuntimeFixture(ctx); !errors.Is(err, context.Canceled) {
		t.Fatalf("canceled worker was not rejected: %v", err)
	}
}

func TestRuntimeWorkerCannotStartWithoutReadDenial(t *testing.T) {
	dir, err := os.MkdirTemp("/private/tmp", "toil-guard-proof-")
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { os.RemoveAll(dir) })
	readCanary := filepath.Join(dir, "read-canary")
	writeCanary := filepath.Join(dir, "write-canary")
	if err := os.WriteFile(readCanary, []byte(readCanaryText), 0600); err != nil {
		t.Fatal(err)
	}
	t.Chdir(dir)
	isolation, err := verifyRuntimeIsolation(readCanary, writeCanary, "127.0.0.1:1")
	if err != nil || isolation.ReadCanaryDenied || isolation.verified() {
		t.Fatalf("out-of-sandbox worker passed preflight: isolation=%+v err=%v", isolation, err)
	}
	if _, err := os.Lstat(writeCanary); !os.IsNotExist(err) {
		t.Fatalf("out-of-sandbox worker reached the write probe: %v", err)
	}
}

func TestRuntimeWorkerOutputBudget(t *testing.T) {
	var out cappedRuntimeOutput
	if n, err := out.Write(bytes.Repeat([]byte{'x'}, 8192)); n != 8192 || err != nil {
		t.Fatalf("limit-sized output was rejected: n=%d err=%v", n, err)
	}
	if n, err := out.Write([]byte{'x'}); n != 0 || err == nil || out.Len() != 8192 {
		t.Fatalf("overflow was accepted: n=%d err=%v length=%d", n, err, out.Len())
	}
}
