import { test, expect } from "bun:test";
import { inspectDirectDependency } from "../skills/grumpy-senior-staff-engineer/examples/bun-lock-evidence.mjs";

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
