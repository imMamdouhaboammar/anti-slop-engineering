package sre

import (
	"testing"

	"github.com/imMamdouhaboammar/anti-slop-engineering/services/toil-guard-go/pkg/model"
)

func TestCheckToilAndScale_BlindSleep(t *testing.T) {
	code := `
func WaitForWorker() {
    time.Sleep(5 * time.Second)
}
`
	findings := CheckToilAndScale("worker.go", code)
	if len(findings) == 0 {
		t.Fatalf("expected blind sleep finding, got 0")
	}

	found := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SLEEP" && f.Severity == model.SeverityBlocker {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-SCALE-SLEEP blocker finding")
	}
}

func TestCheckToilAndScale_SwallowedError(t *testing.T) {
	code := `
func IgnoreFailures() {
    if err != nil { }
}
`
	findings := CheckToilAndScale("err.go", code)
	if len(findings) == 0 {
		t.Fatalf("expected error swallow finding, got 0")
	}

	found := false
	for _, f := range findings {
		if f.Code == "SRE-SCALE-SWALLOW" && f.Severity == model.SeverityBlocker {
			found = true
			break
		}
	}
	if !found {
		t.Errorf("expected SRE-SCALE-SWALLOW finding")
	}
}

func swallowLines(file, content string) []int {
	var lines []int
	for _, f := range CheckToilAndScale(file, content) {
		if f.Code == "SRE-SCALE-SWALLOW" {
			lines = append(lines, f.Line)
		}
	}
	return lines
}

func TestCheckToilAndScale_MultilineCatchTS(t *testing.T) {
	content := "try {\n  work();\n} catch (e) {\n}\n"
	if got := swallowLines("app.ts", content); len(got) != 1 || got[0] != 3 {
		t.Fatalf("expected one swallow finding at line 3, got %v", got)
	}
}

func TestCheckToilAndScale_MultilinePythonExcept(t *testing.T) {
	content := "try:\n    work()\nexcept Exception:\n    pass\n"
	if got := swallowLines("worker.py", content); len(got) != 1 || got[0] != 3 {
		t.Fatalf("expected one swallow finding at line 3, got %v", got)
	}
}

func TestCheckToilAndScale_MultilineNonemptyHandlers(t *testing.T) {
	if got := swallowLines("app.ts", "try {\n  work();\n} catch (e) {\n  console.error(e);\n}\n"); len(got) != 0 {
		t.Fatalf("expected no findings for nonempty catch, got %v", got)
	}
	if got := swallowLines("worker.py", "try:\n    work()\nexcept Exception:\n    log_failure()\n"); len(got) != 0 {
		t.Fatalf("expected no findings for nonempty suite, got %v", got)
	}
}

func TestCheckToilAndScale_LiteralContentsNotFlagged(t *testing.T) {
	if got := swallowLines("tpl.ts", "const tpl = `\n} catch (e) {\n}\n`;\n"); len(got) != 0 {
		t.Fatalf("expected no findings inside template literal, got %v", got)
	}
	if got := swallowLines("doc.py", "message = \"\"\"\nexcept Exception:\n    pass\n\"\"\"\n"); len(got) != 0 {
		t.Fatalf("expected no findings inside triple-quoted string, got %v", got)
	}
}

func TestCheckToilAndScale_PythonDocumentedIgnore(t *testing.T) {
	content := "try:\n    work()\nexcept Exception:\n    # intentional: best-effort cleanup\n    pass\n"
	if got := swallowLines("worker.py", content); len(got) != 0 {
		t.Fatalf("expected no findings for documented ignore, got %v", got)
	}
}

func TestCheckToilAndScale_UnparseableGoFallback(t *testing.T) {
	content := "package main\n\nfunc f() error {\n\terr := doWork()\n\tif err != nil {\n\t}\n\treturn nil\n}\n\nfunc broken( {\n"
	if got := swallowLines("main.go", content); len(got) != 1 || got[0] != 5 {
		t.Fatalf("expected one swallow finding at line 5, got %v", got)
	}
}

func TestCheckToilAndScale_BraceOpeningAndBlockCommentIgnores(t *testing.T) {
	cases := []struct {
		name    string
		file    string
		content string
	}{
		{
			name:    "ts opening line comment",
			file:    "app.ts",
			content: "try {\n  work();\n} catch (e) { // intentional\n}\n",
		},
		{
			name:    "ts inline block comment",
			file:    "app.ts",
			content: "try {\n  work();\n} catch (e) { /* intentional */ }\n",
		},
		{
			name:    "ts multiline block comment",
			file:    "app.ts",
			content: "try {\n  work();\n} catch (e) {\n/*\n * intentional: best-effort cleanup\n */\n}\n",
		},
		{
			name:    "go fallback opening line comment",
			file:    "main.go",
			content: "package main\nfunc f() {\n\tif err != nil { // expected\n\t}\n}\nfunc broken( {\n",
		},
		{
			name:    "go fallback inline block comment",
			file:    "main.go",
			content: "package main\nfunc f() {\n\tif err != nil { /* expected */ }\n}\nfunc broken( {\n",
		},
	}
	for _, tc := range cases {
		if got := swallowLines(tc.file, tc.content); len(got) != 0 {
			t.Errorf("%s: expected no findings, got %v", tc.name, got)
		}
	}
}

func TestCheckToilAndScale_BraceCommentOutsideDoesNotExempt(t *testing.T) {
	before := "try {\n  work();\n/* intentional */ } catch (e) {\n}\n"
	if got := swallowLines("app.ts", before); len(got) != 1 || got[0] != 3 {
		t.Fatalf("expected finding at line 3, got %v", got)
	}
	unrelated := "try {\n  work();\n} catch (e) { /* todo */ }\n"
	if got := swallowLines("app.ts", unrelated); len(got) != 1 || got[0] != 3 {
		t.Fatalf("expected finding at line 3, got %v", got)
	}
}

func TestCheckToilAndScale_CRLFMultilineHandlers(t *testing.T) {
	ts := "try {\r\n  work();\r\n} catch (e) {\r\n}\r\n"
	if got := swallowLines("app.ts", ts); len(got) != 1 || got[0] != 3 {
		t.Fatalf("expected CRLF catch finding at line 3, got %v", got)
	}
	goFallback := "package main\r\nfunc f() {\r\n\tif err != nil {\r\n\t}\r\n}\r\nfunc broken( {\r\n"
	if got := swallowLines("main.go", goFallback); len(got) != 1 || got[0] != 3 {
		t.Fatalf("expected CRLF Go fallback finding at line 3, got %v", got)
	}
}
