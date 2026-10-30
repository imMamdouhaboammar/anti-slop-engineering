package sre

import (
	"strings"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

// ComputeSLIReport generates an SRE score and error budget for an audited file set
func ComputeSLIReport(files map[string]string, findings []model.Finding) model.SLIReport {
	totalFiles := len(files)
	totalLines := 0
	for _, content := range files {
		totalLines += len(strings.Split(content, "\n"))
	}

	blockers := 0
	reviews := 0
	toilCount := 0

	for _, f := range findings {
		if f.Severity == model.SeverityBlocker {
			blockers++
		} else if f.Severity == model.SeverityReview {
			reviews++
		}
		if f.Category == model.CategoryScale {
			toilCount++
		}
	}

	complexityScore := 0.0
	if totalFiles > 0 {
		complexityScore = float64(blockers) / float64(totalFiles)
		if complexityScore > 1.0 {
			complexityScore = 1.0
		}
	}

	// Slop index penalty calculation
	slopIndex := (float64(blockers) * 25.0) + (float64(reviews) * 5.0) + (float64(toilCount) * 10.0)
	if slopIndex > 100.0 {
		slopIndex = 100.0
	}

	errorBudgetLeft := 100.0 - slopIndex
	if errorBudgetLeft < 0.0 {
		errorBudgetLeft = 0.0
	}

	status := "PASSED"
	if blockers > 0 || errorBudgetLeft < 50.0 {
		status = "BLOCKED"
	} else if reviews > 0 || errorBudgetLeft < 90.0 {
		status = "NEEDS_REVIEW"
	}

	return model.SLIReport{
		TotalFiles:       totalFiles,
		TotalLines:       totalLines,
		ComplexityScore:  complexityScore,
		DuplicationRatio: 0.0,
		ToilIncidents:    toilCount,
		SlopIndex:        slopIndex,
		ErrorBudgetLeft:  errorBudgetLeft,
		Status:           status,
	}
}
