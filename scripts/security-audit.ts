import { spawnSync } from "node:child_process";

interface OsvSeverity {
  score?: unknown;
}

interface OsvVulnerability {
  id?: unknown;
  database_specific?: { severity?: unknown };
  ecosystem_specific?: { severity?: unknown };
  severity?: OsvSeverity[];
}

interface OsvPackage {
  package?: { name?: unknown; version?: unknown };
  vulnerabilities?: OsvVulnerability[];
}

interface OsvResult {
  packages?: OsvPackage[];
}

interface AuditFinding {
  id: string;
  packageName: string;
  version: string;
  label: string;
  isHighOrCritical: boolean;
  severityKnown: boolean;
}

const KNOWN_LOWER_SEVERITIES = new Set(["LOW", "MODERATE", "MEDIUM", "NEGLIGIBLE", "INFO", "INFORMATIONAL"]);
const HIGH_SEVERITIES = new Set(["HIGH", "CRITICAL"]);

function objectRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === "string" && value.trim().length > 0;
}

function parseReport(output: string): OsvResult[] {
  const jsonStart = output.indexOf("{");
  const jsonEnd = output.lastIndexOf("}");
  if (jsonStart < 0 || jsonEnd < jsonStart) {
    throw new Error("OSV scanner did not return a valid JSON report");
  }

  const parsed: unknown = JSON.parse(output.slice(jsonStart, jsonEnd + 1));
  if (!objectRecord(parsed) || !Array.isArray(parsed.results)) {
    throw new Error("OSV scanner report is missing a valid results array");
  }

  for (const result of parsed.results) {
    if (!objectRecord(result) || !Array.isArray(result.packages)) {
      throw new Error("OSV scanner report contains a malformed result");
    }
    for (const pkg of result.packages) {
      if (!objectRecord(pkg) || !objectRecord(pkg.package) ||
          !nonEmptyString(pkg.package.name) || !nonEmptyString(pkg.package.version) ||
          !Array.isArray(pkg.vulnerabilities)) {
        throw new Error("OSV scanner report contains a malformed package");
      }
      for (const vuln of pkg.vulnerabilities) {
        if (!objectRecord(vuln) || !nonEmptyString(vuln.id)) {
          throw new Error("OSV scanner report contains a malformed vulnerability");
        }
        for (const detail of [vuln.database_specific, vuln.ecosystem_specific]) {
          if (detail !== undefined && (!objectRecord(detail) ||
              ("severity" in detail && !nonEmptyString(detail.severity)))) {
            throw new Error("OSV scanner report contains malformed severity metadata");
          }
        }
        if (vuln.severity !== undefined && (!Array.isArray(vuln.severity) ||
            !vuln.severity.every((entry: unknown) => objectRecord(entry) && nonEmptyString(entry.type) && nonEmptyString(entry.score)))) {
          throw new Error("OSV scanner report contains malformed CVSS severity data");
        }
      }
    }
  }

  return parsed.results as OsvResult[];
}

function describeVulnerability(vuln: OsvVulnerability, pkg: OsvPackage): AuditFinding {
  const labels = [vuln.database_specific?.severity, vuln.ecosystem_specific?.severity]
    .filter(nonEmptyString)
    .map((value) => value.trim().toUpperCase());

  const scores = (vuln.severity || []).map((entry) => {
    const raw = entry.score;
    if (typeof raw !== "string" || !/^(?:10(?:\.0+)?|[0-9](?:\.\d+)?)$/.test(raw.trim())) {
      return Number.NaN;
    }
    return Number(raw.trim());
  });
  const validScores = scores.filter((score) => Number.isFinite(score) && score >= 0 && score <= 10);
  const everyLabelKnown = labels.every((label) => HIGH_SEVERITIES.has(label) || KNOWN_LOWER_SEVERITIES.has(label));
  // OSV also returns CVSS vector strings. Until scored by a trusted parser, require review
  // even if a separate advisory label says LOW, so an unparsed vector cannot hide a HIGH score.
  const everyScoreKnown = validScores.length === scores.length;
  const highLabel = labels.find((label) => HIGH_SEVERITIES.has(label));

  return {
    id: vuln.id as string,
    packageName: pkg.package?.name as string,
    version: pkg.package?.version as string,
    label: highLabel || labels[0] || (validScores.length > 0 ? "CVSS" : "UNRATED"),
    isHighOrCritical: Boolean(highLabel) || validScores.some((score) => score >= 7),
    severityKnown: (labels.length > 0 || validScores.length > 0) && everyLabelKnown && everyScoreKnown,
  };
}

function executeScanner() {
  const binary = process.env.OSV_SCANNER_BIN?.trim() || "osv-scanner";
  const timeoutSetting = process.env.OSV_SCANNER_TIMEOUT_MS;
  const timeout = timeoutSetting === undefined ? 120_000 : Number(timeoutSetting);
  if (!Number.isSafeInteger(timeout) || timeout < 100 || timeout > 180_000) {
    throw new Error("OSV_SCANNER_TIMEOUT_MS must be an integer between 100 and 180000 milliseconds");
  }

  return spawnSync(binary, ["scan", "-r", ".", "--format", "json"], {
    encoding: "utf8",
    maxBuffer: 20 * 1024 * 1024,
    timeout,
  });
}

console.log("🔍 Running dependency vulnerability audit powered by GitHub Advisory / OSV Database...");

try {
  const scan = executeScanner();
  if (scan.error) {
    throw new Error("Failed to execute osv-scanner: " + scan.error.message);
  }
  if (scan.signal) {
    throw new Error("osv-scanner terminated with signal " + scan.signal);
  }

  const findings = parseReport(scan.stdout || "").flatMap((result) =>
    (result.packages || []).flatMap((pkg) =>
      (pkg.vulnerabilities || []).map((vuln) => describeVulnerability(vuln, pkg)),
    ),
  );

  for (const finding of findings) {
    const summary = finding.id + " in " + finding.packageName + "@" + finding.version;
    console.log("• [" + finding.label + "] " + summary);
    if (finding.isHighOrCritical) {
      console.error("🚨 HIGH or CRITICAL severity advisory detected: " + summary);
    } else if (!finding.severityKnown) {
      console.error("⚠️ Advisory with unknown severity requires review: " + summary);
    }
  }

  // OSV exits 1 for any findings, even when every advisory is below our severity gate.
  // An exit of 1 without corresponding JSON findings still indicates an inconsistent scan.
  if (scan.status !== 0 && !(scan.status === 1 && findings.length > 0)) {
    throw new Error("osv-scanner exited unsuccessfully (status " + String(scan.status) + ")");
  }
  if (findings.some((finding) => finding.isHighOrCritical)) {
    throw new Error("Security audit failed: High or Critical vulnerabilities detected");
  }
  if (findings.some((finding) => !finding.severityKnown)) {
    throw new Error("Security audit failed: advisory severity could not be verified");
  }

  console.log("\n✅ Security audit passed: " + findings.length + " total vulnerabilities, 0 High/Critical.");
} catch (error) {
  console.error("❌ " + (error instanceof Error ? error.message : String(error)));
  process.exitCode = 1;
}
