// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawn } from "node:child_process";
import process from "node:process";

/**
 * Spawns a native binary and collects output.
 */
export function spawnNativeBinary(binPath, args = [], options = {}) {
  return new Promise((resolvePromise) => {
    const child = spawn(binPath, args, {
      cwd: options.cwd || process.cwd(),
      env: { ...process.env, ...options.env },
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => { stdout += chunk.toString(); });
    child.stderr.on("data", (chunk) => { stderr += chunk.toString(); });

    child.on("close", (code) => {
      resolvePromise({
        exitCode: code ?? 1,
        stdout,
        stderr,
        available: true,
      });
    });

    child.on("error", (err) => {
      resolvePromise({
        exitCode: 1,
        stdout: "",
        stderr: err.message,
        available: false,
      });
    });
  });
}

/**
 * Pings an HTTP daemon on local port.
 */
export async function pingLocalDaemon(port, path = "/healthz") {
  let isAlive = false;
  try {
    const res = await fetch(`http://127.0.0.1:${port}${path}`, {
      signal: AbortSignal.timeout(500),
    });
    isAlive = Boolean(res.ok);
  } catch {
    isAlive = false;
  }
  return isAlive;
}

/**
 * Common missing binary failure response.
 */
export function missingBinaryResult(label) {
  return Promise.resolve({
    exitCode: 1,
    stdout: "",
    stderr: `${label} binary not found. Build via 'bun run build'.`,
    available: false,
  });
}
