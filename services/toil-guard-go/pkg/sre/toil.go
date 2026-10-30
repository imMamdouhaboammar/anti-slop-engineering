package sre

import (
	"fmt"
	"regexp"
	"strings"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

var (
	reBlindSleep   = regexp.MustCompile(`(?i)(?:time\.Sleep\([0-9]+\s*\*\s*time\.Second\)|sleep\([0-9]+\)|Thread\.sleep\([0-9]+\))`)
	reFixedRetry   = regexp.MustCompile(`(?i)(?:for\s+retry\s*:=\s*0;\s*retry\s*<\s*[0-9]+;\s*retry\+\+|for\s+attempt\s+in\s+range\([0-9]+\):)`)
	reSwallowErr   = regexp.MustCompile(`(?i)(?:if\s+err\s*!=\s*nil\s*\{\s*\}|catch\s*\([^)]*\)\s*\{\s*\}|except(?:\s+Exception)?\s*:\s*pass)`)
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

func auditLineToil(file string, lineNo int, line string, allLines []string) []model.Finding {
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

	if reSwallowErr.MatchString(trimmed) {
		findings = append(findings, makeToilFinding(
			file, lineNo, model.CategoryScale, model.SeverityBlocker, "SRE-SCALE-SWALLOW",
			"Silent error swallowing turns failure modes into operational diagnostic toil.",
			"Log structured diagnostic metadata or propagate errors with contextual stack traces.",
		))
	}

	if reYAGNIComment.MatchString(trimmed) {
		findings = append(findings, makeToilFinding(
			file, lineNo, model.CategoryYAGNI, model.SeverityReview, "SRE-YAGNI-SPECULATIVE",
			fmt.Sprintf("Speculative placeholder comment detected: '%s'. Build only for verified requirements.", trimmed),
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

// CheckToilAndScale audits code for Google SRE Scale and Operational Toil violations
func CheckToilAndScale(filePath string, content string) []model.Finding {
	if IsTestFile(filePath) {
		return nil
	}

	lines := strings.Split(content, "\n")
	var findings []model.Finding

	for i, line := range lines {
		lineFindings := auditLineToil(filePath, i+1, line, lines)
		findings = append(findings, lineFindings...)
	}

	return findings
}
