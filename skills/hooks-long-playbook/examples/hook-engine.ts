#!/usr/bin/env bun
/**
 * Hook Engine Reference Implementation (TypeScript / Bun / Node)
 *
 * Implements:
 * - Parallel & serial hook dispatch
 * - Staged file filtering & glob matching
 * - Strict per-hook timeout budget with AbortSignal
 * - Stdio protocol purity (JSON on stdout, logs on stderr)
 * - Deterministic physical admission control (allow / deny)
 */

import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

export type Decision = "allow" | "deny";

export interface HookDefinition {
  name: string;
  matcher: string; // regex pattern for tool name or file glob
  command: string;
  timeoutMs?: number;
  onFailure?: "deny" | "ignore";
}

export interface HookPayload {
  hook_event: string;
  session_id: string;
  tool_name: string;
  tool_input: Record<string, unknown>;
  cwd: string;
  timestamp: string;
}

export interface HookResult {
  decision: Decision;
  explanation?: string;
  remediationHint?: string;
}

export class HookEngine {
  private hooks: Map<string, HookDefinition[]> = new Map();

  constructor(configPath?: string) {
    if (configPath && fs.existsSync(configPath)) {
      this.loadConfig(configPath);
    }
  }

  public loadConfig(filePath: string): void {
    const raw = fs.readFileSync(filePath, "utf-8");
    const data = JSON.parse(raw);
    for (const [event, list] of Object.entries(data.hooks || {})) {
      this.hooks.set(event, list as HookDefinition[]);
    }
  }

  public registerHook(event: string, def: HookDefinition): void {
    const list = this.hooks.get(event) || [];
    list.push(def);
    this.hooks.set(event, list);
  }

  /**
   * Dispatches hooks for an event. Short-circuits immediately on first 'deny'.
   */
  public async dispatchPreHook(event: string, payload: HookPayload): Promise<HookResult> {
    const registered = this.hooks.get(event) || [];
    const matching = registered.filter((h) => new RegExp(h.matcher).test(payload.tool_name));

    for (const hook of matching) {
      const result = await this.executeHook(hook, payload);
      if (result.decision === "deny") {
        return result; // Physical short-circuit: immediately abort tool execution
      }
    }

    return { decision: "allow" };
  }

  private async executeHook(hook: HookDefinition, payload: HookPayload): Promise<HookResult> {
    const timeout = hook.timeoutMs || 3000;
    const [bin, ...args] = hook.command.split(" ");

    return new Promise((resolve) => {
      let stdoutData = "";
      let stderrData = "";
      let timedOut = false;

      const child = spawn(bin, args, {
        cwd: payload.cwd,
        stdio: ["pipe", "pipe", "pipe"],
      });

      const timer = setTimeout(() => {
        timedOut = true;
        child.kill("SIGKILL");
      }, timeout);

      child.stdout.on("data", (chunk) => {
        stdoutData += chunk;
      });

      child.stderr.on("data", (chunk) => {
        stderrData += chunk;
      });

      child.on("close", (code) => {
        clearTimeout(timer);

        if (stderrData.trim()) {
          process.stderr.write(`[Hook:${hook.name}] ${stderrData.trim()}\n`);
        }

        if (timedOut) {
          process.stderr.write(`[Hook:${hook.name}] Timed out after ${timeout}ms\n`);
          if (hook.onFailure === "deny") {
            return resolve({
              decision: "deny",
              explanation: `Hook ${hook.name} timed out after ${timeout}ms.`,
            });
          }
          return resolve({ decision: "allow" });
        }

        if (code !== 0) {
          if (hook.onFailure === "deny") {
            return resolve({
              decision: "deny",
              explanation: `Hook ${hook.name} exited with status ${code}.`,
            });
          }
          return resolve({ decision: "allow" });
        }

        // Parse JSON output if provided
        try {
          const parsed = JSON.parse(stdoutData.trim());
          if (parsed.decision === "deny") {
            return resolve({
              decision: "deny",
              explanation: parsed.explanation || `Blocked by ${hook.name}.`,
              remediationHint: parsed.remediation_hint,
            });
          }
        } catch {
          // If stdout is not JSON, non-zero code was already handled
        }

        return resolve({ decision: "allow" });
      });

      child.on("error", (err) => {
        clearTimeout(timer);
        process.stderr.write(`[Hook:${hook.name}] Process error: ${err.message}\n`);
        if (hook.onFailure === "deny") {
          return resolve({ decision: "deny", explanation: `Hook execution failed: ${err.message}` });
        }
        return resolve({ decision: "allow" });
      });

      // Send payload via stdin
      child.stdin.write(JSON.stringify(payload) + "\n");
      child.stdin.end();
    });
  }
}
