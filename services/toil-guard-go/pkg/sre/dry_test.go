package sre

import (
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

func TestCheckDRYDuplicates_Found(t *testing.T) {
	fileA := `
package a
func SetupA() {
    config := loadConfig()
    client := initClient(config)
    token := client.Authenticate()
    session := createSession(token)
    log.Println(session)
}
`
	fileB := `
package b
func SetupB() {
    config := loadConfig()
    client := initClient(config)
    token := client.Authenticate()
    session := createSession(token)
    log.Println(session)
}
`
	files := map[string]string{
		"a.go": fileA,
		"b.go": fileB,
	}

	findings := CheckDRYDuplicates(files)
	if len(findings) == 0 {
		t.Fatalf("expected DRY duplicate finding, got 0")
	}

	found := false
	for _, f := range findings {
		if f.Code == "SRE-DRY-DUPLICATE" && f.Category == model.CategoryDRY {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-DRY-DUPLICATE finding")
	}
}


func TestIsTestFileDoesNotExcludeProductionPaths(t *testing.T) {
    if IsTestFile("src/latest_release.py") || IsTestFile("src/contest_utils.go") {
        t.Fatal("production source files were classified as tests")
    }
    if !IsTestFile("src/test_feature.py") {
        t.Fatal("test file prefix was not recognized")
    }
}

func TestQuotedMappingsAreRetained(t *testing.T) {
    if isIgnoredLine(`"role": "admin"`) {
        t.Fatal("mapping entry must not be removed during normalization")
    }
}

func TestDRYAttributionIsDeterministic(t *testing.T) {
    content := "a()\nb()\nc()\nd()\n"
    for i := 0; i < 20; i++ {
        findings := CheckDRYDuplicates(map[string]string{"b.go": content, "a.go": content})
        if len(findings) == 0 || findings[0].File != "b.go" {
            t.Fatalf("unexpected duplicate attribution: %+v", findings)
        }
    }
}

func TestDRYSameFileIgnoresBlankLinesInOverlapCalculation(t *testing.T) {
    code := "alpha()\nbeta()\ngamma()\ndelta()\n// spacer\nfoo()\nbar()\nalpha()\nbeta()\ngamma()\ndelta()"
    findings := CheckDRYDuplicates(map[string]string{"src/code.go": code})
    if len(findings) == 0 {
        t.Fatal("expected nonoverlapping duplicate in same source file")
    }
}
