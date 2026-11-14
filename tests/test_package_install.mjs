// SPDX-License-Identifier: MIT

import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
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

test("packaged CLI installs offline with or without native compilers on PATH", (t) => {
  const dir = mkdtempSync(join(tmpdir(), "anti-slop-package-"));
  t.after(() => rmSync(dir, { recursive: true, force: true }));
  const archive = join(dir, "package.tgz");
  output(run("bun", ["pm", "pack", "--filename", archive, "--quiet"], { cwd: root }));
  const files = output(run("tar", ["-tzf", archive]));
  assert.doesNotMatch(files, /(?:^|\n)package\/dist\//);
  assert.match(files, /package\/services\/anti-slop-rust\/Cargo.lock/);
  assert.match(files, /package\/services\/toil-guard-go\/go.mod/);

  const npm = output(run("/bin/sh", ["-c", 'which -a npm 2>/dev/null | grep -v "$HOME/.local/bin" | grep -v "$HOME/.bun/bin" | head -n 1 || command -v npm'])).trim();
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
