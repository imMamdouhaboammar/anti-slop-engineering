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

func TestCheckToilAndScale_MultilineGoSwallowedError(t *testing.T) {
	code := `
func IgnoreMultilineGo() {
    if err != nil {
    }
}
`
	findings := CheckToilAndScale("worker.go", code)
	found := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-SCALE-SWALLOW for multiline empty Go if err != nil")
	}
}

func TestCheckToilAndScale_MultilinePythonSwallowedError(t *testing.T) {
	code := `
def worker():
    try:
        run_job()
    except Exception:
        pass
`
	findings := CheckToilAndScale("worker.py", code)
	found := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-SCALE-SWALLOW for multiline Python except pass")
	}
}

func TestCheckToilAndScale_MultilineJSCatchSwallowedError(t *testing.T) {
	code := `
function execute() {
    try {
        doTask();
    } catch (err) {
    }
}
`
	findings := CheckToilAndScale("worker.js", code)
	found := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-SCALE-SWALLOW for multiline JS catch empty")
	}
}

func TestCheckToilAndScale_DocumentedReasonNotFlagged(t *testing.T) {
	goCode := `
func HandleExpected() {
    if err != nil {
        // expected: stream may already be closed by peer
    }
}
`
	findings := CheckToilAndScale("stream.go", goCode)
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" {
			t.Errorf("unexpected SRE-SCALE-SWALLOW for documented reason: %v", f)
		}
	}

	pyCode := `
def cleanup():
    try:
        os.remove(path)
    except FileNotFoundError:
        # intentional: ignore missing file
        pass
`
	findings = CheckToilAndScale("cleanup.py", pyCode)
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" {
			t.Errorf("unexpected SRE-SCALE-SWALLOW for documented python reason: %v", f)
		}
	}
}

func TestCheckToilAndScale_ValidHandlerNotFlagged(t *testing.T) {
	goCode := `
func SafeExecute() error {
    if err != nil {
        log.Printf("task failed: %v", err)
        return err
    }
    return nil
}
`
	findings := CheckToilAndScale("task.go", goCode)
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" {
			t.Errorf("unexpected SRE-SCALE-SWALLOW for valid handler: %v", f)
		}
	}
}

func TestCheckToilAndScale_CommentsAndStringsNotFlagged(t *testing.T) {
	code := `
// if err != nil {
// }
/*
catch (e) {
}
*/
var description = "except Exception:\n    pass"
`
	findings := CheckToilAndScale("docs.go", code)
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" {
			t.Errorf("unexpected SRE-SCALE-SWALLOW in comment or string: %v", f)
		}
	}
}
