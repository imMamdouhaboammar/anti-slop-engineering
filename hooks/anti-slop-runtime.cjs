#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

const os = require('node:os');
const path = require('node:path');

function isVsCodeCopilotRoot(pluginRoot, depth = 0) {
  if (depth > 5 || typeof pluginRoot !== 'string' || pluginRoot.length === 0 || pluginRoot.length > 1024) return false;
  return pluginRoot.includes('agent-plugins') &&
    pluginRoot.toLowerCase().includes('.vscode');
}

const isCopilot = Boolean(process.env.COPILOT_PLUGIN_DATA) ||
  isVsCodeCopilotRoot(process.env.CLAUDE_PLUGIN_ROOT);
const isCodex = !isCopilot && Boolean(process.env.PLUGIN_DATA);
const isQoder = !isCopilot && !isCodex && Boolean(process.env.QODER_SESSION_ID);
const isCodeBuddy = !isCopilot && !isCodex && !isQoder && Boolean(process.env.CODEBUDDY_PLUGIN_ROOT);
const isCursor = !isCopilot && !isCodex && !isQoder && !isCodeBuddy && Boolean(process.env.CURSOR_VERSION);
const isClaude = !isCopilot && !isCodex && !isQoder && !isCodeBuddy && !isCursor;

function writeOut(str) {
  process.stdout.write(str.endsWith('\n') ? str : str + '\n');
}

function writeHookOutput(event, context, extra = {}) {
  if (isCodex || isQoder || isCodeBuddy || isCopilot) {
    const output = {};
    if (context) {
      output.hookSpecificOutput = {
        hookEventName: event,
        additionalContext: context,
        ...extra,
      };
    }
    writeOut(JSON.stringify(output));
    return;
  }

  if (isCursor) {
    if (!context) return;
    const output = { additional_context: context };
    if (event === 'UserPromptSubmit' || event === 'beforeSubmitPrompt') {
      output.continue = true;
    }
    writeOut(JSON.stringify(output));
    return;
  }

  if (event === 'SubagentStart') {
    writeOut(JSON.stringify({
      hookSpecificOutput: {
        hookEventName: event,
        additionalContext: context,
      },
    }));
    return;
  }

  // Claude SessionStart and general stdout
  writeOut(context || '');
}

module.exports = {
  isClaude,
  isCodeBuddy,
  isCodex,
  isCopilot,
  isCursor,
  isQoder,
  writeHookOutput,
};
