#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.join(__dirname, '..');
const TEMPLATE = path.join(ROOT, 'hooks', 'cursor-hooks.json');
const ANTI_SLOP_HOOK = /[\\/]hooks[\\/]anti-slop-[\w-]+\.(?:c?js|mjs)(?=["'\s]|$)/;

function isAntiSlopHook(entry) {
  return Boolean(entry && typeof entry.command === 'string' && ANTI_SLOP_HOOK.test(entry.command));
}

function hooksPath(scope) {
  return scope === 'project'
    ? path.join(process.cwd(), '.cursor', 'hooks.json')
    : path.join(os.homedir(), '.cursor', 'hooks.json');
}

function readConfig(file) {
  let config = {};
  try {
    config = JSON.parse(fs.readFileSync(file, 'utf8').replace(/^\uFEFF/, ''));
  } catch (e) {
    if (e.code !== 'ENOENT') throw e;
  }
  if (!config || typeof config !== 'object' || Array.isArray(config)) {
    throw new Error(file + ' must contain a JSON object; nothing was changed');
  }
  if (config.hooks === undefined) config.hooks = {};
  if (!config.hooks || typeof config.hooks !== 'object' || Array.isArray(config.hooks)) {
    throw new Error(file + ': hooks must be an object; nothing was changed');
  }
  for (const [event, entries] of Object.entries(config.hooks)) {
    if (!Array.isArray(entries)) {
      throw new Error(file + ': hooks.' + event + ' must be an array; nothing was changed');
    }
  }
  return config;
}

function writeConfig(file, config) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, JSON.stringify(config, null, 2) + '\n', 'utf8');
}

function loadTemplate(depth = 0) {
  if (depth > 5) return {};
  const raw = fs.readFileSync(TEMPLATE, 'utf8');
  const normalizedRoot = ROOT.replace(/\\/g, '/');
  return JSON.parse(raw.replaceAll('ANTI_SLOP_DIR', normalizedRoot));
}

function install(scope) {
  const file = hooksPath(scope);
  const config = readConfig(file);
  const template = loadTemplate();

  config.version = template.version || 1;
  for (const [event, entries] of Object.entries(template.hooks || {})) {
    const existing = config.hooks[event] ? config.hooks[event].filter((e) => !isAntiSlopHook(e)) : [];
    config.hooks[event] = existing.concat(entries);
  }

  writeConfig(file, config);
  console.log(`Installed Anti-Slop hooks into ${file}`);
}

function uninstall(scope) {
  const file = hooksPath(scope);
  let config;
  try {
    config = readConfig(file);
  } catch (e) {
    if (e.code === 'ENOENT') return;
    throw e;
  }

  let changed = false;
  for (const [event, entries] of Object.entries(config.hooks)) {
    const filtered = entries.filter((e) => !isAntiSlopHook(e));
    if (filtered.length !== entries.length) {
      changed = true;
      if (filtered.length === 0) {
        delete config.hooks[event];
      } else {
        config.hooks[event] = filtered;
      }
    }
  }

  if (changed) {
    writeConfig(file, config);
    console.log(`Removed Anti-Slop hooks from ${file}`);
  }
}

const action = process.argv[2];
const scope = process.argv.includes('--project') ? 'project' : 'global';

if (action === 'install') {
  install(scope);
} else if (action === 'uninstall') {
  uninstall(scope);
} else {
  console.log('Usage: node scripts/cursor-hooks.js [install|uninstall] [--project]');
  process.exit(1);
}
