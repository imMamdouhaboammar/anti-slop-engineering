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

export function getRustBinaryPath() {
  const nativeSuffix = process.platform === "win32" ? ".exe" : "";
  const executable = "anti-slop-rust" + nativeSuffix;
  const paths = [
    resolve(rootDir, "dist", "bin", executable),
    resolve(rootDir, "services", "anti-slop-rust", "target", "release", executable),
  ];
  return paths.find(existsSync) || null;
}

export function pingRustDaemon(port = 9091) {
  return pingLocalDaemon(port);
}

export function runRustGuard(args = [], options = {}) {
  const binPath = getRustBinaryPath();
  if (!binPath) return missingBinaryResult("Native Rust");
  return spawnNativeBinary(binPath, args, { cwd: rootDir, ...options });
}
