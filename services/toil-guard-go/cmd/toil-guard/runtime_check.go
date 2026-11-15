package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"os"
	"runtime"
	"time"
)

const (
	runtimeFixture  = "go-lookup"
	runtimeTimeout  = 5 * time.Second
	runtimeCPULimit = 2
)

type runtimeIsolation struct {
	Sandbox            string `json:"sandbox"`
	ReadCanaryDenied   bool   `json:"read_canary_denied"`
	WritesDenied       bool   `json:"filesystem_write_denied"`
	NetworkDenied      bool   `json:"network_denied"`
	ChildProcessDenied bool   `json:"child_process_denied"`
	CPULimitSeconds    int    `json:"cpu_limit_seconds"`
}

func (i runtimeIsolation) verified() bool {
	return i.Sandbox != "" && i.ReadCanaryDenied && i.WritesDenied &&
		i.NetworkDenied && i.ChildProcessDenied && i.CPULimitSeconds == runtimeCPULimit
}

type runtimeEvidence struct {
	Isolation    runtimeIsolation   `json:"isolation"`
	Measurements lookupMeasurements `json:"measurements"`
}

type lookupMeasurements struct {
	Items          int                     `json:"items"`
	Iterations     int                     `json:"iterations"`
	BaselineCalls  int                     `json:"single_lookup_calls"`
	BatchedCalls   int                     `json:"batched_lookup_calls"`
	BaselineTimeNS int64                   `json:"single_lookup_elapsed_ns"`
	BatchedTimeNS  int64                   `json:"batched_lookup_elapsed_ns"`
	ResultsMatch   bool                    `json:"results_match"`
	FaultObserved  bool                    `json:"fault_observed"`
	Recovered      bool                    `json:"recovered"`
	Concurrency    concurrencyMeasurements `json:"concurrency"`
}

func (m lookupMeasurements) passed() bool {
	return m.Items == len(lookupKeys) && m.Iterations == lookupIterations &&
		m.BaselineCalls == m.Items*m.Iterations && m.BatchedCalls == m.Iterations &&
		m.BaselineTimeNS > 0 && m.BatchedTimeNS > 0 && m.ResultsMatch && m.FaultObserved && m.Recovered &&
		m.Concurrency.passed()
}

type runtimeCheckReport struct {
	Status        string              `json:"status"`
	Executed      bool                `json:"executed"`
	Reason        string              `json:"reason,omitempty"`
	Fixture       string              `json:"fixture"`
	OS            string              `json:"os"`
	Architecture  string              `json:"architecture"`
	GoVersion     string              `json:"go_version"`
	WallTimeoutMS int64               `json:"wall_timeout_ms"`
	Isolation     *runtimeIsolation   `json:"isolation,omitempty"`
	Measurements  *lookupMeasurements `json:"measurements,omitempty"`
}

func executeRuntimeCheck(ctx context.Context, args []string, stdout, stderr io.Writer,
	run func(context.Context) (runtimeEvidence, error)) int {
	flags := flag.NewFlagSet("runtime-check", flag.ContinueOnError)
	flags.SetOutput(stderr)
	fixture := flags.String("fixture", "", "Explicit built-in fixture: go-lookup")
	if err := flags.Parse(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}
	if *fixture != runtimeFixture || flags.NArg() != 0 {
		fmt.Fprintln(stderr, "Usage: toil-guard runtime-check --fixture=go-lookup")
		return 2
	}

	ctx, cancel := context.WithTimeout(ctx, runtimeTimeout)
	defer cancel()
	evidence, err := run(ctx)
	report, exitCode := newRuntimeCheckReport(evidence, err)
	if err := json.NewEncoder(stdout).Encode(report); err != nil {
		fmt.Fprintln(stderr, "Writing runtime evidence:", err)
		return 1
	}
	return exitCode
}

func newRuntimeCheckReport(evidence runtimeEvidence, err error) (runtimeCheckReport, int) {
	report := runtimeCheckReport{Fixture: runtimeFixture, OS: runtime.GOOS, Architecture: runtime.GOARCH,
		GoVersion: runtime.Version(), WallTimeoutMS: runtimeTimeout.Milliseconds(), Status: "inconclusive"}
	if err != nil {
		report.Reason = err.Error()
		return report, 2
	}
	report.Isolation = &evidence.Isolation
	if !evidence.Isolation.verified() {
		report.Reason = "sandbox isolation or CPU limit could not be verified"
		return report, 2
	}
	report.Executed = true
	report.Measurements = &evidence.Measurements
	if evidence.Measurements.passed() {
		report.Status = "passed"
		return report, 0
	}
	report.Status = "failed"
	report.Reason = "observed lookup, result, recovery, or concurrency evidence did not meet fixture criteria"
	return report, 1
}

func runRuntimeWorker(args []string) int {
	if len(args) != 3 {
		return 2
	}
	isolation, err := verifyRuntimeIsolation(args[0], args[1], args[2])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 2
	}
	evidence := runtimeEvidence{Isolation: isolation}
	if isolation.verified() {
		evidence.Measurements = measureLookupFixture()
	}
	if err := json.NewEncoder(os.Stdout).Encode(evidence); err != nil {
		fmt.Fprintln(os.Stderr, "Writing worker evidence:", err)
		return 2
	}
	return 0
}

const lookupIterations = 4

var lookupKeys = [...]int{0, 1, 2, 3, 4, 5, 6, 7}

type lookupFixture struct {
	values   [len(lookupKeys)]int
	calls    int
	failNext bool
}

var errFixtureUnavailable = errors.New("fixture dependency unavailable")

func (f *lookupFixture) get(keys []int, values []int) error {
	f.calls++
	if f.failNext {
		f.failNext = false
		return errFixtureUnavailable
	}
	for i, key := range keys {
		values[i] = f.values[key]
	}
	return nil
}

func runLookupFixture(fixture *lookupFixture, batchSize int) ([len(lookupKeys)]int, time.Duration, error) {
	var values [len(lookupKeys)]int
	start := time.Now()
	for range lookupIterations {
		for from := 0; from < len(lookupKeys); from += batchSize {
			to := from + batchSize
			if err := fixture.get(lookupKeys[from:to], values[from:to]); err != nil {
				return values, time.Since(start), err
			}
		}
	}
	return values, time.Since(start), nil
}

func measureLookupFixture() lookupMeasurements {
	want := [len(lookupKeys)]int{10, 20, 30, 40, 50, 60, 70, 80}
	single, batch := lookupFixture{values: want}, lookupFixture{values: want}
	singleValues, singleTime, singleErr := runLookupFixture(&single, 1)
	batchValues, batchTime, batchErr := runLookupFixture(&batch, len(lookupKeys))

	var recovered [len(lookupKeys)]int
	fault := lookupFixture{values: want, failNext: true}
	injected := fault.get(lookupKeys[:], recovered[:])
	retried := fault.get(lookupKeys[:], recovered[:])
	return lookupMeasurements{
		Items: len(lookupKeys), Iterations: lookupIterations, BaselineCalls: single.calls, BatchedCalls: batch.calls,
		BaselineTimeNS: singleTime.Nanoseconds(), BatchedTimeNS: batchTime.Nanoseconds(),
		ResultsMatch:  singleErr == nil && batchErr == nil && singleValues == want && batchValues == want,
		FaultObserved: errors.Is(injected, errFixtureUnavailable), Recovered: retried == nil && recovered == want,
		Concurrency: measureLookupConcurrency(),
	}
}
