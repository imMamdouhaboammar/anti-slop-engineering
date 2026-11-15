# Coding agent hook capabilities

| Adapter | Proven pre-tool blocking | Proven post-tool feedback | Prerequisites |
| --- | --- | --- | --- |
| Claude Code | `Read`, `Edit`, `Write` file actions | The same actions after success | Tested on 2.1.318. See [the project opt-in workflow](claude-code-hooks.md). |
| Codex CLI | `apply_patch` file edits on POSIX | `apply_patch` feedback on POSIX | Tested on CLI 0.166.0. The host must trust the project and hook definition. |
| Gemini CLI | Built-in `write_file` on POSIX | Same tool, with feedback appended to the result | Tested on CLI 0.68.0. Trust the workspace and enable hooks in Gemini CLI. |
| Antigravity, Cursor, OpenCode | No verified adapter in this package | No verified adapter in this package | Use the normal skills and explicit repository checks. |

## Codex project setup

```sh
python3 /path/to/anti-slop/scripts/codex_hooks.py install --project /path/to/project --dry-run
python3 /path/to/anti-slop/scripts/codex_hooks.py install --project /path/to/project --yes
```

The installer only changes the selected project's `.codex/hooks.json`. In Codex, review the exact hook via `/hooks` and trust it before use. Keep the executable and package paths stable. In a supported project, set the contract using `anti-slop-engineering exec parse-prompt`. In `review guard` a structured patch is denied before it executes. In `review watch` a policy issue is returned as advisory feedback.

The adapter limits decisions to native patch actions with known target paths. Shell, MCP and tool actions that do not emit this native event are handled by Codex permissions. If the adapter starts and cannot evaluate a matched pre-action, it denies that action and explains the error. Hook launch failures, native timeouts, and skipped or untrusted hooks depend on Codex. This adapter does not claim strict failure blocking. Run `anti-slop-engineering audit` or existing CI to check repository changes at a later boundary.

```sh
python3 /path/to/anti-slop/scripts/codex_hooks.py uninstall --project /path/to/project --dry-run
python3 /path/to/anti-slop/scripts/codex_hooks.py uninstall --project /path/to/project --yes
```

## Gemini CLI project setup

```sh
python3 /path/to/anti-slop/scripts/gemini_hooks.py install --project /path/to/project --dry-run
python3 /path/to/anti-slop/scripts/gemini_hooks.py install --project /path/to/project --yes
```

The adapter changes the selected project's `.gemini/settings.json`. That file may be tracked, so review the change before committing it. Use a stable checkout and interpreter path. The launcher needs a trusted workspace and Gemini CLI hooks enabled. The adapter preserves existing settings, refuses malformed or symlinked settings, and does not toggle trust or hook enablement.

Arm a contract with `anti-slop-engineering exec parse-prompt` from the same project. With `review guard`, Gemini CLI rejects a matched file write before execution. With `review watch`, a write can run with advisory feedback. A successful allow leaves Gemini's own permission behavior in place.

The registered matcher covers the built-in `write_file` tool. Read, replacement, shell, MCP, and other tool actions remain subject to Gemini's own permissions. A launched pre-hook that cannot evaluate a matched payload returns a denial. Gemini CLI may continue on launcher failure, disablement, or timeout, so use independent repository or CI checks for wider coverage.

```sh
python3 /path/to/anti-slop/scripts/gemini_hooks.py uninstall --project /path/to/project --dry-run
python3 /path/to/anti-slop/scripts/gemini_hooks.py uninstall --project /path/to/project --yes
```

[Codex hooks documentation](https://learn.chatgpt.com/docs/hooks) · [Gemini CLI hooks](https://geminicli.com/docs/hooks/reference/) · [Antigravity plugin hooks](https://antigravity.google/docs/build-plugins) · [Cursor hooks](https://cursor.com/docs/hooks) · [OpenCode plugin hooks](https://opencode.ai/docs/build/plugins/server)

## Preview from setup

From a durable POSIX checkout, run either preview from the project directory.

```sh
node /path/to/anti-slop/bin/cli.js setup --agent=codex --codex-hooks --dry-run --json
node /path/to/anti-slop/bin/cli.js setup --agent=gemini --gemini-hooks --dry-run --json
```

The preview reports the project settings path, supported tool, and host trust requirement. Use the standalone adapter to apply or remove the hooks.
