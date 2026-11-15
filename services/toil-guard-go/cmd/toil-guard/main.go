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
	worktreeChanges := fs.String("changeset", "", "Optional v1 worktree evidence file; requires --index-changeset")
	indexChanges := fs.String("index-changeset", "", "Optional v1 index evidence file; requires --changeset")
	if err := fs.Parse(args); err != nil {
		if errors.Is(err, flag.ErrHelp) {
			return 0
		}
		return 2
	}

	var fileMap map[string]string
	var err error
	evidenceRequested := false
	fs.Visit(func(option *flag.Flag) {
		if option.Name == "changeset" || option.Name == "index-changeset" {
			evidenceRequested = true
		}
	})
	switch {
	case !evidenceRequested:
		fileMap, err = collectAuditFiles(fs.Args(), *base)
	case *worktreeChanges == "" || *indexChanges == "" || fs.NArg() != 0:
		fmt.Fprintln(stderr, "Supply both --changeset and --index-changeset without explicit source paths")
		return 2
	default:
		fileMap, err = collectChangeSetSources(*base, *worktreeChanges, *indexChanges)
	}
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

func readGitOutput(cmd *exec.Cmd) ([]byte, error) {
	out, err := cmd.Output()
	var exitErr *exec.ExitError
	if errors.As(err, &exitErr) && len(exitErr.Stderr) > 0 {
		return nil, fmt.Errorf("%w: %s", err, strings.TrimSpace(string(exitErr.Stderr)))
	}
	return out, err
}

func resolveGitAuditBase(ctx context.Context, base string) (string, string, error) {
	if strings.TrimSpace(base) == "" || strings.HasPrefix(base, "-") {
		return "", "", fmt.Errorf("invalid git base reference %q", base)
	}
	rawRoot, err := readGitOutput(exec.CommandContext(ctx, "git", "rev-parse", "--show-toplevel"))
	if err != nil {
		return "", "", fmt.Errorf("locating Git repository root: %w", err)
	}
	rootPath := strings.TrimSuffix(string(rawRoot), "\n")
	revision, err := readGitOutput(exec.CommandContext(ctx, "git", "-C", rootPath,
		"rev-parse", "--verify", "--end-of-options", base+"^{commit}"))
	if err != nil {
		return "", "", fmt.Errorf("invalid git base %q: %w", base, err)
	}
	return rootPath, strings.TrimSpace(string(revision)), nil
}

func collectGitDiffFiles(base string) (map[string]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	rootPath, resolvedBase, err := resolveGitAuditBase(ctx, base)
	if err != nil {
		return nil, err
	}

	tracked, err := readGitOutput(exec.CommandContext(ctx, "git", "-C", rootPath,
		"diff", "--no-ext-diff", "--no-relative", "--name-only", "-z", "--diff-filter=d", resolvedBase, "--"))
	if err != nil {
		return nil, fmt.Errorf("git diff %q failed: %w", base, err)
	}
	// A worktree edit can undo a staged change relative to the chosen base.
	staged, err := readGitOutput(exec.CommandContext(ctx, "git", "-C", rootPath,
		"diff", "--cached", "--no-ext-diff", "--no-relative", "--name-only", "-z", "--diff-filter=d", resolvedBase, "--"))
	if err != nil {
		return nil, fmt.Errorf("git diff --cached %q failed: %w", base, err)
	}
	untracked, err := readGitOutput(exec.CommandContext(ctx, "git", "-C", rootPath,
		"ls-files", "--others", "--exclude-standard", "-z"))
	if err != nil {
		return nil, fmt.Errorf("listing untracked files: %w", err)
	}

	paths, err := parseGitPaths(string(tracked) + string(staged) + string(untracked))
	if err != nil {
		return nil, err
	}
	return readChangedSources(rootPath, paths, 0, 0)
}

func parseGitPaths(output string) ([]string, error) {
	if output == "" {
		return nil, nil
	}
	remaining, ok := strings.CutSuffix(output, "\x00")
	if !ok {
		return nil, fmt.Errorf("unterminated git path list")
	}
	paths := strings.Split(remaining, "\x00")
	for _, path := range paths {
		if path == "" {
			return nil, fmt.Errorf("empty path in git path list")
		}
	}
	return paths, nil
}

func readChangedSources(rootPath string, paths []string, fileLimit, totalLimit int64) (map[string]string, error) {
	root, err := os.OpenRoot(rootPath)
	if err != nil {
		return nil, fmt.Errorf("opening repository root: %w", err)
	}
	defer root.Close()

	files := make(map[string]string, len(paths))
	remaining := totalLimit
	for _, path := range paths {
		if _, exists := files[path]; exists || !isAuditable(path) || isDocFile(path) {
			continue
		}
		info, err := root.Lstat(path)
		if errors.Is(err, os.ErrNotExist) {
			continue
		}
		if err != nil {
			return nil, fmt.Errorf("inspecting %q: %w", path, err)
		}
		if !info.Mode().IsRegular() {
			continue
		}
		content, err := readAuditSource(root, path, info, fileLimit, totalLimit, remaining)
		if err != nil {
			return nil, fmt.Errorf("reading %q: %w", path, err)
		}
		remaining -= int64(len(content))
		if bytes.IndexByte(content, 0) < 0 {
			files[path] = string(content)
		}
	}
	return files, nil
}

func readAuditSource(root *os.Root, path string, info os.FileInfo, fileLimit, totalLimit, remaining int64) ([]byte, error) {
	if fileLimit <= 0 {
		return root.ReadFile(path)
	}
	limit := min(fileLimit, remaining)
	if info.Size() > limit || remaining <= 0 {
		return nil, fmt.Errorf("source exceeds %d-byte per-file or %d-byte total audit budget", fileLimit, totalLimit)
	}
	return readRegularEvidence(path, info, limit, root.OpenFile)
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
