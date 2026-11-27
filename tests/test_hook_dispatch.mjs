import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DISPATCH = path.join(ROOT, "hooks", "hook_dispatch.mjs");

function runHook(args, input) {
  const result = spawnSync(process.execPath, [DISPATCH, ...args], {
    cwd: ROOT,
    input: typeof input === "string" ? input : JSON.stringify(input),
    encoding: "utf8",
  });
  assert.equal(result.status, 0, result.stderr);
  return {
    stdout: JSON.parse(result.stdout.trim()),
    stderr: result.stderr,
  };
}

test("SessionStart exits 0 silently by default", () => {
  const { stdout, stderr } = runHook(["SessionStart"], {});
  assert.deepEqual(stdout, { status: "ok" });
  assert.equal(stderr, "");
});

test("PreToolUse allows clean writes", () => {
  const { stdout } = runHook(["PreToolUse", "write"], {
    tool_name: "edit_file",
    tool_input: { Path: "src/app.ts", Replacement: "export const ok = true;" },
  });
  assert.deepEqual(stdout, { decision: "allow" });
});

test("PreToolUse blocks chained assertions and suppressions in source files", () => {
  for (const content of [
    "const x = y as unknown as string;",
    "// @ts-ignore\nconst x = 1;",
    "except Exception:\n    pass",
  ]) {
    const { stdout } = runHook(["PreToolUse", "write"], {
      tool_name: "write_file",
      tool_input: { Path: "src/module.ts", Content: content },
    });
    assert.equal(stdout.decision, "deny");
    assert.ok(stdout.reason);
  }
});

test("PreToolUse supports Antigravity toolCall payload format", () => {
  const { stdout } = runHook(["PreToolUse", "write"], {
    hookEventName: "PreToolUse",
    toolCall: {
      name: "edit_file",
      args: { Path: "src/index.ts", Replacement: "// eslint-disable-next-line" },
    },
  });
  assert.equal(stdout.decision, "deny");
});

test("PreToolUse exempts test fixtures from suppression rule but blocks tautologies", () => {
  const fixture = runHook(["PreToolUse", "write"], {
    tool_name: "write_file",
    tool_input: { Path: "tests/fixture.test.ts", Content: "// @ts-ignore" },
  });
  assert.deepEqual(fixture.stdout, { decision: "allow" });

  const tautology = runHook(["PreToolUse", "write"], {
    tool_name: "write_file",
    tool_input: { Path: "tests/fixture.test.ts", Content: "expect(true)." + "toBe(true);" },
  });
  assert.equal(tautology.stdout.decision, "deny");
});

test("PreToolUse fails closed on malformed JSON", () => {
  const { stdout } = runHook(["PreToolUse", "write"], "{not-json");
  assert.equal(stdout.decision, "deny");
});

test("PostToolUse exits 0 quietly", () => {
  const { stdout, stderr } = runHook(["PostToolUse", "write"], {
    tool_name: "edit_file",
  });
  assert.deepEqual(stdout, {});
  assert.equal(stderr, "");
});
