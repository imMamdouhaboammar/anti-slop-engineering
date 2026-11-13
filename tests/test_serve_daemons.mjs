// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar and contributors

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { once } from "node:events";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { createConnection, createServer } from "node:net";
import { tmpdir } from "node:os";
import { delimiter, join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const cli = fileURLToPath(new URL("../bin/cli.js", import.meta.url));
const deadline = 8000;
const cliRuntime = process.env.ANTI_SLOP_TEST_CLI_RUNTIME ?? process.execPath;

function startCli(t, args, env = {}) {
  const child = spawn(cliRuntime, [cli, ...args], {
    detached: true,
    env: { ...process.env, ANTI_SLOP_DISABLE_NATIVE: "", ANTI_SLOP_FORCE_FALLBACK: "", ...env },
    stdio: ["ignore", "pipe", "pipe"],
  });
  let closed = false;
  const exited = once(child, "close").then((result) => {
    closed = true;
    return result;
  });
  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8").on("data", (chunk) => { stdout += chunk; });
  child.stderr.setEncoding("utf8").on("data", (chunk) => { stderr += chunk; });

  t.after(async () => {
    if (child.pid && !closed) {
      try {
        process.kill(-child.pid, "SIGKILL");
      } catch (error) {
        if (error.code !== "ESRCH") throw error;
      }
    }
    await exited;
  });

  async function output(pattern) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), deadline);
    try {
      let match = stdout.match(pattern);
      while (!match) {
        const event = await Promise.race([
          once(child.stdout, "data", { signal: controller.signal }).then(() => "data"),
          exited.then(() => "exit"),
        ]);
        if (event === "exit" || child.exitCode !== null || child.signalCode !== null) break;
        match = stdout.match(pattern);
      }
      assert.ok(match, `Missing ${pattern} in stdout: ${stdout}\nstderr: ${stderr}`);
      return match;
    } finally {
      clearTimeout(timer);
      controller.abort();
    }
  }

  return { child, exited, output, stdout: () => stdout, stderr: () => stderr };
}

async function health(port, route = "/healthz") {
  const response = await fetch(`http://127.0.0.1:${port}${route}`, { signal: AbortSignal.timeout(deadline) });
  assert.equal(response.status, 200);
  return response;
}

async function listen(port) {
  const listener = createServer();
  listener.listen(port, "127.0.0.1");
  await once(listener, "listening");
  return listener;
}

const services = [
  { command: "serve-rust", service: "anti-slop-rust", status: "ok", shutdown: /anti-slop-rust daemon shut down/ },
  { command: "serve-go", service: "toil-guard-go", status: "healthy", shutdown: /Toil Guard daemon shut down/ },
];

for (const { command, service, status, shutdown } of services) {
  for (const signal of ["SIGINT", "SIGTERM"]) {
    test(`${command} owns its loopback listener and shuts down on ${signal}`, { timeout: 2 * deadline }, async (t) => {
      const run = startCli(t, [command, "--port", "0"]);
      const [, port] = await run.output(/(?:listening on|running on) http:\/\/127\.0\.0\.1:([1-9]\d*)\n/);
      const payload = await (await health(port)).json();
      assert.equal(payload.status, status);
      assert.equal(payload.service, service);

      if (command === "serve-rust") {
        const legacy = await (await health(port, "/health")).json();
        assert.deepEqual(legacy, payload);
      } else {
        const metrics = await (await health(port, "/metrics")).text();
        assert.match(metrics, /toil_guard_audits_total/);
      }

      assert.ok(run.child.kill(signal));
      assert.deepEqual(await onceOrExit(run), [0, null], run.stderr());
      assert.match(run.stdout(), shutdown);
      const listener = await listen(Number(port));
      await new Promise((resolve, reject) => listener.close((error) => error ? reject(error) : resolve()));
    });
  }

  test(`${command} rejects an occupied port and leaves its owner running`, { timeout: 2 * deadline }, async (t) => {
    const owner = await listen(0);
    t.after(() => new Promise((resolve, reject) => owner.close((error) => error ? reject(error) : resolve())));
    const { port } = owner.address();
    const run = startCli(t, [command, "--port", String(port)]);
    assert.deepEqual(await onceOrExit(run), [1, null]);
    assert.match(run.stderr(), /address already in use/i);
    assert.doesNotMatch(run.stdout(), /(?:listening on|running on) http/);
    assert.equal(owner.address().port, port);
  });

  test(`${command} explains how to build an unavailable native binary`, { timeout: 2 * deadline }, async (t) => {
    const run = startCli(t, [command], { ANTI_SLOP_DISABLE_NATIVE: "1" });
    assert.deepEqual(await onceOrExit(run), [1, null]);
    assert.match(run.stderr(), /binary not found.*anti-slop-engineering build/i);
  });
}

test("serve-rust bounds the time spent draining an active request", { timeout: 2 * deadline }, async (t) => {
  const run = startCli(t, ["serve-rust", "--port", "0"]);
  const [, port] = await run.output(/listening on http:\/\/127\.0\.0\.1:([1-9]\d*)\n/);
  const socket = createConnection({ host: "127.0.0.1", port: Number(port) });
  t.after(() => socket.destroy());
  await once(socket, "connect");
  socket.setEncoding("utf8");
  socket.write("POST /v1/triage HTTP/1.1\r\nHost: localhost\r\nContent-Type: application/json\r\nContent-Length: 2\r\nExpect: 100-continue\r\n\r\n");
  let response = "";
  const signal = AbortSignal.timeout(deadline);
  while (!response.includes("\r\n\r\n")) {
    const [chunk] = await once(socket, "data", { signal });
    response += chunk;
  }
  assert.match(response, /^HTTP\/1\.1 100 Continue\r\n/);
  socket.write("{");

  assert.ok(run.child.kill("SIGTERM"));
  assert.deepEqual(await onceOrExit(run), [1, null]);
  assert.match(run.stderr(), /shutdown timed out/i);
});

async function onceOrExit(run) {
  const timer = AbortSignal.timeout(deadline);
  const abort = once(timer, "abort");
  return Promise.race([
    run.exited,
    abort.then(() => assert.fail(`CLI did not exit: ${run.stdout()}\n${run.stderr()}`)),
  ]);
}

test("one-shot CLI forwards another signal and exits nonzero when interrupted", { timeout: 2 * deadline }, async (t) => {
  const bin = mkdtempSync(join(tmpdir(), "anti-slop-signal-"));
  t.after(() => rmSync(bin, { recursive: true, force: true }));
  writeFileSync(join(bin, "python3"), `#!${process.execPath}
process.on("SIGINT", () => console.log("first signal received"));
setInterval(() => {}, 1000);
console.log("child ready");
`, { mode: 0o755 });

  const run = startCli(t, ["rust", "triage"], {
    ANTI_SLOP_DISABLE_NATIVE: "1",
    PATH: bin + delimiter + process.env.PATH,
  });
  await run.output(/child ready/);
  assert.ok(run.child.kill("SIGINT"));
  await run.output(/first signal received/);
  assert.ok(run.child.kill("SIGTERM"));
  assert.deepEqual(await onceOrExit(run), [1, null]);
});

test("one-shot CLI cannot report success when the child is terminated by a signal", { timeout: 2 * deadline }, async (t) => {
  const bin = mkdtempSync(join(tmpdir(), "anti-slop-signal-"));
  t.after(() => rmSync(bin, { recursive: true, force: true }));
  writeFileSync(join(bin, "python3"), `#!${process.execPath}
process.kill(process.pid, "SIGTERM");
`, { mode: 0o755 });

  const run = startCli(t, ["rust", "triage"], {
    ANTI_SLOP_DISABLE_NATIVE: "1",
    PATH: bin + delimiter + process.env.PATH,
  });
  assert.deepEqual(await onceOrExit(run), [1, null]);
});
