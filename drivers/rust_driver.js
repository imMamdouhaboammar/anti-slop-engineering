// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawnNativeBinary, pingLocalDaemon, missingBinaryResult, resolveNativeBinaryPath, rootDir } from "./common.js";

export function getRustBinaryPath() {
  return resolveNativeBinaryPath("anti-slop-rust", "services", "anti-slop-rust", "target", "release");
}

export function pingRustDaemon(port = 9091) {
  return pingLocalDaemon(port);
}

export function runRustGuard(args = [], options = {}) {
  const binPath = getRustBinaryPath();
  if (!binPath) return missingBinaryResult("Native Rust");
  return spawnNativeBinary(binPath, args, { cwd: rootDir, ...options });
}
