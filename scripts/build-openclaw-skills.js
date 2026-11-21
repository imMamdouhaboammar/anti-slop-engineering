#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const ROOT = path.join(__dirname, '..');
const HOMEPAGE = 'https://github.com/imMamdouhaboammar/anti-slop-engineering';
const MAX_DEPTH = 5;

const DESCRIPTIONS = {
  'anti-slop-engineering': 'Enterprise-grade agentic guard suite, SRE/AST verification engines, and neural invariant governance.',
  'type-level-and-ast-slop-gate': 'Eliminate chained assertions, ungrounded casts, quadratic reducer copies, and AST slop.',
  'mandela-guard': 'Protect test-oracle integrity and eliminate tautological assertions and circular mocks.',
  'repo-memory-and-invariant-steward': 'Prevent architectural drift and govern invariants via the Invariant Ledger.',
  'comment-budget-guard': 'Enforce CCR <= 0.35 and eliminate obvious syntax play-by-play comments.',
  're0-handoff-guard': 'Enforce NVIDIA Re0 1500-token context reset discipline and the Cold-Read Shower Test.',
};

function readSkillBody(name, depth = 0) {
  if (depth > MAX_DEPTH) {
    throw new Error(`Recursion limit exceeded for skill: ${name}`);
  }
  const skillFile = path.join(ROOT, 'skills', name, 'SKILL.md');
  try {
    const src = fs.readFileSync(skillFile, 'utf8').replace(/\r\n/g, '\n');
    const fm = src.match(/^---\n[\s\S]*?\n---\n?/);
    return fm ? src.slice(fm[0].length) : src;
  } catch (error) {
    if (error && error.code === 'ENOENT') {
      return null;
    }
    throw error;
  }
}

function build() {
  for (const [name, desc] of Object.entries(DESCRIPTIONS)) {
    const body = readSkillBody(name, 0);
    if (!body) continue;
    const outDir = path.join(ROOT, '.openclaw', 'skills', name);
    fs.mkdirSync(outDir, { recursive: true });
    const content = `---\nname: ${name}\ndescription: "${desc}"\nhomepage: ${HOMEPAGE}\nlicense: MIT\n---\n${body}`;
    fs.writeFileSync(path.join(outDir, 'SKILL.md'), content, 'utf8');
    console.log(`Generated OpenClaw skill: ${name}`);
  }
}

build();
