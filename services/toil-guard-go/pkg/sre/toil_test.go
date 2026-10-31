package sre

import (
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

func TestCheckToilAndScale_BlindSleep(t *testing.T) {
	code := `
func WaitForWorker() {
    time.Sleep(5 * time.Second)
}
`
	findings := CheckToilAndScale("worker.go", code)
	if len(findings) == 0 {
		t.Fatalf("expected blind sleep finding, got 0")
	}

	found := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SLEEP" && f.Severity == model.SeverityBlocker {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-SCALE-SLEEP blocker finding")
	}
}

func TestCheckToilAndScale_SwallowedError(t *testing.T) {
	code := `
func IgnoreFailures() {
    if err != nil { }
}
`
	findings := CheckToilAndScale("err.go", code)
	if len(findings) == 0 {
		t.Fatalf("expected error swallow finding, got 0")
	}

	found := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" && f.Severity == model.SeverityBlocker {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-SCALE-SWALLOW finding")
	}
}
