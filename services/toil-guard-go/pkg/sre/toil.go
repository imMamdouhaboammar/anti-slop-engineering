package sre

import (
	"go/ast"
	"go/parser"
	"go/token"
	"regexp"
	"sort"
	"strings"
	"unicode/utf8"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

var (
	reBlindSleep         = regexp.MustCompile(`(?i)(?:time\.Sleep\([0-9]+\s*\*\s*time\.Second\)|sleep\([0-9]+\)|Thread\.sleep\([0-9]+\))`)
	reFixedRetry         = regexp.MustCompile(`(?i)(?:for\s+retry\s*:=\s*0;\s*retry\s*<\s*[0-9]+;\s*retry\+\+|for\s+attempt\s+in\s+range\([0-9]+\):)`)
	reSwallowErr         = regexp.MustCompile(`(?i)(?:if\s+err\s*!=\s*nil\s*\{\s*\}|catch\s*\([^)]*\)\s*\{\s*\}|except(?:\s+Exception)?\s*:\s*pass)`)
	reIgnoredErrorReason = regexp.MustCompile(`(?i)\b(?:expected|intentional|deliberate|by design|safe to ignore|fallback|no-?op)\b`)
	reYAGNIComment       = regexp.MustCompile(`(?i)(?:TODO\s*\((?:future|someday|unneeded)\)|placeholder\s+for\s+future|not\s+implemented\s+yet)`)
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

func auditLineToil(file string, lineNo int, line string, allLines []string, swallowed bool) []model.Finding {
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

	if swallowed {
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

func goSwallowedErrorLines(filePath, content string) map[int]bool {
	files := token.NewFileSet()
	parsed, err := parser.ParseFile(files, filePath, content, parser.ParseComments|parser.SkipObjectResolution)
	if err != nil {
		return nil
	}

	findings := make(map[int]bool)
	ast.Inspect(parsed, func(node ast.Node) bool {
		condition, ok := node.(*ast.IfStmt)
		if !ok || len(condition.Body.List) != 0 || !isGoErrorCheck(condition.Cond) {
			return true
		}
		first := sort.Search(len(parsed.Comments), func(i int) bool {
			return parsed.Comments[i].End() > condition.Cond.End()
		})
		for _, comment := range parsed.Comments[first:] {
			if comment.Pos() >= condition.Body.Rbrace {
				break
			}
			for _, part := range comment.List {
				if part.Pos() >= condition.Cond.End() && part.Pos() < condition.Body.Rbrace &&
					reIgnoredErrorReason.MatchString(part.Text) {
					return true
				}
			}
		}
		findings[files.PositionFor(condition.If, false).Line] = true
		return true
	})
	return findings
}

func isGoErrorCheck(expression ast.Expr) bool {
	check, ok := ast.Unparen(expression).(*ast.BinaryExpr)
	if !ok || check.Op != token.NEQ {
		return false
	}
	left, leftOK := ast.Unparen(check.X).(*ast.Ident)
	right, rightOK := ast.Unparen(check.Y).(*ast.Ident)
	return leftOK && rightOK && strings.EqualFold(left.Name, "err") && right.Name == "nil"
}

// CheckToilAndScale audits code for Google SRE Scale and Operational Toil violations
func CheckToilAndScale(filePath string, content string) []model.Finding {
	if IsTestFile(filePath) {
		return nil
	}

	lines := strings.Split(content, "\n")
	var findings []model.Finding
	var goFindings map[int]bool
	if strings.HasSuffix(filePath, ".go") {
		goFindings = goSwallowedErrorLines(filePath, content)
	}
	var blockFindings map[int]bool
	if goFindings == nil {
		blockFindings = blockSwallowedErrorLines(filePath, lines)
	}

	for i, line := range lines {
		swallowed := goFindings[i+1]
		if goFindings == nil {
			swallowed = reSwallowErr.MatchString(line) || blockFindings[i+1]
		}
		lineFindings := auditLineToil(filePath, i+1, line, lines, swallowed)
		findings = append(findings, lineFindings...)
	}

	return findings
}

var (
	rePythonExcept = regexp.MustCompile(`^(\s*)except\b[^:]*:\s*$`)
	reCatchOpen    = regexp.MustCompile(`catch\s*\([^)]*\)\s*\{`)
	reGoErrOpen    = regexp.MustCompile(`if\s+err\s*!=\s*nil\s*\{`)
)

// codeViews returns, per line, the code with string and comment content
// blanked out, plus the comment text found on that line. Multiline
// literals (Python triple quotes, JS template literals, C block
// comments) are tracked across lines so handler-shaped text inside
// them is never treated as code.
func codeViews(filePath string, lines []string) ([]string, []string) {
	code := make([]string, len(lines))
	comments := make([]string, len(lines))
	if strings.HasSuffix(filePath, ".py") {
		codeViewsPython(lines, code, comments)
		return code, comments
	}
	codeViewsCLike(filePath, lines, code, comments)
	return code, comments
}

func codeViewsPython(lines, code, comments []string) {
	triple := ""
	for i, line := range lines {
		var b strings.Builder
		runes := []rune(line)
		for j := 0; j < len(runes); {
			if triple != "" {
				if strings.HasPrefix(string(runes[j:]), triple) {
					b.WriteString("   ")
					j += 3
					triple = ""
				} else {
					b.WriteByte(' ')
					j++
				}
				continue
			}
			if j+2 < len(runes) && (string(runes[j:j+3]) == `"""` || string(runes[j:j+3]) == `'''`) {
				triple = string(runes[j : j+3])
				b.WriteString("   ")
				j += 3
				continue
			}
			c := runes[j]
			if c == '#' {
				comments[i] = string(runes[j:])
				break
			}
			if c == '"' || c == '\'' {
				j++
				for j < len(runes) {
					if runes[j] == '\\' {
						j += 2
						continue
					}
					if runes[j] == c {
						j++
						break
					}
					j++
				}
				b.WriteByte(' ')
				continue
			}
			b.WriteRune(c)
			j++
		}
		code[i] = b.String()
	}
}

func codeViewsCLike(filePath string, lines, code, comments []string) {
	templates := strings.HasSuffix(filePath, ".js") || strings.HasSuffix(filePath, ".jsx") ||
		strings.HasSuffix(filePath, ".ts") || strings.HasSuffix(filePath, ".tsx") ||
		strings.HasSuffix(filePath, ".mjs") || strings.HasSuffix(filePath, ".cjs")
	inBlockComment := false
	inTemplate := false
	templateExprDepth := 0
	for i, line := range lines {
		var b strings.Builder
		runes := []rune(line)
		for j := 0; j < len(runes); {
			if inBlockComment {
				if runes[j] == '*' && j+1 < len(runes) && runes[j+1] == '/' {
					inBlockComment = false
					b.WriteString("  ")
					j += 2
				} else {
					b.WriteByte(' ')
					j++
				}
				continue
			}
			if inTemplate && templateExprDepth == 0 {
				if runes[j] == '\\' {
					b.WriteString("  ")
					j += 2
					continue
				}
				if runes[j] == '`' {
					inTemplate = false
					b.WriteByte(' ')
					j++
					continue
				}
				if runes[j] == '$' && j+1 < len(runes) && runes[j+1] == '{' {
					templateExprDepth = 1
					b.WriteString("  ")
					j += 2
					continue
				}
				b.WriteByte(' ')
				j++
				continue
			}
			c := runes[j]
			if c == '/' && j+1 < len(runes) && runes[j+1] == '/' {
				comments[i] = string(runes[j:])
				break
			}
			if c == '/' && j+1 < len(runes) && runes[j+1] == '*' {
				inBlockComment = true
				b.WriteString("  ")
				j += 2
				continue
			}
			if templates && c == '`' {
				inTemplate = true
				b.WriteByte(' ')
				j++
				continue
			}
			if c == '"' || c == '\'' {
				j++
				for j < len(runes) {
					if runes[j] == '\\' {
						j += 2
						continue
					}
					if runes[j] == c {
						j++
						break
					}
					j++
				}
				b.WriteByte(' ')
				continue
			}
			if inTemplate && templateExprDepth > 0 {
				if c == '{' {
					templateExprDepth++
				}
				if c == '}' {
					templateExprDepth--
				}
			}
			b.WriteRune(c)
			j++
		}
		code[i] = b.String()
	}
}

func indentWidth(codeLine string) int {
	n := 0
	for _, r := range codeLine {
		if r != ' ' && r != '\t' {
			break
		}
		n++
	}
	return n
}

// blockSwallowedErrorLines finds empty error handlers that a formatter
// split across lines, which the per-line reSwallowErr cannot see. It
// covers Python except suites in .py files and brace-delimited catch
// blocks (plus Go error checks on the unparseable-Go fallback path) in
// C-like files. Handlers whose body carries a documented ignore reason
// are exempt, mirroring goSwallowedErrorLines.
func blockSwallowedErrorLines(filePath string, lines []string) map[int]bool {
	code, comments := codeViews(filePath, lines)
	findings := make(map[int]bool)
	if strings.HasSuffix(filePath, ".py") {
		pythonBlockSwallows(code, comments, findings)
		return findings
	}
	openers := []*regexp.Regexp{reCatchOpen}
	if strings.HasSuffix(filePath, ".go") {
		openers = append(openers, reGoErrOpen)
	}
	for i, cv := range code {
		for _, opener := range openers {
			loc := opener.FindStringIndex(cv)
			if loc == nil {
				continue
			}
			braceRune := utf8.RuneCountInString(cv[:loc[1]-1])
			if braceBlockIsEmpty(code, comments, i, braceRune) {
				findings[i+1] = true
			}
		}
	}
	return findings
}

func pythonBlockSwallows(code, comments []string, findings map[int]bool) {
	for i, cv := range code {
		m := rePythonExcept.FindStringSubmatch(cv)
		if m == nil {
			continue
		}
		indent := len(m[1])
		noop, real, reason := 0, false, reIgnoredErrorReason.MatchString(comments[i])
		for j := i + 1; j < len(code); j++ {
			trimmed := strings.TrimSpace(code[j])
			if trimmed == "" {
				if reIgnoredErrorReason.MatchString(comments[j]) {
					reason = true
				}
				continue
			}
			if indentWidth(code[j]) <= indent {
				break
			}
			if reIgnoredErrorReason.MatchString(comments[j]) {
				reason = true
			}
			if trimmed == "pass" || trimmed == "..." {
				noop++
			} else {
				real = true
				break
			}
		}
		if noop > 0 && !real && !reason {
			findings[i+1] = true
		}
	}
}

// braceBlockIsEmpty reports whether the brace block opening at
// code[startLine][bracePos] contains no code before its matching close
// brace, and no documented ignore reason in its comments.
func braceBlockIsEmpty(code, comments []string, startLine, bracePos int) bool {
	depth := 0
	empty := true
	for i := startLine; i < len(code); i++ {
		if reIgnoredErrorReason.MatchString(comments[i]) && depth > 0 {
			return false
		}
		runes := []rune(code[i])
		start := 0
		if i == startLine {
			start = bracePos
		}
		for j := start; j < len(runes); j++ {
			switch runes[j] {
			case '{':
				depth++
			case '}':
				depth--
				if depth == 0 {
					return empty
				}
			default:
				if depth > 0 && runes[j] != ' ' && runes[j] != '\t' {
					empty = false
				}
			}
		}
	}
	return false
}
