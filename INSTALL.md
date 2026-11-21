# Installation Guide: Anti-Slop Engineering

Pick your agent environment below. For an overview of adapter mapping, see [Agent Portability](docs/agent-portability.md).

---

## 1. Antigravity IDE & CLI

```bash
# In Antigravity CLI
agy plugin install https://github.com/imMamdouhaboammar/anti-slop-engineering
```

Or clone directly into your Antigravity plugin directory:
```bash
git clone https://github.com/imMamdouhaboammar/anti-slop-engineering.git ~/.gemini/config/plugins/anti-slop-engineering
```

Anti-Slop automatically registers:
- 15 native MCP tools via `bin/mcp-server.js` and `mcp_config.json`
- 7 specialized subagents in `agents/`
- PreToolUse and PostToolUse guards in `hooks.json`

---

## 2. Claude Code & Claude Desktop

In Claude Code:
```
/plugin marketplace add imMamdouhaboammar/anti-slop-engineering
/plugin install anti-slop-engineering@anti-slop-engineering
```
*(Send as two separate prompts)*

In the Claude Desktop App:
- Open the Code tab, click **+**, choose **Plugins** → **Add plugin**, and add `imMamdouhaboammar/anti-slop-engineering`.

---

## 3. OpenAI Codex

In OpenAI Codex CLI:
```bash
codex plugin marketplace add imMamdouhaboammar/anti-slop-engineering
codex plugin add anti-slop-engineering@anti-slop-engineering
```

Open `/hooks`, review and trust the lifecycle hooks, and start a new thread.

---

## 4. OpenCode & Kilo Code

```bash
opencode plugin add anti-slop-engineering
```

Or add it to your project's `opencode.json`:
```json
{
  "plugins": ["anti-slop-engineering"]
}
```

From a local checkout:
```json
{
  "plugins": ["./.opencode/plugins"]
}
```

---

## 5. Gemini CLI & Qwen Code

```bash
gemini extensions install https://github.com/imMamdouhaboammar/anti-slop-engineering
```

Loads `rules/AGENTS.md` as always-on context and registers the slash commands in `commands/`.

---

## 6. Cursor IDE

Install native hooks into `~/.cursor/hooks.json`:
```bash
node scripts/cursor-hooks.js install
```

Or install locally in the active project:
```bash
node scripts/cursor-hooks.js install --project
```

The always-on `.cursor/rules/anti-slop.mdc` rule is automatically picked up by Cursor.

---

## 7. Windsurf & Cline

- **Windsurf**: Reads `.windsurf/rules/anti-slop.md`.
- **Cline**: Reads `.clinerules/anti-slop.md` or `AGENTS.md`.

---

## 8. Kimi Code

Run:
```
/plugins install https://github.com/imMamdouhaboammar/anti-slop-engineering
```
Then `/reload` or start a new session.

---

## 9. Devin CLI

```bash
devin plugins install imMamdouhaboammar/anti-slop-engineering
```

---

## 10. Qoder

Install as a Qoder plugin:
```bash
qodercli plugins install https://github.com/imMamdouhaboammar/anti-slop-engineering
```

---

## 11. Pi & Oh My Pi (omp)

```bash
# In Pi
pi install git:github.com/imMamdouhaboammar/anti-slop-engineering

# In Oh My Pi
omp plugin install anti-slop-engineering@anti-slop-engineering
```

---

## 12. Hermes Agent

```bash
hermes plugins install imMamdouhaboammar/anti-slop-engineering --enable
```
