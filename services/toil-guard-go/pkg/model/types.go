package model

// Severity defines the triage level
type Severity string

const (
	SeverityBlocker Severity = "BLOCKER"
	SeverityReview  Severity = "REVIEW"
	SeverityInfo    Severity = "INFO"
)

// ViolationCategory represents the SRE discipline area
type ViolationCategory string

const (
	CategoryKISS  ViolationCategory = "KISS"
	CategoryDRY   ViolationCategory = "DRY"
	CategoryYAGNI ViolationCategory = "YAGNI"
	CategoryScale ViolationCategory = "SCALE_TOIL"
)

// Finding represents an SRE or anti-slop violation
type Finding struct {
	File       string            `json:"file"`
	Line       int               `json:"line"`
	Category   ViolationCategory `json:"category"`
	Severity   Severity          `json:"severity"`
	Code       string            `json:"code"`
	Message    string            `json:"message"`
	Suggestion string            `json:"suggestion"`
}

// SLIReport captures the Service Level Indicators for code health
type SLIReport struct {
	TotalFiles       int     `json:"total_files"`
	TotalLines       int     `json:"total_lines"`
	ComplexityScore  float64 `json:"complexity_score"` // 0.0 to 1.0 (lower is simpler)
	DuplicationRatio float64 `json:"duplication_ratio"`// 0.0 to 1.0
	ToilIncidents    int     `json:"toil_incidents"`
	SlopIndex        float64 `json:"slop_index"`       // 0.0 to 100.0
	ErrorBudgetLeft  float64 `json:"error_budget_left"`// 100.0 down to 0.0
	Status           string  `json:"status"`           // PASSED, NEEDS_REVIEW, BLOCKED
}

// AuditReport is the full diagnostic payload
type AuditReport struct {
	Engine    string    `json:"engine"`
	Version   string    `json:"version"`
	SLI       SLIReport `json:"sli"`
	Findings  []Finding `json:"findings"`
}

// NewAuditReport creates a canonical AuditReport
func NewAuditReport(findings []Finding, sli SLIReport) AuditReport {
	return AuditReport{
		Engine:   "toil-guard-go",
		Version:  "0.1.0",
		SLI:      sli,
		Findings: findings,
	}
}
