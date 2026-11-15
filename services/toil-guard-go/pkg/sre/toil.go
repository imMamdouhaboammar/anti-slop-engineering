package sre

import (
	"go/ast"
	"go/parser"
	"go/token"
	"regexp"
	"sort"
	"strings"

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
			return parsed.Comments[i].Pos() > condition.Body.Lbrace
		})
		for _, comment := range parsed.Comments[first:] {
			if comment.Pos() >= condition.Body.Rbrace {
				break
			}
			if reIgnoredErrorReason.MatchString(comment.Text()) {
				return true
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
	return leftOK && rightOK && left.Name == "err" && right.Name == "nil"
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

	for i, line := range lines {
		swallowed := goFindings[i+1]
		if goFindings == nil {
			swallowed = reSwallowErr.MatchString(line)
		}
		lineFindings := auditLineToil(filePath, i+1, line, lines, swallowed)
		findings = append(findings, lineFindings...)
	}

	return findings
}
