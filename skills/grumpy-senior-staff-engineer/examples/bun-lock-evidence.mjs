// SPDX-License-Identifier: MIT
import { readFile } from "node:fs/promises";
import { request } from "node:https";
import { join } from "node:path";

const dependencyGroups = ["dependencies", "optionalDependencies", "devDependencies"];
const versionCore = /^(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)$/;
const registryRange = /^[~^=]?([^\s]+)$/;
const identifier = /^[0-9A-Za-z-]+$/;
const leadingZeroNumber = /^0\d+$/;

function releaseVersion(value) {
  const [release, build, extra] = value.split("+");
  const separator = release.indexOf("-");
  const core = separator < 0 ? release : release.slice(0, separator);
  if (extra !== undefined || !versionCore.test(core)) {
    return false;
  }
  if (build !== undefined && !build.split(".").every((part) => identifier.test(part))) {
    return false;
  }
  return separator < 0 || release.slice(separator + 1).split(".").every(
    (part) => identifier.test(part) && !leadingZeroNumber.test(part),
  );
}


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
  const request = declared.match(registryRange);
  if (!request || !releaseVersion(request[1]) || Object.hasOwn(manifest.overrides ?? {}, packageName)) {
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
  if (!releaseVersion(resolved)) {
    return { status: "unsupported", declared };
  }
  if (!Bun.semver.satisfies(resolved, declared)) {
    return { status: "stale_lock", declared };
  }
  return { status: "locked", declared, resolved, release: resolved.split("+", 1)[0].includes("-") ? "prerelease" : "stable" };
}


export function inspectInstalledPackage(installedText, packageName) {
  if (installedText === null || installedText === undefined) {
    return { status: "missing" };
  }
  let installed;
  try {
    installed = JSON.parse(installedText);
  } catch {
    return { status: "unreadable" };
  }
  if (!installed || typeof installed !== "object" || Array.isArray(installed)) {
    return { status: "unreadable" };
  }
  if (installed.name !== packageName) {
    return { status: "identity_mismatch", name: typeof installed.name === "string" ? installed.name : null };
  }
  if (typeof installed.version !== "string" || !releaseVersion(installed.version)) {
    return { status: "unsupported", name: packageName };
  }
  return { status: "installed", name: packageName, version: installed.version };
}


const npmOrigin = "https://registry.npmjs.org";
const maxRegistryBytes = 2_000_000;
const npmNamePart = /^[a-z0-9][a-z0-9._-]*$/;

function validNpmName(name) {
  if (typeof name !== "string" || name.length > 214) {
    return false;
  }
  if (name.startsWith("@")) {
    const [scope, leaf, extra] = name.slice(1).split("/");
    return extra === undefined && leaf !== undefined && npmNamePart.test(scope) && npmNamePart.test(leaf);
  }
  return npmNamePart.test(name);
}

function requestPublicNpm(url, options) {
  // Node's HTTPS client makes one request, without fetch redirect or proxy discovery.
  return new Promise((resolve, reject) => {
    const outbound = request(url, { headers: options.headers, signal: options.signal }, resolve);
    outbound.on("error", reject);
    outbound.end();
  });
}

async function readBoundedRegistryBody(body) {
  const chunks = [];
  let count = 0;
  for await (const raw of body) {
    const chunk = Buffer.from(raw);
    count += chunk.length;
    if (count > maxRegistryBytes) {
      return null;
    }
    chunks.push(chunk);
  }
  return Buffer.concat(chunks, count).toString("utf8");
}

function metadataEvidence(data, packageName, evidence) {
  if (data?.name !== packageName || !data.versions || !data["dist-tags"]) {
    return { status: "invalid_metadata" };
  }
  const selected = data.versions[evidence.resolved];
  if (selected !== undefined && (selected?.name !== packageName || selected?.version !== evidence.resolved)) {
    return { status: "invalid_metadata" };
  }
  const latest = data["dist-tags"].latest;
  const latestIsVerified = typeof latest === "string" && releaseVersion(latest) &&
    data.versions[latest]?.name === packageName && data.versions[latest]?.version === latest;
  const latestIsStable = latestIsVerified && !latest.split("+", 1)[0].includes("-");
  return {
    status: "observed",
    locked_version: selected ? "listed" : "unlisted",
    deprecated: selected ? typeof selected.deprecated === "string" && selected.deprecated.length > 0 : null,
    latest: latestIsVerified ? latest : null,
    latest_satisfies_declared_range: latestIsStable ? Bun.semver.satisfies(latest, evidence.declared) : null,
  };
}

export async function readPublicNpmEvidence(packageName, evidence, transport = requestPublicNpm) {
  if (!validNpmName(packageName) || evidence.status !== "locked") {
    return { status: "unsupported" };
  }
  const source = npmOrigin + "/" + encodeURIComponent(packageName);
  const options = {
    headers: { accept: "application/vnd.npm.install-v1+json" },
    credentials: "omit", redirect: "error", signal: AbortSignal.timeout(4000),
  };
  try {
    const response = await transport(source, options);
    const code = response.statusCode ?? response.status;
    const body = response.statusCode ? response : response.body;
    if (code !== 200) {
      if (response.statusCode) {
        response.destroy();
      } else {
        await body?.cancel();
      }
      return { source, status: code === 404 ? "package_unlisted" : "unavailable" };
    }
    const raw = await readBoundedRegistryBody(body);
    if (raw === null) {
      return { source, status: "response_too_large" };
    }
    return { source, ...metadataEvidence(JSON.parse(raw), packageName, evidence) };
  } catch (error) {
    return { source, status: error instanceof SyntaxError ? "invalid_metadata" : "unavailable" };
  }
}

if (import.meta.main) {
  const [root, packageName, mode, extra] = process.argv.slice(2);
  if (!root || !packageName || (mode !== undefined && mode !== "--public-npm") || extra !== undefined) {
    console.error("Usage: bun bun-lock-evidence.mjs <project-root> <package-name> [--public-npm]");
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
    let installed = { status: "unsupported" };
    if (validNpmName(packageName)) {
      try {
        const installedText = await readFile(join(root, "node_modules", packageName, "package.json"), "utf8");
        installed = inspectInstalledPackage(installedText, packageName);
      } catch (error) {
        installed = { status: error?.code === "ENOENT" ? "missing" : "unreadable" };
      }
    }
    if (mode === "--public-npm") {
      const registry = await readPublicNpmEvidence(packageName, evidence);
      console.log(JSON.stringify({ ...evidence, registry: { ...registry, observed_at: new Date().toISOString() }, installed }));
      process.exitCode = registry.status === "observed" ? 0 : 2;
    } else {
      console.log(JSON.stringify({ ...evidence, installed }));
      process.exitCode = evidence.status === "locked" ? 0 : 1;
    }
  }
}
