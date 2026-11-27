# Hook Security, Sandboxing & Invariant Defense

Lifecycle hooks have access to system processes, filesystems, and execution environments. This document establishes mandatory security invariants to prevent command injection, directory traversal, privilege escalation, and execution deadlocks.

---

## 1. Zero-Trust Input Boundary

### Never Trust Tool Inputs Inside Hooks
File paths, arguments, and content emitted by LLMs or external tools can be adversarial.

#### Path Traversal Protection
```typescript
import path from "node:path";
import fs from "node:fs";

export function assertWithinWorkspace(targetPath: string, workspaceRoot: string): string {
  const canonicalRoot = fs.realpathSync(workspaceRoot);
  const resolvedTarget = path.resolve(canonicalRoot, targetPath);

  // Must not escape root
  if (!resolvedTarget.startsWith(canonicalRoot + path.sep) && resolvedTarget !== canonicalRoot) {
    throw new SecurityError(`Access denied: Target path "${targetPath}" escapes workspace root "${workspaceRoot}".`);
  }
  return resolvedTarget;
}
```

---

## 2. Shell Injection Defense

### Never Interpolate Variables into Shell Command Strings
Using `child_process.exec()` or `system()` with string concatenation allows arbitrary command execution:

```javascript
// ❌ CRITICAL SECURITY VULNERABILITY
// If targetPath is "file.txt; rm -rf /", catastrophic execution occurs!
execSync(`python3 guard.py --file ${targetPath}`);
```

### Compliant Execution via Argument Arrays
```javascript
// ✅ IMMUNE TO SHELL INJECTION
// Path is passed as a discrete argument to execve, never interpreted by a shell
import { spawn } from "node:child_process";

const child = spawn("python3", ["guard.py", "--file", targetPath], {
  stdio: ["pipe", "pipe", "pipe"],
  timeout: 3000
});
```

---

## 3. Stdio Isolation & Protocol Purity

LSP, MCP, and CLI tool interfaces rely on structured JSON over `stdout`.

1. **`stdout` is strictly for JSON-RPC**:
   ```javascript
   // Output ONLY the final machine contract
   process.stdout.write(JSON.stringify(verdict) + "\n");
   ```

2. **`stderr` is strictly for Human Logs**:
   ```javascript
   // All informational messages, debug logs, and warnings MUST go to stderr
   process.stderr.write("🛡️ [Guard] Scanning staged changes for secrets...\n");
   ```

3. **Silent Crash Prevention**:
   Trap all unhandled exceptions and serialize a machine-readable rejection rather than dumping stack traces to `stdout`:
   ```javascript
   process.on("uncaughtException", (err) => {
     process.stderr.write(`Unhandled hook exception: ${err.stack}\n`);
     process.stdout.write(JSON.stringify({
       decision: "deny",
       explanation: `Internal hook error: ${err.message}`
     }) + "\n");
     process.exit(1);
   });
   ```

---

## 4. Host Deadlock & Script Persistence

### The Session Caching Invariant
Host environments (e.g. Antigravity) snapshot hook registrations at session boot.

1. **Never delete hook scripts mid-session**:
   Deleting `/tmp/hook.py` while the session is alive triggers `ENOENT` on every subsequent tool call, completely freezing the agent.
2. **Tracked Repository Paths**:
   Store all hook scripts inside tracked repository directories (`hooks/` or `.agents/hooks/`), never in volatile OS temp directories.
3. **Graceful Fallback**:
   If an external hook command fails with `ENOENT`, the dispatcher must log a structured warning and fall back to the configured `on_failure` policy rather than crashing the host process.
