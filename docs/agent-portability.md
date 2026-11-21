# Agent Portability

Anti-Slop Engineering is an agent-portable skill and guard distribution. The skills in `skills/` and core rules in `rules/AGENTS.md` hold the central behavior; host-specific files are adapters that make that behavior seamless to load in any agent runtime.

## Supported Adapters

| Host | Files | Integration Tier | Notes |
|------|-------|------------------|-------|
| **Antigravity** | `plugin.json`, `mcp_config.json`, `hooks.json`, `agents/`, `rules/AGENTS.md` | Full Agentic Plugin | Native MCP server with 15 tools, 7 specialized subagents, and pre/post tool use hooks. |
| **Claude Code & Desktop** | `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `commands/`, `hooks/claude-codex-hooks.json`, `hooks/` | Full Plugin | Full plugin install with session activation, subagent arming, slash commands, and pre-tool verification. |
| **OpenAI Codex** | `.codex-plugin/plugin.json`, `hooks/claude-codex-hooks.json`, `hooks/`, `skills/` | Full Plugin | Plugin install with lifecycle hooks for activation and subagent inheritance. |
| **OpenCode & Kilo Code** | `opencode.json`, `.opencode/plugins/anti-slop.mjs`, `.opencode/command/`, `hooks/`, `skills/` | Server Plugin | Dual V1/V2 server plugin injecting rulesets via `session.hook('context')` and registering markdown slash commands. |
| **Gemini CLI & Qwen Code** | `gemini-extension.json`, `rules/AGENTS.md`, `commands/`, `skills/` | Extension | Extension manifest points `contextFileName` at `rules/AGENTS.md` and reuses `commands/*.toml`. |
| **Cursor IDE** | `.cursor/rules/anti-slop.mdc`, `hooks/cursor-hooks.json`, `scripts/cursor-hooks.js` | Rules + Hooks | Rules via `.mdc` and hook merging into `~/.cursor/hooks.json` via installer script. |
| **Windsurf** | `.windsurf/rules/anti-slop.md` | Instruction Tier | Project-level Cascade rules file. |
| **Cline** | `.clinerules/anti-slop.md` | Instruction Tier | Project-level Cline rules file. |
| **Kimi Code** | `.kimi-plugin/plugin.json`, `rules/AGENTS.md`, `skills/` | Native Plugin | Points `systemPromptPath` at `rules/AGENTS.md` and exposes skills. |
| **Devin CLI** | `.devin-plugin/plugin.json`, `skills/` | Native Plugin | Installs anti-slop skills into Devin CLI. |
| **Qoder** | `.qoder-plugin/plugin.json`, `.qoder/rules/anti-slop.md`, `hooks/qoder-hooks.json`, `skills/` | Full Plugin | Auto-loads rules and registers `UserPromptSubmit` and `PreToolUse` hooks. |
| **Pi & Oh My Pi (omp)** | `pi-extension/`, `skills/`, `hooks/` | Package Extension | Injects ruleset each turn through `before_agent_start`. |
| **Hermes Agent** | `plugin.yaml`, `__init__.py`, `skills/` | Native Plugin | Injects ruleset via `pre_llm_call` hook and exposes skills. |
| **OpenClaw (ClawHub)** | `.openclaw/skills/`, `scripts/build-openclaw-skills.js` | Skill Distribution | Skills packaged with ClawHub-compliant frontmatter. |
| **GitHub Copilot CLI** | `.github/copilot-instructions.md`, `hooks/copilot-hooks.json` | Plugin / Instructions | Hook template and repository instructions. |

## Adapter Design Principles

1. **Keep adapters thin**: Point hosts directly to canonical `skills/`, `rules/AGENTS.md`, and `hooks/`.
2. **Zero external dependencies**: Hook runners and adapter parsers rely strictly on standard built-in runtime modules (`node:fs`, `node:path`, `node:module`, `child_process`).
3. **Fail-safe execution**: In non-interactive or minimal environments, hooks emit instructions cleanly without crashing or blocking the session.
