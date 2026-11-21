#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import process from "node:process";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const event = process.argv[2] || "unknown";
const phase = process.argv[3] || "";

// Read hook input payload from stdin if available
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});

process.stdin.on("end", () => {
  let payload = {};
  if (input.trim()) {
    try {
      payload = JSON.parse(input.trim());
    } catch {
      payload = { raw: input.trim() };
    }
  }

  handleHook(event, phase, payload);
});

function handleHook(evt, ph, data) {
  if (evt === "SessionStart") {
    // Session start banner
    process.stderr.write(
      "🛡️  [Anti-Slop Engineering] Plugin active. 7 Gates, SRE invariants & AST guards engaged.\n"
    );
    process.stdout.write(JSON.stringify({ status: "ok" }) + "\n");
    return;
  }

  if (evt === "PreToolUse") {
    const tool = data.tool_name || data.tool || "";
    const toolInput = data.tool_input || data.input || {};

    if (tool === "write_file" || tool === "edit_file") {
      const content = toolInput.Content || toolInput.content || toolInput.Replacement || "";
      // Fast check for forbidden patterns in incoming write
      if (content.includes("as unknown as") || content.includes("as any as")) {
        process.stderr.write(
          "⚠️  [Anti-Slop Warning] Detected chained type assertion (as unknown as T / as any as T). Replace with type guard or branded type.\n"
        );
      }
    }
    process.stdout.write(JSON.stringify({ decision: "allow" }) + "\n");
    return;
  }

  if (evt === "PostToolUse") {
    const tool = data.tool_name || data.tool || "";
    if (tool === "write_file" || tool === "edit_file") {
      process.stderr.write("✓ [Anti-Slop] Code modification recorded. Self-diff verification required at turn conclusion.\n");
    }
    process.stdout.write(JSON.stringify({ status: "ok" }) + "\n");
    return;
  }

  // Fallback
  process.stdout.write(JSON.stringify({ status: "ok" }) + "\n");
}
