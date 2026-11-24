// SPDX-License-Identifier: MIT
import { readFile } from "node:fs/promises";

const SOURCE = "https://nodejs.org/api/process.html#processloadenvfilepath";
const exactStableRelease = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;
const LOAD_ENV_FLOORS = { node: "20.12.0", bun: "1.0.0" };

function compareSemver(a, b) {
  if (typeof Bun !== "undefined" && Bun?.semver?.order) {
    return Bun.semver.order(a, b);
  }
  const [ma, na, pa] = a.split(".").map(Number);
  const [mb, nb, pb] = b.split(".").map(Number);
  return ma !== mb ? ma - mb : na !== nb ? na - nb : pa - pb;
}

function evidenceExports(entries) {
  if (!Array.isArray(entries) || !entries.length) {
    return null;
  }
  if (!entries.every((entry) => entry && typeof entry.export === "string")) {
    return null;
  }
  return entries.map((entry) => entry.export);
}

function pathOnlyOptions(call) {
  return Array.isArray(call?.options) && call.options.length === 1 && call.options[0] === "path";
}

export function reviewDotenv(lock, usage, runtimes) {
  if (usage?.module !== "dotenv") {
    return { status: "not_applicable" };
  }
  const imported = evidenceExports(usage.imports);
  const called = evidenceExports(usage.calls);
  if (!imported || !called) {
    return { status: "inconclusive", reason: "Import and call-site evidence for dotenv is required" };
  }
  if ([...imported, ...called].some((name) => name !== "config")) {
    return { status: "not_applicable" };
  }
  if (usage.calls.some((call) => call && (
    call.hasArgs === true ||
    (typeof call.args === "number" && call.args > 0) ||
    (Array.isArray(call.args) && call.args.length > 0) ||
    (call.hasOptions === true && !pathOnlyOptions(call))
  ))) {
    return { status: "not_applicable" };
  }
  if (lock?.status !== "locked" || typeof lock.resolved !== "string" || !exactStableRelease.test(lock.resolved)) {
    return { status: "inconclusive", reason: "dotenv's exact stable locked version is required" };
  }
  const installed = lock.installed;
  if (installed !== undefined && (installed?.status !== "installed" || installed.name !== "dotenv" ||
      typeof installed.version !== "string" || !exactStableRelease.test(installed.version))) {
    return { status: "inconclusive", reason: "Installed evidence must identify a stable dotenv release" };
  }
  if (!Array.isArray(runtimes) || !runtimes.length ||
      !runtimes.every((runtime) => runtime && typeof runtime.name === "string" &&
        typeof runtime.version === "string" && exactStableRelease.test(runtime.version))) {
    return { status: "inconclusive", reason: "Supply the reviewed supported runtimes with exact versions" };
  }
  if (runtimes.some((runtime) => !Object.hasOwn(LOAD_ENV_FLOORS, runtime.name))) {
    return { status: "inconclusive", reason: "A supported runtime is outside the verified loadEnvFile scope" };
  }
  if (runtimes.some((runtime) => compareSemver(runtime.version, LOAD_ENV_FLOORS[runtime.name]) < 0)) {
    return { status: "compatibility_exception", version: lock.resolved, source: SOURCE };
  }
  const confirmedSimple = usage.calls.every((call) => call && (
    call.signature === "no_args" ||
    call.hasArgs === false ||
    call.args === 0 ||
    (Array.isArray(call.args) && call.args.length === 0) ||
    pathOnlyOptions(call)
  ));
  const suggestion = confirmedSimple
    ? "Every recorded import and call site only loads an environment file through dotenv's config. Replace it with the runtime's native loading (process.loadEnvFile in Node, automatic .env loading in Bun), which populates process.env the same way, then remove the dotenv dependency."
    : "Review recorded dotenv config call signatures: calls that only load an environment file (no options, or a lone path option) can move to the runtime's native loading (process.loadEnvFile in Node, automatic .env loading in Bun), while calls using vault keys, override, or custom parsing still require dotenv.";
  return {
    status: "advisory",
    severity: "review",
    rule: "DOTENV_RUNTIME_LOAD_ENV_FILE",
    version: lock.resolved,
    source: SOURCE,
    suggestion,
  };
}

if (import.meta.main) {
  const [lockPath, usagePath, extra] = process.argv.slice(2);
  if (!lockPath || !usagePath || extra) {
    console.error("Usage: bun dotenv-advisory.mjs <dotenv-lock-evidence.json> <reviewed-usage-and-runtimes.json>");
    process.exitCode = 2;
  } else {
    try {
      const lock = JSON.parse(await readFile(lockPath, "utf8"));
      const record = JSON.parse(await readFile(usagePath, "utf8"));
      console.log(JSON.stringify(reviewDotenv(lock, record, record?.runtimes)));
    } catch {
      console.error("Cannot read dotenv lock, usage, or runtime evidence");
      process.exitCode = 2;
    }
  }
}
