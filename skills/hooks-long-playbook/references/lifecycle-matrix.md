# Lifecycle Event Taxonomy & Payload Matrix

This reference provides exact input/output contracts, latency budgets, and failure policies for every stage of the tool and agent lifecycle.

---

## 1. Complete Event Lifecycle Matrix

| Event Name | Trigger Point | Recommended Timeout | Failure Policy | Expected Return Shape |
| :--- | :--- | :--- | :--- | :--- |
| **`SessionStart`** | Bootstrapping a session or container | 500ms | Fail-Closed | `{ "status": "ok", "context_injections": [...] }` |
| **`PreInvocation`** | User prompt submitted before agent turns | 300ms | Fail-Open | `{ "status": "ok", "suggested_skills": [...], "mcp_servers": [...] }` |
| **`PreToolUse`** | Right before tool/command execution | 200ms | **Fail-Closed** | `{ "decision": "allow"\|"deny", "explanation": "...", "remediation": "..." }` |
| **`PostToolUse`** | Immediately after tool returns results | 1000ms | Fail-Open | `{ "status": "ok", "telemetry": { ... } }` |
| **`ToolError`** | On tool crash, timeout, or runtime error | 500ms | Fail-Open | `{ "status": "ok", "fallback_action": "..." }` |
| **`PreCommit`** | Local Git commit attempt on staged delta | 2000ms | **Fail-Closed** | Exit Code `0` (Pass) or `1` (Abort commit) |
| **`CommitMsg`** | Validating `.git/COMMIT_EDITMSG` text | 100ms | **Fail-Closed** | Exit Code `0` (Valid format) or `1` (Reject message) |
| **`PrePush`** | Git push before remote transmission | 30000ms | **Fail-Closed** | Exit Code `0` (Tests pass) or `1` (Reject push) |
| **`SessionEnd`** | Session termination or context compaction | 1000ms | Fail-Open | `{ "status": "ok", "persisted_state": { ... } }` |

---

## 2. Standardized JSON Payloads

### `PreToolUse` Input Payload (Host -> Hook via `stdin`):
```json
{
  "hook_event": "PreToolUse",
  "session_id": "1c412e63-abaf-474a-9de0-6e117c382188",
  "tool_name": "write_file",
  "tool_input": {
    "Path": "/Users/user/workspace/src/domain.ts",
    "Content": "export interface User { id: string; }"
  },
  "cwd": "/Users/user/workspace",
  "timestamp": "2026-11-27T20:25:00.000Z"
}
```

### `PreToolUse` Allowed Output (Hook -> Host via `stdout`):
```json
{
  "decision": "allow",
  "explanation": "Type checks and AST safety assertions pass cleanly."
}
```

### `PreToolUse` Denied Output (Hook -> Host via `stdout`):
```json
{
  "decision": "deny",
  "explanation": "Blocked: File contains unpulled changes on GitHub (HEAD..@{u}).",
  "remediation_hint": "Run 'git pull --rebase' to reconcile remote changes before editing."
}
```

### `PostToolUse` Payload (Host -> Hook via `stdin`):
```json
{
  "hook_event": "PostToolUse",
  "session_id": "1c412e63-abaf-474a-9de0-6e117c382188",
  "tool_name": "write_file",
  "tool_input": {
    "Path": "/Users/user/workspace/src/domain.ts"
  },
  "tool_output": {
    "status": "success",
    "bytes_written": 42
  },
  "execution_duration_ms": 12,
  "cwd": "/Users/user/workspace"
}
```
