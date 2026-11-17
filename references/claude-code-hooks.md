# Claude Code project hooks

Requires Claude Code 2.1.295 or later for pre-hook failure blocking. Keep the Anti-Slop package or checkout at a stable absolute path. A relocated runner must be reinstalled into the selected project.

```sh
python3 /path/to/anti-slop/scripts/claude_hooks.py install --project /path/to/trusted/project --dry-run
python3 /path/to/anti-slop/scripts/claude_hooks.py install --project /path/to/trusted/project --yes
```

Setup consent changes only the selected project's `.claude/settings.local.json`. The install preserves existing permissions and unrelated hooks, refuses malformed or symlinked settings, and writes settings atomically. Run local settings changes serially while applying or removing hooks. A default skill installation makes no hook changes. Use Claude Code's `/hooks` and `/status` to verify loaded settings.

From the selected project, activate the existing action contract that corresponds to your task.

```sh
anti-slop-engineering exec parse-prompt '$anti-slop review guard -- Review the project'
```

| Boundary | Coverage |
| --- | --- |
| `PreToolUse` | `Read`, `Edit`, `Write` with a structured file path. A denial prevents the supported action. An allow leaves ordinary Claude permission checks in charge. |
| `PostToolUse` | The same tools after success. Any reported policy violation is feedback for the next model request. |
| Outside this adapter | Shell, MCP, NotebookEdit, Glob, Grep, and actions outside Claude's registered tool events remain subject to the host's own controls and explicit repository checks. |

After an authorized `Write` or `Edit`, the adapter checks the syntax of that one project-local Python source or stub using its own Python interpreter. It reads at most 64 KiB plus one byte and rejects symlinks and non-regular files. A syntax error reports the line number without source text. Interpreter warnings are omitted. A skipped check reports the reason. Review the feedback, correct the file if needed, and run its focused tests before the separate repository checks. This checkpoint runs no project code, does not modify project sources, and initiates no retry. Read-only contracts, paths outside the policy, and actions without an active contract keep their normal policy behavior.

In `guard` mode, when the hook payload includes `session_id`, consecutive post-write syntax errors for a `(session_id, target)` pair are tracked in `.anti-slop/checkpoint-state.json` and logged to `.anti-slop/checkpoint-audit.jsonl`. Skipped checks do not count, and a compiling write clears the counter. After 3 consecutive failures, the post-write warning notes budget exhaustion and subsequent `PreToolUse` writes to that file in that session are denied until a compiling write is recorded or a single-use override (`session_id`, `target`, `reason`) at `.anti-slop/checkpoint-override.json` with a non-blank reason is consumed. The attempt budget falls back to the stateless check if the session ID is missing or the state is unavailable. In `watch` mode, the checkpoint only reports the result of each write.

An unconfirmed or off contract leaves decisions to Claude Code. A pre-hook that cannot start, times out, or rejects its payload is configured to stop the matched action. Inspect the local settings and package path if a failure occurs.

```sh
python3 /path/to/anti-slop/scripts/claude_hooks.py uninstall --project /path/to/trusted/project --dry-run
python3 /path/to/anti-slop/scripts/claude_hooks.py uninstall --project /path/to/trusted/project --yes
```

Uninstall removes the exact installed hook entries. If you modified them locally, review and remove those entries yourself to preserve your changes.

[Claude Code hook semantics](https://code.claude.com/docs/en/hooks) · [Claude Code settings scopes](https://code.claude.com/docs/en/settings)

## Preview from setup

From a durable POSIX checkout, run setup in the project with the checkout's CLI:

    node /path/to/anti-slop-engineering/bin/cli.js setup --agent=claude --claude-hooks --dry-run

This preview reports the exact local settings path and covered actions without modifying skills or settings. Use the standalone adapter in that durable checkout to apply or remove the hooks. Registration stores the adapter's absolute path, so do not install from a transient package-manager cache. The standard installer and Bash installation continue to install skills without registering hooks.
