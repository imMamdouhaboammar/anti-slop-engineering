#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { cpSync, existsSync, mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const skillRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = resolve(skillRoot, "assets/anti-slop");
const arguments_ = process.argv.slice(2);
const targetArgument = arguments_.find((arg) => !arg.startsWith("--"));
const target = resolve(process.cwd(), targetArgument ?? "tools/oxlint/anti-slop");
const apply = arguments_.includes("--apply") || arguments_.includes("--force");
const dryRun = !apply;

if (!existsSync(target)) {
  console.error(`Target directory not found: ${target}`);
  console.error(`To perform a fresh installation, run: npx anti-slop-engineering install-oxlint [target]`);
  process.exit(1);
}

function getAllFiles(dir, baseDir = dir) {
  const results = [];
  if (!existsSync(dir)) return results;
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const fullPath = join(dir, entry.name);
    if (entry.isDirectory()) {
      results.push(...getAllFiles(fullPath, baseDir));
    } else {
      results.push(relative(baseDir, fullPath));
    }
  }
  return results;
}

const upstreamFiles = getAllFiles(source).sort();
const localFiles = getAllFiles(target).sort();

const localSet = new Set(localFiles);
const upstreamSet = new Set(upstreamFiles);

const newUpstream = upstreamFiles.filter((f) => !localSet.has(f));
const localOnly = localFiles.filter((f) => !upstreamSet.has(f));
const shared = upstreamFiles.filter((f) => localSet.has(f));

const modified = [];
const identical = [];

for (const rel of shared) {
  const upContent = readFileSync(join(source, rel), "utf8");
  const locContent = readFileSync(join(target, rel), "utf8");
  if (upContent === locContent) {
    identical.push(rel);
  } else {
    modified.push(rel);
  }
}

console.log(`--- Anti-Slop Vendored Update Reconciliation ---`);
console.log(`Target: ${target}`);
console.log(`Mode:   ${dryRun ? "DRY-RUN (use --apply to write changes)" : "APPLYING CHANGES"}`);
console.log(`Status summary:`);
console.log(`  Identical files:        ${identical.length}`);
console.log(`  New upstream files:     ${newUpstream.length}`);
console.log(`  Local custom files:     ${localOnly.length}`);
console.log(`  Modified shared files:  ${modified.length}`);

if (newUpstream.length > 0) {
  console.log(`\nNew upstream rules/modules to adopt:`);
  for (const f of newUpstream) {
    console.log(`  + ${f}`);
    if (apply) {
      const destFile = join(target, f);
      mkdirSync(dirname(destFile), { recursive: true });
      cpSync(join(source, f), destFile);
    }
  }
}

if (localOnly.length > 0) {
  console.log(`\nPreserving local-only customizations:`);
  for (const f of localOnly) {
    console.log(`  * ${f} (retained)`);
  }
}

if (modified.length > 0) {
  console.log(`\nModified shared files:`);
  for (const f of modified) {
    console.log(`  ~ ${f}`);
    if (apply && arguments_.includes("--force")) {
      const destFile = join(target, f);
      cpSync(join(source, f), destFile);
      console.log(`    -> Overwritten (--force)`);
    } else if (apply) {
      console.log(`    -> Skipped to preserve local modifications (use --force to overwrite)`);
    }
  }
}

if (apply) {
  const upstreamMd = join(target, "UPSTREAM.md");
  const provenance = `# Anti-Slop Provenance Record
Last updated: ${new Date().toISOString()}
Target: ${target}
Upstream Version: Latest bundled in anti-slop-engineering
New rules adopted: ${newUpstream.length}
Local custom files preserved: ${localOnly.length}
`;
  writeFileSync(upstreamMd, provenance, "utf8");
  console.log(`\nProvenance updated at: ${upstreamMd}`);
}

console.log(`\nUpdate reconciliation completed.`);
