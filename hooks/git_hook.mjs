#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawnSync } from "node:child_process";
import fs from "node:fs";
import process from "node:process";

const SUPPRESSION_RE = new RegExp(
  "(?:oxlint-" +
    "disable|eslint-" +
    "disable|@" +
    "ts-ignore|@" +
    "ts-expect-error|#\\s*noqa\\b|#\\s*type:\\s*ignore\\b|\\bas\\s+unknown\\s+as\\b)"
);
const SECRET_RE = /(?:-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,})/;
const CONVENTIONAL_RE = /^(?:feat|fix|chore|docs|refactor|test|ci|build|perf|style|revert)(?:\([a-z0-9._/-]+\))?!?: .{1,100}$/;

function run(cmd, args) {
  return spawnSync(cmd, args, { encoding: "utf8" });
}

function preCommit() {
  const diff = run("git", [
    "diff",
    "--cached",
    "-U0",
    "--",
    ".",
    ":!*.md",
    ":!tests/**",
    ":!test/**",
    ":!cases/**",
    ":!skills/**",
    ":!references/**",
    ":!hooks/git_hook.mjs",
    ":!hooks/hook_dispatch.mjs",
    ":!scripts/repo_fortress_guard.py",
  ]);
  if (diff.status !== 0) {
    process.stderr.write(`[anti-slop pre-commit] Failed to inspect staged diff: ${diff.stderr}\n`);
    return 1;
  }

  const violations = [];
  let currentFile = "";
  for (const line of diff.stdout.split("\n")) {
    if (line.startsWith("+++ b/")) {
      currentFile = line.slice(6);
      continue;
    }
    if (!line.startsWith("+") || line.startsWith("+++")) continue;
    const added = line.slice(1);
    if (SUPPRESSION_RE.test(added)) {
      violations.push(`anti-suppression (${currentFile}): ${added.trim().slice(0, 100)}`);
    }
    if (SECRET_RE.test(added)) {
      violations.push(`secret-leak (${currentFile}): potential credential/private key in staged diff`);
    }
  }

  if (violations.length > 0) {
    process.stderr.write("[anti-slop pre-commit] BLOCKED:\n");
    for (const item of violations) {
      process.stderr.write(`  - ${item}\n`);
    }
    return 1;
  }
  return 0;
}

function commitMsg(msgFile) {
  if (!msgFile || !fs.existsSync(msgFile)) {
    process.stderr.write("[anti-slop commit-msg] Missing commit message file.\n");
    return 1;
  }
  const firstLine = fs.readFileSync(msgFile, "utf8").split(/\r?\n/, 1)[0].trim();
  if (firstLine.startsWith("Merge ") || firstLine.startsWith("Revert ")) {
    return 0;
  }
  if (!CONVENTIONAL_RE.test(firstLine)) {
    process.stderr.write(
      `[anti-slop commit-msg] BLOCKED: '${firstLine}' must match Conventional Commits (type(scope): subject <= 100 chars).\n`
    );
    return 1;
  }
  return 0;
}

function prePush() {
  const checks = [
    ["python3", ["scripts/bump_version.py", "--check"]],
    ["ruff", ["check", "."]],
    ["node", ["--test", "tests/test_hook_dispatch.mjs"]],
  ];
  for (const [cmd, args] of checks) {
    const res = run(cmd, args);
    if (res.status !== 0) {
      process.stderr.write(`[anti-slop pre-push] BLOCKED by ${cmd} ${args.join(" ")}:\n`);
      process.stderr.write((res.stderr || res.stdout || "").slice(0, 1500) + "\n");
      return 1;
    }
  }
  return 0;
}

const phase = process.argv[2];
if (phase === "pre-commit") {
  process.exitCode = preCommit();
} else if (phase === "commit-msg") {
  process.exitCode = commitMsg(process.argv[3]);
} else if (phase === "pre-push") {
  process.exitCode = prePush();
} else {
  process.stderr.write("Usage: git_hook.mjs <pre-commit|commit-msg|pre-push> [args]\n");
  process.exitCode = 1;
}
