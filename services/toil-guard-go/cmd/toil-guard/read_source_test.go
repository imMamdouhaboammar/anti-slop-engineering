package main

import (
	"os"
	"path/filepath"
	"testing"
)

func TestReadRegularSourceRequiresOriginalFile(t *testing.T) {
	dir := t.TempDir()
	const expectedSource = "package testfixture\n"
	expectedPath := filepath.Join(dir, "expected.go")
	otherPath := filepath.Join(dir, "other.go")
	for _, path := range []string{expectedPath, otherPath} {
		if err := os.WriteFile(path, []byte(expectedSource), 0600); err != nil {
			t.Fatal(err)
		}
	}
	expectedFile, err := os.Open(expectedPath)
	if err != nil {
		t.Fatal(err)
	}
	defer expectedFile.Close()
	expectedInfo, err := expectedFile.Stat()
	if err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		name    string
		path    string
		limit   int64
		wantErr bool
	}{
		{name: "expected source", path: expectedPath, limit: -1},
		{name: "different source", path: otherPath, limit: -1, wantErr: true},
		{name: "file within limit", path: expectedPath, limit: int64(len(expectedSource))},
		{name: "file exceeding limit", path: expectedPath, limit: int64(len(expectedSource) - 1), wantErr: true},
	} {
		t.Run(test.name, func(t *testing.T) {
			file, err := os.Open(test.path)
			if err != nil {
				t.Fatal(err)
			}
			defer file.Close()
			got, err := readRegularSource(file, expectedInfo, test.limit)
			if test.wantErr {
				if err == nil || got != nil {
					t.Fatalf("expected rejection: got %q, error %v", got, err)
				}
			} else if err != nil || string(got) != expectedSource {
				t.Fatalf("expected file: got %q, error %v", got, err)
			}
		})
	}
}
