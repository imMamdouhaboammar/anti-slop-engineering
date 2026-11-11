// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { test } from 'node:test'
import {
  AGENTS,
  CORE_SKILL,
  installSkills,
  listAvailableSkills,
  resolveTargets,
  writeBlock,
} from '../scripts/installer.mjs'

test('Installer: AGENTS list has 14 supported agents', () => {
  assert.equal(AGENTS.length, 14)
  const ids = AGENTS.map((a) => a.id)
  assert.ok(ids.includes('antigravity'))
  assert.ok(ids.includes('claude'))
  assert.ok(ids.includes('cursor'))
  assert.ok(ids.includes('codex'))
  assert.ok(ids.includes('opencode'))
  assert.ok(ids.includes('deepseek'))
  assert.ok(ids.includes('windsurf'))
})

test('Installer: listAvailableSkills returns core and modular skills', () => {
  const skills = listAvailableSkills()
  assert.ok(skills.includes(CORE_SKILL))
  assert.ok(skills.length >= 10)
})

test('Installer: resolveTargets deduplicates shared folders', () => {
  // antigravity, amp, copilot, kimi, deepseek all share .agents/skills
  const targets = resolveTargets('project', ['antigravity', 'copilot', 'deepseek'])
  assert.equal(targets.length, 1)
  assert.equal(targets[0].agents.length, 3)
})

test('Installer: writeBlock safely injects and replaces pointer block', () => {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-install-test-'))
  const entryFile = path.join(tmpDir, 'AGENTS.md')
  try {
    fs.writeFileSync(entryFile, '# Existing Agent Config\n\nSome custom instructions.\n')
    const block = [
      '<!-- anti-slop-engineering:start -->',
      '## anti-slop-engineering',
      '- Rule 1: SRE KISS',
      '<!-- anti-slop-engineering:end -->'
    ]
    writeBlock(entryFile, block)
    let content = fs.readFileSync(entryFile, 'utf8')
    assert.ok(content.includes('<!-- anti-slop-engineering:start -->'))
    assert.ok(content.includes('Some custom instructions.'))

    // Second write replaces block cleanly without duplicating
    writeBlock(entryFile, [
      '<!-- anti-slop-engineering:start -->',
      '## anti-slop-engineering',
      '- Rule 1: Updated SRE KISS',
      '<!-- anti-slop-engineering:end -->'
    ])
    content = fs.readFileSync(entryFile, 'utf8')
    assert.ok(content.includes('Updated SRE KISS'))
    const matchCount = (content.match(/<!-- anti-slop-engineering:start -->/g) || []).length
    assert.equal(matchCount, 1)
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true })
  }
})

test('Installer: overwriting a managed skill preserves modified files and user additions', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-preserve-'))
  const target = { path: root, agents: [{ id: 'codex', entry: 'AGENTS.md' }] }
  try {
    installSkills({ skills: [CORE_SKILL], targets: [target], overwrite: true })
    const dest = path.join(root, CORE_SKILL)
    const modified = path.join(dest, 'SKILL.md')
    fs.writeFileSync(modified, '# user customization\n')
    fs.writeFileSync(path.join(dest, 'user-notes.md'), 'keep me\n')

    installSkills({ skills: [CORE_SKILL], targets: [target], overwrite: true })

    assert.equal(fs.readFileSync(modified, 'utf8'), '# user customization\n')
    assert.equal(fs.readFileSync(path.join(dest, 'user-notes.md'), 'utf8'), 'keep me\n')
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('Installer: refuses skill IDs containing path traversal', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-traversal-'))
  const target = { path: path.join(root, 'skills'), agents: [{ id: 'codex', entry: 'AGENTS.md' }] }
  try {
    assert.throws(
      () => installSkills({ skills: ['../scripts'], targets: [target], overwrite: true }),
      /Invalid skill|Unknown skill/,
    )
    assert.equal(fs.existsSync(path.join(root, 'scripts')), false)
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})

test('Installer: never follows symlinked agent instruction files', () => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-pointer-'))
  const config = path.join(root, 'AGENTS.md')
  const victim = path.join(root, 'outside.md')
  try {
    fs.writeFileSync(victim, 'owner data\n')
    fs.symlinkSync(victim, config)
    assert.throws(() => writeBlock(config, [
      '<!-- anti-slop-engineering:start -->',
      'payload',
      '<!-- anti-slop-engineering:end -->',
    ]), /symbolic link/i)
    assert.equal(fs.readFileSync(victim, 'utf8'), 'owner data\n')
  } finally {
    fs.rmSync(root, { recursive: true, force: true })
  }
})
