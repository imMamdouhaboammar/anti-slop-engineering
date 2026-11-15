package sre

import (
	"bytes"
	"go/scanner"
	"go/token"
	"regexp"
	"strings"
	"unicode"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

var (
	reBlindSleep   = regexp.MustCompile(`(?i)(?:time\.Sleep\([0-9]+\s*\*\s*time\.Second\)|sleep\([0-9]+\)|Thread\.sleep\([0-9]+\))`)
	reFixedRetry   = regexp.MustCompile(`(?i)(?:for\s+retry\s*:=\s*0;\s*retry\s*<\s*[0-9]+;\s*retry\+\+|for\s+attempt\s+in\s+range\([0-9]+\):)`)
	reSwallowErr   = regexp.MustCompile(`(?i)(?:if\s+err\s*!=\s*nil\s*\{\s*\}|catch\s*(?:\([^)]*\))?\s*\{\s*\}|except(?:\s+[^:]*)?:\s*(?:pass|\.\.\.))`)
	reGoIfErrNil   = regexp.MustCompile(`^(?:if\s+(?:.+;\s*)?err\s*!=\s*nil|if\s+err\s*!=\s*nil)\s*\{?$`)
	reCatchBlock   = regexp.MustCompile(`^(?:\}\s*)?catch\s*(?:\([^)]*\))?\s*\{?$`)
	rePyExcept     = regexp.MustCompile(`^except(?:\s+[^:]*)?:$`)
	reYAGNIComment = regexp.MustCompile(`(?i)(?:TODO\s*\((?:future|someday|unneeded)\)|placeholder\s+for\s+future|not\s+implemented\s+yet)`)
)

func makeToilFinding(file string, lineNo int, cat model.ViolationCategory, sev model.Severity, code, msg, sugg string) model.Finding {
	return model.Finding{
		File:       file,
		Line:       lineNo,
		Category:   cat,
		Severity:   sev,
		Code:       code,
		Message:    msg,
		Suggestion: sugg,
	}
}

func auditLineToil(file string, lineNo int, line string, allLines, swallowLines []string) []model.Finding {
	var findings []model.Finding
	trimmed := strings.TrimSpace(line)

	if reBlindSleep.MatchString(trimmed) {
		findings = append(findings, makeToilFinding(
			file, lineNo, model.CategoryScale, model.SeverityBlocker, "SRE-SCALE-SLEEP",
			"Blind sleep() call detected. Never use fixed sleeps as synchronization band-aids.",
			"Use context cancellation, channel signalling, condition variables, or polling with timeout.",
		))
	}

	if reFixedRetry.MatchString(trimmed) && !hasBackoffLookahead(lineNo-1, allLines) {
		findings = append(findings, makeToilFinding(
			file, lineNo, model.CategoryScale, model.SeverityReview, "SRE-SCALE-RETRY",
			"Retry loop without exponential backoff and full jitter causes thundering herd toil.",
			"Apply exponential backoff with full jitter to distribute retry storms.",
		))
	}

	if isSwallowedError(lineNo-1, strings.TrimSpace(swallowLines[lineNo-1]), swallowLines) {
		findings = append(findings, makeToilFinding(
			file, lineNo, model.CategoryScale, model.SeverityBlocker, "SRE-SCALE-SWALLOW",
			"Silent error swallowing turns failure modes into operational diagnostic toil.",
			"Log structured diagnostic metadata or propagate errors with contextual stack traces.",
		))
	}

	if reYAGNIComment.MatchString(trimmed) {
		findings = append(findings, makeToilFinding(
			file, lineNo, model.CategoryYAGNI, model.SeverityReview, "SRE-YAGNI-SPECULATIVE",
			"Speculative placeholder comment detected: '"+trimmed+"'. Build only for verified requirements.",
			"Remove speculative scaffolding. YAGNI: You Aren't Gonna Need It.",
		))
	}

	return findings
}

func isCommentOrDocLine(line string) bool {
	return strings.HasPrefix(line, "//") ||
		strings.HasPrefix(line, "/*") ||
		strings.HasPrefix(line, "*") ||
		strings.HasPrefix(line, "#") ||
		strings.HasPrefix(line, `"""`) ||
		strings.HasPrefix(line, "'''")
}

func hasDocumentedReason(text string) bool {
	lower := strings.ToLower(text)
	reasons := []string{
		"ignore",
		"intentional",
		"expected",
		"deliberate",
		"by design",
		"suppress",
		"safe to ignore",
		"noop",
		"no-op",
		"skip",
		"fallback",
	}
	for _, r := range reasons {
		if strings.Contains(lower, r) {
			return true
		}
	}
	return false
}

func isInsideStringLiteral(line string, idx int) bool {
	inDouble := false
	inSingle := false
	inBacktick := false
	escaped := false

	for i, r := range line {
		if i >= idx {
			break
		}
		if escaped {
			escaped = false
			continue
		}
		if r == '\\' {
			escaped = true
			continue
		}
		if r == '"' && !inSingle && !inBacktick {
			inDouble = !inDouble
		} else if r == '\'' && !inDouble && !inBacktick {
			inSingle = !inSingle
		} else if r == '`' && !inDouble && !inSingle {
			inBacktick = !inBacktick
		}
	}

	return inDouble || inSingle || inBacktick
}

func isSwallowedError(currentIdx int, trimmed string, allLines []string) bool {
	if isCommentOrDocLine(trimmed) {
		return false
	}

	if loc := reSwallowErr.FindStringIndex(trimmed); loc != nil {
		if !isInsideStringLiteral(trimmed, loc[0]) {
			return true
		}
	}

	if reGoIfErrNil.MatchString(trimmed) {
		return isSwallowedBraceBlock(currentIdx, allLines)
	}

	if reCatchBlock.MatchString(trimmed) {
		return isSwallowedBraceBlock(currentIdx, allLines)
	}

	if rePyExcept.MatchString(trimmed) {
		return isSwallowedPythonExcept(currentIdx, allLines)
	}

	return false
}

func checkCommentDocGo(line string) (bool, bool) {
	if isCommentOrDocLine(line) {
		return true, hasDocumentedReason(line)
	}
	return false, false
}

func isSwallowedBraceBlock(startIdx int, lines []string) bool {
	limit := min(startIdx+25, len(lines))
	depth := 0
	hasDocumented := false

	for j := startIdx; j < limit; j++ {
		line := strings.TrimSpace(lines[j])
		if depth == 0 {
			code, comment, _ := strings.Cut(line, "//")
			if hasDocumentedReason(comment) {
				return false
			}
			open := strings.LastIndexByte(code, '{')
			if open < 0 {
				continue
			}
			depth = 1
			if afterOpen := strings.TrimSpace(code[open+1:]); afterOpen != "" {
				return strings.HasPrefix(afterOpen, "}")
			}
			continue
		}

		if isComment, isDoc := checkCommentDocGo(line); isComment {
			hasDocumented = hasDocumented || isDoc
			continue
		}

		for _, c := range line {
			switch {
			case c == '{':
				depth++
			case c == '}':
				depth--
				if depth == 0 {
					return !hasDocumented
				}
			case unicode.IsSpace(c):
			default:
				return false
			}
		}
	}
	return false
}

func isSwallowedPythonExcept(startIdx int, lines []string) bool {
	limit := startIdx + 20
	if limit > len(lines) {
		limit = len(lines)
	}

	hasStatements := false
	hasDocumented := false
	onlyPassOrEllipsis := false

	baseIndent := len(lines[startIdx]) - len(strings.TrimLeft(lines[startIdx], " \t"))

	for j := startIdx + 1; j < limit; j++ {
		rawLine := lines[j]
		line := strings.TrimSpace(rawLine)
		if line == "" {
			continue
		}

		indent := len(rawLine) - len(strings.TrimLeft(rawLine, " \t"))
		if indent <= baseIndent && line != "" {
			break
		}

		if isComment, isDoc := checkCommentDocGo(line); isComment {
			if isDoc {
				hasDocumented = true
			}
			continue
		}

		if line == "pass" || line == "..." {
			onlyPassOrEllipsis = true
		} else {
			hasStatements = true
		}
	}

	return onlyPassOrEllipsis && !hasStatements && !hasDocumented
}

func hasBackoffLookahead(currentIdx int, lines []string) bool {
	limit := currentIdx + 6
	if limit > len(lines) {
		limit = len(lines)
	}
	for j := currentIdx; j < limit; j++ {
		lower := strings.ToLower(lines[j])
		if strings.Contains(lower, "backoff") || strings.Contains(lower, "jitter") {
			return true
		}
	}
	return false
}

// goSwallowLines preserves Go token positions while removing comments and literal content.
func goSwallowLines(content string) []string {
	file := token.NewFileSet().AddFile("", -1, len(content))
	var tokens scanner.Scanner
	tokens.Init(file, []byte(content), func(token.Position, string) {}, scanner.ScanComments)
	source := []byte(content)
	for {
		pos, tok, lit := tokens.Scan()
		if tok == token.EOF {
			break
		}
		if tok != token.STRING && tok != token.CHAR && tok != token.COMMENT {
			continue
		}
		start := file.Offset(pos)
		end := start + len(lit)
		mask := byte('~')
		if content[start] == 96 {
			// The scanner's raw-string literal omits CRs. Use source offsets.
			end = len(content)
			if close := strings.IndexByte(content[start+1:], 96); close >= 0 {
				end = start + close + 2
			}
		}
		if tok == token.COMMENT {
			if strings.HasPrefix(content[start:], "/*") {
				end = len(content)
				if close := strings.Index(content[start+2:], "*/"); close >= 0 {
					end = start + close + 4
				}
			} else if newline := strings.IndexByte(content[start:], '\n'); newline < 0 {
				end = len(content)
			} else {
				end = start + newline
			}
			if hasDocumentedReason(lit) {
				// Keep the comment's location and a reason marker, preserving CRLF.
				firstLine := bytes.IndexByte(source[start:end], '\n')
				if firstLine < 0 {
					firstLine = end - start
				}
				if firstLine >= len("// expected") {
					copy(source[start:start+firstLine], "// expected")
					start += len("// expected")
				}
			}
			mask = ' '
		}
		for i := start; i < end; i++ {
			if source[i] != '\n' && source[i] != '\r' {
				source[i] = mask
			}
		}
	}
	return strings.Split(string(source), "\n")
}

// CheckToilAndScale audits code for Google SRE Scale and Operational Toil violations
func CheckToilAndScale(filePath string, content string) []model.Finding {
	if IsTestFile(filePath) {
		return nil
	}

	lines := strings.Split(content, "\n")
	swallowLines := lines
	if strings.HasSuffix(filePath, ".go") {
		swallowLines = goSwallowLines(content)
	}
	var findings []model.Finding
	inBlockComment := false

	for i, line := range lines {
		trimmed := strings.TrimSpace(line)
		if inBlockComment {
			if strings.Contains(trimmed, "*/") {
				inBlockComment = false
			}
			continue
		}
		if strings.HasPrefix(trimmed, "/*") {
			if !strings.Contains(trimmed, "*/") {
				inBlockComment = true
			}
			continue
		}

		lineFindings := auditLineToil(filePath, i+1, line, lines, swallowLines)
		findings = append(findings, lineFindings...)
	}

	return findings
}
