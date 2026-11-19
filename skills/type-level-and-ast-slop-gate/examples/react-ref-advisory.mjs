// SPDX-License-Identifier: MIT
import { readFile } from "node:fs/promises";

const SOURCE = "https://react.dev/blog/2024/12/05/react-19#ref-as-a-prop";
const exactStableRelease = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;

export function reviewForwardRef(lock, usage, supportedVersions) {
  if (usage?.module !== "react" || usage.export !== "forwardRef" ||
      usage.kind !== "function-component") {
    return { status: "not_applicable" };
  }
  if (lock?.status !== "locked" || lock.release !== "stable" || (typeof lock.resolved !== "string" || !exactStableRelease.test(lock.resolved))) {
    return { status: "inconclusive", reason: "React's exact stable locked version is required" };
  }
  if (Bun.semver.order(lock.resolved, "19.0.0") < 0) {
    return { status: "not_applicable", version: lock.resolved };
  }
  if (!Array.isArray(supportedVersions) || !supportedVersions.length ||
      !supportedVersions.every((release) => typeof release === "string" && exactStableRelease.test(release))) {
    return { status: "inconclusive", reason: "Supply the reviewed exact React releases in the compatibility matrix" };
  }
  if (supportedVersions.some((release) => Bun.semver.order(release, "19.0.0") < 0)) {
    return { status: "compatibility_exception", version: lock.resolved, source: SOURCE };
  }
  const verified = [lock.resolved, ...supportedVersions];
  if (verified.some((release) => !Bun.semver.satisfies(release, "^19.0.0"))) {
    return { status: "inconclusive", reason: "The React 19 documentation is the verified scope" };
  }
  return {
    status: "advisory",
    severity: "review",
    rule: "REACT19_FORWARD_REF_REDUNDANT",
    version: lock.resolved,
    source: SOURCE,
    suggestion: "Consider accepting a ref prop in the function component. Preserve the public ref type and the forwarding target, then test callback and object refs.",
  };
}

const RENDER_SOURCE = "https://react.dev/blog/2024/04/25/react-19-upgrade-guide#removed-reactdomrender";

export function reviewLegacyRender(lock, usage, supportedVersions) {
  if (usage?.module !== "react-dom" || usage.export !== "render" ||
      usage.kind !== "call") {
    return { status: "not_applicable" };
  }
  if (lock?.status !== "locked" || lock.release !== "stable" || (typeof lock.resolved !== "string" || !exactStableRelease.test(lock.resolved))) {
    return { status: "inconclusive", reason: "React DOM's exact stable locked version is required" };
  }
  const installed = lock.installed;
  if (installed?.status !== "installed" || installed.name !== "react-dom" ||
      (typeof installed.version !== "string" || !exactStableRelease.test(installed.version))) {
    return { status: "inconclusive", reason: "Installed React DOM version evidence from the lock receipt is required" };
  }
  if (Bun.semver.order(installed.version, "19.0.0") < 0) {
    return { status: "not_applicable", version: installed.version };
  }
  if (!Array.isArray(supportedVersions) || !supportedVersions.length ||
      !supportedVersions.every((release) => typeof release === "string" && exactStableRelease.test(release))) {
    return { status: "inconclusive", reason: "Supply the reviewed exact React DOM releases in the compatibility matrix" };
  }
  if (supportedVersions.some((release) => Bun.semver.order(release, "19.0.0") < 0)) {
    return { status: "compatibility_exception", version: installed.version, source: RENDER_SOURCE };
  }
  const verified = [installed.version, lock.resolved, ...supportedVersions];
  if (verified.some((release) => !Bun.semver.satisfies(release, "^19.0.0"))) {
    return { status: "inconclusive", reason: "The React 19 documentation is the verified scope" };
  }
  return {
    status: "advisory",
    severity: "review",
    rule: "REACT19_REACT_DOM_RENDER_REMOVED",
    version: installed.version,
    resolved: lock.resolved,
    evidence_source: "installed",
    source: RENDER_SOURCE,
    suggestion: "React DOM 19 removed the legacy render function. Use createRoot from react-dom/client and keep the returned root so unmount can run during teardown: createRoot(container).render(<App />).",
  };
}

const OXLINT_RULE_CODE = "anti-slop(react-forward-ref-evidence)";
const RENDER_OXLINT_RULE_CODE = "anti-slop(react-dom-render-evidence)";

function usageFromOxlintReport(report) {
  if (!Array.isArray(report?.diagnostics)) {
    throw new Error("Expected an Oxlint JSON diagnostics array");
  }
  if (report.diagnostics.some((diagnostic) => diagnostic?.code === OXLINT_RULE_CODE)) {
    return { module: "react", export: "forwardRef", kind: "function-component" };
  }
  return report.diagnostics.some((diagnostic) => diagnostic?.code === RENDER_OXLINT_RULE_CODE)
    ? { module: "react-dom", export: "render", kind: "call" }
    : undefined;
}

function reviewUsage(lock, usage, supportedVersions) {
  return usage?.module === "react-dom" && usage?.export === "render"
    ? reviewLegacyRender(lock, usage, supportedVersions)
    : reviewForwardRef(lock, usage, supportedVersions);
}

if (import.meta.main) {
  const [lockPath, usagePath, reportOption, reportPath, extra] = process.argv.slice(2);
  const reportRequested = reportOption === "--oxlint-report" && reportPath;
  if (!lockPath || !usagePath || extra || (reportOption !== undefined && !reportRequested)) {
    console.error("Usage: bun react-ref-advisory.mjs <react-lock-evidence.json> <reviewed-usage-or-support.json> [--oxlint-report <oxlint.json>]");
    process.exitCode = 2;
  } else {
    try {
      const lock = JSON.parse(await readFile(lockPath, "utf8"));
      const record = JSON.parse(await readFile(usagePath, "utf8"));
      const usage = reportRequested
        ? usageFromOxlintReport(JSON.parse(await readFile(reportPath, "utf8")))
        : record;
      console.log(JSON.stringify(reviewUsage(lock, usage, record?.supportedVersions)));
    } catch {
      console.error("Cannot read React lock, support, usage, or Oxlint evidence");
      process.exitCode = 2;
    }
  }
}
