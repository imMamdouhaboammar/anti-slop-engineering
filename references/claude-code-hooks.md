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
