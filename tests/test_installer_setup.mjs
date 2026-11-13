import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'

const root = fileURLToPath(new URL('..', import.meta.url))
const installer = path.join(root, 'scripts', 'installer.mjs')

function inDisposableProject(args) {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-setup-'))
  try {
    const processResult = spawnSync(process.execPath, [installer, ...args], {
      cwd: temporary,
      encoding: 'utf8',
      env: { ...process.env, HOME: temporary, CI: 'true' },
      timeout: 10000,
    })
    return { ...processResult, project: temporary }
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true })
  }
}

test('Setup: non-interactive default installs mandatory core only', () => {
  const result = inDisposableProject(['--agent=codex', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(JSON.parse(result.stdout).skills, ['anti-slop-engineering'])
})

test('Setup: explicit optional plugin also includes core', () => {
  const result = inDisposableProject(['--agent=codex', '--skills=decision-guard', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(JSON.parse(result.stdout).skills, ['anti-slop-engineering', 'decision-guard'])
})

test('Setup: explicit all includes every available skill', () => {
  const result = inDisposableProject(['--agent=codex', '--skills=all', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  const plan = JSON.parse(result.stdout)
  assert.ok(plan.skills.length >= 10)
  assert.ok(plan.skills.includes('anti-slop-engineering'))
})

test('Setup: unknown skill is rejected even in dry-run', () => {
  const result = inDisposableProject(['--agent=codex', '--skills=does-not-exist', '--dry-run', '--json'])
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /Unknown|Invalid/i)
})

test('Setup: invalid agent is rejected before installation', () => {
  const result = inDisposableProject(['--agent=unknown-agent', '--skills=core', '--dry-run', '--json'])
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /Unknown|Invalid/i)
})

test('Setup: core remains required for explicit plugin aliases', () => {
  const result = inDisposableProject(['--agent=codex', '--plugins=decision-guard', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  assert.deepEqual(JSON.parse(result.stdout).skills, ['anti-slop-engineering', 'decision-guard'])
})

test('Postinstall: package lifecycle cannot launch remote skills add', () => {
  const temporary = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-lifecycle-'))
  const fakeBin = path.join(temporary, 'bin')
  fs.mkdirSync(fakeBin)
  const marker = path.join(temporary, 'invoked')
  const fakeNpx = path.join(fakeBin, 'npx')
  fs.writeFileSync(fakeNpx, `#!/bin/sh\nprintf 'npx invoked\\n' >> '${marker}'\n`)
  fs.chmodSync(fakeNpx, 0o755)
  try {
    const result = spawnSync(process.execPath, [path.join(root, 'bin', 'postinstall.js')], {
      cwd: temporary,
      encoding: 'utf8',
      env: { ...process.env, CI: '', NODE_ENV: 'production', PATH: fakeBin, HOME: temporary },
      timeout: 5000,
    })
    assert.equal(result.status, 0, result.stderr)
    assert.equal(fs.existsSync(marker), false, 'Package install must not launch a remote installer')
    assert.match(result.stdout, /anti-slop-engineering (?:setup|install)/)
  } finally {
    fs.rmSync(temporary, { recursive: true, force: true })
  }
})
