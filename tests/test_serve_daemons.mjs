// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { createServer } from "node:net";
import http from "node:http";
import { resolve } from "node:path";
import process from "node:process";
import test from "node:test";

const cliPath = resolve("bin/cli.js");

function getAvailablePort() {
  return new Promise((res, rej) => {
    const srv = createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close((err) => {
        if (err) rej(err);
        else res(port);
      });
    });
  });
}

function fetchHttp(url, timeoutMs = 3000) {
  return new Promise((res, rej) => {
    const req = http.get(url, { timeout: timeoutMs }, (response) => {
      let body = "";
      response.setEncoding("utf8");
      response.on("data", (chunk) => {
        body += chunk;
      });
      response.on("end", () => {
        res({ statusCode: response.statusCode, headers: response.headers, body });
      });
    });
    req.on("error", rej);
    req.on("timeout", () => {
      req.destroy();
      rej(new Error(`Timeout fetching ${url}`));
    });
  });
}

async function waitForHealth(url, maxWaitMs = 6000) {
  const start = Date.now();
  let lastErr = null;
  while (Date.now() - start < maxWaitMs) {
    try {
      const resp = await fetchHttp(url, 500);
      if (resp.statusCode === 200) {
        return resp;
      }
    } catch (err) {
      lastErr = err;
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error(`Service at ${url} did not become ready within ${maxWaitMs}ms: ${lastErr?.message}`);
}

function spawnDaemon(command, port, extraEnv = {}) {
  const child = spawn(process.execPath, [cliPath, command, "--port", String(port)], {
    cwd: resolve("."),
    env: { ...process.env, ...extraEnv },
    stdio: ["ignore", "pipe", "pipe"],
  });

  let stdout = "";
  let stderr = "";
  child.stdout.setEncoding("utf8").on("data", (d) => { stdout += d; });
  child.stderr.setEncoding("utf8").on("data", (d) => { stderr += d; });

  return {
    child,
    getStdout: () => stdout,
    getStderr: () => stderr,
  };
}

test("serve-rust daemon: readiness probe, localhost binding, and clean SIGTERM shutdown", async () => {
  const port = await getAvailablePort();
  const { child, getStderr } = spawnDaemon("serve-rust", port);

  try {
    // Process ownership check
    assert.ok(child.pid > 0, "Daemon process must have a valid PID");

    const healthUrl = `http://127.0.0.1:${port}/healthz`;
    const resp = await waitForHealth(healthUrl);
    assert.equal(resp.statusCode, 200);

    const payload = JSON.parse(resp.body);
    assert.equal(payload.status, "ok");
    assert.equal(payload.service, "anti-slop-rust");

    // Also verify /health backward-compatibility
    const healthLegacy = await fetchHttp(`http://127.0.0.1:${port}/health`);
    assert.equal(healthLegacy.statusCode, 200);

    // Clean shutdown via SIGTERM
    const exitPromise = new Promise((res) => {
      child.on("close", (code, signal) => res({ code, signal }));
    });

    child.kill("SIGTERM");
    const exitResult = await Promise.race([
      exitPromise,
      new Promise((_, rej) => setTimeout(() => rej(new Error("Shutdown timed out")), 5000)),
    ]);

    // Clean shutdown must terminate cleanly
    assert.ok(
      exitResult.code === 0 || exitResult.signal === "SIGTERM",
      `Expected clean shutdown, got code ${exitResult.code}, signal ${exitResult.signal}, stderr: ${getStderr()}`
    );
  } finally {
    if (!child.killed) {
      try { child.kill("SIGKILL"); } catch {}
    }
  }
});

test("serve-rust daemon: clean SIGINT shutdown", async () => {
  const port = await getAvailablePort();
  const { child, getStderr } = spawnDaemon("serve-rust", port);

  try {
    const healthUrl = `http://127.0.0.1:${port}/healthz`;
    await waitForHealth(healthUrl);

    const exitPromise = new Promise((res) => {
      child.on("close", (code, signal) => res({ code, signal }));
    });

    child.kill("SIGINT");
    const exitResult = await Promise.race([
      exitPromise,
      new Promise((_, rej) => setTimeout(() => rej(new Error("Shutdown timed out")), 5000)),
    ]);

    assert.ok(
      exitResult.code === 0 || exitResult.signal === "SIGINT",
      `Expected clean shutdown on SIGINT, got code ${exitResult.code}, signal ${exitResult.signal}, stderr: ${getStderr()}`
    );
  } finally {
    if (!child.killed) {
      try { child.kill("SIGKILL"); } catch {}
    }
  }
});

test("serve-rust daemon: port-conflict handling exits non-zero", async () => {
  const port = await getAvailablePort();
  const blocker = createServer();
  await new Promise((res) => blocker.listen(port, "127.0.0.1", res));

  try {
    const { child } = spawnDaemon("serve-rust", port);
    const exitResult = await new Promise((res) => {
      child.on("close", (code, signal) => res({ code, signal }));
    });

    // Binding to an already-in-use port must fail and exit non-zero
    assert.notEqual(exitResult.code, 0, "Daemon should fail to start when port is in use");
  } finally {
    await new Promise((res) => blocker.close(res));
  }
});

test("serve-go daemon: readiness probe, localhost binding, and clean SIGTERM shutdown", async () => {
  const port = await getAvailablePort();
  const { child, getStderr } = spawnDaemon("serve-go", port);

  try {
    assert.ok(child.pid > 0, "Daemon process must have a valid PID");

    const healthUrl = `http://127.0.0.1:${port}/healthz`;
    const resp = await waitForHealth(healthUrl);
    assert.equal(resp.statusCode, 200);

    const payload = JSON.parse(resp.body);
    assert.equal(payload.status, "healthy");
    assert.equal(payload.service, "toil-guard-go");

    // Check Prometheus /metrics endpoint is live
    const metricsResp = await fetchHttp(`http://127.0.0.1:${port}/metrics`);
    assert.equal(metricsResp.statusCode, 200);
    assert.match(metricsResp.body, /toil_guard_audits_total/);

    const exitPromise = new Promise((res) => {
      child.on("close", (code, signal) => res({ code, signal }));
    });

    child.kill("SIGTERM");
    const exitResult = await Promise.race([
      exitPromise,
      new Promise((_, rej) => setTimeout(() => rej(new Error("Shutdown timed out")), 5000)),
    ]);

    assert.ok(
      exitResult.code === 0 || exitResult.signal === "SIGTERM",
      `Expected clean shutdown, got code ${exitResult.code}, signal ${exitResult.signal}, stderr: ${getStderr()}`
    );
  } finally {
    if (!child.killed) {
      try { child.kill("SIGKILL"); } catch {}
    }
  }
});

test("serve-go daemon: clean SIGINT shutdown", async () => {
  const port = await getAvailablePort();
  const { child, getStderr } = spawnDaemon("serve-go", port);

  try {
    const healthUrl = `http://127.0.0.1:${port}/healthz`;
    await waitForHealth(healthUrl);

    const exitPromise = new Promise((res) => {
      child.on("close", (code, signal) => res({ code, signal }));
    });

    child.kill("SIGINT");
    const exitResult = await Promise.race([
      exitPromise,
      new Promise((_, rej) => setTimeout(() => rej(new Error("Shutdown timed out")), 5000)),
    ]);

    assert.ok(
      exitResult.code === 0 || exitResult.signal === "SIGINT",
      `Expected clean shutdown on SIGINT, got code ${exitResult.code}, signal ${exitResult.signal}, stderr: ${getStderr()}`
    );
  } finally {
    if (!child.killed) {
      try { child.kill("SIGKILL"); } catch {}
    }
  }
});

test("serve-go daemon: port-conflict handling exits non-zero", async () => {
  const port = await getAvailablePort();
  const blocker = createServer();
  await new Promise((res) => blocker.listen(port, "127.0.0.1", res));

  try {
    const { child } = spawnDaemon("serve-go", port);
    const exitResult = await new Promise((res) => {
      child.on("close", (code, signal) => res({ code, signal }));
    });

    assert.notEqual(exitResult.code, 0, "Daemon should fail to start when port is in use");
  } finally {
    await new Promise((res) => blocker.close(res));
  }
});

test("serve-* commands with native disabled report actionable error without unhandled crash", async () => {
  const port = await getAvailablePort();
  for (const cmd of ["serve-rust", "serve-go"]) {
    const { child, getStderr } = spawnDaemon(cmd, port, { ANTI_SLOP_DISABLE_NATIVE: "1" });
    const exitResult = await new Promise((res) => {
      child.on("close", (code) => res(code));
    });

    assert.equal(exitResult, 1);
    assert.match(getStderr(), /binary not found|Run 'bunx anti-slop-engineering build'/i);
  }
});
