'use strict';
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

const fs = require('node:fs');

function parseCommandFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---\r?\n([\s\S]*)$/);
  if (!match) return null;
  const description = match[1].match(/description:\s*(.+)/)?.[1]?.trim();
  return { description, template: match[2].trim() };
}

function frontmatterField(frontmatter, key) {
  const lines = frontmatter.split(/\r?\n/);
  const at = lines.findIndex((line) => line.startsWith(key + ':'));
  if (at === -1) return undefined;
  const value = lines[at].slice(key.length + 1).trim();
  if (value[0] !== '>' && value[0] !== '|') return value;

  const block = [];
  for (const line of lines.slice(at + 1)) {
    if (line.trim() && !/^\s/.test(line)) break;
    block.push(line.trim());
  }
  while (block.length && !block[block.length - 1]) block.pop();
  const joined = block.join(value[0] === '|' ? '\n' : ' ');
  return value.endsWith('-') ? joined : joined + '\n';
}

function parseSkillFile(filePath) {
  const content = fs.readFileSync(filePath, 'utf8');
  const match = content.match(/^---\r?\n([\s\S]*?)\r?\n---[^\S\n]*\r?\n?([\s\S]*)$/);
  if (!match) return null;
  return {
    name: frontmatterField(match[1], 'name'),
    description: frontmatterField(match[1], 'description'),
    body: match[2],
  };
}

module.exports = { parseCommandFile, parseSkillFile };
