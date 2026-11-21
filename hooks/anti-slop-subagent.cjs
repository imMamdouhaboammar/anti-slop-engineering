#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

const { getAntiSlopInstructions } = require('./anti-slop-instructions.cjs');
const { writeHookOutput } = require('./anti-slop-runtime.cjs');

function activateSubagent() {
  const instructions = getAntiSlopInstructions();
  try {
    process.stderr.write(
      '🛡️  [Anti-Slop Engineering] Arming subagent with anti-slop invariants.\n'
    );
  } catch (_e) {
    // Ignore stderr closed errors
  }

  writeHookOutput('SubagentStart', instructions);
}

if (require.main === module) {
  activateSubagent();
}

module.exports = { activateSubagent };
