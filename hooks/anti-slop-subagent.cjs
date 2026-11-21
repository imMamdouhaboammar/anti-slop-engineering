#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

const { getAntiSlopInstructions } = require('./anti-slop-instructions.cjs');
const { logHookBanner, writeHookOutput } = require('./anti-slop-runtime.cjs');

function activateSubagent(depth = 0) {
  if (depth > 5) return;
  const instructions = getAntiSlopInstructions();
  logHookBanner(
    '🛡️  [Anti-Slop Engineering] Arming subagent with anti-slop invariants.'
  );

  writeHookOutput('SubagentStart', instructions);
}

if (require.main === module) {
  activateSubagent();
}

module.exports = { activateSubagent };
