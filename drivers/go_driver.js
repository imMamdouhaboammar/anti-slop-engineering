// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { spawnNativeBinary, pingLocalDaemon, missingBinaryResult, resolveNativeBinaryPath, rootDir } from "./common.js";

export function getGoBinaryPath() {
  return resolveNativeBinaryPath("toil-guard", "services", "toil-guard-go", "bin");
}

export function pingGoDaemon(port = 9092) {
  return pingLocalDaemon(port);
}

export function runGoGuard(args = [], options = {}) {
  const binPath = getGoBinaryPath();
  if (!binPath) return missingBinaryResult("Go Toil Guard");
  return spawnNativeBinary(binPath, args, { cwd: rootDir, ...options });
}
