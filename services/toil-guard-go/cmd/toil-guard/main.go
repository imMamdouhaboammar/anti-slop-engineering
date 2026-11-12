package main

import (
	"context"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"strings"
	"syscall"
	"time"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/server"
	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/sre"
)

func main() {
	if len(os.Args) < 2 {
		printUsage()
		os.Exit(1)
	}

	command := os.Args[1]

	switch command {
	case "audit":
		runAudit(os.Args[2:])
	case "serve":
		runServe(os.Args[2:])
	case "stream":
		runStream(os.Args[2:])
	case "help", "-h", "--help":
		printUsage()
	default:
		fmt.Fprintf(os.Stderr, "Unknown subcommand: %s\n", command)
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println("Toil Guard (Go SRE Microservice & Engine)")
	fmt.Println()
	fmt.Println("Usage: toil-guard <command> [arguments]")
	fmt.Println()
	fmt.Println("Commands:")
	fmt.Println("  audit   [paths...]     Audit source paths or git changes against KISS, DRY, YAGNI, and Scale")
	fmt.Println("  serve   [--port 9092]  Start high-throughput HTTP SRE daemon with /healthz, /metrics, /v1/audit")
	fmt.Println("  stream  [--interval 3s]  Stream git diff statistics (not a live error-budget calculation)")
	fmt.Println("  help                   Show this help message")
}

func runAudit(args []string) {
	if code := executeAudit(args, os.Stdout, os.Stderr); code != 0 {
		os.Exit(code)
	}
}

func executeAudit(args []string, stdout, stderr io.Writer) int {
	fs := flag.NewFlagSet("audit", flag.ContinueOnError)
	fs.SetOutput(stderr)
	format := fs.String("format", "text", "Output format: text or json")
	base := fs.String("base", "HEAD", "Git base reference to diff if no files specified")
	if err := fs.Parse(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}

	fileMap, err := collectAuditFiles(fs.Args(), *base)
	if err != nil {
		fmt.Fprintln(stderr, "Audit failed:", err)
		return 1
	}
	allFindings, sli := sre.AuditFiles(fileMap)
	report := model.NewAuditReport(allFindings, sli)

	if err := writeAuditReport(stdout, report, *format); err != nil {
		fmt.Fprintln(stderr, "Audit failed:", err)
		return 1
	}

	if sli.Status == "BLOCKED" {
		return 1
	}
	return 0
}

func collectAuditFiles(targets []string, base string) (map[string]string, error) {
	if len(targets) == 0 {
		return collectGitDiffFiles(base)
	}
	fileMap, err := collectExplicitTargetFiles(targets)
	if err != nil {
		return nil, err
	}
	if len(fileMap) == 0 {
		return nil, fmt.Errorf("no auditable files found")
	}
	return fileMap, nil
}

func collectExplicitTargetFiles(targets []string) (map[string]string, error) {
	fileMap := make(map[string]string)
	for _, target := range targets {
		err := filepath.Walk(target, func(path string, info os.FileInfo, walkErr error) error {
			if walkErr != nil {
				return walkErr
			}
			if info.IsDir() {
				if path != target && (info.Name() == ".git" || info.Name() == "node_modules" || info.Name() == "target") {
					return filepath.SkipDir
				}
				return nil
			}
			if !isAuditable(path) {
				return nil
			}
			content, err := os.ReadFile(path)
			if err != nil {
				return err
			}
			fileMap[path] = string(content)
			return nil
		})
		if err != nil {
			return nil, fmt.Errorf("walking %q: %w", target, err)
		}
	}
	return fileMap, nil
}

func collectGitDiffFiles(base string) (map[string]string, error) {
	if strings.TrimSpace(base) == "" || strings.HasPrefix(base, "-") {
		return nil, fmt.Errorf("invalid git base reference %q", base)
	}
	revOut, revErr := exec.Command("git", "rev-parse", "--verify", base+"^{commit}").CombinedOutput()
	if revErr != nil {
		return nil, fmt.Errorf("invalid git base %q: %w: %s", base, revErr, strings.TrimSpace(string(revOut)))
	}

	out, err := exec.Command("git", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "diff", "--no-ext-diff", base, "--").CombinedOutput()
	if err != nil {
		return nil, fmt.Errorf("git diff %q failed: %w: %s", base, err, strings.TrimSpace(string(out)))
	}
	if len(out) > 0 {
		return parseGitDiff(string(out))
	}
	return collectUntrackedAndModifiedStatusFiles()
}

func collectUntrackedAndModifiedStatusFiles() (map[string]string, error) {
	fileMap := make(map[string]string)
	statusOut, statusErr := exec.Command("git", "status", "--porcelain").CombinedOutput()
	if statusErr != nil {
		return nil, fmt.Errorf("git status failed: %w: %s", statusErr, strings.TrimSpace(string(statusOut)))
	}
	for _, line := range strings.Split(string(statusOut), "\n") {
		if len(line) < 4 || line[0] == 'D' || line[1] == 'D' {
			continue
		}
		path := strings.TrimSpace(line[3:])
		if !isAuditable(path) {
			continue
		}
		content, err := os.ReadFile(path)
		if err != nil {
			return nil, fmt.Errorf("reading %q: %w", path, err)
		}
		fileMap[path] = string(content)
	}
	return fileMap, nil
}

func writeAuditReport(w io.Writer, report model.AuditReport, format string) error {
	if format == "json" {
		data, err := json.MarshalIndent(report, "", "  ")
		if err != nil {
			return fmt.Errorf("marshaling report: %w", err)
		}
		_, err = fmt.Fprintln(w, string(data))
		return err
	}
	if format != "text" {
		return fmt.Errorf("unsupported format %q (expected text or json)", format)
	}

	var buf strings.Builder
	sli := report.SLI
	fmt.Fprintf(&buf, "== Toil Guard SRE Engine Status: %s ==\n", sli.Status)
	fmt.Fprintf(&buf, "Audited Files: %d | Lines: %d | Error Budget Left: %.1f%%\n",
		sli.TotalFiles, sli.TotalLines, sli.ErrorBudgetLeft)
	fmt.Fprintf(&buf, "Toil Incidents: %d | Complexity Score: %.2f\n",
		sli.ToilIncidents, sli.ComplexityScore)

	if len(report.Findings) > 0 {
		buf.WriteString("------------------------------------------------------------\n")
		for _, f := range report.Findings {
			fmt.Fprintf(&buf, "[%s] %s:%d: [%s] %s\n", f.Severity, f.File, f.Line, f.Code, f.Message)
			fmt.Fprintf(&buf, "  Suggestion: %s\n", f.Suggestion)
		}
		buf.WriteString("------------------------------------------------------------\n")
	}
	_, err := io.WriteString(w, buf.String())
	return err
}

func runServe(args []string) {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	port := fs.Int("port", 9092, "Port to bind the HTTP service on")
	_ = fs.Parse(args)

	srv := server.NewServer(*port)
	fmt.Printf("Toil Guard SRE daemon running on http://127.0.0.1:%d\n", *port)
	fmt.Println("Endpoints: /healthz, /metrics, /v1/audit, /v1/sli-budget")

	serverError := make(chan error, 1)
	go func() {
		serverError <- srv.Start()
	}()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(sigChan)
	select {
	case err := <-serverError:
		if err != nil && err != http.ErrServerClosed {
			fmt.Fprintf(os.Stderr, "Server failed: %v\n", err)
			os.Exit(1)
		}
		return
	case <-sigChan:
		fmt.Println("\nShutting down Toil Guard daemon gracefully...")
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		if err := srv.Shutdown(ctx); err != nil {
			fmt.Fprintf(os.Stderr, "Server shutdown failed: %v\n", err)
			os.Exit(1)
		}
	}
}

func runStream(args []string) {
	fs := flag.NewFlagSet("stream", flag.ExitOnError)
	interval := fs.Duration("interval", 3*time.Second, "Polling interval for git telemetry")
	_ = fs.Parse(args)

	fmt.Printf("Toil Guard streaming git telemetry every %v (Press Ctrl+C to exit)...\n", *interval)

	for {
		cmd := exec.Command("git", "diff", "HEAD", "--stat")
		out, err := cmd.Output()
		if err == nil {
			statStr := strings.TrimSpace(string(out))
			if statStr != "" {
				fmt.Printf("[%s] Active git diff:\n%s\n", time.Now().Format("15:04:05"), statStr)
			} else {
				fmt.Printf("[%s] Working tree clean (no diff changes)\n", time.Now().Format("15:04:05"))
			}
		}
		time.Sleep(*interval)
	}
}

func isAuditable(path string) bool {
	if strings.Contains(path, "/.git/") || strings.Contains(path, "node_modules") || strings.Contains(path, "target/") {
		return false
	}
	ext := filepath.Ext(path)
	switch ext {
	case ".go", ".ts", ".js", ".py", ".rs", ".java", ".c", ".cpp":
		return true
	default:
		return false
	}
}

func isDocFile(path string) bool {
	lower := strings.ToLower(path)
	return strings.HasSuffix(lower, ".md") || strings.HasSuffix(lower, ".markdown") ||
		strings.HasSuffix(lower, ".txt") || strings.HasSuffix(lower, ".rst") ||
		strings.Contains(lower, "/docs/") || strings.HasPrefix(lower, "docs/")
}

func parseGitDiff(diffOutput string) (map[string]string, error) {
	fileMap := make(map[string]string)
	if strings.TrimSpace(diffOutput) == "" {
		return fileMap, nil
	}

	lines := strings.Split(diffOutput, "\n")
	currentFile := ""
	var currentLines []string
	sawDiffHeader := false

	flush := func() {
		if currentFile != "" && len(currentLines) > 0 && isAuditable(currentFile) && !isDocFile(currentFile) {
			fileMap[currentFile] = strings.Join(currentLines, "\n")
		}
		currentLines = nil
	}

	for _, line := range lines {
		if strings.HasPrefix(line, "diff --git ") {
			sawDiffHeader = true
			flush()
			parts := strings.Split(line, " b/")
			if len(parts) > 1 {
				currentFile = strings.TrimSpace(parts[1])
			}
		} else if strings.HasPrefix(line, "+++ b/") {
			currentFile = strings.TrimSpace(line[6:])
		} else if strings.HasPrefix(line, "+") && !strings.HasPrefix(line, "+++") {
			currentLines = append(currentLines, line[1:])
		}
	}
	flush()

	if !sawDiffHeader {
		return nil, fmt.Errorf("malformed git diff output: missing diff header")
	}
	return fileMap, nil
}
