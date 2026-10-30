package sre

import (
	"fmt"
	"regexp"
	"strings"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

var (
	funcStartRegex = regexp.MustCompile(`(?m)^\s*(?:func\s+(?:\([^)]+\)\s+)?([A-Za-z0-9_]+)|def\s+([A-Za-z0-9_]+)|function\s+([A-Za-z0-9_]+)|(?:const|let|var)\s+([A-Za-z0-9_]+)\s*=\s*(?:async\s*)?(?:\([^)]*\)|[A-Za-z0-9_]+)\s*=>)`)
)

func newFuncLengthFinding(filePath string, lineNo int, funcName string, count int) model.Finding {
	return model.Finding{
		File:       filePath,
		Line:       lineNo,
		Category:   model.CategoryKISS,
		Severity:   model.SeverityReview,
		Code:       "SRE-KISS-FUNC-LEN",
		Message:    fmt.Sprintf("Function '%s' exceeds 80 lines (%d lines). Violates KISS single-responsibility.", funcName, count),
		Suggestion: "Decompose this large function into cohesive, single-responsibility units.",
	}
}

func auditIndentation(file string, lineNo int, line string) *model.Finding {
	leadingSpaces := len(line) - len(strings.TrimLeft(line, " \t"))
	nestingLevel := leadingSpaces / 4
	if strings.HasPrefix(line, "\t") {
		nestingLevel = len(line) - len(strings.TrimLeft(line, "\t"))
	}
	if nestingLevel <= 4 {
		return nil
	}
	return &model.Finding{
		File:       file,
		Line:       lineNo,
		Category:   model.CategoryKISS,
		Severity:   model.SeverityBlocker,
		Code:       "SRE-KISS-NESTING",
		Message:    fmt.Sprintf("Excessive nesting depth (%d > 4). Control flow must remain simple and readable.", nestingLevel),
		Suggestion: "Refactor nested branches using early returns, guard clauses, or modular helper functions.",
	}
}

type funcTracker struct {
	inFunc     bool
	name       string
	startLine  int
	lineCount  int
	indentBase int
}

func (t *funcTracker) checkLength(filePath string) *model.Finding {
	if t.inFunc && t.lineCount > 80 {
		f := newFuncLengthFinding(filePath, t.startLine, t.name, t.lineCount)
		return &f
	}
	return nil
}

// CheckKISSComplexity verifies KISS invariants: nesting <= 4 and function length <= 80
func CheckKISSComplexity(filePath string, content string) []model.Finding {
	if IsTestFile(filePath) {
		return nil
	}

	var findings []model.Finding
	lines := strings.Split(content, "\n")
	tracker := &funcTracker{}
	parenDepth := 0

	for i, line := range lines {
		lineNo := i + 1
		trimmed := strings.TrimSpace(line)

		if isIgnoredCommentLine(trimmed) {
			if tracker.inFunc {
				tracker.lineCount++
			}
			continue
		}

		inParen := parenDepth > 0
		parenDepth += strings.Count(line, "(") - strings.Count(line, ")")
		parenDepth += strings.Count(line, "[") - strings.Count(line, "]")
		if parenDepth < 0 {
			parenDepth = 0
		}

		if !inParen {
			if f := auditIndentation(filePath, lineNo, line); f != nil {
				findings = append(findings, *f)
			}
		}

		tracker.processLine(filePath, lineNo, line, trimmed, &findings)
	}

	return findings
}

func (t *funcTracker) processLine(filePath string, lineNo int, line, trimmed string, out *[]model.Finding) {
	matches := funcStartRegex.FindStringSubmatch(line)
	leadingSpaces := len(line) - len(strings.TrimLeft(line, " \t"))

	if len(matches) > 0 {
		if f := t.checkLength(filePath); f != nil {
			*out = append(*out, *f)
		}
		t.inFunc = true
		t.startLine = lineNo
		t.lineCount = 1
		t.indentBase = leadingSpaces
		t.name = extractFuncName(matches)
		return
	}

	if t.inFunc {
		t.lineCount++
		if leadingSpaces <= t.indentBase && (strings.HasPrefix(trimmed, "}") || strings.HasPrefix(trimmed, "return")) {
			if f := t.checkLength(filePath); f != nil {
				*out = append(*out, *f)
			}
			t.inFunc = false
		}
	}
}

func extractFuncName(matches []string) string {
	for idx := 1; idx < len(matches); idx++ {
		if matches[idx] != "" {
			return matches[idx]
		}
	}
	return "anonymous"
}

func isIgnoredCommentLine(trimmed string) bool {
	return trimmed == "" || strings.HasPrefix(trimmed, "//") || strings.HasPrefix(trimmed, "#") ||
		strings.HasPrefix(trimmed, "/*") || strings.HasPrefix(trimmed, "*")
}
