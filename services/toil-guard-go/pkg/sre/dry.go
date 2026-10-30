package sre

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"strings"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

type blockLocation struct {
	file string
	line int
}

// IsTestFile returns true if the file path represents a test suite or fixture
func IsTestFile(path string) bool {
	lower := strings.ToLower(path)
	return strings.Contains(lower, "/tests/") || strings.HasPrefix(lower, "tests/") ||
		strings.Contains(lower, "_test.") || strings.Contains(lower, ".test.") ||
		strings.Contains(lower, ".spec.") || strings.Contains(lower, "test_")
}

func filterCleanLines(content string) ([]string, []int) {
	lines := strings.Split(content, "\n")
	cleanLines := make([]string, 0, len(lines))
	lineMap := make([]int, 0, len(lines))

	for idx, line := range lines {
		trimmed := strings.TrimSpace(line)
		if isIgnoredLine(trimmed) {
			continue
		}
		cleanLines = append(cleanLines, trimmed)
		lineMap = append(lineMap, idx+1)
	}
	return cleanLines, lineMap
}

func isIgnoredLine(trimmed string) bool {
	return trimmed == "" || strings.HasPrefix(trimmed, "//") || strings.HasPrefix(trimmed, "#") ||
		strings.HasPrefix(trimmed, "/*") || strings.HasPrefix(trimmed, "*") ||
		strings.HasPrefix(trimmed, "import ") || strings.HasPrefix(trimmed, "package ") ||
		strings.HasPrefix(trimmed, "use ") ||
		(strings.HasPrefix(trimmed, "\"") && strings.HasSuffix(trimmed, "\"")) ||
		trimmed == "}" || trimmed == "{" || trimmed == "return" || trimmed == "};" ||
		trimmed == ");" || trimmed == ")" || trimmed == "]" || trimmed == "]);"
}

// CheckDRYDuplicates scans a collection of files for duplicate code blocks using a sliding window of size >= 4
func CheckDRYDuplicates(files map[string]string) []model.Finding {
	const windowSize = 4
	var findings []model.Finding
	blockRegistry := make(map[string]blockLocation)

	for file, content := range files {
		if IsTestFile(file) {
			continue // DAMP is permitted in test files
		}
		cleanLines, lineMap := filterCleanLines(content)
		if len(cleanLines) < windowSize {
			continue
		}

		for i := 0; i <= len(cleanLines)-windowSize; i++ {
			window := strings.Join(cleanLines[i:i+windowSize], "\n")
			hasher := sha256.New()
			hasher.Write([]byte(window))
			hash := hex.EncodeToString(hasher.Sum(nil))

			loc, exists := blockRegistry[hash]
			if !exists {
				blockRegistry[hash] = blockLocation{file: file, line: lineMap[i]}
				continue
			}

			if loc.file != file || (loc.file == file && i+1-loc.line >= windowSize) {
				findings = append(findings, model.Finding{
					File:       file,
					Line:       lineMap[i],
					Category:   model.CategoryDRY,
					Severity:   model.SeverityReview,
					Code:       "SRE-DRY-DUPLICATE",
					Message:    fmt.Sprintf("Duplicated logic block (%d lines) matches %s:%d. Consolidate into canonical function.", windowSize, loc.file, loc.line),
					Suggestion: "Extract the shared logic into a single source of truth to avoid drift.",
				})
			}
		}
	}

	return findings
}
