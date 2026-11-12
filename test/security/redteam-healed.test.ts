import { describe, expect, test } from "bun:test";
import { spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";

const rootDir = resolve(import.meta.dir, "../..");

type SemverTriple = readonly [number, number, number];

interface CommandOutcome {
  status: number | null;
  stdout: string;
  stderr: string;
}

function readRequiredRepoFile(relativePath: string): string {
  const fullPath = resolve(rootDir, relativePath);
  expect(existsSync(fullPath)).toBe(true);
  return readFileSync(fullPath, "utf-8");
}

function getNestedJsonString(rawJson: string, ...keys: string[]): string | undefined {
  let current: unknown = JSON.parse(rawJson);
  for (const key of keys) {
    if (typeof current !== "object" || current === null || Array.isArray(current)) {
      return undefined;
    }
    const found = Object.entries(current).find(([entryKey]) => entryKey === key);
    current = found?.[1];
  }
  return typeof current === "string" ? current : undefined;
}

function parseMinimumSemverPin(constraint: string): SemverTriple | null {
  const match = constraint.trim().match(/^>=(\d+)\.(\d+)\.(\d+)$/);
  if (!match) {
    return null;
  }
  return [Number(match[1]), Number(match[2]), Number(match[3])];
}

function isSemverAtLeast(actual: SemverTriple, minimum: SemverTriple): boolean {
  for (let i = 0; i < 3; i += 1) {
    if (actual[i] > minimum[i]) {
      return true;
    }
    if (actual[i] < minimum[i]) {
      return false;
    }
  }
  return true;
}

function extractThirdPartyActions(workflowContent: string): string[] {
  const actions: string[] = [];
  for (const rawLine of workflowContent.split("\n")) {
    const trimmed = rawLine.trim();
    if (!trimmed || trimmed.startsWith("#")) {
      continue;
    }
    const usesMatch = trimmed.match(/^(?:-\s*)?uses:\s*([^\s#]+)/);
    if (!usesMatch) {
      continue;
    }
    const target = usesMatch[1];
    if (!target.startsWith("./") && !target.startsWith("../")) {
      actions.push(target);
    }
  }
  return actions;
}

function findUnpinnedActions(workflowContent: string): string[] {
  const unpinned: string[] = [];
  const pinnedShaPattern = /^[\w.-]+\/[\w./-]+@[0-9a-f]{40}$/i;
  for (const action of extractThirdPartyActions(workflowContent)) {
    const hasSha = pinnedShaPattern.test(action);
    const hasMutableTag = /@(?:v\d+|main|master|stable|latest)\b/i.test(action);
    if (!hasSha || hasMutableTag) {
      unpinned.push(action);
    }
  }
  return unpinned;
}

function findMutableSlicePointerAntiPatterns(goSource: string): string[] {
  const violations: string[] = [];
  for (const rawLine of goSource.split("\n")) {
    const trimmed = rawLine.trim();
    if (!trimmed || trimmed.startsWith("//")) {
      continue;
    }
    if (/\*\[\]\s*[\w.]+\b/.test(trimmed) || /\*\w+\s*=\s*append\s*\(/.test(trimmed)) {
      violations.push(trimmed);
    }
  }
  return violations;
}

function runPythonSnippet(code: string): CommandOutcome {
  const res = spawnSync("python3", ["-c", code], {
    cwd: rootDir,
    encoding: "utf-8",
  });
  return { status: res.status, stdout: res.stdout, stderr: res.stderr };
}

function runSecurityAuditWithFakeScanner(scannerJson: string, exitCode: number): CommandOutcome {
  const tempDir = mkdtempSync(join(tmpdir(), "anti-slop-sec-test-"));
  try {
    const binPath = join(tempDir, "fake-osv-scanner");
    const payloadPath = join(tempDir, "payload.json");
    writeFileSync(payloadPath, scannerJson, "utf-8");
    writeFileSync(binPath, `#!/bin/sh\ncat "${payloadPath}"\nexit ${exitCode}\n`, "utf-8");
    chmodSync(binPath, 0o755);

    const res = spawnSync(process.execPath, ["run", "scripts/security-audit.ts"], {
      cwd: rootDir,
      encoding: "utf-8",
      env: { ...process.env, OSV_SCANNER_BIN: binPath },
    });
    return { status: res.status, stdout: res.stdout, stderr: res.stderr };
  } finally {
    rmSync(tempDir, { recursive: true, force: true });
  }
}

describe("Fable & Bug Killer Security Healing Regression Suite", () => {
  test("CVE-2026-111497 (Node2Shell): package.json engines enforce safe minimum pins and reject unsafe ranges", () => {
    const rawPkg = readRequiredRepoFile("package.json");
    const nodeSpec = getNestedJsonString(rawPkg, "engines", "node") ?? "";
    const bunSpec = getNestedJsonString(rawPkg, "engines", "bun") ?? "";

    const nodePin = parseMinimumSemverPin(nodeSpec);
    const bunPin = parseMinimumSemverPin(bunSpec);

    expect(nodePin !== null && isSemverAtLeast(nodePin, [22, 23, 4])).toBe(true);
    expect(bunPin !== null && isSemverAtLeast(bunPin, [1, 0, 0])).toBe(true);

    // Negative mutation checks: downgraded or wildcard engine ranges must be rejected
    const vulnerableNode = parseMinimumSemverPin(">=18.0.0");
    expect(vulnerableNode !== null && isSemverAtLeast(vulnerableNode, [22, 23, 4])).toBe(false);
    const offByOneNode = parseMinimumSemverPin(">=22.23.3");
    expect(offByOneNode !== null && isSemverAtLeast(offByOneNode, [22, 23, 4])).toBe(false);
    expect(parseMinimumSemverPin("*")).toBeNull();
    expect(parseMinimumSemverPin(">=22.23.4 || >=18.0.0")).toBeNull();
  });

  test("BK-AI-CIC-003: third-party GitHub Actions in ci.yml and security-audit.yml are SHA-pinned and CI runs test:security", () => {
    const ciContent = readRequiredRepoFile(".github/workflows/ci.yml");
    const secAuditContent = readRequiredRepoFile(".github/workflows/security-audit.yml");

    expect(extractThirdPartyActions(ciContent).length).toBeGreaterThan(0);
    expect(extractThirdPartyActions(secAuditContent).length).toBeGreaterThan(0);
    expect(findUnpinnedActions(ciContent)).toEqual([]);
    expect(findUnpinnedActions(secAuditContent)).toEqual([]);

    // Negative mutation checks: mutable tags on both `uses:` and `- uses:` list steps must fail
    const mutatedListStep = ciContent.replace(
      /- uses:\s+actions\/checkout@[0-9a-f]{40}/i,
      "- uses: actions/checkout@v7",
    );
    expect(findUnpinnedActions(mutatedListStep)).toEqual(["actions/checkout@v7"]);

    const mutatedMapStep = ciContent.replace(
      /uses:\s+oven-sh\/setup-bun@[0-9a-f]{40}/i,
      "uses: oven-sh/setup-bun@main",
    );
    expect(findUnpinnedActions(mutatedMapStep)).toEqual(["oven-sh/setup-bun@main"]);

    // Verify CI and package.json wire the Bun security suite
    const rawPkg = readRequiredRepoFile("package.json");
    expect(getNestedJsonString(rawPkg, "scripts", "test:security")).toBe(
      "bun test test/security/redteam-healed.test.ts",
    );
    expect(ciContent).toMatch(/bun run test:security|bun test test\/security\/redteam-healed\.test\.ts/);
  });

  test("BK-AI-MEM-004: toil-guard-go pkg/sre avoids mutable slice pointer dereferences", () => {
    const sreFiles = [
      "services/toil-guard-go/pkg/sre/complexity.go",
      "services/toil-guard-go/pkg/sre/dry.go",
      "services/toil-guard-go/pkg/sre/toil.go",
    ];

    for (const file of sreFiles) {
      const source = readRequiredRepoFile(file);
      expect(findMutableSlicePointerAntiPatterns(source)).toEqual([]);
    }

    const complexitySource = readRequiredRepoFile("services/toil-guard-go/pkg/sre/complexity.go");
    expect(complexitySource).toMatch(/func\s+\([^)]+\)\s+processLine\([^)]*\)\s+\*model\.Finding\b/);

    // Negative mutation check: re-introducing mutable slice pointer dereference must be caught
    const mutatedGo = "func (t *funcTracker) processLine(out *[]model.Finding) {\n  *out = append(*out, f)\n}";
    expect(findMutableSlicePointerAntiPatterns(mutatedGo).length).toBe(2);
  });

  test("BK-AI-DOS-001: decision_guard.py enforces depth-bounded finding recording and rejects malformed inputs", () => {
    readRequiredRepoFile("scripts/decision_guard.py");

    const boundCheck = runPythonSnippet(
      [
        "import json",
        "from scripts import decision_guard",
        "within = []",
        "decision_guard._record_finding(within, False, 'E_OK', 'ok', 100, 100)",
        "over = []",
        "decision_guard._record_finding(over, False, 'E_DEEP', 'too deep', 101, 100)",
        "print(json.dumps({'within': len(within), 'over': len(over)}))",
      ].join("\n"),
    );
    expect(boundCheck.status).toBe(0);
    expect(JSON.parse(boundCheck.stdout)).toEqual({ within: 1, over: 0 });

    const validCli = spawnSync(
      "python3",
      ["scripts/decision_guard.py", "audit", "skills/decision-guard/examples/architecture-record.json", "--json"],
      { cwd: rootDir, encoding: "utf-8" },
    );
    expect(validCli.status).toBe(0);
    expect(getNestedJsonString(validCli.stdout, "record_status")).toBe("complete");

    const tempDir = mkdtempSync(join(tmpdir(), "anti-slop-decision-test-"));
    try {
      const badJsonPath = join(tempDir, "non-object.json");
      writeFileSync(badJsonPath, "[]", "utf-8");
      const badCli = spawnSync(
        "python3",
        ["scripts/decision_guard.py", "audit", badJsonPath, "--json"],
        { cwd: rootDir, encoding: "utf-8" },
      );
      expect(badCli.status).toBe(1);
      expect(badCli.stderr).toContain("decision record must be an object");
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  test("BK-AI-SEC-005: security-audit.ts fails closed on HIGH or unrated OSV advisories", () => {
    readRequiredRepoFile("scripts/security-audit.ts");

    const cleanResult = runSecurityAuditWithFakeScanner(JSON.stringify({ results: [] }), 0);
    expect(cleanResult.status).toBe(0);

    const highVulnReport = JSON.stringify({
      results: [
        {
          packages: [
            {
              package: { name: "example-pkg", version: "1.0.0" },
              vulnerabilities: [
                { id: "GHSA-test-high", database_specific: { severity: "HIGH" } },
              ],
            },
          ],
        },
      ],
    });
    const highResult = runSecurityAuditWithFakeScanner(highVulnReport, 1);
    expect(highResult.status).toBe(1);
    expect(highResult.stderr).toContain("High or Critical vulnerabilities detected");

    const unratedVectorReport = JSON.stringify({
      results: [
        {
          packages: [
            {
              package: { name: "example-pkg", version: "1.0.0" },
              vulnerabilities: [
                {
                  id: "GHSA-test-unrated",
                  severity: [{ type: "CVSS_V3", score: "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H" }],
                },
              ],
            },
          ],
        },
      ],
    });
    const unratedResult = runSecurityAuditWithFakeScanner(unratedVectorReport, 1);
    expect(unratedResult.status).toBe(1);
    expect(unratedResult.stderr).toContain("advisory severity could not be verified");
  });
});
