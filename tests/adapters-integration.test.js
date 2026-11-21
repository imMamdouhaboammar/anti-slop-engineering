// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { describe, expect, test } from "bun:test";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.resolve(__dirname, "..");

describe("Multi-Agent Adapters Integration Test Suite", () => {
  describe("Claude Code Plugin", () => {
    test(".claude-plugin/plugin.json is valid and references existing hooks and commands", () => {
      const pluginPath = path.join(ROOT, ".claude-plugin", "plugin.json");
      expect(fs.existsSync(pluginPath)).toBe(true);

      const content = JSON.parse(fs.readFileSync(pluginPath, "utf8"));
      const pkg = JSON.parse(fs.readFileSync(path.join(ROOT, "package.json"), "utf8"));
      expect(content.name).toBe("anti-slop-engineering");
      expect(content.version).toBe(pkg.version);
      expect(Array.isArray(content.hooks)).toBe(true);

      for (const hookRef of content.hooks) {
        const resolvedHook = path.resolve(ROOT, hookRef);
        expect(fs.existsSync(resolvedHook)).toBe(true);
      }

      const commandsDir = path.resolve(ROOT, content.commands);
      expect(fs.existsSync(commandsDir)).toBe(true);
    });

    test(".claude-plugin/marketplace.json is valid against marketplace schema shape", () => {
      const marketplacePath = path.join(ROOT, ".claude-plugin", "marketplace.json");
      expect(fs.existsSync(marketplacePath)).toBe(true);

      const content = JSON.parse(fs.readFileSync(marketplacePath, "utf8"));
      expect(content.name).toBe("anti-slop-engineering");
      expect(Array.isArray(content.plugins)).toBe(true);
      expect(content.plugins.length).toBeGreaterThan(0);
      expect(content.plugins[0].name).toBe("anti-slop-engineering");
    });
  });

  describe("OpenAI Codex Plugin", () => {
    test(".codex-plugin/plugin.json references hooks and skills", () => {
      const codexPath = path.join(ROOT, ".codex-plugin", "plugin.json");
      expect(fs.existsSync(codexPath)).toBe(true);

      const content = JSON.parse(fs.readFileSync(codexPath, "utf8"));
      expect(content.name).toBe("anti-slop-engineering");
      expect(content.hooks).toBe("./hooks/claude-codex-hooks.json");
      expect(fs.existsSync(path.resolve(ROOT, content.hooks))).toBe(true);
      expect(fs.existsSync(path.resolve(ROOT, content.skills))).toBe(true);
    });
  });

  describe("OpenCode & Kilo Code Plugin", () => {
    test("opencode.json schema configuration is present", () => {
      const opencodeJsonPath = path.join(ROOT, "opencode.json");
      expect(fs.existsSync(opencodeJsonPath)).toBe(true);
      const content = JSON.parse(fs.readFileSync(opencodeJsonPath, "utf8"));
      expect(content.$schema).toBeDefined();
    });

    test(".opencode/plugins/anti-slop.mjs implements V1 server and V2 setup", async () => {
      const pluginUrl = pathToFileURL(path.join(ROOT, ".opencode", "plugins", "anti-slop.mjs"));
      const mod = await import(pluginUrl);
      const plugin = mod.default;

      expect(plugin).toBeDefined();
      expect(plugin.id).toBe("anti-slop-engineering");
      expect(typeof plugin.setup).toBe("function");
      expect(typeof plugin.server).toBe("function");

      const serverObj = await plugin.server();
      expect(serverObj).toBeDefined();
      expect(typeof serverObj.config).toBe("function");
      expect(typeof serverObj["experimental.chat.system.transform"]).toBe("function");
    });

    test(".opencode/command/ contains valid markdown command files", () => {
      const cmdDir = path.join(ROOT, ".opencode", "command");
      expect(fs.existsSync(cmdDir)).toBe(true);
      const files = fs.readdirSync(cmdDir).filter((f) => f.endsWith(".md"));
      expect(files.length).toBeGreaterThanOrEqual(4);

      for (const file of files) {
        const text = fs.readFileSync(path.join(cmdDir, file), "utf8");
        expect(text).toContain("---");
        expect(text).toContain("description:");
      }
    });
  });

  describe("Gemini CLI & Qwen Code", () => {
    test("gemini-extension.json exists and points to valid contextFileName", () => {
      const extPath = path.join(ROOT, "gemini-extension.json");
      expect(fs.existsSync(extPath)).toBe(true);

      const content = JSON.parse(fs.readFileSync(extPath, "utf8"));
      expect(content.name).toBe("anti-slop-engineering");
      expect(content.contextFileName).toBeDefined();
      expect(fs.existsSync(path.resolve(ROOT, content.contextFileName))).toBe(true);
    });
  });

  describe("Universal Slash Commands", () => {
    test("commands/ directory contains valid TOML files", () => {
      const cmdDir = path.join(ROOT, "commands");
      expect(fs.existsSync(cmdDir)).toBe(true);
      const tomls = fs.readdirSync(cmdDir).filter((f) => f.endsWith(".toml"));
      expect(tomls.length).toBeGreaterThanOrEqual(5);

      for (const toml of tomls) {
        const content = fs.readFileSync(path.join(cmdDir, toml), "utf8");
        expect(content).toContain("description =");
        expect(content).toContain("prompt =");
      }
    });
  });

  describe("Cursor, Windsurf, Cline & Copilot", () => {
    test(".cursor/rules/anti-slop.mdc exists and has frontmatter", () => {
      const rulePath = path.join(ROOT, ".cursor", "rules", "anti-slop.mdc");
      expect(fs.existsSync(rulePath)).toBe(true);
      const content = fs.readFileSync(rulePath, "utf8");
      expect(content).toContain("alwaysApply: true");
    });

    test("hooks/cursor-hooks.json is valid template", () => {
      const hookPath = path.join(ROOT, "hooks", "cursor-hooks.json");
      expect(fs.existsSync(hookPath)).toBe(true);
      const content = JSON.parse(fs.readFileSync(hookPath, "utf8"));
      expect(content.version).toBe(1);
      expect(Array.isArray(content.hooks.sessionStart)).toBe(true);
    });

    test(".windsurf/rules/anti-slop.md exists", () => {
      expect(fs.existsSync(path.join(ROOT, ".windsurf", "rules", "anti-slop.md"))).toBe(true);
    });

    test(".clinerules/anti-slop.md exists", () => {
      expect(fs.existsSync(path.join(ROOT, ".clinerules", "anti-slop.md"))).toBe(true);
    });

    test(".github/copilot-instructions.md exists", () => {
      expect(fs.existsSync(path.join(ROOT, ".github", "copilot-instructions.md"))).toBe(true);
    });
  });

  describe("Kimi, Devin, Qoder, Pi & Hermes", () => {
    test(".kimi-plugin/plugin.json is valid and points to AGENTS.md", () => {
      const kimiPath = path.join(ROOT, ".kimi-plugin", "plugin.json");
      expect(fs.existsSync(kimiPath)).toBe(true);
      const content = JSON.parse(fs.readFileSync(kimiPath, "utf8"));
      expect(content.name).toBe("anti-slop-engineering");
      expect(fs.existsSync(path.resolve(ROOT, content.systemPromptPath))).toBe(true);
    });

    test(".devin-plugin/plugin.json is valid", () => {
      const devinPath = path.join(ROOT, ".devin-plugin", "plugin.json");
      expect(fs.existsSync(devinPath)).toBe(true);
      const content = JSON.parse(fs.readFileSync(devinPath, "utf8"));
      expect(content.name).toBe("anti-slop-engineering");
    });

    test(".qoder-plugin/plugin.json is valid and points to rules and hooks", () => {
      const qoderPath = path.join(ROOT, ".qoder-plugin", "plugin.json");
      expect(fs.existsSync(qoderPath)).toBe(true);
      const content = JSON.parse(fs.readFileSync(qoderPath, "utf8"));
      expect(fs.existsSync(path.resolve(ROOT, content.hooks))).toBe(true);
    });

    test("pi-extension/index.js exports activate function", async () => {
      const piUrl = pathToFileURL(path.join(ROOT, "pi-extension", "index.js"));
      const mod = await import(piUrl);
      expect(typeof mod.default).toBe("function");
    });

    test("plugin.yaml exists for Hermes Agent", () => {
      const yamlPath = path.join(ROOT, "plugin.yaml");
      expect(fs.existsSync(yamlPath)).toBe(true);
      const content = fs.readFileSync(yamlPath, "utf8");
      expect(content).toContain("name: anti-slop-engineering");
      expect(content).toContain("provides_hooks:");
    });
  });

  describe("OpenClaw Skills Distribution", () => {
    test(".openclaw/skills/ contains generated skills", () => {
      const openclawDir = path.join(ROOT, ".openclaw", "skills");
      expect(fs.existsSync(openclawDir)).toBe(true);
      const skillDirs = fs.readdirSync(openclawDir);
      expect(skillDirs).toContain("anti-slop-engineering");
      const skillPath = path.join(openclawDir, "anti-slop-engineering", "SKILL.md");
      expect(fs.existsSync(skillPath)).toBe(true);
    });
  });

  describe("Hooks Runtime Execution", () => {
    test("anti-slop-instructions returns non-empty ruleset containing 7 gates", async () => {
      const instUrl = pathToFileURL(path.join(ROOT, "hooks", "anti-slop-instructions.js"));
      const mod = await import(instUrl);
      const instructions = mod.getAntiSlopInstructions();
      expect(instructions).toContain("ANTI-SLOP ENGINEERING ACTIVE");
      expect(instructions).toContain("Gate 0");
    });
  });
});
