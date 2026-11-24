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

test('Setup: version fallback is limited to a missing package manifest', () => {
  const fixture = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-installer-version-')))
  const launch = path.join(fixture, 'scripts', 'installer.mjs')
  const manifest = path.join(fixture, 'package.json')
  const locked = path.join(fixture, 'locked')
  try {
    fs.mkdirSync(path.dirname(launch))
    fs.copyFileSync(installer, launch)
    const help = () => spawnSync(process.execPath, [launch, '--help'], { encoding: 'utf8' })
    const missing = help()
    assert.equal(missing.status, 0, missing.stderr)
    assert.match(missing.stdout, /v1\.6\.0/)
    fs.writeFileSync(manifest, '{"version":"2.3.4"}')
    const present = help()
    assert.equal(present.status, 0, present.stderr)
    assert.match(present.stdout, /v2\.3\.4/)
    fs.writeFileSync(manifest, 'malformed')
    assert.notEqual(help().status, 0)

    if (process.platform !== 'win32' && process.getuid?.() !== 0) {
      fs.unlinkSync(manifest)
      fs.mkdirSync(locked)
      fs.writeFileSync(path.join(locked, 'metadata.json'), '{"version":"3.0.0"}')
      fs.symlinkSync(path.join(locked, 'metadata.json'), manifest)
      fs.chmodSync(locked, 0o000)
      const unreadable = help()
      assert.notEqual(unreadable.status, 0, unreadable.stdout)
      assert.match(unreadable.stderr, /EACCES/)
    }
  } finally {
    if (fs.existsSync(locked)) fs.chmodSync(locked, 0o700)
    fs.rmSync(fixture, { recursive: true, force: true })
  }
})

test('Setup: explicitly empty presets fail before installing', () => {
  for (const arg of ['--preset=', '--pack=']) {
    const result = inDisposableProject([arg, '--agent=codex', '--json'])
    assert.equal(result.status, 1)
    assert.match(result.stderr, /Preset name cannot be empty/)
  }
})

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
  assert.doesNotMatch(installerHelp.stdout, /\b(todo|fixme|dev[- ]note|developer[- ]note|agent[- ]note|mock data)\b/i)
})

test('Setup: role preset backend selects backend and sre skills', () => {
  const result = inDisposableProject(['--agent=codex', '--preset=backend', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  const skills = JSON.parse(result.stdout).skills
  assert.ok(skills.includes('anti-slop-engineering'))
  assert.ok(skills.includes('decision-guard'))
  assert.ok(skills.includes('paranoid-principal-architect'))
  assert.ok(skills.includes('observability-and-slo-architect'))
  assert.equal(skills.includes('apple-craft-and-interaction-physics'), false)
})

test('Setup: role preset frontend selects frontend and UI craft skills', () => {
  const result = inDisposableProject(['--agent=codex', '--preset=frontend', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  const skills = JSON.parse(result.stdout).skills
  assert.ok(skills.includes('anti-slop-engineering'))
  assert.ok(skills.includes('ui-and-copy-discipline'))
  assert.ok(skills.includes('apple-craft-and-interaction-physics'))
  assert.ok(skills.includes('styleseed-guard'))
  assert.equal(skills.includes('zero-downtime-migration-gate'), false)
})

test('Setup: role preset lead selects lead and governance skills', () => {
  const result = inDisposableProject(['--agent=codex', '--preset=lead', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  const skills = JSON.parse(result.stdout).skills
  assert.ok(skills.includes('anti-slop-engineering'))
  assert.ok(skills.includes('decision-guard'))
  assert.ok(skills.includes('root-fix-gate'))
  assert.ok(skills.includes('grumpy-senior-staff-engineer'))
  assert.ok(skills.includes('pr-boundary-guard'))
})

test('Setup: domain pack core-decisions selects domain pack skills', () => {
  const result = inDisposableProject(['--agent=codex', '--preset=core-decisions', '--dry-run', '--json'])
  assert.equal(result.status, 0, result.stderr)
  const skills = JSON.parse(result.stdout).skills
  assert.ok(skills.includes('anti-slop-engineering'))
  assert.ok(skills.includes('decision-guard'))
  assert.ok(skills.includes('reduction-guard'))
})

test('Setup: a packaged domain manifest controls membership and reports missing modules', () => {
  const fixture = fs.realpathSync(fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-preset-manifest-')))
  try {
    const launcher = path.join(fixture, 'scripts', 'installer.mjs')
    fs.mkdirSync(path.dirname(launcher), { recursive: true })
    fs.copyFileSync(installer, launcher)
    fs.writeFileSync(path.join(fixture, 'skills.sh.json'), JSON.stringify({
      groupings: [{ title: 'Core & Decisions', skills: ['anti-slop-engineering', 'added-module', 'missing-module'] }],
    }))
    const modulePath = path.join(fixture, 'skills', 'added-module')
    fs.mkdirSync(modulePath, { recursive: true })
    fs.writeFileSync(path.join(modulePath, 'SKILL.md'), '---\nname: added-module\n---\n')
    const result = spawnSync(process.execPath, [
      launcher, '--selection-only', '--preset=core-decisions', '--skills=added-module',
    ], { cwd: fixture, encoding: 'utf8', env: { ...process.env, HOME: fixture, CI: 'true' } })
    assert.equal(result.status, 0, result.stderr)
    assert.deepEqual(JSON.parse(result.stdout).skills, ['anti-slop-engineering', 'added-module'])
    assert.match(result.stderr, /missing-module/)
  } finally {
    fs.rmSync(fixture, { recursive: true, force: true })
  }
})

test('Setup: a checkout uses its shipped core instead of a local agent copy', () => {
  const checkout = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-checkout-'))
  try {
    for (const relative of ['bin/cli.js', 'scripts/installer.mjs', 'scripts/safe_install.py', 'package.json']) {
      const destination = path.join(checkout, relative)
      fs.mkdirSync(path.dirname(destination), { recursive: true })
      fs.copyFileSync(path.join(root, relative), destination)
    }
    const core = 'skills/anti-slop-engineering/SKILL.md'
    const local = '.agents/skills/anti-slop-engineering/SKILL.md'
    for (const [relative, description] of [[core, 'Shipped core'], [local, 'Local agent copy']]) {
      const destination = path.join(checkout, relative)
      fs.mkdirSync(path.dirname(destination), { recursive: true })
      fs.writeFileSync(destination, `---\nname: anti-slop-engineering\ndescription: ${description}\n---\n`)
    }
    for (const args of [['init', '-q'], ['add', 'bin', 'scripts', 'package.json', core]]) {
      const git = spawnSync('git', args, { cwd: checkout, encoding: 'utf8' })
      assert.equal(git.status, 0, git.stderr)
    }
    const result = spawnSync(process.execPath, [
      path.join(checkout, 'bin/cli.js'), 'setup', '--agent=codex', '--scope=project', '--skills=core', '--json',
    ], { cwd: checkout, encoding: 'utf8', env: { ...process.env, HOME: checkout, CI: 'true' }, timeout: 12000 })
    assert.equal(result.status, 0, result.stderr)
    const installed = path.join(checkout, '.codex/skills/anti-slop-engineering/SKILL.md')
    assert.match(fs.readFileSync(installed, 'utf8'), /Shipped core/)
  } finally {
    fs.rmSync(checkout, { recursive: true, force: true })
  }
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

test('Removal: dry-run previews managed files without changing the installation', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-remove-preview-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 15000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=tagore-guard', '--json']).status, 0)
    const skillRoot = path.join(project, '.codex', 'skills')
    const manifest = path.join(skillRoot, '.anti-slop-selection.json')
    const before = fs.readFileSync(manifest, 'utf8')
    const result = run(['--agent=codex', '--remove', 'tagore-guard', '--dry-run', '--json'])
    assert.equal(result.status, 0, result.stderr)
    const plan = JSON.parse(result.stdout)
    assert.equal(plan.remove, 'tagore-guard')
    assert.equal(plan.dryRun, true)
    assert.equal(plan.targets.length, 1)
    assert.equal(plan.targets[0].status, 'preview')
    assert.ok(plan.targets[0].files.includes('SKILL.md'))
    assert.deepEqual(plan.targets[0].conflicts, [])
    assert.ok(fs.existsSync(path.join(skillRoot, 'tagore-guard', 'SKILL.md')))
    assert.equal(fs.readFileSync(manifest, 'utf8'), before)
    assert.ok(fs.readFileSync(path.join(project, 'AGENTS.md'), 'utf8').includes('`tagore-guard`:'))
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Removal: applying removal reconciles disk, manifest and generated block', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-remove-apply-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 15000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=tagore-guard', '--json']).status, 0)
    const entry = path.join(project, 'AGENTS.md')
    fs.appendFileSync(entry, '\nPersonal instructions remain.\n')
    const result = run(['--agent=codex', '--remove', 'tagore-guard', '--json'])
    assert.equal(result.status, 0, result.stderr)
    const report = JSON.parse(result.stdout)
    assert.equal(report.targets[0].status, 'removed')
    assert.equal(path.basename(report.targets[0].backup), 'tagore-guard')
    assert.ok(fs.existsSync(path.join(report.targets[0].backup, 'SKILL.md')))
    assert.ok(report.targets[0].files.includes('SKILL.md'))
    const skillRoot = path.join(project, '.codex', 'skills')
    assert.equal(fs.existsSync(path.join(skillRoot, 'tagore-guard')), false)
    assert.ok(fs.existsSync(path.join(skillRoot, 'anti-slop-engineering', 'SKILL.md')))
    const inventory = JSON.parse(fs.readFileSync(path.join(skillRoot, '.anti-slop-selection.json'), 'utf8'))
    assert.equal(inventory.format, 1)
    assert.deepEqual(inventory.skills, ['anti-slop-engineering'])
    const config = fs.readFileSync(entry, 'utf8')
    assert.ok(!config.includes('`tagore-guard`:'), config)
    assert.ok(config.includes('`anti-slop-engineering`:'))
    assert.ok(config.includes('Personal instructions remain.'))
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Removal: a second removal is a harmless no-op', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-remove-twice-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 15000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=tagore-guard', '--json']).status, 0)
    assert.equal(run(['--agent=codex', '--remove', 'tagore-guard', '--json']).status, 0)
    const second = run(['--agent=codex', '--remove', 'tagore-guard', '--json'])
    assert.equal(second.status, 0, second.stderr)
    assert.equal(JSON.parse(second.stdout).targets[0].status, 'not-installed')
    const inventory = JSON.parse(fs.readFileSync(
      path.join(project, '.codex', 'skills', '.anti-slop-selection.json'), 'utf8'))
    assert.deepEqual(inventory.skills, ['anti-slop-engineering'])
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Removal: a modified managed file blocks removal and is reported as a conflict', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-remove-conflict-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 15000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=tagore-guard', '--json']).status, 0)
    const installed = path.join(project, '.codex/skills/tagore-guard/SKILL.md')
    fs.writeFileSync(installed, 'my local version\n')
    const result = run(['--agent=codex', '--remove', 'tagore-guard', '--json'])
    assert.equal(result.status, 1, result.stdout)
    const report = JSON.parse(result.stdout)
    assert.equal(report.targets[0].status, 'conflict')
    assert.ok(report.targets[0].conflicts.includes('SKILL.md'))
    assert.equal(fs.readFileSync(installed, 'utf8'), 'my local version\n')
    const inventory = JSON.parse(fs.readFileSync(
      path.join(project, '.codex', 'skills', '.anti-slop-selection.json'), 'utf8'))
    assert.deepEqual(inventory.skills, ['anti-slop-engineering', 'tagore-guard'])
    assert.ok(fs.readFileSync(path.join(project, 'AGENTS.md'), 'utf8').includes('`tagore-guard`:'))
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Removal: the required core skill cannot be removed', () => {
  const result = inDisposableProject(['--agent=codex', '--remove', 'anti-slop-engineering', '--json'])
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /core/i)
})

test('Removal: a symlinked managed inventory fails without following its target', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-remove-link-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 15000,
  })
  try {
    assert.equal(run(['--agent=codex', '--skills=tagore-guard', '--json']).status, 0)
    const inventory = path.join(project, '.codex', 'skills', 'tagore-guard', '.anti-slop-managed.json')
    const victim = path.join(project, 'private.json')
    fs.writeFileSync(victim, '{"private":true}\n')
    fs.unlinkSync(inventory)
    fs.symlinkSync(victim, inventory)
    const result = run(['--agent=codex', '--remove', 'tagore-guard', '--json'])
    assert.notEqual(result.status, 0)
    assert.match(result.stderr, /symbolic link/i)
    assert.equal(fs.readFileSync(victim, 'utf8'), '{"private":true}\n')
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})

test('Removal: an unknown skill is rejected', () => {
  const result = inDisposableProject(['--agent=codex', '--remove', 'no-such-skill', '--json'])
  assert.notEqual(result.status, 0)
  assert.match(result.stderr, /Unknown or invalid/)
})

test('Removal: installed-selection audit still runs core after removal', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-remove-audit-'))
  const run = (args) => spawnSync(process.execPath, [installer, ...args], {
    cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 15000,
  })
  const git = (args) => spawnSync('git', args, { cwd: project, encoding: 'utf8' })
  try {
    git(['init', '-q'])
    git(['-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.test', 'commit', '--allow-empty', '-qm', 'fixture'])
    assert.equal(run(['--agent=codex', '--skills=tagore-guard', '--json']).status, 0)
    assert.equal(run(['--agent=codex', '--remove', 'tagore-guard', '--json']).status, 0)
    const manifest = path.join(project, '.codex', 'skills', '.anti-slop-selection.json')
    const audit = spawnSync('python3', [path.join(root, 'scripts', 'audit_runner.py'),
      'audit', '--json', '--installed-selection', manifest], {
      cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project }, timeout: 60000,
    })
    assert.equal(audit.status, 0, audit.stderr)
    const guards = JSON.parse(audit.stdout).guards
    assert.equal(guards.tagore_guard.skip_type, 'not-selected')
    assert.equal(guards.diff_guard.status, 'PASS')
    assert.equal(guards.sre_guard.status, 'PASS')
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

const claudeSettings = '.claude/settings.local.json'

let activePreviewHome = null

function inClaudeWorkspace(callback) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'ase-hook-plan-'))
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'ase-hook-home-'))
  const previousHome = activePreviewHome
  activePreviewHome = home
  try {
    callback(dir, home)
  } finally {
    activePreviewHome = previousHome
    fs.rmSync(dir, { recursive: true, force: true })
    fs.rmSync(home, { recursive: true, force: true })
  }
}

function runClaudePreview(dir, args, home = activePreviewHome || dir) {
  return spawnSync(process.execPath, [installer, ...args], {
    cwd: dir, encoding: 'utf8', env: { ...process.env, HOME: home, CI: 'true' },
  })
}

test('default project skill setup leaves Claude hook settings untouched', () => {
  inClaudeWorkspace((dir) => {
    const result = runClaudePreview(dir, ['--agent=claude', '--skills=core', '--json'])
    assert.equal(result.status, 0, result.stderr)
    assert.equal(fs.existsSync(path.join(dir, claudeSettings)), false)
    assert.equal(Object.hasOwn(JSON.parse(result.stdout), 'hookPlan'), false)
  })
})

test('explicit project selection previews real Claude settings without writing', { skip: process.platform === 'win32' }, () => {
  inClaudeWorkspace((dir) => {
    const result = runClaudePreview(dir, ['--agent=claude,cursor', '--claude-hooks', '--dry-run', '--json'])
    assert.equal(result.status, 0, result.stderr)
    const {hookPlan} = JSON.parse(result.stdout)
    assert.equal(hookPlan.status, 'would_change')
    assert.equal(hookPlan.settings, fs.realpathSync(dir) + '/' + claudeSettings)
    assert.deepEqual(hookPlan.tools, ['Read', 'Edit', 'Write'])
    assert.equal(fs.existsSync(path.join(dir, '.claude')), false)
  })
})

test('hook preview requires dry run and cannot be used to modify project settings', () => {
  inClaudeWorkspace((dir) => {
    const result = runClaudePreview(dir, ['--agent=claude', '--skills=core', '--claude-hooks', '--json'])
    assert.notEqual(result.status, 0, result.stderr)
    assert.match(result.stderr, /standalone Claude adapter/)
    assert.equal(fs.existsSync(path.join(dir, '.claude')), false)
  })
})

test('unsupported scope and invalid settings fail before installation writes', () => {
  inClaudeWorkspace((dir) => {
    for (const args of [['--agent=cursor', '--claude-hooks', '--dry-run'], ['--scope=global', '--agent=claude', '--claude-hooks', '--dry-run']]) {
      const result = runClaudePreview(dir, args)
      assert.notEqual(result.status, 0, result.stderr)
      assert.equal(fs.existsSync(path.join(dir, '.claude')), false)
      assert.equal(fs.existsSync(path.join(dir, '.cursor')), false)
    }
    fs.mkdirSync(path.join(dir, '.claude'))
    fs.writeFileSync(path.join(dir, claudeSettings), 'fixture invalid JSON')
    const result = runClaudePreview(dir, ['--agent=claude', '--skills=core', '--claude-hooks', '--dry-run', '--json'])
    assert.notEqual(result.status, 0)
    assert.equal(fs.existsSync(path.join(dir, '.claude/skills')), false)
    assert.equal(fs.readFileSync(path.join(dir, claudeSettings), 'utf8'), 'fixture invalid JSON')
  })
})

const additionalHookPreviews = [
  ['codex', '.codex/hooks.json', 'apply_patch'],
  ['gemini', '.gemini/settings.json', 'write_file'],
]

for (const [agent, settings, tool] of additionalHookPreviews) {
  test('public setup previews ' + agent + ' adapter without writing', { skip: process.platform === 'win32' }, () => {
    inClaudeWorkspace((dir) => {
      const args = ['--agent=' + agent, '--skills=core', '--' + agent + '-hooks', '--json']
      const run = (...options) => spawnSync(process.execPath, [cli, 'setup', ...args, ...options], {
        cwd: dir, encoding: 'utf8', env: { ...process.env, HOME: activePreviewHome || dir, CI: 'true' }, timeout: 12000,
      })
      const preview = run('--dry-run')
      assert.equal(preview.status, 0, preview.stderr)
      const { hookPlan } = JSON.parse(preview.stdout)
      assert.ok(hookPlan, 'Setup did not return a hook preview')
      assert.equal(hookPlan.status, 'would_change')
      assert.equal(hookPlan.settings, path.join(fs.realpathSync(dir), settings))
      assert.deepEqual(hookPlan.tools, [tool])
      assert.equal(hookPlan.requires_host_hook_trust, true)
      assert.deepEqual(fs.readdirSync(dir), [])
      assert.notEqual(run().status, 0)
      assert.notEqual(run('--dry-run', '--scope=global').status, 0)
      const otherAgent = spawnSync(process.execPath, [cli, 'setup', '--agent=cursor', '--' + agent + '-hooks', '--dry-run'], {
        cwd: dir, encoding: 'utf8', env: { ...process.env, HOME: activePreviewHome || dir, CI: 'true' }, timeout: 12000,
      })
      assert.notEqual(otherAgent.status, 0)
      assert.notEqual(run('--dry-run', '--claude-hooks').status, 0)
      assert.deepEqual(fs.readdirSync(dir), [])
    })
  })
}


test('hook preview on Windows reports the platform instead of the checkout', () => {
  inClaudeWorkspace((dir) => {
    const shim = path.join(dir, 'win32-shim.cjs')
    fs.writeFileSync(shim, 'Object.defineProperty(process, "platform", { value: "win32" })\n')
    const shimBin = path.join(dir, 'shim-bin')
    fs.mkdirSync(shimBin)
    const python3 = spawnSync('/bin/sh', ['-c', 'command -v python3'], { encoding: 'utf8' }).stdout.trim()
    fs.symlinkSync(python3, path.join(shimBin, 'python'))
    const result = spawnSync(process.execPath, [cli, 'setup', '--agent=codex', '--skills=core', '--codex-hooks', '--dry-run', '--json'], {
      cwd: dir, encoding: 'utf8', env: { ...process.env, HOME: dir, CI: 'true', NODE_OPTIONS: '--require ' + shim, PATH: shimBin + path.delimiter + process.env.PATH }, timeout: 12000,
    })
    assert.notEqual(result.status, 0, result.stdout)
    assert.match(result.stderr, /not supported on Windows/)
    assert.doesNotMatch(result.stderr, /no \.git directory/)
    assert.equal(fs.existsSync(path.join(dir, '.codex')), false)
  })
})

test('Removal preserves an unowned empty directory in the skill tree', () => {
  inClaudeWorkspace((dir) => {
    const run = (args) => runClaudePreview(dir, ['--agent=codex', '--json', ...args])
    assert.equal(run(['--skills=tagore-guard']).status, 0)
    const skill = path.join(dir, '.codex', 'skills', 'tagore-guard')
    fs.mkdirSync(path.join(skill, 'personal-notes'))
    const result = run(['--remove', 'tagore-guard'])
    assert.equal(result.status, 1, result.stderr)
    assert.deepEqual(JSON.parse(result.stdout).targets[0].conflicts, ['personal-notes'])
    assert.ok(fs.existsSync(path.join(skill, 'personal-notes')))
    assert.ok(fs.existsSync(path.join(skill, 'SKILL.md')))
  })
})

test('Removal checks the instruction destination before changing the installed skill', () => {
  inClaudeWorkspace((dir) => {
    const run = (args) => runClaudePreview(dir, ['--agent=codex', '--json', ...args])
    assert.equal(run(['--skills=tagore-guard']).status, 0)
    const entry = path.join(dir, 'AGENTS.md')
    const root = path.join(dir, '.codex', 'skills')
    const manifest = path.join(root, '.anti-slop-selection.json')
    const before = fs.readFileSync(manifest, 'utf8')
    fs.unlinkSync(entry)
    fs.mkdirSync(entry)
    assert.notEqual(run(['--remove', 'tagore-guard']).status, 0)
    assert.ok(fs.existsSync(path.join(root, 'tagore-guard', 'SKILL.md')))
    assert.equal(fs.readFileSync(manifest, 'utf8'), before)
  })
})

test('Removal preserves a file added during the handoff of the installed skill', () => {
  inClaudeWorkspace((dir) => {
    const common = ['--agent=codex', '--json']
    assert.equal(runClaudePreview(dir, [...common, '--skills=tagore-guard']).status, 0)
    const skill = path.join(dir, '.codex', 'skills', 'tagore-guard')
    const injection = path.join(dir, 'write-during-removal.mjs')
    fs.writeFileSync(injection, `
      import fs from 'node:fs';
      import path from 'node:path';
      const target = ${JSON.stringify(skill)};
      for (const action of ['rmSync', 'renameSync']) {
        const original = fs[action];
        fs[action] = (source, ...args) => {
          if (typeof source === 'string' && source.split(path.sep).join('/').endsWith('/.codex/skills/tagore-guard')) {
            fs.writeFileSync(target + '/concurrent-notes.txt', 'keep this');
          }
          return original(source, ...args);
        };
      }
    `)
    const result = spawnSync(process.execPath, ['--import', injection, installer, ...common, '--remove', 'tagore-guard'], {
      cwd: dir, encoding: 'utf8', env: { ...process.env, HOME: dir, CI: 'true' }, timeout: 15000,
    })
    assert.notEqual(result.status, 0, result.stderr)
    assert.equal(fs.readFileSync(path.join(skill, 'concurrent-notes.txt'), 'utf8'), 'keep this')
    assert.ok(fs.existsSync(path.join(skill, 'SKILL.md')))
    assert.match(fs.readFileSync(path.join(dir, 'AGENTS.md'), 'utf8'), /tagore-guard/)
  })
})

test('Removal keeps shared instructions for a different installed agent', () => {
  inClaudeWorkspace((dir) => {
    const setup = runClaudePreview(dir, ['--agent=cursor,codex', '--json', '--skills=tagore-guard'])
    assert.equal(setup.status, 0, setup.stderr)
    const result = runClaudePreview(dir, ['--agent=cursor', '--json', '--remove', 'tagore-guard'])
    assert.equal(result.status, 0, result.stderr)
    assert.ok(fs.existsSync(path.join(dir, '.codex', 'skills', 'tagore-guard', 'SKILL.md')))
    const pointers = fs.readFileSync(path.join(dir, 'AGENTS.md'), 'utf8')
    assert.ok(pointers.includes('.codex/skills/tagore-guard/SKILL.md'), pointers)
  })
})

function runCodexPreview(dir, options, home = activePreviewHome || dir) {
  return spawnSync(process.execPath, [cli, 'setup', '--agent=codex', '--skills=core', '--codex-hooks', '--dry-run', '--json', ...options], {
    cwd: dir, encoding: 'utf8', env: { ...process.env, HOME: home, CI: 'true' }, timeout: 12000,
  })
}

test('Enforcement: Codex preview identifies the session prerequisite for advisory mode', { skip: process.platform === 'win32' }, () => {
  inClaudeWorkspace((dir) => {
    const result = runCodexPreview(dir, ['--enforcement=advisory'])
    assert.equal(result.status, 0, result.stderr)
    const { hookPlan } = JSON.parse(result.stdout)
    assert.equal(hookPlan.enforcement.requested, 'advisory')
    assert.equal(hookPlan.enforcement.effective, null)
    assert.equal(hookPlan.enforcement.supported, false)
    assert.match(hookPlan.enforcement.reason, /review watch/)
    assert.equal(hookPlan.settings, path.join(fs.realpathSync(dir), '.codex', 'hooks.json'))
    assert.equal(hookPlan.requires_host_hook_trust, true)
    assert.deepEqual(fs.readdirSync(dir), [])
    const plain = JSON.parse(runCodexPreview(dir, []).stdout).hookPlan
    assert.equal(plain.enforcement.requested, null)
    assert.equal(plain.enforcement.supported, true)
    assert.deepEqual(fs.readdirSync(dir), [])
  })
})

test('Enforcement: Codex preview reports strict as explicitly unsupported', { skip: process.platform === 'win32' }, () => {
  inClaudeWorkspace((dir) => {
    const result = runCodexPreview(dir, ['--enforcement=strict'])
    assert.equal(result.status, 0, result.stderr)
    const { hookPlan } = JSON.parse(result.stdout)
    assert.equal(hookPlan.enforcement.requested, 'strict')
    assert.equal(hookPlan.enforcement.supported, false)
    assert.equal(hookPlan.enforcement.effective, null)
    assert.match(hookPlan.enforcement.reason, /strict failure blocking/)
    assert.deepEqual(fs.readdirSync(dir), [])
  })
})

test('Enforcement: Codex preview reports git-boundary as unsupported for the adapter', { skip: process.platform === 'win32' }, () => {
  inClaudeWorkspace((dir) => {
    const result = runCodexPreview(dir, ['--enforcement=git-boundary'])
    assert.equal(result.status, 0, result.stderr)
    const { hookPlan } = JSON.parse(result.stdout)
    assert.equal(hookPlan.enforcement.requested, 'git-boundary')
    assert.equal(hookPlan.enforcement.supported, false)
    assert.equal(hookPlan.enforcement.effective, null)
    assert.deepEqual(fs.readdirSync(dir), [])
  })
})

test('Enforcement: skills-only targets no hook files', { skip: process.platform === 'win32' }, () => {
  inClaudeWorkspace((dir) => {
    const result = runCodexPreview(dir, ['--enforcement=skills-only'])
    assert.equal(result.status, 0, result.stderr)
    const { hookPlan } = JSON.parse(result.stdout)
    assert.equal(hookPlan.status, 'skills_only')
    assert.equal(hookPlan.enforcement.requested, 'skills-only')
    assert.equal(hookPlan.enforcement.effective, 'skills-only')
    assert.equal(hookPlan.enforcement.supported, true)
    assert.deepEqual(hookPlan.tools, [])
    assert.equal(hookPlan.requires_host_hook_trust, false)
    assert.deepEqual(fs.readdirSync(dir), [])
  })
})

test('Enforcement: previews preserve an existing user hooks configuration', { skip: process.platform === 'win32' }, () => {
  inClaudeWorkspace((dir) => {
    fs.mkdirSync(path.join(dir, '.codex'))
    const settings = path.join(dir, '.codex', 'hooks.json')
    const content = '{"hooks":{"PreToolUse":[{"hooks":[{"type":"command","command":"echo user-hook"}]}]}}\n'
    fs.writeFileSync(settings, content)
    for (const mode of ['advisory', 'strict']) {
      const result = runCodexPreview(dir, ['--enforcement=' + mode])
      assert.equal(result.status, 0, result.stderr)
      const { hookPlan } = JSON.parse(result.stdout)
      assert.equal(hookPlan.enforcement.requested, mode)
      assert.equal(fs.readFileSync(settings, 'utf8'), content)
    }
  })
})

test('Enforcement: the flag is rejected without a preview, for other adapters, or with an unknown mode', { skip: process.platform === 'win32' }, () => {
  inClaudeWorkspace((dir) => {
    const run = (args) => spawnSync(process.execPath, [cli, 'setup', ...args], {
      cwd: dir, encoding: 'utf8', env: { ...process.env, HOME: activePreviewHome || dir, CI: 'true' }, timeout: 12000,
    })
    const noPreview = run(['--agent=codex', '--skills=core', '--enforcement=advisory', '--dry-run', '--json'])
    assert.notEqual(noPreview.status, 0)
    assert.match(noPreview.stderr, /--enforcement/)
    const unknown = runCodexPreview(dir, ['--enforcement=banana'])
    assert.notEqual(unknown.status, 0)
    assert.match(unknown.stderr, /Unknown enforcement mode/)
    const gemini = run(['--agent=gemini', '--skills=core', '--gemini-hooks', '--dry-run', '--json', '--enforcement=advisory'])
    assert.notEqual(gemini.status, 0)
    assert.match(gemini.stderr, /only for the Codex/)
    assert.deepEqual(fs.readdirSync(dir), [])
  })
})

test('Setup: tracked instruction file updates require explicit consent', () => {
  const project = fs.mkdtempSync(path.join(os.tmpdir(), 'anti-slop-consent-'))
  try {
    const git = (args) => {
      const result = spawnSync('git', args, { cwd: project, encoding: 'utf8' })
      assert.equal(result.status, 0, result.stderr)
    }
    const run = (args) => spawnSync(process.execPath, [installer, ...args], {
      cwd: project, encoding: 'utf8', env: { ...process.env, HOME: project, CI: 'true' }, timeout: 20000,
    })
    git(['init', '-q', '.'])
    git(['config', 'user.email', 'test@example.com'])
    git(['config', 'user.name', 'Test'])
    const entry = path.join(project, 'AGENTS.md')
    const original = '# Project\n\nHand-written instructions.\n'
    fs.writeFileSync(entry, original)
    git(['add', 'AGENTS.md'])
    git(['commit', '-qm', 'init'])

    const dry = run(['--agent=codex', '--dry-run', '--json'])
    assert.equal(dry.status, 0, dry.stderr)
    const plan = JSON.parse(dry.stdout)
    assert.equal(plan.selections.length, 1)
    assert.equal(plan.selections[0].action, 'create')
    assert.equal(plan.pointers.length, 1)
    assert.equal(plan.pointers[0].file, entry)
    assert.equal(plan.pointers[0].action, 'update')
    assert.equal(plan.pointers[0].tracked, true)
    assert.equal(plan.pointers[0].requiresConsent, true)
    assert.equal(fs.readFileSync(entry, 'utf8'), original)
    assert.equal(spawnSync('git', ['status', '--porcelain'], { cwd: project, encoding: 'utf8' }).stdout, '')

    const human = run(['--agent=codex', '--dry-run'])
    assert.equal(human.status, 0, human.stderr)
    assert.match(human.stdout, /pointers/)
    assert.match(human.stdout, /AGENTS\.md/)

    const blocked = run(['--agent=codex', '--json'])
    assert.equal(blocked.status, 1)
    assert.match(blocked.stderr, /--update-instructions/)
    assert.equal(fs.readFileSync(entry, 'utf8'), original)
    assert.equal(fs.existsSync(path.join(project, '.codex')), false)

    const applied = run(['--agent=codex', '--update-instructions', '--json'])
    assert.equal(applied.status, 0, applied.stderr)
    const updated = fs.readFileSync(entry, 'utf8')
    assert.match(updated, /anti-slop-engineering:start/)
    assert.match(updated, /Hand-written instructions\./)

    const settled = JSON.parse(run(['--agent=codex', '--dry-run', '--json']).stdout)
    assert.equal(settled.pointers[0].action, 'no-op')
    assert.equal(settled.pointers[0].requiresConsent, false)

    const repeat = run(['--agent=codex', '--json'])
    assert.equal(repeat.status, 0, repeat.stderr)
    assert.equal(fs.readFileSync(entry, 'utf8'), updated)
  } finally {
    fs.rmSync(project, { recursive: true, force: true })
  }
})
