package sre

import (
	"strings"
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

func TestCheckKISSComplexity_Nesting(t *testing.T) {
	code := `
func ProcessData() {
    if a {
        if b {
            if c {
                if d {
                    if e {
                        doSomething()
                    }
                }
            }
        }
    }
}
`
	findings := CheckKISSComplexity("test.go", code)
	if len(findings) == 0 {
		t.Fatalf("expected nesting blocker finding, got 0")
	}

	found := false
	for _, f := range findings {
		if f.Code == "SRE-KISS-NESTING" && f.Severity == model.SeverityBlocker {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-KISS-NESTING blocker finding")
	}
}

func TestCheckKISSComplexity_FunctionLength(t *testing.T) {
	var lines []string
	lines = append(lines, "func LongFunction() {")
	for i := 0; i < 90; i++ {
		lines = append(lines, "    step()")
	}
	lines = append(lines, "}")

	code := strings.Join(lines, "\n")
	findings := CheckKISSComplexity("long.go", code)

	found := false
	for _, f := range findings {
		if f.Code == "SRE-KISS-FUNC-LEN" {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-KISS-FUNC-LEN finding")
	}
}
