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

if (import.meta.main) {
  const [lockPath, usagePath] = process.argv.slice(2);
  if (!lockPath || !usagePath || process.argv.length !== 4) {
    console.error("Usage: bun react-ref-advisory.mjs <react-lock-evidence.json> <reviewed-usage.json>");
    process.exitCode = 2;
  } else {
    try {
      const lock = JSON.parse(await readFile(lockPath, "utf8"));
      const usage = JSON.parse(await readFile(usagePath, "utf8"));
      console.log(JSON.stringify(reviewForwardRef(lock, usage, usage?.supportedVersions)));
    } catch {
      console.error("Cannot read React lock evidence or usage JSON");
      process.exitCode = 2;
    }
  }
}
