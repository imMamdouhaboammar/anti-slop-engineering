// anti-slop-engineering — OpenCode plugin (V1 & V2 compatible).
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);

const { getAntiSlopInstructions } = require('../../hooks/anti-slop-instructions');
const { parseCommandFile, parseSkillFile } = require('./anti-slop-frontmatter.cjs');

function readCommands() {
  const dir = path.join(__dirname, '..', 'command');
  try {
    return fs.readdirSync(dir)
      .filter((file) => file.endsWith('.md'))
      .map((file) => {
        const parsed = parseCommandFile(path.join(dir, file));
        return parsed && { name: path.basename(file, '.md'), ...parsed };
      })
      .filter(Boolean);
  } catch (_e) {
    return [];
  }
}

function readSkills() {
  const dir = path.resolve(__dirname, '../../skills');
  try {
    return fs.readdirSync(dir, { withFileTypes: true })
      .filter((entry) => entry.isDirectory() && !entry.name.includes('..') && /^[a-z0-9_-]+$/i.test(entry.name))
      .map((entry) => {
        const file = path.resolve(dir, entry.name, 'SKILL.md');
        if (!file.startsWith(dir)) return null;
        let parsed = null;
        try {
          parsed = parseSkillFile(file);
        } catch (err) {
          if (err && err.code === 'ENOENT') return null;
          throw err;
        }
        return parsed && {
          id: entry.name,
          name: parsed.name || entry.name,
          description: parsed.description,
          path: file,
          content: parsed.body,
        };
      })
      .filter(Boolean);
  } catch (_e) {
    return [];
  }
}

function withArguments(template, input) {
  const text = String(input == null ? '' : input);
  if (template.includes('$ARGUMENTS')) return template.replaceAll('$ARGUMENTS', text);
  return text.trim() ? template + '\n\n' + text.trim() : template;
}

export default {
  id: 'anti-slop-engineering',

  async setup(ctx) {
    const commands = readCommands();
    const skills = readSkills();

    if (ctx.skill && typeof ctx.skill.transform === 'function') {
      await ctx.skill.transform((editor) => {
        for (const skill of skills) editor.add(skill);
      });
    }

    if (ctx.command && typeof ctx.command.transform === 'function') {
      await ctx.command.transform((editor) => {
        for (const command of commands) {
          editor.add({
            name: command.name,
            description: command.description,
            execute: async ({ sessionID, prompt, delivery }) => {
              const withoutMentions = (items) => items?.map(({ mention, ...item }) => item);
              await ctx.session.prompt({
                ...prompt,
                sessionID,
                text: withArguments(command.template, prompt?.text),
                files: withoutMentions(prompt?.files),
                agents: withoutMentions(prompt?.agents),
                skills: withoutMentions(prompt?.skills),
                delivery,
              });
            },
          });
        }
      });
    }

    const addRuleset = (event) => {
      if (!event || !Array.isArray(event.system)) return;
      event.system.push({ type: 'text', text: getAntiSlopInstructions() });
    };

    if (ctx.session && typeof ctx.session.hook === 'function') {
      await ctx.session.hook('context', addRuleset);
      await ctx.session.hook('compaction', addRuleset);
    }
  },

  async server({ client } = {}) {
    const log = (level, message) => {
      try {
        if (client && client.app && typeof client.app.log === 'function') {
          client.app.log({ body: { service: 'anti-slop-engineering', level, message } });
        }
      } catch (_e) {}
    };

    return {
      config: async (config) => {
        if (!config.command) config.command = {};
        for (const command of readCommands()) {
          config.command[command.name] = { description: command.description, template: command.template };
        }

        config.skills = config.skills || {};
        config.skills.paths = config.skills.paths || [];
        const skillsDir = path.resolve(__dirname, '../../skills');
        if (!config.skills.paths.includes(skillsDir)) {
          config.skills.paths.push(skillsDir);
        }
        log('info', 'anti-slop-engineering skills and commands registered');
      },

      'experimental.chat.system.transform': async (_input, output) => {
        if (!output || !Array.isArray(output.system)) return;
        const instructions = getAntiSlopInstructions();
        if (output.system.length > 0) {
          output.system[output.system.length - 1] += '\n\n' + instructions;
        } else {
          output.system.push(instructions);
        }
      },
    };
  },
};
