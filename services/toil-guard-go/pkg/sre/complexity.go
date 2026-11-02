package sre

import (
	"regexp"
	"strconv"
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
		Message:    "Function '" + funcName + "' exceeds 80 lines (" + strconv.Itoa(count) + " lines). Violates KISS single-responsibility.",
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
		Message:    "Excessive nesting depth (" + strconv.Itoa(nestingLevel) + " > 4). Control flow must remain simple and readable.",
		Suggestion: "Refactor nested branches using early returns, guard clauses, or modular helper functions.",
	}
}

type funcTracker struct {
	inFunc     bool
	name       string
	startLine  int
	lineCount  int
	indentBase int
	python bool
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
	tracker := &funcTracker{python: strings.HasSuffix(strings.ToLower(filePath), ".py")}
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

		if f := tracker.processLine(filePath, lineNo, line, trimmed); f != nil {
			findings = append(findings, *f)
		}
	}

	if f := tracker.checkLength(filePath); f != nil {
		findings = append(findings, *f)
	}
	return findings
}

func (t *funcTracker) processLine(filePath string, lineNo int, line, trimmed string) *model.Finding {
	matches := funcStartRegex.FindStringSubmatch(line)
	leadingSpaces := len(line) - len(strings.TrimLeft(line, " \t"))

	var finding *model.Finding
	if t.inFunc && t.python && trimmed != "" && leadingSpaces <= t.indentBase {
		finding = t.checkLength(filePath)
		t.inFunc = false
	}

	if len(matches) > 0 {
		if finding == nil {
			finding = t.checkLength(filePath)
		}
		t.inFunc = true
		t.startLine = lineNo
		t.lineCount = 1
		t.indentBase = leadingSpaces
		t.name = extractFuncName(matches)
		if !t.python && ((strings.Contains(trimmed, "{") && strings.Contains(trimmed, "}")) ||
			(strings.Contains(trimmed, "=>") && !strings.Contains(trimmed, "{"))) {
			t.inFunc = false
		}
		return finding
	}

	if t.inFunc {
		t.lineCount++
		if !t.python && leadingSpaces <= t.indentBase && strings.HasPrefix(trimmed, "}") {
			if finding == nil {
				finding = t.checkLength(filePath)
			}
			t.inFunc = false
		}
	}
	return finding
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
