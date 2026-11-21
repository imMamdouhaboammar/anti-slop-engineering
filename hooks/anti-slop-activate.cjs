#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

const { getAntiSlopInstructions } = require('./anti-slop-instructions.cjs');
const { logHookBanner, writeHookOutput } = require('./anti-slop-runtime.cjs');

function activate(depth = 0) {
  if (depth > 5) return;
  const instructions = getAntiSlopInstructions();
  logHookBanner(
    '🛡️  [Anti-Slop Engineering] Multi-agent harness active. 7 Gates, SRE invariants & AST guards engaged.'
  );

  writeHookOutput('SessionStart', instructions);
}

if (require.main === module) {
  activate();
}

module.exports = { activate };
