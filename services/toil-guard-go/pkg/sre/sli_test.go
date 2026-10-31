package sre

import (
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

func TestComputeSLIReport_Clean(t *testing.T) {
	files := map[string]string{
		"a.go": "package a\nfunc Clean() {}\n",
	}
	findings := []model.Finding{}

	sli := ComputeSLIReport(files, findings)
	if sli.Status != "PASSED" {
		t.Errorf("expected PASSED, got %s", sli.Status)
	}
	if sli.ErrorBudgetLeft != 100.0 {
		t.Errorf("expected 100.0 error budget, got %f", sli.ErrorBudgetLeft)
	}
}

func TestComputeSLIReport_Blocked(t *testing.T) {
	files := map[string]string{
		"a.go": "package a\n",
	}
	findings := []model.Finding{
		{
			File:     "a.go",
			Line:     1,
			Category: model.CategoryKISS,
			Severity: model.SeverityBlocker,
			Code:     "SRE-KISS-NESTING",
		},
	}

	sli := ComputeSLIReport(files, findings)
	if sli.Status != "BLOCKED" {
		t.Errorf("expected BLOCKED, got %s", sli.Status)
	}
	if sli.ErrorBudgetLeft >= 100.0 {
		t.Errorf("expected reduced error budget, got %f", sli.ErrorBudgetLeft)
	}
}


func TestComputeSLIReportDuplicateRatio(t *testing.T) {
    files := map[string]string{"one.go": "package main", "two.go": "package main"}
    findings := []model.Finding{{File: "two.go", Category: model.CategoryDRY, Severity: model.SeverityReview}}
    sli := ComputeSLIReport(files, findings)
    if sli.DuplicationRatio != 0.5 {
        t.Fatalf("expected one of two files duplicated, got %f", sli.DuplicationRatio)
    }
}
