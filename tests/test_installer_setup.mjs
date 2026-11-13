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

test('Setup: --all flag explicitly requests the full optional catalog', () => {
  const result = inDisposableProject(['--agent=codex', '--all', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  assert.ok(JSON.parse(result.stdout).skills.length >= 10)
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

test('Setup: selected plugins remain installed after a core-only update', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-selected-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
  })
  try {
    const setup = run(['--agent=codex', '--skills=decision-guard', '--json'])
    assert.equal(setup.status, 0, setup.stderr)
    const skillRoot = path.join(project, '.codex', 'skills')
    assert.ok(fs.existsSync(path.join(skillRoot, 'anti-slop-engineering', 'SKILL.md')))
    assert.ok(fs.existsSync(path.join(skillRoot, 'decision-guard', 'SKILL.md')))
    assert.equal(fs.existsSync(path.join(skillRoot, 'future-scale-gate')), false)

    const update = run(['update', '--json'])
    assert.equal(update.status, 0, update.stderr)
    assert.ok(fs.existsSync(path.join(skillRoot, 'decision-guard', 'SKILL.md')))
    assert.equal(fs.existsSync(path.join(skillRoot, 'future-scale-gate')), false)
    const report = JSON.parse(update.stdout)
    assert.deepEqual(report.updated.find((entry) => entry.location === 'project').skills,
      ['anti-slop-engineering', 'decision-guard'])
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: a malformed installed skill is excluded from generated instructions', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-valid-pointer-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=decision-guard']).status, 0)
    const entry = path.join(project, 'AGENTS.md')
    fs.appendFileSync(entry, '\nPersonal instructions remain.\n')
    const installed = path.join(project, '.codex/skills/decision-guard/SKILL.md')
    fs.writeFileSync(installed, 'invalid plugin metadata\n')
    const result = run(['update', '--json'])
    assert.equal(result.status, 0, result.stderr)
    const config = fs.readFileSync(entry, 'utf8')
    assert.ok(config.includes('Personal instructions remain.'))
    assert.ok(config.includes('anti-slop-engineering'))
    assert.ok(!config.includes('`decision-guard`:'), config)
    assert.equal(fs.readFileSync(installed, 'utf8'), 'invalid plugin metadata\n')
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: dry-run reports file conflicts without changing installed files', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-preview-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=core']).status, 0)
    const installed = path.join(project, '.codex/skills/anti-slop-engineering/SKILL.md')
    fs.writeFileSync(installed, 'my local version\n')
    const result = run(['--agent=codex', '--skills=core', '--overwrite', '--dry-run', '--json'])
    assert.equal(result.status, 0, result.stderr)
    const plan = JSON.parse(result.stdout)
    assert.ok(plan.operations.some((operation) => operation.conflicted.includes('SKILL.md')))
    assert.equal(fs.readFileSync(installed, 'utf8'), 'my local version\n')
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
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
