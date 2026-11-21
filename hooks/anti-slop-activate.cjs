#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

const { getAntiSlopInstructions } = require('./anti-slop-instructions.cjs');
const { writeHookOutput } = require('./anti-slop-runtime.cjs');

function activate() {
  const instructions = getAntiSlopInstructions();
  try {
    process.stderr.write(
      '🛡️  [Anti-Slop Engineering] Multi-agent harness active. 7 Gates, SRE invariants & AST guards engaged.\n'
    );
  } catch (_e) {
    // Ignore stderr closed errors
  }

  writeHookOutput('SessionStart', instructions);
}

if (require.main === module) {
  activate();
}

module.exports = { activate };
