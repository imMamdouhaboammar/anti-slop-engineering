// SPDX-License-Identifier: MIT
import { readFile } from "node:fs/promises";

const SOURCE = "https://tailwindcss.com/docs/upgrade-guide";
const exactStableRelease = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;

function compareSemver(a, b) {
  if (typeof Bun !== "undefined" && Bun?.semver?.order) {
    return Bun.semver.order(a, b);
  }
  const [ma, na, pa] = a.split(".").map(Number);
  const [mb, nb, pb] = b.split(".").map(Number);
  return ma !== mb ? ma - mb : na !== nb ? na - nb : pa - pb;
}

export function reviewTailwindDirectives(lock, usage, supportedVersions) {
  if (usage?.module !== "tailwindcss" || usage.idiom !== "tailwind-directives" ||
      usage.kind !== "css-directives") {
    return { status: "not_applicable" };
  }
  if (lock?.status !== "locked" || lock.release !== "stable" ||
      typeof lock.resolved !== "string" || !exactStableRelease.test(lock.resolved)) {
    return { status: "inconclusive", reason: "Tailwind's exact stable locked version is required" };
  }
  const installed = lock.installed;
  if (installed !== undefined && (installed?.status !== "installed" || installed.name !== "tailwindcss" ||
      typeof installed.version !== "string" || !exactStableRelease.test(installed.version))) {
    return { status: "inconclusive", reason: "Installed evidence must identify a stable tailwindcss release" };
  }
  const effective = installed?.version ?? lock.resolved;
  if (compareSemver(effective, "4.0.0") < 0) {
    return { status: "not_applicable", version: effective };
  }
  if (compareSemver(effective, "5.0.0") >= 0) {
    return { status: "inconclusive", reason: "The Tailwind v4 upgrade guide is the verified scope" };
  }
  if (!Array.isArray(supportedVersions) || !supportedVersions.length ||
      !supportedVersions.every((release) => typeof release === "string" && exactStableRelease.test(release))) {
    return { status: "inconclusive", reason: "Supply the reviewed exact Tailwind releases in the compatibility matrix" };
  }
  if (supportedVersions.some((release) => compareSemver(release, "4.0.0") < 0)) {
    return { status: "compatibility_exception", version: effective, source: SOURCE };
  }
  if (supportedVersions.some((release) => compareSemver(release, "5.0.0") >= 0)) {
    return { status: "inconclusive", reason: "The Tailwind v4 upgrade guide is the verified scope" };
  }
  return {
    status: "advisory",
    severity: "review",
    rule: "TAILWIND_V4_CSS_FIRST_IMPORT",
    version: effective,
    source: SOURCE,
    suggestion: "Tailwind CSS v4 replaces the @tailwind base, @tailwind components, and @tailwind utilities directives with a single @import \"tailwindcss\" and moves configuration into CSS. Replace the directives, port tailwind.config theme extensions to @theme tokens, and keep a config file only for options v4 still reads from it.",
  };
}

if (import.meta.main) {
  const [lockPath, usagePath, extra] = process.argv.slice(2);
  if (!lockPath || !usagePath || extra) {
    console.error("Usage: bun tailwind-directives-advisory.mjs <tailwind-lock-evidence.json> <reviewed-usage-or-support.json>");
    process.exitCode = 2;
  } else {
    try {
      const lock = JSON.parse(await readFile(lockPath, "utf8"));
      const record = JSON.parse(await readFile(usagePath, "utf8"));
      console.log(JSON.stringify(reviewTailwindDirectives(lock, record, record?.supportedVersions)));
    } catch {
      console.error("Cannot read Tailwind lock, support, or usage evidence");
      process.exitCode = 2;
    }
  }
}
