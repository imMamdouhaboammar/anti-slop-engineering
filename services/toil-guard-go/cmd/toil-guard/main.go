package main

import (
	"encoding/json"
	"flag"
	"fmt"
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
	fs := flag.NewFlagSet("audit", flag.ExitOnError)
	format := fs.String("format", "text", "Output format: text or json")
	base := fs.String("base", "HEAD", "Git base reference to diff if no files specified")
	_ = fs.Parse(args)

	fileMap, err := collectAuditFiles(fs.Args(), *base)
	if err != nil {
		fmt.Fprintln(os.Stderr, "Audit failed:", err)
		os.Exit(1)
	}
	allFindings, sli := sre.AuditFiles(fileMap)
	report := model.NewAuditReport(allFindings, sli)

	printAuditReport(report, *format)

	if sli.Status == "BLOCKED" {
		os.Exit(1)
	}
}

func collectAuditFiles(targets []string, base string) (map[string]string, error) {
	fileMap := make(map[string]string)
	if len(targets) > 0 {
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
	} else {
		cmd := exec.Command("git", "diff", base, "--")
		out, err := cmd.CombinedOutput()
		if err != nil {
			return nil, fmt.Errorf("git diff %q failed: %w: %s", base, err, strings.TrimSpace(string(out)))
		}
		if len(out) > 0 {
			fileMap = parseGitDiff(string(out))
		} else {
			statusOut, statusErr := exec.Command("git", "status", "--porcelain").CombinedOutput()
			if statusErr != nil {
				return nil, fmt.Errorf("git status failed: %w: %s", statusErr, strings.TrimSpace(string(statusOut)))
			}
			for _, line := range strings.Split(string(statusOut), "\n") {
				if len(line) < 4 {
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
		}
	}
	if len(fileMap) == 0 {
		return nil, fmt.Errorf("no auditable files found")
	}
	return fileMap, nil
}

func printAuditReport(report model.AuditReport, format string) {
	if format == "json" {
		data, _ := json.MarshalIndent(report, "", "  ")
		fmt.Println(string(data))
		return
	}

	sli := report.SLI
	fmt.Printf("== Toil Guard SRE Engine Status: %s ==\n", sli.Status)
	fmt.Printf("Audited Files: %d | Lines: %d | Error Budget Left: %.1f%%\n",
		sli.TotalFiles, sli.TotalLines, sli.ErrorBudgetLeft)
	fmt.Printf("Toil Incidents: %d | Complexity Score: %.2f\n",
		sli.ToilIncidents, sli.ComplexityScore)

	if len(report.Findings) > 0 {
		fmt.Println("------------------------------------------------------------")
		for _, f := range report.Findings {
			fmt.Printf("[%s] %s:%d: [%s] %s\n", f.Severity, f.File, f.Line, f.Code, f.Message)
			fmt.Printf("  Suggestion: %s\n", f.Suggestion)
		}
		fmt.Println("------------------------------------------------------------")
	}
}

func runServe(args []string) {
	fs := flag.NewFlagSet("serve", flag.ExitOnError)
	port := fs.Int("port", 9092, "Port to bind the HTTP service on")
	_ = fs.Parse(args)

	srv := server.NewServer(*port)
	fmt.Printf("Toil Guard SRE daemon running on http://127.0.0.1:%d\n", *port)
	fmt.Println("Endpoints: /healthz, /metrics, /v1/audit, /v1/sli-budget")

	go func() {
		if err := srv.Start(); err != nil {
			fmt.Fprintf(os.Stderr, "Server stopped: %v\n", err)
		}
	}()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	<-sigChan

	fmt.Println("\nShutting down Toil Guard daemon gracefully...")
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

func parseGitDiff(diffOutput string) map[string]string {
	fileMap := make(map[string]string)
	lines := strings.Split(diffOutput, "\n")
	currentFile := ""
	var currentLines []string

	flush := func() {
		if currentFile != "" && len(currentLines) > 0 && isAuditable(currentFile) && !isDocFile(currentFile) {
			fileMap[currentFile] = strings.Join(currentLines, "\n")
		}
		currentLines = nil
	}

	for _, line := range lines {
		if strings.HasPrefix(line, "diff --git") {
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
	return fileMap
}
