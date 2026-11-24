// SPDX-License-Identifier: MIT
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { reviewTailwindDirectives } from "../skills/type-level-and-ast-slop-gate/examples/tailwind-directives-advisory.mjs";

const script = fileURLToPath(
  new URL("../skills/type-level-and-ast-slop-gate/examples/tailwind-directives-advisory.mjs", import.meta.url));

const lock = {
  status: "locked", declared: "^4.0.0", resolved: "4.1.0", release: "stable",
  installed: { status: "installed", name: "tailwindcss", version: "4.1.0" },
};
const usage = { module: "tailwindcss", idiom: "tailwind-directives", kind: "css-directives" };
const supported = ["4.1.0", "4.0.3"];

test("v3 directives on an installed Tailwind v4 receive an advisory", () => {
  const result = reviewTailwindDirectives(lock, usage, supported);
  assert.equal(result.status, "advisory");
  assert.equal(result.severity, "review");
  assert.equal(result.rule, "TAILWIND_V4_CSS_FIRST_IMPORT");
  assert.equal(result.version, "4.1.0");
  assert.equal(result.source, "https://tailwindcss.com/docs/upgrade-guide");
  assert.match(result.suggestion, /@import "tailwindcss"/);
});

test("the directives are correct on Tailwind v3 and stay applicable", () => {
  const v3Lock = {
    status: "locked", declared: "^3.4.0", resolved: "3.4.17", release: "stable",
    installed: { status: "installed", name: "tailwindcss", version: "3.4.17" },
  };
  assert.equal(reviewTailwindDirectives(v3Lock, usage, ["3.4.17"]).status, "not_applicable");
  const installedV3 = { ...lock, installed: { status: "installed", name: "tailwindcss", version: "3.4.17" } };
  const result = reviewTailwindDirectives(installedV3, usage, supported);
  assert.equal(result.status, "not_applicable");
  assert.equal(result.version, "3.4.17");
});

test("a compatibility matrix still supporting v3 is a compatibility exception", () => {
  const result = reviewTailwindDirectives(lock, usage, ["4.1.0", "3.4.17"]);
  assert.equal(result.status, "compatibility_exception");
  assert.equal(result.version, "4.1.0");
  assert.equal(result.source, "https://tailwindcss.com/docs/upgrade-guide");
});

test("missing or out-of-scope evidence is inconclusive, never an advisory", () => {
  assert.equal(reviewTailwindDirectives(lock, usage, undefined).status, "inconclusive");
  assert.equal(reviewTailwindDirectives(lock, usage, []).status, "inconclusive");
  assert.equal(reviewTailwindDirectives({ status: "stale_lock" }, usage, supported).status, "inconclusive");
  const v5Lock = { ...lock, resolved: "5.0.0", installed: { status: "installed", name: "tailwindcss", version: "5.0.0" } };
  assert.equal(reviewTailwindDirectives(v5Lock, usage, ["5.0.0"]).status, "inconclusive");
  const wrongInstalled = { ...lock, installed: { status: "installed", name: "other", version: "4.1.0" } };
  assert.equal(reviewTailwindDirectives(wrongInstalled, usage, supported).status, "inconclusive");
});

test("other idioms and modules are not applicable", () => {
  assert.equal(reviewTailwindDirectives(lock, { module: "react", idiom: "tailwind-directives", kind: "css-directives" }, supported).status, "not_applicable");
  assert.equal(reviewTailwindDirectives(lock, { module: "tailwindcss", idiom: "config-file", kind: "css-directives" }, supported).status, "not_applicable");
});

test("CLI prints the advisory verdict from evidence files", () => {
  const dir = mkdtempSync(join(tmpdir(), "tailwind-advisory-"));
  try {
    writeFileSync(join(dir, "lock.json"), JSON.stringify(lock));
    writeFileSync(join(dir, "usage.json"), JSON.stringify({ ...usage, supportedVersions: supported }));
    const output = spawnSync(process.execPath, [script, join(dir, "lock.json"), join(dir, "usage.json")],
      { encoding: "utf8" });
    assert.equal(output.status, 0, output.stderr);
    assert.equal(JSON.parse(output.stdout).status, "advisory");
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
});
