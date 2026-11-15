//go:build !darwin

package main

import (
	"context"
	"errors"
)

func runSandboxedRuntimeFixture(context.Context) (runtimeEvidence, error) {
	return runtimeEvidence{}, errors.New("verified runtime sandbox is available on supported macOS hosts only")
}

func verifyRuntimeIsolation(string, string, string) (runtimeIsolation, error) {
	return runtimeIsolation{}, errors.New("runtime worker requires the verified macOS sandbox")
}
