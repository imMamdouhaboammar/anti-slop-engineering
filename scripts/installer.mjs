#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { spawnSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const rootDir = path.resolve(__dirname, '..')

const pkgPath = path.join(rootDir, 'package.json')
export const VERSION = fs.existsSync(pkgPath)
  ? JSON.parse(fs.readFileSync(pkgPath, 'utf8')).version
  : '1.6.0'

export const CORE_SKILL = 'anti-slop-engineering'

export const AGENTS = [
  { id: 'antigravity', label: 'Antigravity', dir: '.agents/skills', globalDir: '.gemini/config/skills', entry: 'AGENTS.md' },
  { id: 'claude', label: 'Claude Code', dir: '.claude/skills', entry: 'CLAUDE.md' },
  { id: 'cursor', label: 'Cursor', dir: '.cursor/skills', entry: 'AGENTS.md' },
  { id: 'codex', label: 'Codex', dir: '.codex/skills', globalDir: '.agents/skills', readsAlso: ['.agents/skills'], entry: 'AGENTS.md' },
  { id: 'opencode', label: 'OpenCode', dir: '.opencode/skills', globalDir: '.config/opencode/skills', readsAlso: ['.claude/skills', '.agents/skills'], entry: 'AGENTS.md' },
  { id: 'cline', label: 'Cline', dir: '.cline/skills', readsAlso: ['.claude/skills'], entry: 'AGENTS.md' },
  { id: 'amp', label: 'Amp', dir: '.agents/skills', globalDir: '.config/agents/skills', readsAlso: ['.claude/skills'], entry: 'AGENTS.md' },
  { id: 'gemini', label: 'Gemini CLI', dir: '.gemini/skills', entry: 'GEMINI.md' },
  { id: 'hermes', label: 'Hermes', dir: '.hermes/skills', readsAlso: ['.agents/skills'], entry: 'AGENTS.md' },
  { id: 'copilot', label: 'GitHub Copilot', dir: '.agents/skills', readsAlso: ['.claude/skills'], entry: 'AGENTS.md' },
  { id: 'kimi', label: 'Kimi Code', dir: '.agents/skills', entry: 'AGENTS.md' },
  { id: 'deepseek', label: 'DeepSeek Harness', dir: '.agents/skills', entry: 'AGENTS.md' },
  { id: 'pi', label: 'Pi', dir: '.pi/skills', globalDir: '.pi/agent/skills', readsAlso: ['.agents/skills'], entry: 'AGENTS.md' },
  { id: 'windsurf', label: 'Windsurf', dir: '.windsurf/skills', entry: 'AGENTS.md' },
]

export function skillSourceDir() {
  const rootSkills = path.join(rootDir, 'skills')
  if (fs.existsSync(rootSkills)) return rootSkills
  const agentSkills = path.join(rootDir, '.agents', 'skills')
  if (fs.existsSync(agentSkills)) return agentSkills
  return null
}

function readSkillMetadata(file) {
  if (!fs.existsSync(file) || !fs.lstatSync(file).isFile()) return null
  const content = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n')
  if (!content.startsWith('---\n')) return null
  const end = content.indexOf('\n---', 4)
  if (end < 0) return null
  const lines = content.slice(4, end).split('\n')
  const name = lines.find((line) => line.startsWith('name:'))?.slice(5).trim().replace(/^['"]|['"]$/g, '')
  const index = lines.findIndex((line) => line.startsWith('description:'))
  const raw = index < 0 ? '' : lines[index].slice('description:'.length).trim()
  const parts = []
  if (/^[>|]/.test(raw)) {
    for (const line of lines.slice(index + 1)) {
      if (!/^\s+\S/.test(line)) break
      parts.push(line.trim())
    }
  }
  return { name, description: parts.length ? parts.join(' ') : raw.replace(/^['"]|['"]$/g, '') }
}

export function listAvailableSkills() {
  const dir = skillSourceDir()
  if (!dir) return [CORE_SKILL]
  const entries = fs.readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory() && readSkillMetadata(path.join(dir, e.name, 'SKILL.md'))?.name === e.name)
    .map((e) => e.name)
  if (!entries.includes(CORE_SKILL)) entries.unshift(CORE_SKILL)
  return entries
}

export function listAvailableModules() {
  const source = skillSourceDir()
  return listAvailableSkills().map((id) => {
    const file = source && path.join(source, id, 'SKILL.md')
    return { id, required: id === CORE_SKILL, description: (file && readSkillMetadata(file)?.description) || id }
  })
}

export function resolveSkillSelection(requested, available = listAvailableSkills()) {
  const requestedIds = requested === 'all' ? available
    : requested === 'core' || requested === '' ? []
      : Array.isArray(requested) ? requested : requested.split(',').map((id) => id.trim())
  const valid = new Set(available)
  for (const id of requestedIds) {
    if (!/^[a-z0-9][a-z0-9-]*$/.test(id) || !valid.has(id)) {
      throw new Error(`Unknown or invalid plugin: ${id}`)
    }
  }
  return [CORE_SKILL, ...new Set(requestedIds.filter((id) => id !== CORE_SKILL))]
}

function resolveBase(location) {
  return location === 'global' ? os.homedir() : process.cwd()
}

function skillPath(agent, location) {
  const dir = location === 'global' ? (agent.globalDir ?? agent.dir) : agent.dir
  return path.join(resolveBase(location), dir)
}

export function resolveTargets(location, selected = AGENTS.map((a) => a.id)) {
  const byPath = new Map()
  for (const agent of AGENTS.filter((a) => selected.includes(a.id))) {
    const target = skillPath(agent, location)
    const found = byPath.get(target)
    if (found) found.agents.push(agent)
    else byPath.set(target, { agents: [agent], path: target, exists: fs.existsSync(target) })
  }
  return [...byPath.values()]
}

export function detectAgents(location) {
  return AGENTS.flatMap((a) => fs.existsSync(path.dirname(skillPath(a, location))) ? [a.id] : [])
}

function safeCopy(src, dest, version, dryRun = false) {
  const helper = path.join(rootDir, 'scripts', 'safe_install.py')
  const candidates = process.platform === 'win32' ? [['py', '-3'], ['python', '']] : [['python3', '']]
  for (const [executable, flag] of candidates) {
    const args = [...(flag ? [flag] : []), helper, '--source', src, '--dest', dest]
    if (version) args.push('--version', version)
    if (dryRun) args.push('--dry-run')
    const result = spawnSync(executable, args, { encoding: 'utf8' })
    if (result.error?.code === 'ENOENT') continue
    if (result.error || result.status !== 0) {
      throw new Error(result.stderr?.trim() || result.error?.message || `Safe installer exited ${result.status}`)
    }
    return JSON.parse(result.stdout)
  }
  throw new Error('Python 3 is required for safe file installation')
}

function sourceForSkill(skill, source) {
  if (skill === CORE_SKILL) {
    for (const candidate of [
      path.join(rootDir, '.agents', 'skills', CORE_SKILL),
      path.join(rootDir, 'skills', CORE_SKILL),
      rootDir,
    ]) {
      if (fs.existsSync(path.join(candidate, 'SKILL.md'))) return candidate
    }
  } else if (source) {
    return path.join(source, skill)
  }
  throw new Error(`Missing skill source: ${skill}`)
}

export function installSkills({ skills, targets, overwrite = false, dryRun = false }) {
  const source = skillSourceDir()
  const available = new Set(listAvailableSkills())
  for (const skill of skills) {
    if (!/^[a-z0-9][a-z0-9-]*$/.test(skill) || !available.has(skill)) {
      throw new Error(`Invalid skill ID or unknown skill: ${skill}`)
    }
  }
  const written = []
  for (const t of targets) {
    for (const skill of skills) {
      const src = sourceForSkill(skill, source)

      const dest = path.join(t.path, skill)
      assertSafeFilePath(dest)
      if (fs.existsSync(dest) && !overwrite) {
        written.push({ skill, agents: t.agents.map((a) => a.id), path: dest, status: 'skipped' })
        continue
      }
      const outcome = safeCopy(src, dest, VERSION, dryRun)
      written.push({ skill, agents: t.agents.map((a) => a.id), path: dest, ...outcome })
    }
  }
  return written
}

const POINTER_START = '<!-- anti-slop-engineering:start -->'
const POINTER_END = '<!-- anti-slop-engineering:end -->'
const SELECTION_FILE = '.anti-slop-selection.json'

function assertSafeFilePath(entry) {
  for (let current = path.resolve(entry); ; current = path.dirname(current)) {
    try {
      if (fs.lstatSync(current).isSymbolicLink()) {
        throw new Error(`Refusing symbolic link in installer path: ${current}`)
      }
    } catch (err) {
      if (err.code !== 'ENOENT') throw err
    }
    if (current === path.dirname(current)) break
  }
}

function isString(value) {
  return Object.prototype.toString.call(value) === '[object String]'
}

function readSelection(target) {
  const file = path.join(target.path, SELECTION_FILE)
  assertSafeFilePath(file)
  if (!fs.existsSync(file)) return null
  const state = JSON.parse(fs.readFileSync(file, 'utf8'))
  if (state?.format !== 1 || !Array.isArray(state.skills) || !Array.isArray(state.agents)
    || !['project', 'global'].includes(state.scope) || !isString(state.version)) {
    throw new Error(`Invalid installed module selection: ${file}`)
  }
  const available = new Set(listAvailableSkills())
  for (const id of state.skills) {
    if (!isString(id) || !available.has(id)) {
      throw new Error(`Unknown previously installed module ${String(id)} in ${file}`)
    }
  }
  if (!state.skills.includes(CORE_SKILL)) throw new Error(`Missing required core in ${file}`)
  return state
}

function writeSelections(targets, scope, skills) {
  const states = []
  for (const target of targets) {
    const previous = readSelection(target)
    const selected = [...new Set([...(previous?.skills || []), ...skills])]
      .filter((id) => fs.existsSync(path.join(target.path, id, 'SKILL.md')))
    const state = { format: 1, version: VERSION, scope,
      agents: target.agents.map((agent) => agent.id), skills: selected }
    const file = path.join(target.path, SELECTION_FILE)
    const temporary = `${file}.${process.pid}.${randomUUID()}.tmp`
    try {
      fs.writeFileSync(temporary, JSON.stringify(state, null, 2) + '\n', { flag: 'wx' })
      fs.renameSync(temporary, file)
    } finally {
      if (fs.existsSync(temporary)) fs.unlinkSync(temporary)
    }
    states.push({ file, ...state })
  }
  return states
}

function pointerBlock(skills, skillPaths) {
  return [
    POINTER_START,
    '## anti-slop-engineering',
    'Follow Anti-Slop Engineering standards, Google SRE Discipline (KISS, DRY, YAGNI, Fix Issues at Scale), and clean-room gates:',
    ...skills.filter((s) => skillPaths.has(s)).map((s) => `- \`${s}\`: \`${skillPaths.get(s)}\``),
    'Before concluding tasks, verify against automated guards: `bunx anti-slop-engineering check --base HEAD`.',
    'Run audit dossier on demand: `bunx anti-slop-engineering audit`.',
    'To update anti-slop-engineering across all agents: `bunx anti-slop-engineering update`.',
    POINTER_END,
  ]
}

function scanMarkers(lines) {
  const fenced = Array.from({ length: lines.length }, () => false)
  let mark = null
  let len = 0
  let from = -1
  lines.forEach((line, i) => {
    const m = /^\s*(`{3,}|~{3,})/.exec(line)
    if (m) {
      if (!mark) {
        mark = m[1][0]
        len = m[1].length
        from = i
      } else if (m[1][0] === mark && m[1].length >= len && /^[ \t]*$/.test(line.slice(m[0].length))) {
        mark = null
        from = -1
      }
      fenced[i] = true
      return
    }
    fenced[i] = Boolean(mark)
  })
  if (mark) for (let i = from; i < lines.length; i++) fenced[i] = false

  const starts = []
  const ends = []
  lines.forEach((line, i) => {
    if (fenced[i]) return
    const t = line.trim()
    if (t === POINTER_START) starts.push(i)
    else if (t === POINTER_END) ends.push(i)
  })
  return { starts, ends }
}

export function writeBlock(entry, block) {
  assertSafeFilePath(entry)
  let existing = ''
  let exists = true
  try {
    existing = fs.readFileSync(entry, 'utf8')
  } catch (err) {
    if (err && err.code !== 'ENOENT') throw err
    exists = false
  }
  const crlf = (existing.match(/\r\n/g) || []).length
  const eol = crlf > (existing.match(/\n/g) || []).length - crlf ? '\r\n' : '\n'
  const lines = existing ? existing.split(/\r?\n/) : []
  const { starts, ends } = scanMarkers(lines)
  const start = starts.length ? starts[0] : -1
  const end = start === -1 ? -1 : ends.find((i) => i > start) ?? -1
  const paired = start !== -1 && end !== -1

  const removed = new Set([...starts, ...ends])
  if (paired) for (let i = start; i <= end; i++) removed.add(i)

  const insertAt = paired ? start : lines.length
  const head = lines.slice(0, insertAt).filter((_, i) => !removed.has(i))
  const tail = lines.slice(insertAt).filter((_, i) => !removed.has(insertAt + i))

  while (head.length && head[head.length - 1].trim() === '') head.pop()
  while (tail.length && tail[0].trim() === '') tail.shift()

  const body = [...head, '', ...block, ...(tail.length ? ['', ...tail] : [])]
    .join(eol)
    .replace(/^\r?\n+/, '')
    .trimEnd()

  const helper = path.join(rootDir, 'scripts', 'safe_install.py')
  const expected = exists ? createHash('sha256').update(existing).digest('hex') : 'absent'
  const candidates = process.platform === 'win32' ? [['py', '-3'], ['python', '']] : [['python3', '']]
  for (const [executable, flag] of candidates) {
    const args = [...(flag ? [flag] : []), helper, '--write-instruction', path.resolve(entry), '--expected-hash', expected]
    const result = spawnSync(executable, args, { encoding: 'utf8', input: body + eol })
    if (result.error?.code === 'ENOENT') continue
    if (result.error || result.status !== 0) {
      throw new Error(result.stderr?.trim() || result.error?.message || `Instruction writer exited ${result.status}`)
    }
    return
  }
  throw new Error('Python 3 is required for safe agent instruction updates')
}

export function updatePointers({ targets, skills }) {
  const entries = new Map()
  const validSkills = new Set(listAvailableSkills())
  for (const t of targets) {
    for (const a of t.agents) {
      if (!entries.has(a.entry)) entries.set(a.entry, new Map())
      const skillPaths = entries.get(a.entry)
      for (const skill of skills) {
        const file = path.join(t.path, skill, 'SKILL.md')
        if (!validSkills.has(skill) || skillPaths.has(skill) || !fs.existsSync(file)) continue
        if (readSkillMetadata(file)?.name !== skill) continue
        skillPaths.set(skill, path.relative(process.cwd(), file).split(path.sep).join('/'))
      }
    }
  }

  const written = []
  for (const [name, skillPaths] of entries) {
    const entry = path.join(process.cwd(), name)
    writeBlock(entry, pointerBlock(skills, skillPaths))
    written.push(entry)
  }
  return written
}

export function updateAll({ locations = ['project', 'global'] } = {}) {
  const results = []
  const projectTargets = []
  const allAvailable = listAvailableSkills()

  for (const location of locations) {
    for (const target of resolveTargets(location)) {
      if (!fs.existsSync(path.join(target.path, CORE_SKILL))) continue
      const saved = readSelection(target)
      const skills = (saved?.skills || allAvailable).filter((s) => fs.existsSync(path.join(target.path, s)))
      if (skills.length === 0) continue
      const entries = installSkills({ skills, targets: [target], overwrite: true })
      const state = writeSelections([target], location, skills)[0]
      const changes = Object.fromEntries(
        ['installed', 'updated', 'preserved', 'skipped', 'conflicted'].map(
          (status) => [status, entries.flatMap((entry) => entry[status] || [])]
        )
      )
      results.push({ location, path: target.path, agents: target.agents.map((a) => a.id),
        skills, version: VERSION, changes, entries, state })
      if (location === 'project') projectTargets.push(target)
    }
  }

  const pointers = projectTargets.length > 0
    ? updatePointers({ targets: projectTargets, skills: allAvailable })
    : []
  return { results, pointers }
}

function optionValue(args, names) {
  for (const name of names) {
    const index = args.findIndex((arg) => arg === `--${name}` || arg.startsWith(`--${name}=`))
    if (index === -1) continue
    const raw = args[index]
    if (raw.includes('=')) return raw.slice(raw.indexOf('=') + 1)
    const value = args[index + 1]
    if (!value || value.startsWith('--')) throw new Error(`Missing value for --${name}`)
    return value
  }
  return null
}

export async function promptForSkills(modules, targets, input = process.stdin, output = process.stdout,
  setup = { scope: 'project', agents: [], allowTargetChange: true }) {
  const rl = readline.createInterface({ input, output, terminal: true })
  rl.on('SIGINT', () => rl.close())
  const ask = (prompt) => new Promise((resolve) => {
    let finished = false
    const finish = (answer) => {
      if (finished) return
      finished = true
      rl.off('close', closed)
      resolve(answer)
    }
    const closed = () => finish(null)
    rl.on('close', closed)
    rl.question(prompt, finish)
  })
  const optional = modules.filter((module) => !module.required)
  const width = Math.max(32, output.columns || 80)
  let activeScope = setup.scope
  let activeAgents = setup.agents
  let activeTargets = targets
  try {
    while (true) {
      output.write('\nAnti-Slop Engineering setup (Core is required)\n')
      output.write('  1. Core only\n  2. Select plugins\n  3. Install everything\n')
      if (setup.allowTargetChange) output.write('  t. Change agents/scope\n')
      output.write('  q. Cancel\n')
      const mode = (await ask('Choose installation: '))?.trim().toLowerCase()
      if (mode == null || mode === 'q') return null
      if (mode === 't' && setup.allowTargetChange) {
        output.write(`Available agents: ${AGENTS.map((agent) => agent.id).join(', ')}\n`)
        const agentInput = (await ask('Agent IDs (comma-separated, Enter keep): '))?.trim()
        if (agentInput == null) return null
        const nextAgents = agentInput
          ? [...new Set(agentInput.split(',').map((id) => id.trim().toLowerCase()))] : activeAgents
        const known = new Set(AGENTS.map((agent) => agent.id))
        if (nextAgents.length === 0 || nextAgents.some((agent) => !known.has(agent))) {
          output.write('Unknown agent selection; keeping previous targets\n')
          continue
        }
        const scopeInput = (await ask('Scope [project/global] (Enter keep): '))?.trim().toLowerCase()
        if (scopeInput == null) return null
        if (scopeInput && !['project', 'global'].includes(scopeInput)) {
          output.write('Unknown scope; keeping previous targets\n')
          continue
        }
        activeScope = scopeInput || activeScope
        activeAgents = nextAgents
        activeTargets = resolveTargets(activeScope, activeAgents)
        continue
      }
      if (!['1', '2', '3'].includes(mode)) {
        output.write('Enter 1, 2, 3, t, or q\n')
        continue
      }
      let skills = [CORE_SKILL]
      if (mode === '3') skills = resolveSkillSelection('all')
      if (mode === '2') {
        output.write('\nSelect optional plugins (Core remains installed):\n')
        optional.forEach((module, index) => {
          const name = `${index + 1}. ${module.id}`
          for (let i = 0; i < name.length; i += width - 4) {
            output.write(`  ${name.slice(i, i + width - 4)}\n`)
          }
          const limit = width - 8
          output.write(`    ${module.description.slice(0, limit)}${module.description.length > limit ? '...' : ''}\n`)
        })
        const choice = (await ask('Plugins (comma-separated; b back): '))?.trim()
        if (choice == null || choice.toLowerCase() === 'q') return null
        if (choice.toLowerCase() === 'b') continue
        const parts = choice ? choice.split(',').map((part) => part.trim()) : []
        const picked = []
        let invalid = null
        for (const part of parts) {
          const plugin = /^\d+$/.test(part) ? optional[Number(part) - 1]?.id : part
          if (!plugin || !optional.some((module) => module.id === plugin)) {
            invalid = part
            break
          }
          picked.push(plugin)
        }
        if (invalid != null) {
          output.write(`Unknown plugin selection: ${invalid}\n`)
          continue
        }
        skills = resolveSkillSelection(picked)
      }
      output.write(`\nInstallation plan:\n  Required: ${CORE_SKILL}\n`)
      output.write(`  Optional: ${skills.filter((skill) => skill !== CORE_SKILL).join(', ') || '(none)'}\n`)
      activeTargets.forEach((target) => output.write(`  Target: ${target.path}\n`))
      const operations = installSkills({ skills, targets: activeTargets, overwrite: true, dryRun: true })
      const counts = ['installed', 'updated', 'preserved', 'skipped', 'conflicted']
        .map((kind) => `${kind}: ${operations.reduce((total, entry) => total + (entry[kind]?.length || 0), 0)}`)
      output.write(`  Files: ${counts.join(', ')}\n`)
      for (const entry of operations) {
        for (const relative of entry.installed || []) output.write(`  Add: ${entry.path}/${relative}\n`)
        for (const relative of entry.updated || []) output.write(`  Update: ${entry.path}/${relative}\n`)
        if (entry.conflicted?.length) output.write(`  Conflicts preserved: ${entry.path}: ${entry.conflicted.join(', ')}\n`)
      }
      const confirmation = (await ask('Confirm installation? [y/N/b]: '))?.trim().toLowerCase()
      if (confirmation == null || confirmation === 'q') return null
      if (confirmation === 'b') continue
      if (confirmation === 'y' || confirmation === 'yes') {
        return { skills, targets: activeTargets, scope: activeScope, agents: activeAgents }
      }
      output.write('Installation cancelled before any files were changed\n')
      return null
    }
  } finally {
    rl.close()
  }
}

export async function runInstallerCLI(args = process.argv.slice(2)) {
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
📦 Anti-Slop Engineering Universal Multi-Agent Installer (v${VERSION})

Core is required in every installation. Optional skill plugins are discovered
from bundled SKILL.md definitions; native guards are still shipped together.
An interactive terminal prompts when no explicit skill selection was given.
CI, piped input, --json and --dry-run default to core only.

Usage:
  bunx anti-slop-engineering install [options]
  bunx anti-slop-engineering update
  bunx anti-slop-engineering setup

Options:
  --agent <names>     Target agents (comma-separated, or 'all'). Default: detected agents
  --scope <scope>     Install scope: 'project' (default) or 'global'
  --skills <skills>   Optional skill IDs: 'all', 'core', or comma-separated names
  --plugins <names>   Alias for --skills; core is always included
  --all               Select every available optional skill
  --overwrite         Refresh managed files, preserving local edits and conflicts
  --dry-run           Simulate installation without writing files
  --json              Output JSON result
  --no-interactive    Skip terminal selection (defaults to core only)
  --help, -h          Show this help menu
`)
    return 0
  }

  const isUpdate = args.includes('--update') || args[0] === 'update'
  if (isUpdate) {
    const { results, pointers } = updateAll()
    if (args.includes('--json')) {
      console.log(JSON.stringify({ updated: results, pointers }, null, 2))
    } else {
      console.log(`\n🔄 Checked ${results.length} installed target(s) for anti-slop-engineering v${VERSION}.`)
      for (const r of results) {
        console.log(`  ${r.path} (${r.agents.join(', ')}): ${r.changes.updated.length} updated, ${r.changes.installed.length} installed, ${r.changes.skipped.length} unchanged`)
        for (const entry of r.entries) {
          if (entry.conflicted?.length) console.log(`  ⚠ Conflicts preserved in ${entry.path}: ${entry.conflicted.join(', ')}`)
          if (entry.backup) console.log(`  Recovery backup: ${entry.backup}`)
        }
      }
      if (pointers.length > 0) {
        console.log(`  ✓ Pointers refreshed in: ${pointers.join(', ')}`)
      }
    }
    return 0
  }

  const scopeArg = optionValue(args, ['scope']) || (args.includes('--global') ? 'global' : 'project')
  const agentArg = optionValue(args, ['agent'])
  const skillsArg = args.includes('--all') ? 'all' : optionValue(args, ['skills', 'plugins', 'modules'])
  const overwrite = args.includes('--overwrite')
  const dryRun = args.includes('--dry-run')
  const jsonMode = args.includes('--json')
  const selectionOnly = args.includes('--selection-only')
  if (!['project', 'global'].includes(scopeArg)) throw new Error(`Invalid installation scope: ${scopeArg}`)

  const detected = detectAgents(scopeArg)
  let selectedAgents = []
  if (agentArg === 'all') {
    selectedAgents = AGENTS.map((a) => a.id)
  } else if (agentArg) {
    selectedAgents = agentArg.split(',').map((s) => s.trim().toLowerCase())
  } else {
    selectedAgents = detected.length > 0 ? detected : ['antigravity', 'claude', 'cursor']
  }
  const validAgents = new Set(AGENTS.map((agent) => agent.id))
  for (const agent of selectedAgents) {
    if (!validAgents.has(agent)) throw new Error(`Unknown or invalid agent: ${agent}`)
  }

  const availableSkills = listAvailableSkills()
  let selectedSkills = resolveSkillSelection(skillsArg ?? 'core', availableSkills)

  let targets = resolveTargets(scopeArg, selectedAgents)
  let resolvedScope = scopeArg

  const promptOutput = selectionOnly ? process.stderr : process.stdout
  const interactive = !dryRun && !jsonMode && !process.env.CI && !args.includes('--no-interactive')
    && skillsArg == null && process.stdin.isTTY && promptOutput.isTTY
  if (interactive) {
    const response = await promptForSkills(listAvailableModules(), targets, process.stdin, promptOutput,
      { scope: resolvedScope, agents: selectedAgents, allowTargetChange: !selectionOnly })
    if (response == null) {
      console.error('Setup cancelled; no installation files were changed')
      return 130
    }
    selectedSkills = response.skills
    targets = response.targets
    resolvedScope = response.scope
    selectedAgents = response.agents
  }

  if (selectionOnly) {
    console.log(JSON.stringify({ skills: selectedSkills, agents: selectedAgents, scope: resolvedScope }))
    return 0
  }

  if (dryRun) {
    const operations = installSkills({ skills: selectedSkills, targets, overwrite, dryRun: true })
    const plan = { scope: resolvedScope, agents: selectedAgents, skills: selectedSkills, targets: targets.map((t) => t.path), operations }
    if (jsonMode) console.log(JSON.stringify(plan, null, 2))
    else console.log('Dry-run installation plan:', plan)
    return 0
  }

  const installed = installSkills({ skills: selectedSkills, targets, overwrite: overwrite || interactive })
  const selections = writeSelections(targets, resolvedScope, selectedSkills)
  const installedSelection = [...new Set(selections.flatMap((state) => state.skills))]
  const pointers = resolvedScope === 'project' ? updatePointers({ targets, skills: installedSelection }) : []

  if (jsonMode) {
    console.log(JSON.stringify({ installed, pointers, selections, version: VERSION }, null, 2))
  } else {
    const changed = installed.filter((item) => item.installed?.length || item.updated?.length)
    console.log(`\n✅ Installed or updated ${changed.length} skill entries across ${targets.length} agent target(s).`)
    console.log(`  Modules: ${selectedSkills.join(', ')}`)
    for (const item of installed) {
      if (item.conflicted?.length) console.log(`  ⚠ Conflicts preserved in ${item.path}: ${item.conflicted.join(', ')}`)
      if (item.backup) console.log(`  Previous installation retained: ${item.backup}`)
    }
    for (const t of targets) {
      console.log(`  Target: ${t.path} (${t.agents.map((a) => a.label).join(', ')})`)
    }
    if (pointers.length > 0) {
      console.log(`  Instruction pointers written: ${pointers.join(', ')}`)
    }
  }
  return 0
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  runInstallerCLI().then((code) => {
    if (code !== 0) process.exitCode = code
  }).catch((err) => {
    console.error(`Installer error: ${err.message}`)
    process.exitCode = 1
  })
}
