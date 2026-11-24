import { test, expect } from "bun:test";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { inspectDirectDependency, inspectInstalledPackage, readPublicNpmEvidence, readRegistryEvidenceWithCache } from "../skills/grumpy-senior-staff-engineer/examples/bun-lock-evidence.mjs";

const script = new URL("../skills/grumpy-senior-staff-engineer/examples/bun-lock-evidence.mjs", import.meta.url);

const manifest = '{"dependencies":{"@demo/library":"^2.0.0"},"devDependencies":{"example-prerelease":"3.0.0-rc.1"}}';
const lock = String.raw`{
  "lockfileVersion": 2,
  "workspaces": {
    "": {"dependencies":{"@demo/library":"^2.0.0"},"devDependencies":{"example-prerelease":"3.0.0-rc.1"}},
  },
  "packages": {
    "@demo/library": ["@demo/library@2.1.0", "", {}, "sha512-example"],
    "example-prerelease": ["example-prerelease@3.0.0-rc.1", "", {}, "sha512-example"],
    "transitive": ["transitive@9.0.0", "", {}, "sha512-example"],
  },
}`;

test("reports the locked release separately from the manifest range", () => {
  const evidence = inspectDirectDependency(manifest, lock, "@demo/library");
  expect(evidence).toEqual({
    status: "locked", declared: "^2.0.0", resolved: "2.1.0", release: "stable",
  });
  expect(inspectDirectDependency(manifest, lock, "example-prerelease")).toEqual({
    status: "locked", declared: "3.0.0-rc.1", resolved: "3.0.0-rc.1", release: "prerelease",
  });
});

test("keeps stale declarations and transitive records from proving a direct dependency", () => {
  const changed = manifest.replace("^2.0.0", "^3.0.0");
  expect(inspectDirectDependency(changed, lock, "@demo/library").status).toBe("stale_lock");
  expect(inspectDirectDependency(manifest, lock, "transitive").status).toBe("not_direct");
  expect(inspectDirectDependency(manifest, lock.replace("@demo/library@2.1.0", "@demo/library@3.0.0"), "@demo/library").status).toBe("stale_lock");
  expect(inspectDirectDependency(manifest, lock.replace("@demo/library@2.1.0", "@demo/library@2.1.0-rc.1"), "@demo/library").status).toBe("stale_lock");
});

test("honors unsupported lock versions, malformed input, and unsupported resolutions", () => {
  for (const version of ["2.1.0-", "2.1.0-!", "2.1.0-alpha+", "2.1.0-alpha.01", "2.1.0+meta+data"]) {
    const corruptedLock = lock.replace("@demo/library@2.1.0", "@demo/library@" + version);
    expect(inspectDirectDependency(manifest, corruptedLock, "@demo/library").status).toBe("unsupported");
  }
  expect(inspectDirectDependency(manifest, lock.replace('"lockfileVersion": 2', '"lockfileVersion": 999'), "@demo/library").status).toBe("unsupported");
  expect(inspectDirectDependency(manifest, "{", "@demo/library").status).toBe("unreadable");
  expect(inspectDirectDependency(
    manifest.replace("^2.0.0", "^broken"),
    lock.replace("^2.0.0", "^broken"),
    "@demo/library",
  ).status).toBe("unsupported");
  expect(inspectDirectDependency(
    manifest.replace("^2.0.0", "workspace:*"),
    lock.replace("^2.0.0", "workspace:*"),
    "@demo/library",
  ).status).toBe("unsupported");
  expect(inspectDirectDependency(
    manifest.replace("^2.0.0", "latest"),
    lock.replace("^2.0.0", "latest"),
    "@demo/library",
  ).status).toBe("unsupported");
  expect(inspectDirectDependency(manifest, lock.replace("@demo/library@2.1.0", "other-library@2.1.0"), "@demo/library").status).toBe("unsupported");
  expect(inspectDirectDependency(manifest, lock.replace('["example-prerelease@3.0.0-rc.1", "", {}, "sha512-example"]', '["example-prerelease@3.0.0-rc.1", "", {}]'), "example-prerelease").status).toBe("unsupported");
});

test("compares fixed public npm metadata with a locked direct dependency", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const metadata = {
    name: "@demo/library", "dist-tags": { latest: "3.2.0" }, versions: {
      "2.1.0": { name: "@demo/library", version: "2.1.0", deprecated: "Retired release" },
      "3.2.0": { name: "@demo/library", version: "3.2.0" },
    },
  };
  const transport = async (url, options) => {
    expect(String(url)).toBe("https://registry.npmjs.org/%40demo%2Flibrary");
    expect(options.redirect).toBe("error");
    expect(options.credentials).toBe("omit");
    expect(Object.keys(options.headers)).toEqual(["accept"]);
    return Response.json(metadata);
  };
  const result = await readPublicNpmEvidence("@demo/library", locked, transport);
  expect(result).toMatchObject({
    source: "https://registry.npmjs.org/%40demo%2Flibrary",
    status: "observed", locked_version: "listed", deprecated: true, latest: "3.2.0",
    latest_satisfies_declared_range: false,
  });
});

test("public npm lookup distinguishes unsupported, unknown, and oversized evidence", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const deny = async () => { throw new Error("transport unavailable"); };
  const notFound = () => new Response(null, { status: 404 });
  expect((await readPublicNpmEvidence("@demo/library", locked, deny)).status).toBe("unavailable");
  expect((await readPublicNpmEvidence("@demo/library", locked, notFound)).status).toBe("package_unlisted");
  const wrongPackage = () => Response.json({ name: "other", versions: {}, "dist-tags": {} });
  expect((await readPublicNpmEvidence("@demo/library", locked, wrongPackage)).status).toBe("invalid_metadata");
  const tooLarge = () => new Response(" ".repeat(2_000_001));
  expect((await readPublicNpmEvidence("@demo/library", locked, tooLarge)).status).toBe("response_too_large");
  let attempted = false;
  const unexpected = () => { attempted = true; return Response.json({}); };
  expect((await readPublicNpmEvidence("https://example.com/a", locked, unexpected)).status).toBe("unsupported");
  expect((await readPublicNpmEvidence("@demo/library", { status: "stale_lock" }, unexpected)).status).toBe("unsupported");
  expect(attempted).toBe(false);
});

test("latest pointing at a prerelease does not count as stable", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const result = await readPublicNpmEvidence("@demo/library", locked, () => Response.json({
    name: "@demo/library", "dist-tags": { latest: "3.0.0-rc.1" }, versions: {
      "3.0.0-rc.1": { name: "@demo/library", version: "3.0.0-rc.1" },
    },
  }));
  expect(result.status).toBe("observed");
  expect(result.locked_version).toBe("unlisted");
  expect(result.latest).toBe("3.0.0-rc.1");
  expect(result.latest_satisfies_declared_range).toBeNull();
});

test("reports installed identity and version separately from the lock evidence", () => {
  expect(inspectInstalledPackage('{"name":"@demo/library","version":"2.1.0"}', "@demo/library")).toEqual({
    status: "installed", name: "@demo/library", version: "2.1.0",
  });
  expect(inspectInstalledPackage('{"name":"@demo/library","version":"2.0.4"}', "@demo/library")).toEqual({
    status: "installed", name: "@demo/library", version: "2.0.4",
  });
});

test("keeps missing, malformed, wrong-identity, and invalid installed metadata explicit", () => {
  expect(inspectInstalledPackage(null, "@demo/library")).toEqual({ status: "missing" });
  expect(inspectInstalledPackage("{", "@demo/library").status).toBe("unreadable");
  expect(inspectInstalledPackage('{"name":"other-library","version":"2.1.0"}', "@demo/library")).toEqual({
    status: "identity_mismatch", name: "other-library",
  });
  expect(inspectInstalledPackage('{"name":"@demo/library","version":"2.1.0-!"}', "@demo/library").status).toBe("unsupported");
  expect(inspectInstalledPackage('{"name":"@demo/library"}', "@demo/library").status).toBe("unsupported");
});

function writeProject(installedVersion) {
  const dir = mkdtempSync(join(tmpdir(), "bun-lock-evidence-"));
  writeFileSync(join(dir, "package.json"), manifest);
  writeFileSync(join(dir, "bun.lock"), lock);
  if (installedVersion !== null) {
    const packageDir = join(dir, "node_modules", "@demo", "library");
    mkdirSync(packageDir, { recursive: true });
    writeFileSync(join(packageDir, "package.json"), JSON.stringify({ name: "@demo/library", version: installedVersion }));
  }
  return dir;
}

test("CLI receipt exposes a three-way disagreement between declared, locked, and installed", () => {
  const dir = writeProject("2.0.4");
  try {
    const output = Bun.spawnSync([process.execPath, script.pathname, dir, "@demo/library"]);
    expect(output.exitCode).toBe(0);
    expect(JSON.parse(output.stdout.toString())).toEqual({
      status: "locked", declared: "^2.0.0", resolved: "2.1.0", release: "stable",
      installed: { status: "installed", name: "@demo/library", version: "2.0.4" },
    });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("CLI receipt reports a missing installation without changing the lock verdict", () => {
  const dir = writeProject(null);
  try {
    const output = Bun.spawnSync([process.execPath, script.pathname, dir, "@demo/library"]);
    expect(output.exitCode).toBe(0);
    const receipt = JSON.parse(output.stdout.toString());
    expect(receipt.status).toBe("locked");
    expect(receipt.installed).toEqual({ status: "missing" });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

const cacheRecord = {
  package: "@demo/library", resolved: "2.1.0",
  source: "https://registry.npmjs.org/%40demo%2Flibrary", status: "observed",
  locked_version: "listed", deprecated: true, latest: "3.2.0",
  latest_satisfies_declared_range: false, observed_at: "2026-11-20T10:00:00.000Z",
};
const cacheNow = new Date("2026-11-20T10:30:00.000Z");

test("serves a fresh cached registry result without consulting the registry", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  let calls = 0;
  const transport = async () => { calls += 1; throw new Error("must not be called"); };
  const result = await readRegistryEvidenceWithCache("@demo/library", locked, cacheRecord, cacheNow, 3600, transport);
  expect(calls).toBe(0);
  expect(result).toEqual({
    source: cacheRecord.source, status: "observed", locked_version: "listed", deprecated: true,
    latest: "3.2.0", latest_satisfies_declared_range: false, channels: null, observed_at: "2026-11-20T10:00:00.000Z",
    provenance: "cache", age_seconds: 1800, freshness: "fresh",
  });
});

test("serves an expired cache as stale evidence while offline", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const offline = async () => { throw new Error("transport unavailable"); };
  const result = await readRegistryEvidenceWithCache("@demo/library", locked, cacheRecord, cacheNow, 900, offline);
  expect(result).toEqual({
    source: cacheRecord.source, status: "observed", locked_version: "listed", deprecated: true,
    latest: "3.2.0", latest_satisfies_declared_range: false, channels: null, observed_at: "2026-11-20T10:00:00.000Z",
    provenance: "cache", age_seconds: 1800, freshness: "stale", live_status: "unavailable",
  });
});

test("refreshes an expired cache from the registry and reports zero age", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const metadata = {
    name: "@demo/library", "dist-tags": { latest: "3.2.0" }, versions: {
      "2.1.0": { name: "@demo/library", version: "2.1.0", deprecated: "Retired release" },
      "3.2.0": { name: "@demo/library", version: "3.2.0" },
    },
  };
  const result = await readRegistryEvidenceWithCache(
    "@demo/library", locked, cacheRecord, cacheNow, 900, async () => Response.json(metadata));
  expect(result).toEqual({
    source: cacheRecord.source, status: "observed", locked_version: "listed", deprecated: true,
    latest: "3.2.0", latest_satisfies_declared_range: false, channels: { latest: "3.2.0" }, observed_at: "2026-11-20T10:30:00.000Z",
    provenance: "registry", age_seconds: 0, freshness: "fresh",
  });
});

test("reports an unavailable registry when no cache can serve", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const offline = async () => { throw new Error("transport unavailable"); };
  expect(await readRegistryEvidenceWithCache("@demo/library", locked, null, cacheNow, 3600, offline)).toEqual({
    source: cacheRecord.source, status: "unavailable", observed_at: "2026-11-20T10:30:00.000Z",
  });
  const otherLock = { ...cacheRecord, resolved: "2.0.0" };
  expect((await readRegistryEvidenceWithCache("@demo/library", locked, otherLock, cacheNow, 3600, offline)).status)
    .toBe("unavailable");
});

test("CLI serves a fresh cache file and keeps the offline lock verdict", () => {
  const dir = writeProject("2.1.0");
  try {
    const cachePath = join(dir, "registry-cache.json");
    const recent = { ...cacheRecord, observed_at: new Date(Date.now() - 600_000).toISOString() };
    writeFileSync(cachePath, JSON.stringify(recent));
    const output = Bun.spawnSync([process.execPath, script.pathname, dir, "@demo/library",
      "--public-npm", "--cache", cachePath, "--cache-max-age", "3600"]);
    expect(output.exitCode).toBe(0);
    const receipt = JSON.parse(output.stdout.toString());
    expect(receipt.status).toBe("locked");
    expect(receipt.registry).toMatchObject({
      status: "observed", provenance: "cache", freshness: "fresh", latest: "3.2.0",
    });
    expect(receipt.registry.age_seconds).toBeGreaterThanOrEqual(600);
    expect(receipt.registry.age_seconds).toBeLessThan(3600);
    expect(JSON.parse(readFileSync(cachePath, "utf8"))).toEqual(recent);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("CLI distinguishes unreadable installed metadata from a missing manifest", () => {
  const dir = writeProject("2.0.4");
  try {
    const manifestPath = join(dir, "node_modules", "@demo", "library", "package.json");
    rmSync(manifestPath);
    mkdirSync(manifestPath);
    const output = Bun.spawnSync([process.execPath, script.pathname, dir, "@demo/library"]);
    expect(output.exitCode).toBe(0);
    expect(JSON.parse(output.stdout.toString()).installed).toEqual({ status: "unreadable" });
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});

test("reports the verified release channels from dist-tags", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const result = await readPublicNpmEvidence("@demo/library", locked, () => Response.json({
    name: "@demo/library",
    "dist-tags": { latest: "3.2.0", next: "4.0.0-beta.1", beta: "3.3.0-beta.2", legacy: "9.9.9" },
    versions: {
      "2.1.0": { name: "@demo/library", version: "2.1.0" },
      "3.2.0": { name: "@demo/library", version: "3.2.0" },
      "4.0.0-beta.1": { name: "@demo/library", version: "4.0.0-beta.1" },
      "3.3.0-beta.2": { name: "@demo/library", version: "3.3.0-beta.2" },
    },
  }));
  expect(result.status).toBe("observed");
  expect(result.channels).toEqual({ latest: "3.2.0", next: "4.0.0-beta.1", beta: "3.3.0-beta.2" });
});

test("observes a locked prerelease on its own terms", async () => {
  const locked = inspectDirectDependency(manifest, lock, "example-prerelease");
  const result = await readPublicNpmEvidence("example-prerelease", locked, () => Response.json({
    name: "example-prerelease", "dist-tags": { latest: "3.0.0" }, versions: {
      "3.0.0-rc.1": { name: "example-prerelease", version: "3.0.0-rc.1" },
      "3.0.0": { name: "example-prerelease", version: "3.0.0" },
    },
  }));
  expect(result).toMatchObject({ status: "observed", locked_version: "listed", deprecated: false });
});

test("an unlisted locked version is never reported as yanked", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const result = await readPublicNpmEvidence("@demo/library", locked, () => Response.json({
    name: "@demo/library", "dist-tags": { latest: "3.2.0" }, versions: {
      "3.2.0": { name: "@demo/library", version: "3.2.0" },
    },
  }));
  expect(result.status).toBe("observed");
  expect(result.locked_version).toBe("unlisted");
  expect(result.deprecated).toBeNull();
  expect(result.yanked).toBeUndefined();
});

test("distinguishes a rate-limited registry from an unavailable one", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const limited = () => new Response(null, { status: 429 });
  expect((await readPublicNpmEvidence("@demo/library", locked, limited)).status).toBe("rate_limited");
});

test("serves a stale cache when the registry rate-limits the refresh", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const limited = async () => new Response(null, { status: 429 });
  const result = await readRegistryEvidenceWithCache("@demo/library", locked, cacheRecord, cacheNow, 900, limited);
  expect(result).toMatchObject({ provenance: "cache", freshness: "stale", live_status: "rate_limited" });
});

test("registry metadata contradicting the locked version is untrusted", async () => {
  const locked = inspectDirectDependency(manifest, lock, "@demo/library");
  const result = await readPublicNpmEvidence("@demo/library", locked, () => Response.json({
    name: "@demo/library", "dist-tags": { latest: "3.2.0" }, versions: {
      "2.1.0": { name: "@demo/library", version: "2.1.1" },
      "3.2.0": { name: "@demo/library", version: "3.2.0" },
    },
  }));
  expect(result.status).toBe("invalid_metadata");
});
