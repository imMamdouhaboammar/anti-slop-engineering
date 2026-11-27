// SPDX-License-Identifier: MIT

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, realpathSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { performance } from "node:perf_hooks";
import test from "node:test";

const root = fileURLToPath(new URL("..", import.meta.url));
const packageName = "anti-slop-engineering";

function run(executable, args, options = {}) {
  return spawnSync(executable, args, { encoding: "utf8", timeout: 30000, ...options });
}

function output(result) {
  assert.ifError(result.error);
  assert.equal(result.status, 0, result.stdout + result.stderr);
  return result.stdout;
}

function realNpm() {
  const npm = join(dirname(realpathSync(process.execPath)), "npm");
  assert.ok(existsSync(npm), "Install real npm alongside Node for npm package compatibility tests");
  return npm;
}

test("packaged CLI installs offline with or without native compilers on PATH", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "anti-slop-package-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const archive = join(dir, "package.tgz");
  output(run("bun", ["pm", "pack", "--filename", archive, "--quiet"], { cwd: root }));
  const files = output(run("tar", ["-tzf", archive]));
  assert.doesNotMatch(files, /(?:^|\n)package\/dist\//);
  assert.match(files, /package\/services\/anti-slop-rust\/Cargo.lock/);
  assert.match(files, /package\/services\/toil-guard-go\/go.mod/);

  const npm = realNpm();
  const python = output(run("/bin/sh", ["-c", "command -v python3"])).trim();
  const bash = output(run("/bin/sh", ["-c", "command -v bash"])).trim();

  for (const toolchains of ["absent", "present"]) {
    const project = join(dir, toolchains);
    const bin = join(project, "bin");
    const marker = join(project, "unexpected-tool");
    mkdirSync(bin, { recursive: true });
    writeFileSync(join(project, "package.json"), '{"name":"anti-slop-smoke","private":true}\n');
    symlinkSync(process.execPath, join(bin, "node"));
    symlinkSync("/bin/sh", join(bin, "sh"));
    if (bash) symlinkSync(bash, join(bin, "bash"));
    symlinkSync(python, join(bin, "python3"));

    const commands = toolchains === "present" ? ["cargo", "go", "bunx", "npx"] : ["bunx", "npx"];
    for (const command of commands) {
      writeFileSync(join(bin, command), '#!/bin/sh\n: > "$ANTI_SLOP_TEST_MARKER"\nexit 1\n', { mode: 0o755 });
    }
    const options = {
      cwd: project,
      env: {
        ...process.env,
        PATH: bin,
        HOME: project,
        CI: "",
        NODE_ENV: "",
        ANTI_SLOP_DISABLE_NATIVE: "",
        ANTI_SLOP_FORCE_FALLBACK: "",
        ANTI_SLOP_TEST_MARKER: marker,
        npm_config_cache: join(project, "cache"),
        npm_config_userconfig: join(project, ".npmrc"),
      },
    };

    const started = performance.now();
    const install = output(run(npm, ["install", "--offline", "--no-audit", "--no-fund", "--foreground-scripts", archive], options));
    t.diagnostic(`Offline install with compilers ${toolchains}: ${Math.round(performance.now() - started)} ms`);
    assert.match(install, /Package ready/);
    assert.equal(existsSync(marker), false);
    assert.equal(existsSync(join(project, ".codex")), false);

    const installed = join(project, "node_modules", packageName);
    const cli = join(project, "node_modules", ".bin", packageName);
    const { version } = JSON.parse(readFileSync(join(installed, "package.json"), "utf8"));
    assert.equal(output(run(cli, ["--version"], options)).trim(), version);
    const missingNative = run(cli, ["serve-rust"], options);
    assert.equal(missingNative.status, 1);
    assert.match(missingNative.stderr, /binary not found.*anti-slop-engineering build/i);

    output(run(cli, ["setup", "--agent=codex", "--skills=core", "--json"], options));
    assert.ok(existsSync(join(project, ".codex", "skills", packageName, "SKILL.md")));
    assert.equal(existsSync(marker), false);
  }
});

test("packaged CLI requires consent before updating a tracked instruction file", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "anti-slop-package-consent-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const archive = join(dir, "package.tgz");
  output(run("bun", ["pm", "pack", "--filename", archive, "--quiet"], { cwd: root }));
  const npm = output(run("/bin/sh", ["-c", "command -v npm"])).trim();

  const project = join(dir, "project");
  mkdirSync(project, { recursive: true });
  writeFileSync(join(project, "package.json"), '{"name":"anti-slop-consent","private":true}\n');
  const entry = join(project, "AGENTS.md");
  const original = "# Project\n\nHand-written instructions.\n";
  writeFileSync(entry, original);
  const git = (args) => output(run("git", args, { cwd: project }));
  git(["init", "-q", "."]);
  git(["config", "user.email", "test@example.com"]);
  git(["config", "user.name", "Test"]);
  git(["add", "AGENTS.md"]);
  git(["commit", "-qm", "init"]);

  const options = {
    cwd: project,
    env: {
      ...process.env,
      HOME: project,
      CI: "true",
      npm_config_cache: join(project, "cache"),
      npm_config_userconfig: join(project, ".npmrc"),
    },
  };
  output(run(npm, ["install", "--offline", "--no-audit", "--no-fund", "--foreground-scripts", archive], options));
  const cli = join(project, "node_modules", ".bin", packageName);

  const dry = JSON.parse(output(run(cli, ["setup", "--agent=codex", "--skills=core", "--dry-run", "--json"], options)));
  assert.equal(dry.pointers.length, 1);
  assert.equal(dry.pointers[0].action, "update");
  assert.equal(dry.pointers[0].tracked, true);
  assert.equal(dry.pointers[0].requiresConsent, true);
  assert.equal(readFileSync(entry, "utf8"), original);

  const blocked = run(cli, ["setup", "--agent=codex", "--skills=core", "--json"], options);
  assert.equal(blocked.status, 1);
  assert.match(blocked.stderr, /--update-instructions/);
  assert.equal(readFileSync(entry, "utf8"), original);
  assert.equal(existsSync(join(project, ".codex")), false);

  output(run(cli, ["setup", "--agent=codex", "--skills=core", "--update-instructions", "--json"], options));
  const updated = readFileSync(entry, "utf8");
  assert.match(updated, /anti-slop-engineering:start/);
  assert.match(updated, /Hand-written instructions\./);
});

test("packaged npm install gives an actionable hook diagnostic and a skills-only path", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "anti-slop-package-hooks-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const archive = join(dir, "package.tgz");
  output(run("bun", ["pm", "pack", "--filename", archive, "--quiet"], { cwd: root }));
  const project = join(dir, "project");
  mkdirSync(project, { recursive: true });
  writeFileSync(join(project, "package.json"), '{"name":"anti-slop-hooks","private":true}\n');
  const npm = realNpm();
  const options = {
    cwd: project,
    env: {
      ...process.env,
      HOME: project,
      CI: "",
      NODE_ENV: "",
      npm_config_cache: join(project, "cache"),
      npm_config_userconfig: join(project, ".npmrc"),
    },
  };
  output(run(npm, ["install", "--offline", "--no-audit", "--no-fund", "--foreground-scripts", archive], options));
  const cli = join(project, "node_modules", ".bin", packageName);
  const base = ["install", "--agent=codex", "--skills=core", "--scope=project", "--codex-hooks", "--dry-run", "--json"];

  const hooks = run(cli, [...base, "--enforcement=advisory"], options);
  assert.notEqual(hooks.status, 0, hooks.stdout);
  const diagnostic = hooks.stdout + hooks.stderr;
  assert.match(diagnostic, /no \.git directory/);
  assert.match(diagnostic, /git clone https:\/\/github\.com\/imMamdouhaboammar\/anti-slop-engineering/);
  assert.match(diagnostic, /skills-only/);
  assert.equal(existsSync(join(project, ".codex")), false);

  const skillsOnly = JSON.parse(output(run(cli, [...base, "--enforcement=skills-only"], options)));
  assert.equal(skillsOnly.hookPlan.status, "skills_only");
  assert.equal(existsSync(join(project, ".codex")), false);
});

test("packaged CLI keeps version parity and user-facing guard surfaces", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "anti-slop-package-consistency-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const archive = join(dir, "package.tgz");
  output(run("bun", ["pm", "pack", "--filename", archive, "--quiet"], { cwd: root }));
  const project = join(dir, "project");
  mkdirSync(project, { recursive: true });
  writeFileSync(join(project, "package.json"), '{"name":"anti-slop-consistency","private":true}\n');
  const npm = realNpm();
  const options = {
    cwd: project,
    env: {
      ...process.env,
      HOME: project,
      CI: "",
      NODE_ENV: "",
      npm_config_cache: join(project, "cache"),
      npm_config_userconfig: join(project, ".npmrc"),
    },
  };
  output(run(npm, ["install", "--offline", "--no-audit", "--no-fund", "--foreground-scripts", archive], options));
  const installed = join(project, "node_modules", packageName);
  const cli = join(project, "node_modules", ".bin", packageName);
  const { version } = JSON.parse(readFileSync(join(installed, "package.json"), "utf8"));

  output(run(cli, ["setup", "--agent=codex", "--skills=core", "--json"], options));
  const skillDir = join(project, ".codex", "skills", packageName);
  assert.equal(readFileSync(join(skillDir, "VERSION"), "utf8").trim(), version);
  const skillMd = readFileSync(join(skillDir, "SKILL.md"), "utf8");
  assert.ok(skillMd.includes(`version: "${version}"`), "installed SKILL.md version must match package.json");

  const sreHelp = output(run(cli, ["sre", "--help"], options));
  assert.match(sreHelp, /usage: anti-slop-engineering sre/);
  assert.doesNotMatch(sreHelp, /sre_guard\.py/);
  const astHelp = output(run(cli, ["ast", "--help"], options));
  assert.match(astHelp, /usage: anti-slop-engineering ast/);
  assert.doesNotMatch(astHelp, /ast_slop_guard\.py/);

  writeFileSync(join(project, "a.ts"), "export const a: number = 1;\n");
  writeFileSync(join(project, "b.ts"), "export const b: number = 2;\n");
  const multi = JSON.parse(output(run(cli, ["ast", "a.ts", "b.ts", "--json"], options)));
  assert.equal(multi.mode, "files");
  assert.match(multi.target, /a\.ts/);
  assert.match(multi.target, /b\.ts/);

  const invalid = run(cli, ["ast", "--nonsense"], options);
  assert.equal(invalid.status, 2);
  assert.match(invalid.stderr, /usage: anti-slop-engineering ast/);
});
