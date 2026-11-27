import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const DISPATCH = path.join(ROOT, "hooks", "hook_dispatch.mjs");
const GIT_HOOK = path.join(ROOT, "hooks", "git_hook.mjs");

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

test("PreInvocation returns context hint for matching prompt and status ok otherwise", () => {
  const matched = runHook(["PreInvocation"], { prompt: "Fix the CSS contrast in modal" });
  assert.equal(matched.stdout.hookSpecificOutput.hookEventName, "PreInvocation");
  assert.match(matched.stdout.hookSpecificOutput.additionalContext, /contrast/);

  const plain = runHook(["PreInvocation"], { prompt: "hello" });
  assert.deepEqual(plain.stdout, { status: "ok" });
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
      name: "replace_file_content",
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

test("git_hook commit-msg enforces Conventional Commits", () => {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), "anti-slop-msg-"));
  const msgFile = path.join(dir, "COMMIT_EDITMSG");
  try {
    fs.writeFileSync(msgFile, "feat(hooks): add pre-push preflight\n");
    const ok = spawnSync(process.execPath, [GIT_HOOK, "commit-msg", msgFile], { encoding: "utf8" });
    assert.equal(ok.status, 0, ok.stderr);

    fs.writeFileSync(msgFile, "wip stuff\n");
    const bad = spawnSync(process.execPath, [GIT_HOOK, "commit-msg", msgFile], { encoding: "utf8" });
    assert.equal(bad.status, 1);
  } finally {
    fs.rmSync(dir, { recursive: true, force: true });
  }
});
