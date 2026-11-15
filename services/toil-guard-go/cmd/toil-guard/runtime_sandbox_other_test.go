//go:build !darwin

package main

import (
	"bytes"
	"context"
	"encoding/json"
	"io"
	"testing"
)

func TestRuntimeCheckReportsUnavailableHost(t *testing.T) {
	var out bytes.Buffer
	exitCode := executeRuntimeCheck(context.Background(), []string{"--fixture=go-lookup"}, &out, io.Discard, runSandboxedRuntimeFixture)
	var report runtimeCheckReport
	if err := json.Unmarshal(out.Bytes(), &report); err != nil {
		t.Fatal(err)
	}
	if exitCode != 2 || report.Status != "inconclusive" || report.Executed || report.Measurements != nil || report.Reason == "" {
		t.Fatalf("unsupported host produced misleading evidence: exit=%d result=%+v", exitCode, report)
	}
}
