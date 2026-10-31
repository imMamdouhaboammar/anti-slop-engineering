package sre

import (
    "sort"
    "github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

// AuditFiles executes the canonical suite of SRE checks across a map of file paths to contents
func AuditFiles(files map[string]string) ([]model.Finding, model.SLIReport) {
	var allFindings []model.Finding

	paths := make([]string, 0, len(files))
	for path := range files {
		paths = append(paths, path)
	}
	sort.Strings(paths)
	for _, path := range paths {
		content := files[path]
		allFindings = append(allFindings, CheckKISSComplexity(path, content)...)
		allFindings = append(allFindings, CheckToilAndScale(path, content)...)
	}

	allFindings = append(allFindings, CheckDRYDuplicates(files)...)
	sli := ComputeSLIReport(files, allFindings)

	return allFindings, sli
}
