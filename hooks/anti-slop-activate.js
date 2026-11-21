#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { getAntiSlopInstructions } from './anti-slop-instructions.js';
import { logHookBanner, writeHookOutput } from './anti-slop-runtime.js';

export function activate(depth = 0) {
  if (depth > 5) return;
  const instructions = getAntiSlopInstructions();
  logHookBanner(
    '🛡️  [Anti-Slop Engineering] Multi-agent harness active. 7 Gates, SRE invariants & AST guards engaged.'
  );

  writeHookOutput('SessionStart', instructions);
}

activate();
