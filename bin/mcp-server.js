#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { createInterface } from "node:readline";
import process from "node:process";
import { executeGuard } from "../drivers/driver_orchestrator.js";
import { routeNeuralQuery } from "../neural/router.js";
import { backpropagateFinding } from "../neural/backprop.js";

const SERVER_NAME = "anti-slop-engineering";
const SERVER_VERSION = "1.12.0";

const makeBaseSchema = (extra = {}) => ({
  type: "object",
  properties: {
    base: { type: "string", description: "Git base revision to compare against (default: HEAD)" },
    ...extra,
  },
});

const makePathSchema = (extra = {}) =>
  makeBaseSchema({
    path: { type: "string", description: "Target directory or file path" },
    ...extra,
  });

const TOOLS = [
  {
    name: "anti_slop_audit",
    description: "Run comprehensive multi-guard anti-slop audit across the workspace or git diff.",
    inputSchema: makeBaseSchema({
      strict: { type: "boolean", description: "Fail on warnings as well as errors" },
      guards: { type: "array", items: { type: "string" }, description: "Specific guard names to evaluate" },
    }),
  },
  {
    name: "anti_slop_diff_guard",
    description: "Evaluate git diff against base ref for KISS nesting depth, max line counts, and forbidden patterns.",
    inputSchema: makeBaseSchema(),
  },
  {
    name: "anti_slop_sre_guard",
    description: "Audit code for Google SRE violations (control flow depth > 4, functions > 80 lines, toil, blind sleeps, unhandled exceptions).",
    inputSchema: makeBaseSchema({
      file: { type: "string", description: "Specific file path to inspect" },
    }),
  },
  {
    name: "anti_slop_ast_guard",
    description: "Scan TypeScript/JavaScript for AST slop: chained casts (as unknown as T), ungrounded assertions, empty spreads, quadratic reducer copies, module mocks.",
    inputSchema: makePathSchema(),
  },
  {
    name: "anti_slop_comment_guard",
    description: "Audit Comment-to-Code Ratio (CCR <= 0.35) and flag syntax play-by-play narration comments.",
    inputSchema: makePathSchema(),
  },
  {
    name: "anti_slop_contrast_guard",
    description: "Scan source files or evaluate color hex pairs for WCAG 2.2 AA/AAA contrast compliance.",
    inputSchema: {
      type: "object",
      properties: {
        foreground: { type: "string", description: "Foreground color hex (e.g. #FFFFFF)" },
        background: { type: "string", description: "Background color hex (e.g. #0F172A)" },
        scan_path: { type: "string", description: "Source directory to scan for low-contrast color pairs" },
      },
    },
  },
  {
    name: "anti_slop_demock_guard",
    description: "Detect test doubles, mock databases, and silent SQLite dummy fallbacks on production paths.",
    inputSchema: makePathSchema(),
  },
  {
    name: "anti_slop_mandela_guard",
    description: "Audit test suites for the 8 Mandela Leakage Patterns (tautologies, circular mocks, swallowed assertion errors).",
    inputSchema: {
      type: "object",
      properties: {
        test_dir: { type: "string", description: "Directory containing tests (default: tests)" },
      },
    },
  },
  {
    name: "anti_slop_reduction_guard",
    description: "Evaluate Musk 5-step reduction algorithm compliance and inspect .anti-slop/add-back-ledger.jsonl (10%-25% target).",
    inputSchema: {
      type: "object",
      properties: {
        action: { type: "string", enum: ["status", "audit"], description: "Action to perform" },
      },
    },
  },
  {
    name: "anti_slop_re0_handoff",
    description: "Validate NVIDIA Re0 state note format (<= 1500 tokens) and audit cold-read readiness with the Shower Test.",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string", description: "Path to state note file" },
        action: { type: "string", enum: ["shower-test", "validate"], description: "Action to perform" },
      },
    },
  },
  {
    name: "anti_slop_invariant_steward",
    description: "Sync .anti-slop/invariant-ledger.json, audit architectural drift against committed invariants, and validate triggers.",
    inputSchema: makeBaseSchema({
      action: { type: "string", enum: ["sync", "drift", "audit"], description: "Action to perform" },
    }),
  },
  {
    name: "anti_slop_attention_guard",
    description: "Audit documentation, PR descriptions, or agent messages for cognitive load, scannability, deliverable purity, and terminal blocking question placement.",
    inputSchema: {
      type: "object",
      properties: {
        file: { type: "string", description: "File path to audit" },
      },
    },
  },
  {
    name: "anti_slop_neural_route",
    description: "Query the anti-slop neural connection graph for autonomous tool, invariant, and agent selection from intent or code diff.",
    inputSchema: {
      type: "object",
      properties: {
        intent: { type: "string", description: "User request or task description" },
        files: { type: "array", items: { type: "string" }, description: "Modified or target file paths" },
        diff: { type: "string", description: "Git diff snippet" },
      },
    },
  },
  {
    name: "anti_slop_backprop",
    description: "Backpropagate downstream test failures or code smells into upstream repository rules and invariant ledger.",
    inputSchema: {
      type: "object",
      required: ["type", "message"],
      properties: {
        type: { type: "string", description: "Rule or failure category identifier" },
        file: { type: "string", description: "File path where violation was discovered" },
        message: { type: "string", description: "Detail of the issue" },
        remediation: { type: "string", description: "Suggested invariant or remediation step" },
      },
    },
  },
  {
    name: "anti_slop_forensic_hunter",
    description: "Run zero-trust forensic bug hunter static scanner across 9 tech stacks for security, memory, and concurrency risks.",
    inputSchema: {
      type: "object",
      properties: {
        target_dir: { type: "string", description: "Target directory to scan" },
      },
    },
  },
];

async function handleAuditCalls(name, args) {
  if (name === "anti_slop_audit") {
    const cliArgs = ["--json"];
    if (args.base) cliArgs.push("--base", args.base);
    if (args.strict) cliArgs.push("--strict");
    if (args.guards) {
      for (const g of args.guards) cliArgs.push("--guard", g);
    }
    const res = await executeGuard("audit", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_diff_guard") {
    const cliArgs = ["--json", "--base", args.base || "HEAD"];
    const res = await executeGuard("diff", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_sre_guard") {
    const cliArgs = ["--json", "--base", args.base || "HEAD"];
    if (args.file) cliArgs.push(args.file);
    const res = await executeGuard("sre", cliArgs);
    return res.stdout || res.stderr;
  }
  return null;
}

async function handleCodeGuards(name, args) {
  if (name === "anti_slop_ast_guard") {
    const cliArgs = ["--json", "--base", args.base || "HEAD"];
    if (args.path) cliArgs.push(args.path);
    const res = await executeGuard("ast", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_comment_guard") {
    const cliArgs = ["--json", "--base", args.base || "HEAD"];
    if (args.path) cliArgs.push(args.path);
    const res = await executeGuard("comment", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_contrast_guard") {
    const cliArgs = ["--json"];
    if (args.foreground && args.background) {
      cliArgs.push(args.foreground, args.background);
    } else if (args.scan_path) {
      cliArgs.push("--scan", args.scan_path);
    }
    const res = await executeGuard("contrast", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_demock_guard") {
    const cliArgs = ["--json", "--base", args.base || "HEAD"];
    if (args.path) cliArgs.push(args.path);
    const res = await executeGuard("demock", cliArgs);
    return res.stdout || res.stderr;
  }
  return null;
}

async function handleGovernanceGuards(name, args) {
  if (name === "anti_slop_mandela_guard") {
    const cliArgs = ["--json", args.test_dir || "tests"];
    const res = await executeGuard("mandela", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_reduction_guard") {
    const cliArgs = ["--json"];
    if (args.action) cliArgs.push(args.action);
    const res = await executeGuard("reduction", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_re0_handoff") {
    const cliArgs = ["--json"];
    if (args.action) cliArgs.push(args.action);
    if (args.file) cliArgs.push(args.file);
    const res = await executeGuard("re0", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_invariant_steward") {
    const cliArgs = ["--json"];
    if (args.action) cliArgs.push(args.action);
    if (args.base) cliArgs.push("--base", args.base);
    const res = await executeGuard("steward", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_attention_guard") {
    const cliArgs = ["--json"];
    if (args.file) cliArgs.push("--file", args.file);
    const res = await executeGuard("attention", cliArgs);
    return res.stdout || res.stderr;
  }
  if (name === "anti_slop_forensic_hunter") {
    const cliArgs = ["--json"];
    if (args.target_dir) cliArgs.push(args.target_dir);
    const res = await executeGuard("hunter", cliArgs);
    return res.stdout || res.stderr;
  }
  return null;
}

async function handleToolCall(name, args = {}) {
  const auditRes = await handleAuditCalls(name, args);
  if (auditRes !== null) return auditRes;

  const codeRes = await handleCodeGuards(name, args);
  if (codeRes !== null) return codeRes;

  const govRes = await handleGovernanceGuards(name, args);
  if (govRes !== null) return govRes;

  if (name === "anti_slop_neural_route") {
    return JSON.stringify(routeNeuralQuery(args), null, 2);
  }
  if (name === "anti_slop_backprop") {
    return JSON.stringify(backpropagateFinding(args), null, 2);
  }

  throw new Error(`Unknown anti-slop tool: ${name}`);
}

function sendResponse(id, result, error = null) {
  const resp = { jsonrpc: "2.0", id };
  if (error) {
    resp.error = error;
  } else {
    resp.result = result;
  }
  process.stdout.write(JSON.stringify(resp) + "\n");
}

export function startMcpServer() {
  const rl = createInterface({
    input: process.stdin,
    output: process.stdout,
    terminal: false,
  });

  rl.on("line", async (line) => {
    const trimmed = line.trim();
    if (!trimmed) return;

    let msg;
    try {
      msg = JSON.parse(trimmed);
    } catch {
      sendResponse(null, null, { code: -32700, message: "Parse error" });
      return;
    }

    const { id, method, params } = msg;

    if (method === "initialize") {
      sendResponse(id, {
        protocolVersion: "2024-11-05",
        capabilities: { tools: {} },
        serverInfo: { name: SERVER_NAME, version: SERVER_VERSION },
      });
      return;
    }

    if (method === "notifications/initialized") return;

    if (method === "ping") {
      sendResponse(id, {});
      return;
    }

    if (method === "tools/list") {
      sendResponse(id, { tools: TOOLS });
      return;
    }

    if (method === "tools/call") {
      const toolName = params?.name;
      const toolArgs = params?.arguments || {};
      try {
        const output = await handleToolCall(toolName, toolArgs);
        sendResponse(id, {
          content: [
            {
              type: "text",
              text: typeof output === "string" ? output : JSON.stringify(output, null, 2),
            },
          ],
          isError: false,
        });
      } catch (err) {
        sendResponse(id, {
          content: [{ type: "text", text: `Error executing ${toolName}: ${err.message}` }],
          isError: true,
        });
      }
      return;
    }

    if (id !== undefined && id !== null) {
      sendResponse(id, null, { code: -32601, message: `Method not found: ${method}` });
    }
  });
}

if (process.argv[1] && process.argv[1].endsWith("mcp-server.js")) {
  startMcpServer();
}
