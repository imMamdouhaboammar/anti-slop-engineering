package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"io"
	"strings"
	"testing"
	"time"
)

func TestRuntimeCheckRequiresExplicitBuiltInFixture(t *testing.T) {
	for _, args := range [][]string{
		nil,
		{"--fixture=anything-else"},
		{"--fixture=go-lookup", "/arbitrary/program"},
	} {
		var out, stderr bytes.Buffer
		called := false
		exit := executeRuntimeCheck(context.Background(), args, &out, &stderr, func(context.Context) (runtimeEvidence, error) {
			called = true
			return runtimeEvidence{}, nil
		})
		if exit != 2 || called || out.Len() != 0 || !strings.Contains(stderr.String(), "go-lookup") {
			t.Errorf("unexpected invalid invocation result: args=%v exit=%d launched=%t out=%q stderr=%q",
				args, exit, called, out.String(), stderr.String())
		}
	}
}

func TestRuntimeCheckUnavailableIsInconclusive(t *testing.T) {
	var out bytes.Buffer
	exit := executeRuntimeCheck(context.Background(), []string{"--fixture=go-lookup"}, &out, io.Discard,
		func(context.Context) (runtimeEvidence, error) {
			return runtimeEvidence{}, errors.New("sandbox preflight unavailable")
		})
	var report runtimeCheckReport
	if err := json.Unmarshal(out.Bytes(), &report); err != nil {
		t.Fatal(err)
	}
	if exit != 2 || report.Status != "inconclusive" || report.Executed || report.Measurements != nil || report.Reason != "sandbox preflight unavailable" {
		t.Fatalf("unverified sandbox was not reported as inconclusive: exit=%d report=%+v", exit, report)
	}
}

func TestFixtureComparesActualLookupsAndRecovers(t *testing.T) {
	evidence := measureLookupFixture()
	if evidence.BaselineCalls != 32 || evidence.BatchedCalls != 4 || evidence.BaselineTimeNS <= 0 ||
		evidence.BatchedTimeNS <= 0 || !evidence.ResultsMatch || !evidence.FaultObserved || !evidence.Recovered {
		t.Fatalf("unexpected fixture measurements: %+v", evidence)
	}
}

func TestRuntimeCheckCannotPassFailedMeasurements(t *testing.T) {
	for _, mutate := range []func(*runtimeEvidence){
		func(e *runtimeEvidence) { e.Measurements.BatchedCalls = e.Measurements.BaselineCalls },
		func(e *runtimeEvidence) { e.Measurements.Recovered = false },
	} {
		evidence := runtimeEvidence{Isolation: verifiedRuntimeIsolation(), Measurements: measureLookupFixture()}
		mutate(&evidence)
		var out bytes.Buffer
		exit := executeRuntimeCheck(context.Background(), []string{"--fixture=go-lookup"}, &out, io.Discard,
			func(context.Context) (runtimeEvidence, error) { return evidence, nil })
		var report runtimeCheckReport
		if err := json.Unmarshal(out.Bytes(), &report); err != nil {
			t.Fatal(err)
		}
		if exit != 1 || report.Status != "failed" || !report.Executed || report.Measurements == nil {
			t.Fatalf("fixture failed but report lost executed evidence: exit=%d report=%+v", exit, report)
		}
	}
}

func TestRuntimeCheckDenialProofMustBeComplete(t *testing.T) {
	evidence := runtimeEvidence{Isolation: verifiedRuntimeIsolation(), Measurements: measureLookupFixture()}
	evidence.Isolation.NetworkDenied = false
	var out bytes.Buffer
	exit := executeRuntimeCheck(context.Background(), []string{"--fixture=go-lookup"}, &out, io.Discard,
		func(context.Context) (runtimeEvidence, error) { return evidence, nil })
	var report runtimeCheckReport
	if err := json.Unmarshal(out.Bytes(), &report); err != nil {
		t.Fatal(err)
	}
	if exit != 2 || report.Status != "inconclusive" || report.Executed || report.Measurements != nil {
		t.Fatalf("incomplete isolation passed: exit=%d report=%+v", exit, report)
	}
}

func verifiedRuntimeIsolation() runtimeIsolation {
	return runtimeIsolation{Sandbox: "test", ReadCanaryDenied: true, WritesDenied: true, NetworkDenied: true,
		ChildProcessDenied: true, CPULimitSeconds: 2}
}

func TestRuntimeCheckRejectsCanceledLaunch(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	var out bytes.Buffer
	exit := executeRuntimeCheck(ctx, []string{"--fixture=go-lookup"}, &out, io.Discard,
		func(ctx context.Context) (runtimeEvidence, error) {
			if !errors.Is(ctx.Err(), context.Canceled) {
				t.Fatal("fixture driver ignored caller cancellation")
			}
			return runtimeEvidence{}, ctx.Err()
		})
	var report runtimeCheckReport
	if err := json.Unmarshal(out.Bytes(), &report); err != nil {
		t.Fatal(err)
	}
	if exit != 2 || report.Status != "inconclusive" || report.Executed {
		t.Fatalf("canceled fixture produced a result: exit=%d report=%+v", exit, report)
	}
}

func TestRuntimeCheckCapsWorkerDeadline(t *testing.T) {
	var out bytes.Buffer
	before := time.Now()
	exit := executeRuntimeCheck(context.Background(), []string{"--fixture=go-lookup"}, &out, io.Discard,
		func(ctx context.Context) (runtimeEvidence, error) {
			deadline, ok := ctx.Deadline()
			if !ok || deadline.Before(before) || time.Until(deadline) > 5*time.Second {
				t.Fatal("fixture driver did not provide the bounded wall deadline")
			}
			return runtimeEvidence{}, context.DeadlineExceeded
		})
	if exit != 2 || !strings.Contains(out.String(), `"executed":false`) {
		t.Fatalf("timeout did not remain inconclusive: %d %s", exit, out.String())
	}
}
