// SPDX-License-Identifier: MIT
import { readFile } from "node:fs/promises";
import { join } from "node:path";

const dependencyGroups = ["dependencies", "optionalDependencies", "devDependencies"];
const registryRange = /^(?:[vV]?\d|[~^<>*=xX])[0-9A-Za-z.*~^<>=+| -]*$/;

export function inspectDirectDependency(manifestText, lockText, packageName) {
  let manifest;
  let lock;
  try {
    manifest = JSON.parse(manifestText);
    lock = Bun.JSONC.parse(lockText);
  } catch {
    return { status: "unreadable" };
  }
  if (!manifest || typeof manifest !== "object" || Array.isArray(manifest)) {
    return { status: "unreadable" };
  }
  const root = lock?.workspaces?.[""];
  if (lock?.lockfileVersion !== 2 || !root || !lock.packages) {
    return { status: "unsupported" };
  }

  const groups = dependencyGroups.filter((group) => Object.hasOwn(manifest[group] ?? {}, packageName));
  if (groups.length === 0) {
    return { status: "not_direct" };
  }
  if (groups.length !== 1) {
    return { status: "unsupported" };
  }
  const group = groups[0];
  const declared = manifest[group][packageName];
  if (typeof declared !== "string" || declared.length === 0) {
    return { status: "unreadable" };
  }
  if (!Object.hasOwn(root[group] ?? {}, packageName) || root[group][packageName] !== declared) {
    return { status: "stale_lock", declared };
  }
  if (!registryRange.test(declared) || Object.hasOwn(manifest.overrides ?? {}, packageName)) {
    return { status: "unsupported", declared };
  }

  const record = Object.hasOwn(lock.packages, packageName) ? lock.packages[packageName] : undefined;
  if (!record) {
    return { status: "missing_resolution", declared };
  }
  const prefix = packageName + "@";
  if (!Array.isArray(record) || typeof record[0] !== "string" || !record[0].startsWith(prefix) ||
      typeof record[3] !== "string" || !record[3].startsWith("sha")) {
    return { status: "unsupported", declared };
  }
  const resolved = record[0].slice(prefix.length);
  if (!Bun.semver.satisfies(resolved, resolved)) {
    return { status: "unsupported", declared };
  }
  if (!Bun.semver.satisfies(resolved, declared)) {
    return { status: "stale_lock", declared };
  }
  return { status: "locked", declared, resolved, release: resolved.split("+", 1)[0].includes("-") ? "prerelease" : "stable" };
}

if (import.meta.main) {
  const [root, packageName] = process.argv.slice(2);
  if (!root || !packageName) {
    console.error("Usage: bun bun-lock-evidence.mjs <project-root> <package-name>");
    process.exitCode = 2;
  } else {
    let evidence;
    try {
      const manifest = await readFile(join(root, "package.json"), "utf8");
      const lock = await readFile(join(root, "bun.lock"), "utf8");
      evidence = inspectDirectDependency(manifest, lock, packageName);
    } catch {
      evidence = { status: "unreadable" };
    }
    console.log(JSON.stringify(evidence));
    process.exitCode = evidence.status === "locked" ? 0 : 1;
  }
}
