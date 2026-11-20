// SPDX-License-Identifier: MIT
import { readFile } from "node:fs/promises";

const SOURCE = "https://nodejs.org/api/crypto.html#cryptorandomuuidoptions";
const exactStableRelease = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;
const RANDOM_UUID_FLOORS = { node: "19.0.0", bun: "1.0.0", deno: "1.0.0" };

function evidenceExports(entries) {
  if (!Array.isArray(entries) || !entries.length) {
    return null;
  }
  if (!entries.every((entry) => entry && typeof entry.export === "string")) {
    return null;
  }
  return entries.map((entry) => entry.export);
}

export function reviewUuidV4(lock, usage, runtimes) {
  if (usage?.module !== "uuid") {
    return { status: "not_applicable" };
  }
  const imported = evidenceExports(usage.imports);
  const called = evidenceExports(usage.calls);
  if (!imported || !called) {
    return { status: "inconclusive", reason: "Import and call-site evidence for uuid is required" };
  }
  if ([...imported, ...called].some((name) => name !== "v4")) {
    return { status: "not_applicable" };
  }
  if (lock?.status !== "locked" || typeof lock.resolved !== "string" || !exactStableRelease.test(lock.resolved)) {
    return { status: "inconclusive", reason: "uuid's exact stable locked version is required" };
  }
  const installed = lock.installed;
  if (installed !== undefined && (installed?.status !== "installed" || installed.name !== "uuid" ||
      typeof installed.version !== "string" || !exactStableRelease.test(installed.version))) {
    return { status: "inconclusive", reason: "Installed evidence must identify a stable uuid release" };
  }
  if (!Array.isArray(runtimes) || !runtimes.length ||
      !runtimes.every((runtime) => runtime && typeof runtime.name === "string" &&
        typeof runtime.version === "string" && exactStableRelease.test(runtime.version))) {
    return { status: "inconclusive", reason: "Supply the reviewed supported runtimes with exact versions" };
  }
  if (runtimes.some((runtime) => !(runtime.name in RANDOM_UUID_FLOORS))) {
    return { status: "inconclusive", reason: "A supported runtime is outside the verified randomUUID scope" };
  }
  if (runtimes.some((runtime) => Bun.semver.order(runtime.version, RANDOM_UUID_FLOORS[runtime.name]) < 0)) {
    return { status: "compatibility_exception", version: lock.resolved, source: SOURCE };
  }
  return {
    status: "advisory",
    severity: "review",
    rule: "UUID_V4_RUNTIME_RANDOMUUID",
    version: lock.resolved,
    source: SOURCE,
    suggestion: "Every recorded import and call site only generates version 4 UUIDs. Replace the uuid import with randomUUID from node:crypto (the global crypto.randomUUID in Bun, Deno, and browsers), which returns the same RFC 4122 version 4 string, then remove the uuid dependency.",
  };
}

if (import.meta.main) {
  const [lockPath, usagePath, extra] = process.argv.slice(2);
  if (!lockPath || !usagePath || extra) {
    console.error("Usage: bun uuid-v4-advisory.mjs <uuid-lock-evidence.json> <reviewed-usage-and-runtimes.json>");
    process.exitCode = 2;
  } else {
    try {
      const lock = JSON.parse(await readFile(lockPath, "utf8"));
      const record = JSON.parse(await readFile(usagePath, "utf8"));
      console.log(JSON.stringify(reviewUuidV4(lock, record, record?.runtimes)));
    } catch {
      console.error("Cannot read uuid lock, usage, or runtime evidence");
      process.exitCode = 2;
    }
  }
}
