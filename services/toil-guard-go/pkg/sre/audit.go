package sre

import "github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"

// AuditFiles executes the canonical suite of SRE checks across a map of file paths to contents
func AuditFiles(files map[string]string) ([]model.Finding, model.SLIReport) {
	var allFindings []model.Finding

	for path, content := range files {
		allFindings = append(allFindings, CheckKISSComplexity(path, content)...)
		allFindings = append(allFindings, CheckToilAndScale(path, content)...)
	}

	allFindings = append(allFindings, CheckDRYDuplicates(files)...)
	sli := ComputeSLIReport(files, allFindings)

	return allFindings, sli
}
