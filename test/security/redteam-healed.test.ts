import { describe, expect, test } from "bun:test";
import { readFileSync, existsSync } from "node:fs";
import { resolve } from "node:path";

const rootDir = resolve(import.meta.dir, "../..");

describe("Fable & Bug Killer Security Healing Regression Suite", () => {
  test("CVE-2026-111497 (Node2Shell): package.json engines are safely pinned", () => {
    const pkgPath = resolve(rootDir, "package.json");
    expect(existsSync(pkgPath)).toBe(true);

    const pkg = JSON.parse(readFileSync(pkgPath, "utf-8"));
    expect(pkg.engines).toBeDefined();
    expect(pkg.engines.node).toBe(">=22.23.4");
    expect(pkg.engines.bun).toBe(">=1.0.0");
  });

  test("BK-AI-CIC-003: All third-party GitHub Actions in ci.yml are pinned to immutable 40-char commit SHAs", () => {
    const ciPath = resolve(rootDir, ".github/workflows/ci.yml");
    expect(existsSync(ciPath)).toBe(true);

    const ciContent = readFileSync(ciPath, "utf-8");
    const actionLines = ciContent
      .split("\n")
      .map((line) => line.trim())
      .filter((line) => line.startsWith("uses:") && !line.includes("./"));

    expect(actionLines.length).toBeGreaterThan(0);

    const shaPattern = /uses:\s+[\w\-./]+@[0-9a-f]{40}/i;
    for (const actionLine of actionLines) {
      expect(actionLine).toMatch(shaPattern);
      // Ensure no mutable tags (e.g. @v4, @v5, @main, @master, @stable without SHA)
      expect(actionLine).not.toMatch(/@v\d+\b/);
      expect(actionLine).not.toMatch(/@(main|master|stable)\b/);
    }
  });

  test("BK-AI-MEM-004: services/toil-guard-go eliminates mutable slice pointer dereferences in complexity.go", () => {
    const complexityPath = resolve(rootDir, "services/toil-guard-go/pkg/sre/complexity.go");
    expect(existsSync(complexityPath)).toBe(true);

    const content = readFileSync(complexityPath, "utf-8");
    // Assert processLine returns *model.Finding instead of taking out *[]model.Finding
    expect(content).toContain("func (t *funcTracker) processLine(filePath string, lineNo int, line, trimmed string) *model.Finding");
    expect(content).not.toContain("out *[]model.Finding");
    expect(content).not.toContain("*out = append");
  });

  test("BK-AI-DOS-001: decision_guard.py enforces explicit depth-bounded validation recording", () => {
    const decisionPath = resolve(rootDir, "scripts/decision_guard.py");
    expect(existsSync(decisionPath)).toBe(true);

    const content = readFileSync(decisionPath, "utf-8");
    expect(content).toContain("def _record_finding(findings, condition, code, message, depth=0, max_depth=100):");
    expect(content).toContain("if depth > max_depth:");
  });

  test("BK-AI-WEB-003: teardown.mjs uses parser-based HTML extraction instead of naive regex tag stripping", () => {
    const teardownPath = resolve(rootDir, ".agents/skills/reverse-engineer-marketing/scripts/teardown.mjs");
    if (existsSync(teardownPath)) {
      const content = readFileSync(teardownPath, "utf-8");
      expect(content).toContain("const parseHtmlText = (html) =>");
      expect(content).not.toContain("html.replace(/<[^>]+>/g, ' ')");
    }
  });
});
