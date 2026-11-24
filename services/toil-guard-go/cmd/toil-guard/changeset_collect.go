package main

import (
	"bytes"
	"context"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os/exec"
	"strconv"
	"strings"
	"time"
	"unicode/utf8"
)

// This file ports scripts/git_changeset.py's collector so the default audit
// path consumes the same v1 change-set documents the evidence mode takes,
// produced in-process from the same Git invocations. Any failure here is the
// explicit fallback trigger for the legacy name-only collector.

var diffEvidenceOptions = []string{
	"--raw", "--numstat", "-z", "--patch", "--no-ext-diff", "--no-textconv",
	"--no-color", "--no-relative", "--src-prefix=a/", "--dst-prefix=b/",
	"--find-renames", "--unified=0", "--inter-hunk-context=0", "--submodule=short",
	"--output-indicator-new=+", "--output-indicator-old=-", "--output-indicator-context= ",
}

type changeKey struct{ first, second string }

type parsedChange struct {
	file    changeSetFile
	added   *int
	deleted *int
}

type tokenStream struct {
	tokens [][]byte
	next   int
}

func (stream *tokenStream) pull() ([]byte, error) {
	if stream.next >= len(stream.tokens) {
		return nil, errors.New("unexpected end of Git change output")
	}
	token := stream.tokens[stream.next]
	stream.next++
	return token, nil
}

func localPathRecord(raw string) *changeSetPath {
	if utf8.ValidString(raw) {
		return &changeSetPath{Text: raw}
	}
	return &changeSetPath{RawHex: hex.EncodeToString([]byte(raw))}
}

func parseRawAndCounts(data []byte) (map[changeKey]*parsedChange, []changeKey, error) {
	stream := &tokenStream{tokens: bytes.Split(data, []byte{0})}
	records := map[changeKey]*parsedChange{}
	counts := map[changeKey][2]*int{}
	var order []changeKey
	for stream.next < len(stream.tokens) {
		token := stream.tokens[stream.next]
		stream.next++
		if len(token) == 0 {
			continue
		}
		if token[0] == ':' {
			fields := strings.Split(string(token[1:]), " ")
			if len(fields) != 5 {
				return nil, nil, errors.New("unexpected Git raw record")
			}
			status := fields[4]
			if status == "" || !strings.ContainsRune("ACDMRTUXB", rune(status[0])) {
				return nil, nil, errors.New("unexpected Git path status")
			}
			var score *int
			if len(status) > 1 {
				value, err := strconv.Atoi(status[1:])
				if err != nil {
					return nil, nil, errors.New("unexpected Git path status score")
				}
				score = &value
			}
			first, err := stream.pull()
			if err != nil {
				return nil, nil, err
			}
			second := first
			if status[0] == 'R' || status[0] == 'C' {
				if second, err = stream.pull(); err != nil {
					return nil, nil, err
				}
			}
			change := changeSetFile{Status: status[:1], Score: score, Hunks: []changeSetHunk{}}
			if status[0] != 'A' {
				change.OldPath = localPathRecord(string(first))
			}
			if status[0] != 'D' {
				change.NewPath = localPathRecord(string(second))
			}
			if fields[0] != "000000" {
				change.OldMode = &fields[0]
			}
			if fields[1] != "000000" {
				change.NewMode = &fields[1]
			}
			key := changeKey{string(first), string(second)}
			if _, exists := records[key]; !exists {
				order = append(order, key)
			}
			records[key] = &parsedChange{file: change}
			continue
		}
		fields := strings.SplitN(string(token), "\t", 3)
		if len(fields) != 3 {
			return nil, nil, errors.New("unexpected Git numstat record")
		}
		first, second := fields[2], fields[2]
		if first == "" {
			oldToken, err := stream.pull()
			if err != nil {
				return nil, nil, err
			}
			newToken, err := stream.pull()
			if err != nil {
				return nil, nil, err
			}
			first, second = string(oldToken), string(newToken)
		}
		var pair [2]*int
		if fields[0] == "-" && fields[1] == "-" {
			// Binary: counts stay nil.
		} else {
			added, err := strconv.Atoi(fields[0])
			if err != nil {
				return nil, nil, errors.New("unexpected Git numstat count")
			}
			deleted, err := strconv.Atoi(fields[1])
			if err != nil {
				return nil, nil, errors.New("unexpected Git numstat count")
			}
			pair = [2]*int{&added, &deleted}
		}
		counts[changeKey{first, second}] = pair
	}
	if len(records) != len(counts) {
		return nil, nil, errors.New("Git raw and numstat file records differ")
	}
	for key, record := range records {
		pair, ok := counts[key]
		if !ok {
			return nil, nil, errors.New("Git raw and numstat file records differ")
		}
		record.added, record.deleted = pair[0], pair[1]
		record.file.Added, record.file.Deleted = pair[0], pair[1]
		record.file.Binary = pair[0] == nil
	}
	return records, order, nil
}

func unquoteGitPath(token []byte) ([]byte, error) {
	if len(token) < 2 || token[0] != '"' || token[len(token)-1] != '"' {
		return token, nil
	}
	inner := token[1 : len(token)-1]
	var out []byte
	for i := 0; i < len(inner); i++ {
		if inner[i] != '\\' || i+1 >= len(inner) {
			out = append(out, inner[i])
			continue
		}
		i++
		switch inner[i] {
		case 'n':
			out = append(out, '\n')
		case 't':
			out = append(out, '\t')
		case '\\':
			out = append(out, '\\')
		case '"':
			out = append(out, '"')
		default:
			if inner[i] < '0' || inner[i] > '7' || i+2 >= len(inner) {
				return nil, errors.New("invalid quoted Git path")
			}
			value, err := strconv.ParseUint(string(inner[i:i+3]), 8, 32)
			if err != nil {
				return nil, errors.New("invalid quoted Git path")
			}
			out = append(out, byte(value))
			i += 2
		}
	}
	return out, nil
}

func patchPath(token []byte, prefix string) (*string, error) {
	// Git terminates ---/+++ header names containing a space with a tab.
	token = bytes.TrimSuffix(token, []byte("\t"))
	if string(token) == "/dev/null" {
		return nil, nil
	}
	decoded, err := unquoteGitPath(token)
	if err != nil {
		return nil, err
	}
	if !strings.HasPrefix(string(decoded), prefix) || len(decoded) == 2 {
		return nil, errors.New("unexpected Git patch path prefix")
	}
	value := string(decoded[2:])
	return &value, nil
}

func patchLineRange(token, prefix string) (int, int, error) {
	if !strings.HasPrefix(token, prefix) {
		return 0, 0, errors.New("unexpected Git patch side")
	}
	start, count, found := strings.Cut(token[1:], ",")
	startValue, err := strconv.Atoi(start)
	if err != nil {
		return 0, 0, errors.New("unexpected Git patch range")
	}
	countValue := 1
	if found {
		if countValue, err = strconv.Atoi(count); err != nil {
			return 0, 0, errors.New("unexpected Git patch range")
		}
	}
	return startValue, countValue, nil
}

func parsePatchRanges(patch []byte) (map[changeKey][]changeSetHunk, error) {
	ranges := map[changeKey][]changeSetHunk{}
	var oldPath, newPath *string
	header := false
	for _, line := range bytes.Split(patch, []byte("\n")) {
		switch {
		case bytes.HasPrefix(line, []byte("diff --git ")):
			oldPath, newPath, header = nil, nil, true
		case header && bytes.HasPrefix(line, []byte("--- ")):
			value, err := patchPath(line[4:], "a/")
			if err != nil {
				return nil, err
			}
			oldPath = value
		case header && bytes.HasPrefix(line, []byte("+++ ")):
			value, err := patchPath(line[4:], "b/")
			if err != nil {
				return nil, err
			}
			newPath = value
		case bytes.HasPrefix(line, []byte("@@ ")):
			header = false
			fields := strings.SplitN(string(line), " ", 4)
			if len(fields) != 4 || !strings.HasPrefix(fields[3], "@@") || (oldPath == nil && newPath == nil) {
				return nil, errors.New("unexpected Git patch range")
			}
			oldStart, oldCount, err := patchLineRange(fields[1], "-")
			if err != nil {
				return nil, err
			}
			newStart, newCount, err := patchLineRange(fields[2], "+")
			if err != nil {
				return nil, err
			}
			key := changeKey{}
			if oldPath != nil {
				key.first = *oldPath
			} else {
				key.first = *newPath
			}
			if newPath != nil {
				key.second = *newPath
			} else {
				key.second = *oldPath
			}
			ranges[key] = append(ranges[key], changeSetHunk{
				OldStart: oldStart, OldCount: oldCount, NewStart: newStart, NewCount: newCount,
			})
		}
	}
	return ranges, nil
}

func collectLocalChangeSet(ctx context.Context, root, baseOID, snapshot string) (changeSetEvidence, error) {
	args := []string{"-C", root, "diff"}
	args = append(args, diffEvidenceOptions...)
	if snapshot == "index" {
		args = append(args, "--cached")
	}
	args = append(args, baseOID, "--")
	out, err := readGitOutput(exec.CommandContext(ctx, "git", args...))
	if err != nil {
		return changeSetEvidence{}, fmt.Errorf("collecting %s change set: %w", snapshot, err)
	}
	data, patch, _ := bytes.Cut(out, []byte{0, 0})
	records, order, err := parseRawAndCounts(data)
	if err != nil {
		return changeSetEvidence{}, fmt.Errorf("collecting %s change set: %w", snapshot, err)
	}
	ranges, err := parsePatchRanges(patch)
	if err != nil {
		return changeSetEvidence{}, fmt.Errorf("collecting %s change set: %w", snapshot, err)
	}
	document := changeSetEvidence{
		Version: 1, Snapshot: snapshot, Base: baseOID,
		Files: []changeSetFile{}, Untracked: []changeSetPath{},
	}
	for _, key := range order {
		record := records[key]
		hunks, ok := ranges[key]
		if ok {
			record.file.Hunks = hunks
			delete(ranges, key)
		}
		document.Files = append(document.Files, record.file)
	}
	if len(ranges) != 0 {
		return changeSetEvidence{}, errors.New("Git patch ranges could not be attributed to file changes")
	}
	if snapshot == "worktree" {
		raw, err := readGitOutput(exec.CommandContext(ctx, "git", "-C", root,
			"ls-files", "--others", "--exclude-standard", "-z"))
		if err != nil {
			return changeSetEvidence{}, fmt.Errorf("collecting untracked paths: %w", err)
		}
		for _, item := range strings.Split(string(raw), "\x00") {
			if item != "" {
				document.Untracked = append(document.Untracked, *localPathRecord(item))
			}
		}
	}
	encoded, err := json.Marshal(document)
	if err != nil {
		return changeSetEvidence{}, err
	}
	if err := validateChangeSetEnvelope(encoded, document, snapshot, baseOID); err != nil {
		return changeSetEvidence{}, fmt.Errorf("validating %s change set: %w", snapshot, err)
	}
	return document, nil
}

// collectChangeSetDefaultFiles is the migrated default collector: it feeds
// both locally produced snapshots through the evidence mode's candidate and
// scope pipeline, but keeps the legacy read budgets (0, 0) so previously
// audited large files do not become hard failures.
func collectChangeSetDefaultFiles(base string) (map[string]string, error) {
	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	defer cancel()
	root, oid, err := resolveGitAuditBase(ctx, base)
	if err != nil {
		return nil, err
	}
	var paths []string
	for _, snapshot := range []string{"worktree", "index"} {
		document, err := collectLocalChangeSet(ctx, root, oid, snapshot)
		if err != nil {
			return nil, err
		}
		candidates, err := changeSetCandidatePaths(document)
		if err != nil {
			return nil, fmt.Errorf("%s change set: %w", snapshot, err)
		}
		paths = append(paths, candidates...)
	}
	if len(paths) == 0 {
		return map[string]string{}, nil
	}
	if err := confirmGitCandidateScope(ctx, root, paths); err != nil {
		return nil, err
	}
	return readChangedSources(root, paths, 0, 0)
}

func collectDefaultGitFiles(base string, stderr io.Writer) (map[string]string, error) {
	return collectDefaultGitFilesWith(base, stderr, collectChangeSetDefaultFiles)
}

func collectDefaultGitFilesWith(base string, stderr io.Writer,
	primary func(string) (map[string]string, error)) (map[string]string, error) {
	files, err := primary(base)
	if err == nil {
		return files, nil
	}
	fmt.Fprintf(stderr, "note: change-set collection failed (%v); falling back to the legacy collector\n", err)
	return collectGitDiffFiles(base)
}
