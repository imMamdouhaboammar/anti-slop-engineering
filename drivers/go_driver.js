// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";
import { spawnNativeBinary, pingLocalDaemon, missingBinaryResult } from "./common.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const rootDir = resolve(__dirname, "..");

export function getGoBinaryPath() {
  const nativeSuffix = process.platform === "win32" ? ".exe" : "";
  const executable = "toil-guard" + nativeSuffix;
  const paths = [
    resolve(rootDir, "dist", "bin", executable),
    resolve(rootDir, "services", "toil-guard-go", "bin", executable),
  ];
  return paths.find(existsSync) || null;
}

export function pingGoDaemon(port = 9092) {
  return pingLocalDaemon(port);
}

export function runGoGuard(args = [], options = {}) {
  const binPath = getGoBinaryPath();
  if (!binPath) return missingBinaryResult("Go Toil Guard");
  return spawnNativeBinary(binPath, args, { cwd: rootDir, ...options });
}
