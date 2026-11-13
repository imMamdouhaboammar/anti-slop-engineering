import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { test } from 'node:test'
import { listAvailableModules } from '../scripts/installer.mjs'

const root = fileURLToPath(new URL('..', import.meta.url))
const installer = path.join(root, 'scripts', 'installer.mjs')
const cli = path.join(root, 'bin', 'cli.js')

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

test('Setup: public CLI forwards JSON setup without prompts or extra output', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-entry-'))
  try {
    const result = spawnSync(process.execPath, [cli, 'setup', '--agent=codex', '--dry-run', '--json'], {
      cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
    })
    assert.equal(result.status, 0, result.stderr)
    assert.deepEqual(JSON.parse(result.stdout).skills, ['anti-slop-engineering'])
    assert.equal(fs.existsSync(path.join(project, '.codex')), false)
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: both help entrypoints describe the required core and optional plugins', () => {
  const general = spawnSync(process.execPath, [cli, '--help'], { encoding: 'utf8' })
  const installerHelp = spawnSync(process.execPath, [installer, '--help'], { encoding: 'utf8' })
  assert.equal(general.status, 0, general.stderr)
  assert.equal(installerHelp.status, 0, installerHelp.stderr)
  assert.match(general.stdout, /required core/i)
  assert.match(installerHelp.stdout, /core is required/i)
  assert.match(installerHelp.stdout, /optional skill/i)
})

test('Setup: module descriptions come from existing skill definitions', () => {
  const modules = listAvailableModules()
  assert.equal(modules.filter((module) => module.required).length, 1)
  assert.equal(modules.find((module) => module.required).id, 'anti-slop-engineering')
  assert.match(modules.find((module) => module.id === 'decision-guard').description, /decision|architecture/i)
  assert.equal(new Set(modules.map((module) => module.id)).size, modules.length)
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

test('Setup: install everything writes the complete validated skill catalog', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-all-'))
  try {
    const result = spawnSync(process.execPath,
      [installer, '--agent=codex', '--skills=all', '--json'], {
        cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 20000,
      })
    assert.equal(result.status, 0, result.stderr)
    const installed = JSON.parse(result.stdout).installed.map((entry) => entry.skill)
    const skillsDir = path.join(root, 'skills')
    const diskSkills = fs.readdirSync(skillsDir, { withFileTypes: true })
      .filter((e) => e.isDirectory() && fs.existsSync(path.join(skillsDir, e.name, 'SKILL.md')))
      .map((e) => e.name)
    const expectedCatalog = ['anti-slop-engineering', ...diskSkills.filter((s) => s !== 'anti-slop-engineering')]
    assert.deepEqual(installed.sort(), expectedCatalog.sort())
    for (const id of expectedCatalog) {
      assert.ok(fs.existsSync(path.join(project, '.codex/skills', id, 'SKILL.md')), id)
    }
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
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
    const inventory = JSON.parse(fs.readFileSync(path.join(skillRoot, '.anti-slop-selection.json'), 'utf8'))
    assert.equal(inventory.format, 1)
    assert.equal(inventory.scope, 'project')
    assert.deepEqual(inventory.skills, ['anti-slop-engineering', 'decision-guard'])

    const repeated = run(['--agent=codex', '--skills=core'])
    assert.equal(repeated.status, 0, repeated.stderr)
    assert.ok(fs.readFileSync(path.join(project, 'AGENTS.md'), 'utf8').includes('`decision-guard`:'),
      'A core-only rerun must not silently remove previously selected plugin instructions')

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

test('Setup: a symlinked selection inventory fails without following its target', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-inventory-link-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=core']).status, 0)
    const inventory = path.join(project, '.codex/skills/.anti-slop-selection.json')
    const victim = path.join(project, 'private.json')
    fs.writeFileSync(victim, '{"private":true}\n')
    fs.unlinkSync(inventory)
    fs.symlinkSync(victim, inventory)
    const result = run(['update', '--json'])
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /symbolic link/i)
    assert.equal(fs.readFileSync(victim, 'utf8'), '{"private":true}\n')
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: unknown persisted plugin cannot silently become a selected update', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-unknown-state-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=core']).status, 0)
    const inventory = path.join(project, '.codex/skills/.anti-slop-selection.json')
    const state = JSON.parse(fs.readFileSync(inventory, 'utf8'))
    state.skills.push('unknown-plugin')
    fs.writeFileSync(inventory, JSON.stringify(state))
    const result = run(['update', '--json'])
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /Unknown previously installed module/)
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: an existing symlinked module cannot be silently accepted as installed', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-existing-link-'))
  const outside = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-outside-'))
  try {
    fs.mkdirSync(path.join(project, '.codex', 'skills'), { recursive: true })
    fs.writeFileSync(path.join(outside, 'SKILL.md'), '---\nname: anti-slop-engineering\n---\n')
    fs.symlinkSync(outside, path.join(project, '.codex/skills/anti-slop-engineering'))
    const result = spawnSync(process.execPath, [installer, '--agent=codex', '--skills=core'], {
      cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
    })
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /symbolic link/i)
    assert.equal(fs.existsSync(path.join(project, 'AGENTS.md')), false)
    assert.equal(fs.readFileSync(path.join(outside, 'SKILL.md'), 'utf8'),
      '---\nname: anti-slop-engineering\n---\n')
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
    fs.rmSync(outside, { recursive: true, force: true })
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

test('Setup: preflight rejects corrupted target selection before copying', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-corrupt-preflight-'))
  try {
    const target = path.join(project, '.codex', 'skills')
    fs.mkdirSync(target, { recursive: true })
    fs.writeFileSync(path.join(target, '.anti-slop-selection.json'), '{ "format": 999 }')
    const result = spawnSync(process.execPath, [installer, '--agent=codex', '--skills=core'], {
      cwd: project,
      encoding: 'utf8',
      env: { ...process.env, HOME: project, CI: 'true' },
      timeout: 10000,
    })
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /Invalid installed module selection/i)
    assert.equal(fs.existsSync(path.join(target, 'anti-slop-engineering', 'SKILL.md')), false)
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: updateAll scopes instruction pointer updates to installed project selection', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-update-pointers-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 12000,
  })
  try {
    const setup = run(['--agent=codex', '--skills=core', '--json'])
    assert.equal(setup.status, 0, setup.stderr)
    const updateResult = run(['update', '--json'])
    assert.equal(updateResult.status, 0, updateResult.stderr)
    const agentsMd = fs.readFileSync(path.join(project, 'AGENTS.md'), 'utf8')
    assert.ok(agentsMd.includes('`anti-slop-engineering`: `.codex/skills/anti-slop-engineering/SKILL.md`'))
    assert.equal(agentsMd.includes('decision-guard'), false)
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: clean offline installation succeeds via CLI without network access', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-offline-setup-'))
  try {
    const result = spawnSync(process.execPath, [cli, 'setup', '--agent=codex', '--skills=core', '--json'], {
      cwd: project,
      encoding: 'utf8',
      env: {
        ...process.env,
        HOME: project,
        CI: 'true',
        http_proxy: 'http://127.0.0.1:0',
        https_proxy: 'http://127.0.0.1:0',
        ALL_PROXY: 'http://127.0.0.1:0',
      },
      timeout: 12000,
    })
    assert.equal(result.status, 0, result.stderr)
    const skillPath = path.join(project, '.codex', 'skills', 'anti-slop-engineering', 'SKILL.md')
    assert.ok(fs.existsSync(skillPath))
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Setup: compiler-absent environment executes setup and falls back gracefully in CLI', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-compiler-absent-'))
  const safeBin = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-safe-bin-'))
  try {
    if (!fs.existsSync(path.join(safeBin, 'node'))) {
      fs.symlinkSync(process.execPath, path.join(safeBin, 'node'))
    }
    const pythonBin = fs.existsSync('/usr/bin/python3') ? '/usr/bin/python3' : null
    if (pythonBin) {
      if (!fs.existsSync(path.join(safeBin, 'python3'))) {
        fs.symlinkSync(pythonBin, path.join(safeBin, 'python3'))
      }
      if (!fs.existsSync(path.join(safeBin, 'python'))) {
        fs.symlinkSync(pythonBin, path.join(safeBin, 'python'))
      }
    }
    const result = spawnSync(process.execPath, [cli, 'setup', '--agent=codex', '--skills=core', '--json'], {
      cwd: project,
      encoding: 'utf8',
      env: {
        ...process.env,
        HOME: project,
        PATH: `${safeBin}:/usr/bin:/bin`,
        CI: 'true',
      },
      timeout: 12000,
    })
    assert.equal(result.status, 0, result.stderr)
    const skillPath = path.join(project, '.codex', 'skills', 'anti-slop-engineering', 'SKILL.md')
    assert.ok(fs.existsSync(skillPath))
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
    fs.rmSync(safeBin, { recursive: true, force: true })
  }
})
