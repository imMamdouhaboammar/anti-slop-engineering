#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import { fileURLToPath } from "node:url";

const PLUGIN_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

const FILE_TOOLS = new Set([
  "write_file",
  "edit_file",
  "Write",
  "Edit",
  "MultiEdit",
  "write_to_file",
  "replace_file_content",
  "multi_replace_file_content",
]);
const EXEMPT_PATH_RE = /(?:^|\/)(?:tests?|cases|skills|references)\/|\.(?:md|test\.[cm]?[jt]sx?|spec\.[cm]?[jt]sx?)$/i;

const SLOP_RULES = [
  {
    id: "AST_CHAINED_ASSERTION",
    pattern: new RegExp("\\bas\\s+(?:unknown|any)\\s+as\\b"),
    message: "Blocked: Chained type assertion detected. Use a type guard or schema boundary.",
  },
  {
    id: "TYPE_CHECK_SUPPRESSION",
    pattern: new RegExp(
      "(?:@" + "ts-ignore|@" + "ts-expect-error|eslint-" + "disable|oxlint-" + "disable|#\\s*noqa\\b|#\\s*type:\\s*ignore\\b)"
    ),
    message: "Blocked: Lint/type suppression directive detected. Fix the underlying type or lint issue instead of suppressing it.",
  },
  {
    id: "SILENT_EXCEPTION_SWALLOW",
    pattern: new RegExp("(?:except\\s+Exception(?:\\s+as\\s+\\w+)?\\s*:\\s*pass\\b|catch\\s*\\([^)]*\\)\\s*\\{\\s*\\})"),
    message: "Blocked: Silent exception swallowing detected. Log or propagate the error explicitly.",
  },
];

const ALWAYS_BLOCKED_RULES = [
  {
    id: "TAUTOLOGICAL_ASSERTION",
    pattern: new RegExp("\\bexpect\\s*\\(\\s*true\\s*\\)\\s*\\.toBe\\s*\\(\\s*true\\s*\\)"),
    message: "Blocked: Tautological test assertion detected.",
  },
];

const INVOCATION_HINTS = [
  {
    pattern: /\b(?:ui|css|tailwind|component|modal|button|layout|contrast|a11y|design)\b/i,
    hint: "Anti-Slop UI gates: verify contrast (>=4.5:1), exhaustive UI states, and design-integrity rules.",
  },
  {
    pattern: /\b(?:pr|pull request|commit|push|merge|release)\b/i,
    hint: "Anti-Slop PR/Git gates: run diff_guard, sre_guard, and pr-guard before pushing.",
  },
  {
    pattern: /\b(?:refactor|architecture|schema|migration|api|auth|security)\b/i,
    hint: "Anti-Slop Architecture gates: enforce KISS/DRY/YAGNI, boundary parsing, and fail-closed invariants.",
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

function evaluateSessionStart() {
  const required = [
    path.join(PLUGIN_ROOT, "bin", "cli.js"),
    path.join(PLUGIN_ROOT, "scripts", "diff_guard.py"),
    path.join(PLUGIN_ROOT, "scripts", "sre_guard.py"),
  ];
  const missing = required.filter((file) => !fs.existsSync(file));
  if (missing.length > 0) {
    process.stderr.write(`[Anti-Slop Engineering] Missing runtime files: ${missing.join(", ")}\n`);
  } else if (process.env.ANTI_SLOP_VERBOSE === "1") {
    process.stderr.write("[Anti-Slop Engineering] Plugin hooks active.\n");
  }
  return { status: "ok" };
}

function evaluatePreInvocation(data) {
  const prompt = String(data.prompt || data.user_prompt || data.message || "");
  if (!prompt.trim()) {
    return { status: "ok" };
  }
  const matched = INVOCATION_HINTS.flatMap((item) => (item.pattern.test(prompt) ? [item.hint] : []));
  if (matched.length === 0) {
    return { status: "ok" };
  }
  return {
    hookSpecificOutput: {
      hookEventName: "PreInvocation",
      additionalContext: matched.join(" "),
    },
  };
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
    respond(evaluateSessionStart(), 0);
    return;
  }

  if (event === "PreInvocation") {
    respond(parseError ? { status: "ok" } : evaluatePreInvocation(data), 0);
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
