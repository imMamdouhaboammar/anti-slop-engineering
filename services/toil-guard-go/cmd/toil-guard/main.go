package main

import (
	"bytes"
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
	"regexp"
	"strconv"
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

func runGitCommand(args ...string) ([]byte, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	return exec.CommandContext(ctx, "git", args...).CombinedOutput()
}

func collectGitDiffFiles(base string) (map[string]string, error) {
	if strings.TrimSpace(base) == "" || strings.HasPrefix(base, "-") {
		return nil, fmt.Errorf("invalid git base reference %q", base)
	}
	if revOut, revErr := runGitCommand("rev-parse", "--verify", base+"^{commit}"); revErr != nil {
		return nil, fmt.Errorf("invalid git base %q: %w: %s", base, revErr, strings.TrimSpace(string(revOut)))
	}

	fileMap := make(map[string]string)
	out, err := runGitCommand("-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "diff", "--no-ext-diff", base, "--")
	if err != nil {
		return nil, fmt.Errorf("git diff %q failed: %w: %s", base, err, strings.TrimSpace(string(out)))
	}
	if len(out) > 0 {
		diffMap, err := parseGitDiff(string(out))
		if err != nil {
			return nil, err
		}
		for k, v := range diffMap {
			if content, err := os.ReadFile(k); err == nil && isAuditable(k) {
				fileMap[k] = string(content)
			} else {
				fileMap[k] = v
			}
		}
	}
	statusMap, err := collectUntrackedAndModifiedStatusFiles()
	if err != nil {
		return nil, err
	}
	for k, v := range statusMap {
		if _, exists := fileMap[k]; !exists {
			fileMap[k] = v
		}
	}
	return fileMap, nil
}

func collectUntrackedAndModifiedStatusFiles() (map[string]string, error) {
	fileMap := make(map[string]string)
	statusOut, statusErr := runGitCommand("status", "--porcelain", "--untracked-files=all")
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
	listener, err := srv.Listen()
	if err != nil {
		fmt.Fprintf(os.Stderr, "Server failed: %v\n", err)
		os.Exit(1)
	}

	defer listener.Close()

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)
	defer signal.Stop(sigChan)

	fmt.Printf("Toil Guard SRE daemon running on http://%s\n", listener.Addr())
	fmt.Println("Endpoints: /healthz, /metrics, /v1/audit, /v1/sli-budget")

	serverError := make(chan error, 1)
	go func() {
		serverError <- srv.Serve(listener)
	}()

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
		fmt.Println("Toil Guard daemon shut down")
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

var hunkHeaderRegex = regexp.MustCompile(`^@@\s+-[0-9]+(?:,[0-9]+)?\s+\+([0-9]+)(?:,[0-9]+)?\s+@@`)

func cleanGitPath(raw string) string {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" || trimmed == "/dev/null" {
		return ""
	}
	if strings.HasPrefix(trimmed, "\"") && strings.HasSuffix(trimmed, "\"") && len(trimmed) >= 2 {
		trimmed = unescapeGitCString(trimmed[1 : len(trimmed)-1])
	}
	trimmed = strings.TrimPrefix(trimmed, "b/")
	trimmed = strings.TrimPrefix(trimmed, "a/")
	return filepath.Clean(filepath.ToSlash(trimmed))
}

func parseOctal(runes []rune, start int) (byte, int) {
	val := int(runes[start] - '0')
	idx := start
	count := 1
	for count < 3 && idx+1 < len(runes) && runes[idx+1] >= '0' && runes[idx+1] <= '7' {
		idx++
		count++
		val = val*8 + int(runes[idx]-'0')
	}
	return byte(val), idx
}

func decodeEscapeByte(c rune) (byte, bool) {
	switch c {
	case 'n':
		return '\n', true
	case 'r':
		return '\r', true
	case 't':
		return '\t', true
	case 'b':
		return '\b', true
	case 'f':
		return '\f', true
	case 'a':
		return '\a', true
	case 'v':
		return '\v', true
	case '\\':
		return '\\', true
	case '"':
		return '"', true
	default:
		return 0, false
	}
}

func unescapeGitCString(s string) string {
	var buf bytes.Buffer
	runes := []rune(s)
	for i := 0; i < len(runes); i++ {
		if runes[i] != '\\' || i+1 >= len(runes) {
			buf.WriteRune(runes[i])
			continue
		}
		i++
		c := runes[i]
		if c >= '0' && c <= '7' {
			b, nextIdx := parseOctal(runes, i)
			buf.WriteByte(b)
			i = nextIdx
			continue
		}
		if b, ok := decodeEscapeByte(c); ok {
			buf.WriteByte(b)
		} else {
			buf.WriteRune(c)
		}
	}
	return buf.String()
}

func padLinesToHunkStart(currentLines []string, line string) []string {
	m := hunkHeaderRegex.FindStringSubmatch(line)
	if len(m) <= 1 {
		return currentLines
	}
	start, err := strconv.Atoi(m[1])
	if err != nil || start <= 1 {
		return currentLines
	}
	for len(currentLines) < start-1 {
		currentLines = append(currentLines, "")
	}
	return currentLines
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
	inHunk := false

	flush := func() {
		if currentFile != "" && len(currentLines) > 0 && isAuditable(currentFile) && !isDocFile(currentFile) {
			fileMap[currentFile] = strings.Join(currentLines, "\n")
		}
		currentLines = nil
		inHunk = false
	}

	for _, line := range lines {
		if strings.HasPrefix(line, "diff --git ") {
			sawDiffHeader = true
			flush()
			rest := strings.TrimPrefix(line, "diff --git ")
			var targetPart string
			if idx := strings.LastIndex(rest, " \"b/"); idx != -1 {
				targetPart = rest[idx+1:]
			} else if idx := strings.LastIndex(rest, " b/"); idx != -1 {
				targetPart = rest[idx+1:]
			} else {
				targetPart = rest
			}
			currentFile = cleanGitPath(targetPart)
		} else if strings.HasPrefix(line, "+++ ") {
			target := cleanGitPath(strings.TrimPrefix(line, "+++ "))
			if target != "" {
				currentFile = target
			}
		} else if strings.HasPrefix(line, "rename to ") {
			target := cleanGitPath(strings.TrimPrefix(line, "rename to "))
			if target != "" {
				currentFile = target
			}
		} else if strings.HasPrefix(line, "@@") {
			inHunk = true
			currentLines = padLinesToHunkStart(currentLines, line)
		} else if inHunk {
			if strings.HasPrefix(line, "+") && !strings.HasPrefix(line, "+++") {
				currentLines = append(currentLines, line[1:])
			} else if strings.HasPrefix(line, " ") {
				currentLines = append(currentLines, line[1:])
			} else if line == "" {
				currentLines = append(currentLines, "")
			}
		}
	}
	flush()

	if !sawDiffHeader {
		return nil, fmt.Errorf("malformed git diff output: missing diff header")
	}
	return fileMap, nil
}
