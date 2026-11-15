package main

import (
	"bytes"
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"strings"
	"time"
	"unicode/utf8"
)

const (
	maxEvidenceBytes       = 8 << 20
	maxEvidenceFileBytes   = 2 << 20
	maxEvidenceSourceBytes = 32 << 20
	maxEvidencePaths       = 10000
)

type changeSetEvidence struct {
	Version   int             `json:"version"`
	Snapshot  string          `json:"snapshot"`
	Base      string          `json:"base"`
	Target    *string         `json:"target"`
	Files     []changeSetFile `json:"files"`
	Untracked []changeSetPath `json:"untracked"`
}

type changeSetFile struct {
	Status  string         `json:"status"`
	OldPath *changeSetPath `json:"old_path"`
	NewPath *changeSetPath `json:"new_path"`
	NewMode *string        `json:"new_mode"`
}

type changeSetPath struct {
	Text   string `json:"text"`
	RawHex string `json:"raw_hex"`
}

func changeSetPathValue(record *changeSetPath) (string, error) {
	if record == nil || (record.Text == "") == (record.RawHex == "") {
		return "", errors.New("Git path needs exactly one text or raw_hex representation")
	}
	if record.Text != "" {
		return validateChangeSetPath(record.Text)
	}
	raw, err := hex.DecodeString(record.RawHex)
	if err != nil || len(raw) == 0 || utf8.Valid(raw) {
		return "", errors.New("invalid raw_hex Git path representation")
	}
	return validateChangeSetPath(string(raw))
}

func validateChangeSetPath(name string) (string, error) {
	if name == "" || name == "." || strings.ContainsRune(name, 0) || path.Clean(name) != name ||
		strings.HasPrefix(name, "../") || name == ".." || path.IsAbs(name) || !filepath.IsLocal(filepath.FromSlash(name)) {
		return "", fmt.Errorf("invalid repository-relative path %q", name)
	}
	for part := range strings.SplitSeq(name, "/") {
		if strings.EqualFold(part, ".git") {
			return "", fmt.Errorf("invalid repository-relative path %q", name)
		}
	}
	return name, nil
}

func readChangeSetDocument(file, snapshot, resolvedBase string) (changeSetEvidence, error) {
	var record changeSetEvidence
	stat, err := os.Lstat(file)
	if err != nil {
		return record, err
	}
	if !stat.Mode().IsRegular() || stat.Size() > maxEvidenceBytes {
		return record, errors.New("Git change evidence must be a regular file under the 8 MiB limit")
	}
	data, err := readRegularEvidence(file, stat, maxEvidenceBytes, os.OpenFile)
	if err != nil {
		return record, err
	}
	if !utf8.Valid(data) {
		return record, errors.New("Git change evidence is not valid JSON text")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	if err := decoder.Decode(&record); err != nil {
		return record, fmt.Errorf("invalid Git change evidence: %w", err)
	}
	if err := decoder.Decode(new(any)); !errors.Is(err, io.EOF) {
		return record, errors.New("unexpected trailing Git change evidence")
	}
	if err := validateChangeSetEnvelope(data, record, snapshot, resolvedBase); err != nil {
		return record, err
	}
	return record, nil
}

var errEvidenceFileChanged = errors.New("evidence or source file changed before it could be read")

func readRegularEvidence(path string, original os.FileInfo, limit int64, open func(string, int, os.FileMode) (*os.File, error)) ([]byte, error) {
	file, err := open(path, os.O_RDONLY|evidenceOpenFlags, 0)
	if err != nil {
		return nil, err
	}
	defer file.Close()
	actual, err := file.Stat()
	if err != nil {
		return nil, err
	}
	if !actual.Mode().IsRegular() || !os.SameFile(original, actual) {
		return nil, errEvidenceFileChanged
	}
	data, err := io.ReadAll(io.LimitReader(file, limit+1))
	if int64(len(data)) > limit {
		return nil, errors.New("file content exceeded the read budget")
	}
	return data, err
}

func validateChangeSetEnvelope(data []byte, record changeSetEvidence, snapshot, resolvedBase string) error {
	if record.Version != 1 {
		return errors.New("unsupported Git change evidence version")
	}
	if record.Snapshot != snapshot {
		return fmt.Errorf("expected %s snapshot", snapshot)
	}
	if record.Base != resolvedBase {
		return errors.New("Git change evidence base does not match the resolved Git base")
	}
	var envelope map[string]json.RawMessage
	if err := json.Unmarshal(data, &envelope); err != nil {
		return err
	}
	if record.Target != nil || !bytes.Equal(envelope["target"], []byte("null")) {
		return errors.New("worktree and index snapshot target must be null")
	}
	if record.Files == nil || record.Untracked == nil || len(record.Files)+len(record.Untracked) > maxEvidencePaths {
		return errors.New("Git change evidence must include bounded files and untracked arrays")
	}
	if snapshot == "index" && len(record.Untracked) != 0 {
		return errors.New("Git index snapshot must have no untracked paths")
	}
	return nil
}

func candidateFromChange(change changeSetFile) (string, error) {
	if len(change.Status) != 1 || !strings.Contains("ACDMRTUXB", change.Status) {
		return "", errors.New("invalid Git change status")
	}
	if (change.OldPath == nil) != (change.Status == "A") || (change.NewPath == nil) != (change.Status == "D") {
		return "", errors.New("Git change paths do not match the declared status")
	}
	if change.OldPath != nil {
		if _, err := changeSetPathValue(change.OldPath); err != nil {
			return "", err
		}
	}
	if change.NewPath == nil {
		return "", nil
	}
	name, err := changeSetPathValue(change.NewPath)
	if err != nil {
		return "", err
	}
	if change.NewMode != nil {
		switch *change.NewMode {
		case "100644", "100755", "120000", "160000":
		default:
			return "", errors.New("invalid Git change destination mode")
		}
	}
	return name, nil
}

func changeSetCandidatePaths(record changeSetEvidence) ([]string, error) {
	paths := make([]string, 0, len(record.Files)+len(record.Untracked))
	for _, change := range record.Files {
		name, err := candidateFromChange(change)
		if err != nil {
			return nil, err
		}
		if name != "" && isAuditable(name) && !isDocFile(name) {
			paths = append(paths, name)
		}
	}
	for _, item := range record.Untracked {
		name, err := changeSetPathValue(&item)
		if err != nil {
			return nil, err
		}
		if isAuditable(name) && !isDocFile(name) {
			paths = append(paths, name)
		}
	}
	return paths, nil
}

func collectChangeSetSources(base, worktreeFile, indexFile string) (map[string]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	root, oid, err := resolveGitAuditBase(ctx, base)
	if err != nil {
		return nil, err
	}
	var paths []string
	for _, evidence := range []struct{ file, snapshot string }{{worktreeFile, "worktree"}, {indexFile, "index"}} {
		document, err := readChangeSetDocument(evidence.file, evidence.snapshot, oid)
		if err != nil {
			return nil, fmt.Errorf("%s evidence: %w", evidence.snapshot, err)
		}
		candidates, err := changeSetCandidatePaths(document)
		if err != nil {
			return nil, fmt.Errorf("%s evidence: %w", evidence.snapshot, err)
		}
		paths = append(paths, candidates...)
	}
	if len(paths) == 0 {
		return map[string]string{}, nil
	}
	if err := confirmGitCandidateScope(ctx, root, paths); err != nil {
		return nil, err
	}
	return readChangedSources(root, paths, maxEvidenceFileBytes, maxEvidenceSourceBytes)
}

func confirmGitCandidateScope(ctx context.Context, root string, paths []string) error {
	repoRoot, err := os.OpenRoot(root)
	if err != nil {
		return err
	}
	defer repoRoot.Close()

	wanted := make(map[string]bool, len(paths))
	for _, name := range paths {
		wanted[name] = false
	}
	cmd := exec.CommandContext(ctx, "git", "-C", root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
	out, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	if err := cmd.Start(); err != nil {
		return err
	}
	data, readErr := io.ReadAll(io.LimitReader(out, maxEvidenceBytes+1))
	if len(data) > maxEvidenceBytes || readErr != nil {
		out.Close()
	}
	waitErr := cmd.Wait()
	if readErr != nil {
		return readErr
	}
	if len(data) > maxEvidenceBytes {
		return errors.New("Git candidate membership exceeded the 8 MiB path budget")
	}
	if waitErr != nil {
		return fmt.Errorf("validating Git file scope: %w", waitErr)
	}
	names, err := parseGitPaths(string(data))
	if err != nil {
		return err
	}
	for _, name := range names {
		if _, required := wanted[name]; required {
			wanted[name] = true
		}
	}
	for _, name := range paths {
		if wanted[name] {
			continue
		}
		if _, err := repoRoot.Lstat(name); errors.Is(err, os.ErrNotExist) {
			continue
		}
		return fmt.Errorf("candidate %q is outside tracked or non-ignored untracked Git scope", name)
	}
	return nil
}
