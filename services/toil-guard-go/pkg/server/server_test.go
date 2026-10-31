package server

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

func TestHealthzEndpoint(t *testing.T) {
	req := httptest.NewRequest(http.MethodGet, "/healthz", nil)
	w := httptest.NewRecorder()

	handleHealthz(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var res map[string]string
	if err := json.NewDecoder(w.Body).Decode(&res); err != nil {
		t.Fatalf("failed to decode json: %v", err)
	}
	if res["status"] != "healthy" {
		t.Errorf("expected status healthy, got %s", res["status"])
	}
}

func TestAuditEndpoint(t *testing.T) {
	auditReq := AuditRequest{
		Files: map[string]string{
			"clean.go": "package main\nfunc Clean() {}\n",
			"bad.go":   "package main\nfunc Bad() {\n    time.Sleep(5 * time.Second)\n}\n",
		},
	}
	body, _ := json.Marshal(auditReq)
	req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(body))
	w := httptest.NewRecorder()

	handleAudit(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("expected status 200, got %d", w.Code)
	}

	var report model.AuditReport
	if err := json.NewDecoder(w.Body).Decode(&report); err != nil {
		t.Fatalf("failed to decode audit report: %v", err)
	}

	if report.SLI.Status != "BLOCKED" {
		t.Errorf("expected status BLOCKED due to blind sleep, got %s", report.SLI.Status)
	}
	if len(report.Findings) == 0 {
		t.Errorf("expected findings for bad.go, got 0")
	}
}


func TestAuditRequestBodySizeLimit(t *testing.T) {
    body := append([]byte(`{"files":{"large.go":"`), bytes.Repeat([]byte("x"), 1<<20+1)...)
    body = append(body, []byte(`"}}`)... )
    req := httptest.NewRequest(http.MethodPost, "/v1/audit", bytes.NewReader(body))
    w := httptest.NewRecorder()
    _, ok := decodeAuditRequest(w, req)
    if ok || w.Code != http.StatusRequestEntityTooLarge {
        t.Fatalf("expected request rejection 413, got status %d, ok=%v", w.Code, ok)
    }
}

func TestServerBindsOnlyToLoopback(t *testing.T) {
    srv := NewServer(9092)
    if srv.httpServer.Addr != "127.0.0.1:9092" {
        t.Fatalf("unexpected bind address: %s", srv.httpServer.Addr)
    }
}
