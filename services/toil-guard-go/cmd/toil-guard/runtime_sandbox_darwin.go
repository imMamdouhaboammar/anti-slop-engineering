package main

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net"
	"os"
	"os/exec"
	"os/user"
	"path/filepath"
	"strconv"
	"strings"
	"syscall"
	"time"
)

const runtimeSandboxProfile = `
(version 1)
(deny default)
(allow file-read*)
(allow sysctl-read)
(allow mach-lookup)
(allow file-write* (literal "/dev/null"))
(allow process-exec (literal (param "worker")))
(deny process-fork)
(deny file-read* (subpath (param "home")) (subpath (param "caller")) (literal (param "readCanary")))
`

const readCanaryText = "runtime isolation canary"

func runSandboxedRuntimeFixture(ctx context.Context) (runtimeEvidence, error) {
	if err := ctx.Err(); err != nil {
		return runtimeEvidence{}, err
	}
	worker, err := canonicalRuntimePath(os.Executable())
	if err != nil {
		return runtimeEvidence{}, fmt.Errorf("locating trusted worker: %w", err)
	}
	account, err := user.Current()
	if err != nil {
		return runtimeEvidence{}, fmt.Errorf("locating account for read isolation: %w", err)
	}
	home, err := canonicalRuntimePath(account.HomeDir, nil)
	if err != nil {
		return runtimeEvidence{}, fmt.Errorf("locating home for read isolation: %w", err)
	}
	caller, err := canonicalRuntimePath(os.Getwd())
	if err != nil {
		return runtimeEvidence{}, fmt.Errorf("locating caller for read isolation: %w", err)
	}
	dir, err := os.MkdirTemp("/private/tmp", "toil-guard-proof-")
	if err != nil {
		return runtimeEvidence{}, fmt.Errorf("creating disposable runtime directory: %w", err)
	}
	defer os.RemoveAll(dir)
	worker, err = prepareRuntimeSandbox(dir, worker)
	if err != nil {
		return runtimeEvidence{}, err
	}
	listener, err := net.Listen("tcp4", "127.0.0.1:0")
	if err != nil {
		return runtimeEvidence{}, fmt.Errorf("creating loopback canary: %w", err)
	}
	defer listener.Close()

	return executeSandboxWorker(ctx, dir, worker, home, caller, listener.Addr().String())
}

func canonicalRuntimePath(path string, err error) (string, error) {
	if err != nil {
		return "", err
	}
	return filepath.EvalSymlinks(path)
}

func prepareRuntimeSandbox(dir, worker string) (string, error) {
	// Use the current executable's trusted bytes, outside the denied home/workspace.
	copyPath := filepath.Join(dir, "fixture-worker")
	if err := copyRuntimeWorker(worker, copyPath); err != nil {
		return "", fmt.Errorf("preparing trusted runtime worker: %w", err)
	}
	readCanary := filepath.Join(dir, "read-canary")
	if err := os.WriteFile(readCanary, []byte(readCanaryText), 0600); err != nil {
		return "", fmt.Errorf("creating filesystem canary: %w", err)
	}
	if data, err := os.ReadFile(readCanary); err != nil || string(data) != readCanaryText {
		return "", errors.New("could not verify the readable filesystem canary before containment")
	}
	writeCanary := filepath.Join(dir, "write-canary")
	if err := os.WriteFile(writeCanary, []byte{}, 0600); err != nil {
		return "", fmt.Errorf("checking writable disposable directory: %w", err)
	}
	if err := os.Remove(writeCanary); err != nil {
		return "", fmt.Errorf("resetting disposable write canary: %w", err)
	}
	return copyPath, nil
}

func copyRuntimeWorker(source, destination string) error {
	reader, err := os.Open(source)
	if err != nil {
		return err
	}
	defer reader.Close()
	info, err := reader.Stat()
	if err != nil {
		return err
	}
	const maximumBinaryBytes = 64 << 20
	if !info.Mode().IsRegular() || info.Size() > maximumBinaryBytes {
		return errors.New("trusted runtime executable exceeds the supported file bounds")
	}

	writer, err := os.OpenFile(destination, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0500)
	if err != nil {
		return err
	}
	written, copyErr := io.Copy(writer, io.LimitReader(reader, maximumBinaryBytes+1))
	if copyErr == nil && written != info.Size() {
		copyErr = errors.New("trusted runtime executable changed during copy")
	}
	return errors.Join(copyErr, writer.Close())
}

func executeSandboxWorker(ctx context.Context, dir, worker, home, caller, loopback string) (runtimeEvidence, error) {
	readCanary := filepath.Join(dir, "read-canary")
	writeCanary := filepath.Join(dir, "write-canary")
	cmd := exec.CommandContext(ctx, "/usr/bin/sandbox-exec", "-p", runtimeSandboxProfile,
		"-D", "worker="+worker, "-D", "home="+home, "-D", "caller="+caller, "-D", "readCanary="+readCanary,
		worker, "_runtime-worker", readCanary, writeCanary, loopback)
	cmd.Dir = dir
	cmd.Env = []string{"GOMAXPROCS=2", "GOMEMLIMIT=32MiB"}
	cmd.WaitDelay = time.Second
	var output cappedRuntimeOutput
	cmd.Stdout, cmd.Stderr = &output, &output
	if err := cmd.Run(); err != nil {
		if contextErr := ctx.Err(); contextErr != nil {
			return runtimeEvidence{}, fmt.Errorf("sandboxed worker did not finish: %w", contextErr)
		}
		return runtimeEvidence{}, fmt.Errorf("sandboxed worker did not provide verifiable evidence: %w", err)
	}
	if _, err := os.Lstat(writeCanary); !errors.Is(err, fs.ErrNotExist) {
		return runtimeEvidence{}, errors.New("filesystem write canary was not absent after the sandboxed worker")
	}
	var evidence runtimeEvidence
	dec := json.NewDecoder(bytes.NewReader(output.Bytes()))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&evidence); err != nil {
		return runtimeEvidence{}, fmt.Errorf("invalid sandbox evidence: %w", err)
	}
	if err := dec.Decode(new(any)); !errors.Is(err, io.EOF) {
		return runtimeEvidence{}, errors.New("unexpected trailing sandbox evidence")
	}
	return evidence, nil
}

type cappedRuntimeOutput struct {
	bytes.Buffer
}

func (b *cappedRuntimeOutput) Write(p []byte) (int, error) {
	const maximumOutputBytes = 8 << 10
	if len(p) > maximumOutputBytes-b.Len() {
		return 0, errors.New("runtime worker exceeded its output budget")
	}
	return b.Buffer.Write(p)
}

func verifyRuntimeIsolation(readCanary, writeCanary, loopback string) (runtimeIsolation, error) {
	if err := validateRuntimeCanaries(readCanary, writeCanary, loopback); err != nil {
		return runtimeIsolation{}, err
	}
	isolation := runtimeIsolation{Sandbox: "macos-sandbox-exec"}
	_, readErr := os.ReadFile(readCanary)
	isolation.ReadCanaryDenied = errors.Is(readErr, fs.ErrPermission)
	if !isolation.ReadCanaryDenied {
		return isolation, nil
	}

	limit := syscall.Rlimit{Cur: runtimeCPULimit, Max: runtimeCPULimit}
	if err := syscall.Setrlimit(syscall.RLIMIT_CPU, &limit); err != nil {
		return runtimeIsolation{}, fmt.Errorf("applying worker CPU limit: %w", err)
	}
	var effective syscall.Rlimit
	if err := syscall.Getrlimit(syscall.RLIMIT_CPU, &effective); err != nil || effective != limit {
		return runtimeIsolation{}, errors.New("could not verify the worker CPU limit")
	}

	writeFile, writeErr := os.OpenFile(writeCanary, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0600)
	if writeErr == nil {
		writeFile.Close()
	}
	connection, connectErr := net.DialTimeout("tcp4", loopback, 200*time.Millisecond)
	if connectErr == nil {
		connection.Close()
	}
	listener, listenErr := net.Listen("tcp4", "127.0.0.1:0")
	if listenErr == nil {
		listener.Close()
	}
	cmd := exec.Command("/usr/bin/true")
	cmd.Stdin, cmd.Stdout, cmd.Stderr = os.Stdin, os.Stdout, os.Stderr
	var forkErr *os.PathError
	childDenied := errors.As(cmd.Run(), &forkErr) && forkErr.Op == "fork/exec" && errors.Is(forkErr, fs.ErrPermission)

	isolation.WritesDenied = errors.Is(writeErr, fs.ErrPermission)
	isolation.NetworkDenied = errors.Is(connectErr, fs.ErrPermission) && errors.Is(listenErr, fs.ErrPermission)
	isolation.ChildProcessDenied = childDenied
	isolation.CPULimitSeconds = int(effective.Max)
	return isolation, nil
}

func validateRuntimeCanaries(readCanary, writeCanary, loopback string) error {
	dir, err := os.Getwd()
	if err != nil {
		return err
	}
	host, port, err := net.SplitHostPort(loopback)
	portNumber, portErr := strconv.ParseUint(port, 10, 16)
	if filepath.Dir(dir) != "/private/tmp" || !strings.HasPrefix(filepath.Base(dir), "toil-guard-proof-") ||
		readCanary != filepath.Join(dir, "read-canary") || writeCanary != filepath.Join(dir, "write-canary") ||
		err != nil || host != "127.0.0.1" || portErr != nil || portNumber == 0 {
		return errors.New("runtime worker requires a disposable parent-created canary directory and IPv4 loopback")
	}
	info, err := os.Lstat(dir)
	if err != nil || !info.IsDir() || info.Mode().Perm() != 0700 {
		return errors.New("runtime canary directory does not have private permissions")
	}
	owner, ok := info.Sys().(*syscall.Stat_t)
	if !ok || int(owner.Uid) != os.Geteuid() {
		return errors.New("runtime canary directory is not owned by the current account")
	}
	return nil
}
