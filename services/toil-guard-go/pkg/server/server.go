package server

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"sync/atomic"
	"time"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/sre"
)

var (
	metricAuditsTotal   uint64
	metricBlockersTotal uint64
	metricToilTotal     uint64
)

type AuditRequest struct {
	Files map[string]string `json:"files"`
}

type Server struct {
	httpServer *http.Server
}

func NewServer(port int) *Server {
	mux := http.NewServeMux()

	mux.HandleFunc("/healthz", handleHealthz)
	mux.HandleFunc("/metrics", handleMetrics)
	mux.HandleFunc("/v1/audit", handleAudit)
	mux.HandleFunc("/v1/sli-budget", handleSLIBudget)

	return &Server{
		httpServer: &http.Server{
			Addr:         fmt.Sprintf("127.0.0.1:%d", port),
			Handler:      mux,
			ReadTimeout:  15 * time.Second,
			WriteTimeout: 15 * time.Second,
		},
	}
}

func (s *Server) Start() error {
	return s.httpServer.ListenAndServe()
}

func (s *Server) Shutdown(ctx context.Context) error {
	return s.httpServer.Shutdown(ctx)
}

func handleHealthz(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status":  "healthy",
		"service": "toil-guard-go",
		"version": "0.1.0",
	})
}

func handleMetrics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}
	w.Header().Set("Content-Type", "text/plain; version=0.0.4")
	fmt.Fprintf(w, "# HELP toil_guard_audits_total Total number of audits conducted\n")
	fmt.Fprintf(w, "# TYPE toil_guard_audits_total counter\n")
	fmt.Fprintf(w, "toil_guard_audits_total %d\n", atomic.LoadUint64(&metricAuditsTotal))

	fmt.Fprintf(w, "# HELP toil_guard_blockers_total Total SRE blockers identified\n")
	fmt.Fprintf(w, "# TYPE toil_guard_blockers_total counter\n")
	fmt.Fprintf(w, "toil_guard_blockers_total %d\n", atomic.LoadUint64(&metricBlockersTotal))

	fmt.Fprintf(w, "# HELP toil_guard_toil_total Total toil and scale incidents detected\n")
	fmt.Fprintf(w, "# TYPE toil_guard_toil_total counter\n")
	fmt.Fprintf(w, "toil_guard_toil_total %d\n", atomic.LoadUint64(&metricToilTotal))
}

func decodeAuditRequest(w http.ResponseWriter, r *http.Request) (*AuditRequest, bool) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return nil, false
	}
	const maxAuditBodySize = 1 << 20 // 1 MiB
	r.Body = http.MaxBytesReader(w, r.Body, maxAuditBodySize)
	var req AuditRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		var maxBytesError *http.MaxBytesError
		if errors.As(err, &maxBytesError) {
			http.Error(w, "audit request body too large", http.StatusRequestEntityTooLarge)
		} else {
			http.Error(w, fmt.Sprintf("invalid json payload: %v", err), http.StatusBadRequest)
		}
		return nil, false
	}
	return &req, true
}

func handleAudit(w http.ResponseWriter, r *http.Request) {
	req, ok := decodeAuditRequest(w, r)
	if !ok {
		return
	}

	atomic.AddUint64(&metricAuditsTotal, 1)

	allFindings, sli := sre.AuditFiles(req.Files)

	for _, f := range allFindings {
		if f.Severity == model.SeverityBlocker {
			atomic.AddUint64(&metricBlockersTotal, 1)
		}
		if f.Category == model.CategoryScale {
			atomic.AddUint64(&metricToilTotal, 1)
		}
	}

	report := model.NewAuditReport(allFindings, sli)
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(report)
}

func handleSLIBudget(w http.ResponseWriter, r *http.Request) {
	req, ok := decodeAuditRequest(w, r)
	if !ok {
		return
	}

	_, sli := sre.AuditFiles(req.Files)

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(sli)
}
