#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import process from "node:process";

const FILE_TOOLS = new Set(["write_file", "edit_file", "Write", "Edit", "MultiEdit"]);
const EXEMPT_PATH_RE = /(?:^|\/)(?:tests?|cases|skills|references)\/|\.(?:md|test\.[cm]?[jt]sx?|spec\.[cm]?[jt]sx?)$/i;

const SLOP_RULES = [
  {
    id: "AST_CHAINED_ASSERTION",
    pattern: /\bas\s+(?:unknown|any)\s+as\b/,
    message: "Blocked: Chained type assertion (`as unknown as` / `as any as`) detected. Use a type guard or schema boundary.",
  },
  {
    id: "TYPE_CHECK_SUPPRESSION",
    pattern: /(?:@ts-ignore|@ts-expect-error|eslint-disable|oxlint-disable|#\s*noqa\b|#\s*type:\s*ignore\b)/,
    message: "Blocked: Lint/type suppression directive detected. Fix the underlying type or lint issue instead of suppressing it.",
  },
  {
    id: "SILENT_EXCEPTION_SWALLOW",
    pattern: /(?:except\s+Exception(?:\s+as\s+\w+)?\s*:\s*pass\b|catch\s*\([^)]*\)\s*\{\s*\})/,
    message: "Blocked: Silent exception swallowing detected. Log or propagate the error explicitly.",
  },
];

const ALWAYS_BLOCKED_RULES = [
  {
    id: "TAUTOLOGICAL_ASSERTION",
    pattern: /\bexpect\s*\(\s*true\s*\)\s*\.toBe\s*\(\s*true\s*\)/,
    message: "Blocked: Tautological test assertion (`expect(true).toBe(true)`) detected.",
  },
];

function respond(payload, exitCode = 0) {
  process.stdout.write(JSON.stringify(payload) + "\n");
  process.exitCode = exitCode;
}

function extractContext(data) {
  const tool = data.tool_name || data.tool || data.toolCall?.name || "";
  const toolInput = data.tool_input || data.input || data.toolCall?.args || {};
  const targetPath =
    toolInput.Path ||
    toolInput.path ||
    toolInput.file_path ||
    toolInput.TargetFile ||
    "";
  const content =
    toolInput.Content ||
    toolInput.content ||
    toolInput.Replacement ||
    toolInput.ReplacementContent ||
    toolInput.new_string ||
    "";
  return { tool, targetPath: String(targetPath), content: String(content) };
}

function evaluatePreToolUse(data) {
  const { tool, targetPath, content } = extractContext(data);
  if (!FILE_TOOLS.has(tool) || !content) {
    return { decision: "allow" };
  }

  for (const rule of ALWAYS_BLOCKED_RULES) {
    if (rule.pattern.test(content)) {
      return { decision: "deny", reason: rule.message };
    }
  }

  if (!EXEMPT_PATH_RE.test(targetPath.replaceAll("\\", "/"))) {
    for (const rule of SLOP_RULES) {
      if (rule.pattern.test(content)) {
        return { decision: "deny", reason: rule.message };
      }
    }
  }

  return { decision: "allow" };
}

function handleHook(event, data, parseError) {
  if (event === "SessionStart") {
    if (process.env.ANTI_SLOP_VERBOSE === "1") {
      process.stderr.write("[Anti-Slop Engineering] Plugin hooks active.\n");
    }
    respond({ status: "ok" }, 0);
    return;
  }

  if (event === "PreToolUse") {
    if (parseError) {
      const reason = "Blocked: Malformed JSON hook payload on stdin (fail-closed).";
      respond({ decision: "deny", reason }, 0);
      return;
    }
    respond(evaluatePreToolUse(data), 0);
    return;
  }

  if (event === "PostToolUse") {
    respond({}, 0);
    return;
  }

  respond({ status: "ok" }, 0);
}

const event = process.argv[2] || "unknown";
let input = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", (chunk) => {
  input += chunk;
});
process.stdin.on("end", () => {
  let payload = {};
  let parseError = false;
  if (input.trim()) {
    try {
      const parsed = JSON.parse(input.trim());
      if (Object.prototype.toString.call(parsed) === "[object Object]") {
        payload = parsed;
      } else {
        parseError = true;
      }
    } catch {
      parseError = true;
    }
  }
  handleHook(event, payload, parseError);
});
