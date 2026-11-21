// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, "..");
const scriptsDir = resolve(rootDir, "scripts");

/**
 * Execute a Python-based anti-slop guard script.
 */
export function runPythonGuard(scriptName, args = [], options = {}) {
  return new Promise((resolvePromise) => {
    const scriptPath = resolve(scriptsDir, scriptName);
    if (!existsSync(scriptPath)) {
      return resolvePromise({
        exitCode: 1,
        stdout: "",
        stderr: `Script not found: ${scriptPath}`,
        json: null,
      });
    }

    const py = process.env.PYTHON || "python3";
    const proc = spawn(py, [scriptPath, ...args], {
      cwd: options.cwd || rootDir,
      env: Object.assign({}, process.env, options.env),
      stdio: ["pipe", "pipe", "pipe"],
    });

    let bufOut = "";
    let bufErr = "";
    const limit = options.timeoutMs || 30000;
    const timer = setTimeout(() => {
      proc.kill("SIGKILL");
      bufErr += `\n[TIMEOUT] Execution exceeded ${limit}ms`;
    }, limit);

    proc.stdout.on("data", (chunk) => { bufOut += chunk; });
    proc.stderr.on("data", (chunk) => { bufErr += chunk; });

    proc.on("close", (code) => {
      clearTimeout(timer);
      let parsed = null;
      try {
        parsed = JSON.parse(bufOut.trim());
      } catch {
        parsed = null;
      }
      resolvePromise({ exitCode: code ?? 1, stdout: bufOut, stderr: bufErr, json: parsed });
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      resolvePromise({ exitCode: 1, stdout: "", stderr: err.message, json: null });
    });
  });
}
