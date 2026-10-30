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
