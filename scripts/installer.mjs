#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import tty from 'node:tty'
import { spawnSync } from 'node:child_process'
import { createHash, randomUUID } from 'node:crypto'
import readline from 'node:readline'
import { fileURLToPath } from 'node:url'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const rootDir = path.resolve(__dirname, '..')

function readPackageVersion() {
  try {
    return JSON.parse(fs.readFileSync(path.join(rootDir, 'package.json'), 'utf8')).version
  } catch (error) {
    if (error.code === 'ENOENT') return '1.6.0'
    throw error
  }
}

export const VERSION = readPackageVersion()

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
  if (!fs.existsSync(path.join(rootDir, '.git')) && fs.existsSync(agentSkills)) return agentSkills
  return null
}

function readSkillMetadata(file) {
  let content
  try {
    content = fs.readFileSync(file, 'utf8').replace(/\r\n/g, '\n')
  } catch (err) {
    if (err && (err.code === 'ENOENT' || err.code === 'EISDIR' || err.code === 'ENOTDIR')) return null
    throw err
  }
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

function readDomainGroups() {
  try {
    return JSON.parse(fs.readFileSync(path.join(rootDir, 'skills.sh.json'), 'utf8')).groupings
  } catch (error) {
    if (error.code === 'ENOENT') return []
    throw error
  }
}

const domainGroups = readDomainGroups()
export const DOMAIN_PACKS = Object.fromEntries(domainGroups.map(({ title, skills }) => [
  title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, ''), skills,
]))

const BACKEND = [
  'decision-guard', 'root-fix-gate', 'future-scale-gate',
  ...(DOMAIN_PACKS['systems-architecture'] ?? []),
  ...(DOMAIN_PACKS['performance-diagnostics'] ?? []),
  'deterministic-simulation-and-property-testing', 'verification-oracle-architect',
  'demock-guard', 'api-ergonomics-and-contract-governor',
]
const FRONTEND = [
  ...(DOMAIN_PACKS['ui-motion-craft'] ?? []),
  'type-level-and-ast-slop-gate', 'comment-budget-guard', 'mechanical-sympathy-and-perf-gate',
]
const LEAD = [
  ...(DOMAIN_PACKS['core-decisions'] ?? []),
  'api-ergonomics-and-contract-governor', 'type-level-and-ast-slop-gate',
  'comment-budget-guard', 'pr-boundary-guard', 'demock-guard', 'mandela-guard', 'honeypot-trap-guard',
  ...(DOMAIN_PACKS['discourse-handoffs'] ?? []),
]

export const PRESETS = {
  minimal: [CORE_SKILL],
  core: [CORE_SKILL],
  full: 'all',
  all: 'all',
  ci: [
    'decision-guard', 'root-fix-gate', 'pr-boundary-guard', 'type-level-and-ast-slop-gate',
    'comment-budget-guard', 'cognitive-load-and-attention-governor', 'demock-guard',
    'mandela-guard', 'honeypot-trap-guard',
  ],
  backend: BACKEND,
  'backend-sre': BACKEND,
  frontend: FRONTEND,
  'frontend-ui': FRONTEND,
  lead: LEAD,
  'lead-review': LEAD,
  ...DOMAIN_PACKS,
}

export function resolvePreset(presetName, available = listAvailableSkills()) {
  const normalized = String(presetName || '').trim().toLowerCase()
  if (!normalized) {
    throw new Error('Preset name cannot be empty. Available presets: minimal, full, ci, backend, frontend, lead')
  }
  if (!Object.prototype.hasOwnProperty.call(PRESETS, normalized)) {
    throw new Error(`Unknown or invalid preset: ${presetName}. Available presets: ${Object.keys(PRESETS).join(', ')}`)
  }
  const selection = PRESETS[normalized]
  if (selection === 'all') {
    return available
  }
  const availableSet = new Set(available)
  const missing = [...new Set(selection.filter((id) => !availableSet.has(id)))]
  if (missing.length > 0) console.error(`Preset "${normalized}" has unavailable skills: ${missing.join(', ')}`)
  return resolveSkillSelection(selection.filter((id) => availableSet.has(id)), available)
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

function runSafeInstall(args, input) {
  const helper = path.join(rootDir, 'scripts', 'safe_install.py')
  const candidates = process.platform === 'win32' ? [['py', '-3'], ['python', '']] : [['python3', '']]
  for (const [executable, flag] of candidates) {
    const result = spawnSync(executable, [...(flag ? [flag] : []), helper, ...args], { encoding: 'utf8', input })
    if (result.error?.code === 'ENOENT') continue
    if (result.error || result.status !== 0) {
      throw new Error(result.stderr?.trim() || result.error?.message || `Safe installer exited ${result.status}`)
    }
    return JSON.parse(result.stdout)
  }
  throw new Error('Python 3 is required for safe file installation')
}

function safeCopy(source, destination) {
  return runSafeInstall(['--source', source, '--dest', destination, '--version', VERSION])
}

function sourceForSkill(skill, source) {
  if (skill === CORE_SKILL) {
    const candidates = [path.join(rootDir, 'skills', CORE_SKILL), rootDir]
    if (!fs.existsSync(path.join(rootDir, '.git'))) {
      candidates.unshift(path.join(rootDir, '.agents', 'skills', CORE_SKILL))
    }
    for (const candidate of candidates) {
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
  for (const target of targets) {
    const previews = []
    for (const skill of skills) {
      const src = sourceForSkill(skill, source)
      const destination = path.join(target.path, skill)
      const entry = { skill, agents: target.agents.map((agent) => agent.id), path: destination }
      assertSafeFilePath(destination)
      if (fs.existsSync(destination) && !overwrite) {
        written.push({ ...entry, status: 'skipped' })
      } else if (dryRun) {
        previews.push({ index: written.length, paths: [src, destination] })
        written.push(entry)
      } else {
        written.push({ ...entry, ...safeCopy(src, destination) })
      }
    }
    if (previews.length) {
      const requests = JSON.stringify(previews.map(({ paths }) => paths))
      const results = runSafeInstall(['--preview-batch', '--version', VERSION], requests)
      previews.forEach(({ index }, position) => {
        Object.assign(written[index], results[position])
      })
    }
  }
  return written
}

const POINTER_START = '<!-- anti-slop-engineering:start -->'
const POINTER_END = '<!-- anti-slop-engineering:end -->'
const SELECTION_FILE = '.anti-slop-selection.json'

const SYSTEM_SYMLINKS = new Set(process.platform === 'darwin' ? ['/var', '/tmp', '/etc'] : [])

function assertSafeFilePath(entry) {
  for (let current = path.resolve(entry); ; current = path.dirname(current)) {
    if (SYSTEM_SYMLINKS.has(current)) break
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
  let raw
  try {
    raw = fs.readFileSync(file, 'utf8')
  } catch (err) {
    if (err && err.code === 'ENOENT') return null
    throw err
  }
  let state
  try {
    state = JSON.parse(raw)
  } catch {
    throw new Error(`Invalid installed module selection: ${file}`)
  }
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

function buildSelectionState(target, scope, skills, skillExists) {
  const previous = readSelection(target)
  const combined = new Set([...(previous?.skills || []), ...skills, CORE_SKILL])
  const selected = [...combined].filter((id) => skillExists(id))
  if (!selected.includes(CORE_SKILL)) {
    selected.unshift(CORE_SKILL)
  }
  return { format: 1, version: VERSION, scope,
    agents: target.agents.map((agent) => agent.id), skills: selected }
}

function writeSelections(targets, scope, skills) {
  const source = skillSourceDir()
  const states = []
  for (const target of targets) {
    const coreSkillPath = path.join(target.path, CORE_SKILL, 'SKILL.md')
    if (!fs.existsSync(coreSkillPath) && source) {
      try {
        const src = sourceForSkill(CORE_SKILL, source)
        safeCopy(src, path.join(target.path, CORE_SKILL))
      } catch {
        // repair attempt
      }
    }
    const state = buildSelectionState(target, scope, skills,
      (id) => fs.existsSync(path.join(target.path, id, 'SKILL.md')))
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

const MANAGED_INVENTORY = '.anti-slop-managed.json'

function readRemovalFile(file) {
  const fd = fs.openSync(file, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK)
  try {
    if (!fs.fstatSync(fd).isFile()) throw new Error(`Expected a regular skill file: ${file}`)
    return fs.readFileSync(fd)
  } finally {
    fs.closeSync(fd)
  }
}

function readManagedInventory(directory) {
  const file = path.join(directory, MANAGED_INVENTORY)
  assertSafeFilePath(file)
  let raw
  try {
    raw = readRemovalFile(file).toString('utf8')
  } catch (err) {
    if (err && err.code === 'ENOENT') return null
    throw err
  }
  let state
  try {
    state = JSON.parse(raw)
  } catch {
    throw new Error(`Invalid managed inventory: ${file}`)
  }
  if (state?.format !== 1 || Object.prototype.toString.call(state.files) !== '[object Object]') {
    throw new Error(`Invalid managed inventory: ${file}`)
  }
  return state.files
}

function listInstalledFiles(directory) {
  const found = []
  const walk = (current) => {
    const entries = fs.readdirSync(current, { withFileTypes: true })
    for (const entry of entries) {
      const full = path.join(current, entry.name)
      const relative = path.relative(directory, full).split(path.sep).join('/')
      if (entry.isDirectory() && walk(full)) continue
      found.push({ relative, regular: entry.isFile() })
    }
    return entries.length > 0
  }
  walk(directory)
  return found
}

function fileDigest(file) {
  return createHash('sha256').update(readRemovalFile(file)).digest('hex')
}

function inspectSkillRemoval(directory, skill) {
  const snapshot = []
  const conflicts = []
  assertSafeFilePath(directory)
  if (!fs.existsSync(directory)) return { snapshot: null, conflicts }
  const inventory = readManagedInventory(directory)
  const source = skillSourceDir()
  const entries = listInstalledFiles(directory).sort((a, b) => a.relative.localeCompare(b.relative))
  for (const { relative, regular } of entries) {
    if (!regular) {
      conflicts.push(relative)
      continue
    }
    let expected = inventory?.[relative] ?? null
    if (!expected && source && relative !== MANAGED_INVENTORY) {
      const bundled = path.join(sourceForSkill(skill, source), relative)
      const stats = fs.lstatSync(bundled, { throwIfNoEntry: false })
      if (stats?.isFile()) expected = fileDigest(bundled)
    }
    if (!expected && relative !== MANAGED_INVENTORY) {
      conflicts.push(relative)
      continue
    }
    const digest = fileDigest(path.join(directory, relative))
    if (relative === MANAGED_INVENTORY || digest === expected) snapshot.push([relative, digest])
    else conflicts.push(relative)
  }
  return { snapshot, conflicts }
}

function planSkillRemoval(target, skill) {
  const plan = { path: target.path, agents: target.agents.map((agent) => agent.id), status: 'not-installed', files: [], conflicts: [] }
  const selection = readSelection(target)
  if (!selection || !selection.skills.includes(skill)) return { plan, snapshot: null }
  const { snapshot, conflicts } = inspectSkillRemoval(path.join(target.path, skill), skill)
  plan.files = snapshot?.map(([relative]) => relative) ?? []
  plan.conflicts = conflicts
  plan.status = conflicts.length ? 'conflict' : 'removable'
  return { plan, snapshot }
}

function restoreArchivedSkill(backup, directory) {
  if (fs.lstatSync(directory, { throwIfNoEntry: false })) {
    throw new Error(`Destination was recreated: ${directory}`)
  }
  fs.renameSync(backup, directory)
  fs.rmdirSync(path.dirname(backup))
}

function archiveRemovedSkill(directory, skill, snapshot) {
  const parent = path.dirname(path.dirname(directory))
  assertSafeFilePath(directory)
  const backupRoot = fs.mkdtempSync(path.join(parent, '.anti-slop-removed-'))
  const backup = path.join(backupRoot, skill)
  try {
    fs.renameSync(directory, backup)
    const current = inspectSkillRemoval(backup, skill)
    if (current.conflicts.length || JSON.stringify(current.snapshot) !== JSON.stringify(snapshot)) {
      throw new Error(`Installed files changed during removal: ${directory}`)
    }
    return backup
  } catch (error) {
    if (fs.lstatSync(backup, { throwIfNoEntry: false })) {
      try {
        restoreArchivedSkill(backup, directory)
      } catch (restoreError) {
        throw new Error(`${error.message}. Files retained at ${backup}: ${restoreError.message}`)
      }
      throw error
    }
    fs.rmdirSync(backupRoot)
    throw error
  }
}

function writeSelectionRemoval(target, skill) {
  const previous = readSelection(target)
  if (!previous || !previous.skills.includes(skill)) return null
  const state = { format: previous.format, version: previous.version, scope: previous.scope,
    agents: previous.agents, skills: previous.skills.filter((id) => id !== skill) }
  const file = path.join(target.path, SELECTION_FILE)
  const temporary = `${file}.${process.pid}.${randomUUID()}.tmp`
  try {
    fs.writeFileSync(temporary, JSON.stringify(state, null, 2) + '\n', { flag: 'wx' })
    fs.renameSync(temporary, file)
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary)
  }
  return { file, ...state }
}

function removeSkill({ skill, targets, scope, dryRun }) {
  const planned = targets.map((target) => planSkillRemoval(target, skill))
  const plans = planned.map(({ plan }) => plan)
  if (dryRun) {
    for (const plan of plans) if (plan.status === 'removable') plan.status = 'preview'
    return { plans, selections: [], pointers: [] }
  }
  if (plans.some((plan) => plan.status === 'conflict')) {
    for (const plan of plans) if (plan.status === 'removable') plan.status = 'blocked'
    return { plans, selections: [], pointers: [] }
  }
  const changes = planned.filter(({ plan }) => plan.status === 'removable')
  const pointerTargets = []
  if (scope === 'project' && changes.length) {
    const entries = new Set(targets.flatMap((target) => target.agents.map((agent) => agent.entry)))
    for (const name of entries) {
      const entry = path.join(process.cwd(), name)
      assertSafeFilePath(entry)
      const stats = fs.lstatSync(entry, { throwIfNoEntry: false })
      if (stats && !stats.isFile()) throw new Error(`Invalid instruction file: ${entry}`)
    }
    for (const target of resolveTargets('project')) {
      const agents = target.agents.filter((agent) => entries.has(agent.entry))
      if (agents.length && readSelection(target)) pointerTargets.push({ ...target, agents })
    }
  }
  try {
    for (const { plan, snapshot } of changes) {
      const directory = path.join(plan.path, skill)
      if (snapshot !== null) plan.backup = archiveRemovedSkill(directory, skill, snapshot)
      else if (fs.lstatSync(directory, { throwIfNoEntry: false })) {
        throw new Error(`Installed files changed during removal: ${directory}`)
      }
    }
  } catch (error) {
    const retained = []
    for (const { plan } of changes.reverse()) {
      if (!plan.backup) continue
      try {
        restoreArchivedSkill(plan.backup, path.join(plan.path, skill))
      } catch {
        retained.push(plan.backup)
      }
    }
    if (retained.length) throw new Error(`${error.message}. Files retained at ${retained.join(', ')}`)
    throw error
  }
  const selections = []
  let pointers = []
  try {
    for (const { plan } of changes) {
      const state = writeSelectionRemoval(plan, skill)
      if (state) selections.push(state)
      plan.status = 'removed'
    }
    if (pointerTargets.length) {
      const remaining = [...new Set(pointerTargets.flatMap((target) => readSelection(target)?.skills || []))]
      pointers = updatePointers({ targets: pointerTargets, skills: remaining })
    }
  } catch (error) {
    const backups = changes.flatMap(({ plan }) => plan.backup ? [plan.backup] : [])
    if (backups.length) throw new Error(`${error.message}. Files retained at ${backups.join(', ')}`)
    throw error
  }
  return { plans, selections, pointers }
}

function runRemoval({ skill, scope, agents, dryRun, jsonMode }) {
  if (!/^[a-z0-9][a-z0-9-]*$/.test(skill) || !listAvailableSkills().includes(skill)) {
    throw new Error(`Unknown or invalid plugin: ${skill}`)
  }
  if (skill === CORE_SKILL) {
    throw new Error(`The required core skill (${CORE_SKILL}) cannot be removed`)
  }
  const targets = resolveTargets(scope, agents)
  const { plans, selections, pointers } = removeSkill({ skill, targets, scope, dryRun })
  const blocked = plans.some((plan) => plan.status === 'conflict')
  if (jsonMode) {
    console.log(JSON.stringify({ remove: skill, scope, agents, dryRun, targets: plans, selections, pointers }, null, 2))
  } else {
    for (const plan of plans) {
      if (plan.status === 'preview') console.log(`  Would remove ${skill} from ${plan.path}: ${plan.files.length} managed file(s)`)
      if (plan.status === 'removed') {
        console.log(`  Removed ${skill} from ${plan.path}: ${plan.files.length} managed file(s)`)
        if (plan.backup) console.log(`  Backup: ${plan.backup}`)
      }
      if (plan.status === 'not-installed') console.log(`  ${skill} is not installed in ${plan.path}`)
      if (plan.status === 'blocked') console.log(`  Kept ${skill} in ${plan.path} because another target has conflicts`)
      if (plan.status === 'conflict') console.log(`  ⚠ Removal blocked in ${plan.path}: modified files: ${plan.conflicts.join(', ')}`)
    }
    if (pointers.length > 0) console.log(`  Instruction pointers written: ${pointers.join(', ')}`)
  }
  return blocked ? 1 : 0
}

function pointerBlock(skills, skillPaths) {
  return [
    POINTER_START,
    '## anti-slop-engineering',
    'Follow Anti-Slop Engineering standards, Google SRE Discipline (KISS, DRY, YAGNI, Fix Issues at Scale), and clean-room gates:',
    ...skills.filter((s) => skillPaths.has(s)).map((s) => `- \`${s}\`: \`${skillPaths.get(s)}\``),
    'Before concluding tasks, verify diff triage: `bunx anti-slop-engineering diff --base HEAD` (or `check --base HEAD`).',
    'For multi-guard verification, run: `bunx anti-slop-engineering audit --base HEAD`.',
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

function computeBlockBody(existing, block) {
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
  return { body, eol }
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
  const { body, eol } = computeBlockBody(existing, block)

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

function pointerSkillPaths(targets, skills, skillFile) {
  const entries = new Map()
  const validSkills = new Set(listAvailableSkills())
  for (const t of targets) {
    for (const a of t.agents) {
      if (!entries.has(a.entry)) entries.set(a.entry, new Map())
      const skillPaths = entries.get(a.entry)
      for (const skill of skills) {
        const file = skillFile(t, skill)
        if (!file || !validSkills.has(skill) || skillPaths.has(skill)) continue
        if (readSkillMetadata(file)?.name !== skill) continue
        const installed = path.join(t.path, skill, 'SKILL.md')
        skillPaths.set(skill, path.relative(process.cwd(), installed).split(path.sep).join('/'))
      }
    }
  }
  return entries
}

export function updatePointers({ targets, skills }) {
  const entries = pointerSkillPaths(targets, skills, (t, skill) => {
    const file = path.join(t.path, skill, 'SKILL.md')
    return fs.existsSync(file) ? file : null
  })

  const written = []
  for (const [name, skillPaths] of entries) {
    const entry = path.join(process.cwd(), name)
    writeBlock(entry, pointerBlock(skills, skillPaths))
    written.push(entry)
  }
  return written
}

function isTrackedFile(file) {
  const result = spawnSync('git', ['ls-files', '--error-unmatch', '--', path.resolve(file)],
    { cwd: process.cwd(), encoding: 'utf8' })
  return result.status === 0
}

function writeAction(file, nextContent) {
  let existing
  try {
    existing = fs.readFileSync(file, 'utf8')
  } catch (err) {
    if (err && err.code === 'ENOENT') return 'create'
    throw err
  }
  return existing === nextContent ? 'no-op' : 'update'
}

export function planWrites({ targets, scope, skills }) {
  const selections = targets.map((target) => {
    const state = buildSelectionState(target, scope, skills,
      (id) => skills.includes(id) || fs.existsSync(path.join(target.path, id, 'SKILL.md')))
    const file = path.join(target.path, SELECTION_FILE)
    return { file, action: writeAction(file, JSON.stringify(state, null, 2) + '\n'), state }
  })
  const pointers = []
  if (scope === 'project') {
    const installedSelection = [...new Set(selections.flatMap((s) => s.state.skills))]
    const source = skillSourceDir()
    const entries = pointerSkillPaths(targets, installedSelection, (t, skill) => {
      const installed = path.join(t.path, skill, 'SKILL.md')
      if (fs.existsSync(installed)) return installed
      return skill === CORE_SKILL || skills.includes(skill) ? path.join(sourceForSkill(skill, source), 'SKILL.md') : null
    })
    for (const [name, skillPaths] of entries) {
      const file = path.join(process.cwd(), name)
      assertSafeFilePath(file)
      let existing = ''
      let exists = true
      try {
        existing = fs.readFileSync(file, 'utf8')
      } catch (err) {
        if (err && err.code !== 'ENOENT') throw err
        exists = false
      }
      const { body, eol } = computeBlockBody(existing, pointerBlock(installedSelection, skillPaths))
      const action = exists ? (existing === body + eol ? 'no-op' : 'update') : 'create'
      const tracked = exists && isTrackedFile(file)
      pointers.push({ file, action, tracked, requiresConsent: action === 'update' && tracked })
    }
  }
  return { selections: selections.map(({ file, action }) => ({ file, action })), pointers }
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

  const projectSkills = [...new Set(results.filter((r) => r.location === 'project').flatMap((r) => r.skills || []))]
  const pointers = projectTargets.length > 0
    ? updatePointers({ targets: projectTargets, skills: projectSkills })
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
  let activeEnforcement = setup.enforcement || null
  try {
    while (true) {
      output.write('\nAnti-Slop Engineering setup (Core is required)\n')
      output.write('  1. Core only\n  2. Select plugins\n  3. Install everything\n')
      output.write('  p. Role presets\n')
      output.write('  g. Domain packs\n')
      if (setup.allowTargetChange) output.write('  t. Change agents/scope\n')
      if (activeScope === 'project' && activeAgents.includes('codex')) output.write('  e. Enforcement mode (Codex hooks)\n')
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
      if (mode === 'e' && activeScope === 'project' && activeAgents.includes('codex')) {
        output.write('\nCodex hook enforcement (the plan shows the effective capability):\n')
        ENFORCEMENT_MODES.forEach((name, index) => output.write(`  ${index + 1}. ${name}\n`))
        output.write('  0. None (adapter default)\n')
        output.write(`  Current: ${activeEnforcement || 'none'}\n`)
        const pick = (await ask('Enforcement mode [1-4, name, 0 none, Enter keep]: '))?.trim().toLowerCase()
        if (pick == null) return null
        if (pick) {
          const chosen = pick === '0' || pick === 'none' ? null
            : /^\d+$/.test(pick) ? ENFORCEMENT_MODES[Number(pick) - 1]
            : ENFORCEMENT_MODES.includes(pick) ? pick : undefined
          if (chosen === undefined) {
            output.write(`Unknown enforcement mode: ${pick}; keeping previous selection\n`)
            continue
          }
          activeEnforcement = chosen
          if (chosen) {
            const plan = enforcementPlan('codex', chosen)
            output.write(`  Enforcement (${plan.requested}): ${plan.capability}\n`)
            if (plan.reason) output.write(`  Reason: ${plan.reason}\n`)
            if (!plan.supported) output.write('  This mode will not be applied; the installation continues without it.\n')
          } else {
            output.write('  Enforcement: none (adapter default)\n')
          }
        }
        continue
      }
      if (!['1', '2', '3', 'p', 'g'].includes(mode)) {
        output.write('Enter 1, 2, 3, p, g, t, or q\n')
        continue
      }
      let skills = [CORE_SKILL]
      if (mode === '3') skills = resolveSkillSelection('all')
      if (mode === 'p') {
        output.write('\nRole presets:\n')
        output.write('  1. backend   (Backend, SRE, Architecture & Scaled Systems)\n')
        output.write('  2. frontend  (Frontend, UI, HIG Physics & Design Systems)\n')
        output.write('  3. lead      (Lead, Review, Contracts & Gate Governance)\n')
        output.write('  4. ci        (CI Pipeline, AST & Diff Automation)\n')
        output.write('  b. Back\n')
        const presetChoice = (await ask('Choose role preset [1-4, or b]: '))?.trim().toLowerCase()
        if (presetChoice == null || presetChoice === 'q') return null
        if (presetChoice === 'b') continue
        const map = {
          '1': 'backend', '2': 'frontend', '3': 'lead', '4': 'ci',
          backend: 'backend', frontend: 'frontend', lead: 'lead', ci: 'ci',
        }
        const chosen = map[presetChoice]
        if (!chosen) {
          output.write(`Unknown preset selection: ${presetChoice}\n`)
          continue
        }
        skills = resolvePreset(chosen, listAvailableSkills())
      }
      if (mode === 'g') {
        output.write('\nGrouped domain packs (from skills.sh.json):\n')
        const packKeys = Object.keys(DOMAIN_PACKS)
        packKeys.forEach((key, idx) => {
          output.write(`  ${idx + 1}. ${key} (${DOMAIN_PACKS[key].length} skills)\n`)
        })
        const packChoice = (await ask(`Domain pack [1-${packKeys.length}, name, or b]: `))?.trim().toLowerCase()
        if (packChoice == null || packChoice === 'q') return null
        if (packChoice === 'b') continue
        let chosenPack = null
        if (/^\d+$/.test(packChoice)) {
          chosenPack = packKeys[Number(packChoice) - 1]
        } else if (Object.hasOwn(DOMAIN_PACKS, packChoice)) {
          chosenPack = packChoice
        }
        if (!chosenPack) {
          output.write(`Unknown domain pack: ${packChoice}\n`)
          continue
        }
        skills = resolvePreset(chosenPack, listAvailableSkills())
      }
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
      if (activeEnforcement && activeScope === 'project' && activeAgents.includes('codex')) {
        const hookPlan = previewAgentHooks('codex', activeScope, activeAgents, activeEnforcement)
        output.write(`  Codex hook settings: ${hookPlan.settings}\n`)
        if (hookPlan.requires) output.write(`  Requires: ${hookPlan.requires}\n`)
        output.write(`  Enforcement (${hookPlan.enforcement.requested}): ${hookPlan.enforcement.capability}\n`)
        if (hookPlan.enforcement.reason) output.write(`  Reason: ${hookPlan.enforcement.reason}\n`)
      }
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
        return { skills, targets: activeTargets, scope: activeScope, agents: activeAgents, enforcement: activeEnforcement }
      }
      output.write('Installation cancelled before any files were changed\n')
      return null
    }
  } finally {
    rl.close()
  }
}

const hookPreviewAdapters = {
  claude: ['Claude Code', 'references/claude-code-hooks.md', ['PreToolUse policy', 'PostToolUse feedback'],
    'Claude Code 2.1.295 or later and a durable adapter checkout'],
  codex: ['Codex', 'references/agent-hook-capabilities.md', ['PreToolUse policy', 'PostToolUse feedback'],
    'Codex project hook trust and a durable adapter checkout'],
  gemini: ['Gemini CLI', 'references/agent-hook-capabilities.md', ['BeforeTool policy', 'AfterTool feedback'],
    'Gemini workspace trust, enabled hooks, and a durable adapter checkout'],
}

const ENFORCEMENT_MODES = ['strict', 'advisory', 'git-boundary', 'skills-only']

const hookEnforcement = {
  codex: {
    advisory: { effective: null, supported: false, capability: 'PostToolUse feedback for apply_patch actions', reason: 'The adapter cannot enforce an advisory-only installation. Use an armed review watch session for feedback without denial' },
    strict: { effective: null, supported: false, capability: 'PreToolUse denial for apply_patch actions the adapter can evaluate', reason: 'The Codex adapter does not claim strict failure blocking: hook launch failures, timeouts, and skipped or untrusted hooks are host-dependent. Enforce strict denial with the audit command or CI at the repository boundary instead' },
    'git-boundary': { effective: null, supported: false, capability: 'The Codex adapter configures agent tool hooks only', reason: 'Git-boundary enforcement is provided by the audit command and CI, not by this adapter' },
    'skills-only': { effective: 'skills-only', supported: true, capability: 'No agent hooks are configured; skills and explicit repository checks only' },
  },
}

function enforcementPlan(agent, mode) {
  if (!mode) {
    return {
      requested: null, effective: null, supported: true,
      capability: 'No enforcement mode requested; the adapter registers its hook stages and the armed session contract decides whether a matched action is denied or only receives feedback',
    }
  }
  const entry = hookEnforcement[agent][mode]
  const plan = { requested: mode, effective: entry.effective, supported: entry.supported, capability: entry.capability }
  if (entry.reason) plan.reason = entry.reason
  return plan
}

function previewAgentHooks(agent, scope, agents, enforcement = null) {
  const [label, docs, stages, requires] = hookPreviewAdapters[agent]
  if (scope !== 'project' || !agents.includes(agent)) {
    throw new Error(label + ' hook preview requires project scope and the ' + label + ' agent')
  }
  if (enforcement) {
    if (!ENFORCEMENT_MODES.includes(enforcement)) {
      throw new Error('Unknown enforcement mode: ' + enforcement + ' (expected one of: ' + ENFORCEMENT_MODES.join(', ') + ')')
    }
    if (!hookEnforcement[agent]) {
      throw new Error('Enforcement modes are currently supported only for the Codex hook preview')
    }
  }
  if (enforcement === 'skills-only') {
    return {
      status: 'skills_only',
      settings: path.join(fs.realpathSync(process.cwd()), '.' + agent, 'hooks.json'),
      tools: [],
      requires_host_hook_trust: false,
      stages: [],
      requires: null,
      enforcement: enforcementPlan(agent, enforcement),
    }
  }
  if (process.platform === 'win32') {
    throw new Error(label + ' hook preview is not supported on Windows: the hook adapters are POSIX-only. Run it from a POSIX checkout (Linux, macOS, or WSL), or use --enforcement=skills-only to install the skills without hooks. See ' + path.join(rootDir, docs))
  }
  if (!fs.existsSync(path.join(rootDir, '.git'))) {
    throw new Error(label + ' hook preview requires a durable checkout of the anti-slop-engineering repository: the package at ' + rootDir + ' has no .git directory, so it is an npm install or an extracted tarball, not a checkout. Run it from a checkout instead: git clone https://github.com/imMamdouhaboammar/anti-slop-engineering, then node anti-slop-engineering/bin/cli.js install --agent=' + agent + ' --skills=core --scope=project --' + agent + '-hooks --dry-run. Or keep this installation and use --enforcement=skills-only to install the skills without hooks. See ' + path.join(rootDir, docs))
  }
  const adapter = path.join(rootDir, 'scripts', agent + '_hooks.py')
  const preview = spawnSync('python3', [adapter, 'install', '--dry-run'], {
    encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'pipe'],
  })
  if (preview.error || preview.status !== 0) {
    throw new Error(preview.stderr?.trim() || preview.error?.message || label + ' hook preview failed')
  }
  return { ...JSON.parse(preview.stdout), stages, requires, enforcement: enforcementPlan(agent, enforcement) }
}

function applyCodexEnforcement(mode) {
  const plan = enforcementPlan('codex', mode)
  if (!plan.supported) return { applied: false, requested: mode, reason: plan.reason }
  // The verified skills-only state is "no adapter hooks configured", so
  // applying it removes the adapter's own hook groups through the adapter's
  // configure path, which preserves unrelated hooks.
  const adapter = path.join(rootDir, 'scripts', 'codex_hooks.py')
  const result = spawnSync('python3', [adapter, 'uninstall', '--project', fs.realpathSync(process.cwd()), '--yes'], {
    encoding: 'utf8', timeout: 5000, stdio: ['ignore', 'pipe', 'pipe'],
  })
  if (result.error || result.status !== 0) {
    throw new Error(result.stderr?.trim() || result.error?.message || 'Codex hook configuration failed')
  }
  const outcome = JSON.parse(result.stdout)
  return { applied: true, requested: mode, effective: plan.effective, settings: outcome.settings, status: outcome.status }
}

export async function runInstallerCLI(args = process.argv.slice(2)) {
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
📦 Anti-Slop Engineering Universal Multi-Agent Installer (v${VERSION})

Core is required in every installation. Optional skill plugins are discovered
from bundled skill definitions. Non-interactive executions default to core only.

Usage:
  bunx anti-slop-engineering install [options]
  bunx anti-slop-engineering update
  bunx anti-slop-engineering setup

Options:
  --agent <names>     Target agents (comma-separated, or 'all'). Default: detected agents
  --scope <scope>     Install scope: 'project' (default) or 'global'
  --preset <preset>   Preset: 'full', 'minimal', 'ci', 'backend', 'frontend', 'lead', or domain pack
  --skills <skills>   Optional skill IDs: 'all', 'core', or comma-separated names
  --plugins <names>   Alias for --skills; core is always included
  --remove <skill>    Remove one installed optional skill (core cannot be removed); use --dry-run to preview
  --all               Select every available optional skill
  --overwrite         Refresh managed files, preserving local edits and conflicts
  --update-instructions  Allow a noninteractive install to update existing tracked instruction files (AGENTS.md, CLAUDE.md, GEMINI.md)
  --dry-run           Simulate installation without writing files
  --claude-hooks      With --dry-run, preview local Claude hooks from this checkout
  --codex-hooks       With --dry-run, preview local Codex hooks from this checkout
  --gemini-hooks      With --dry-run, preview local Gemini hooks from this checkout
  --enforcement <mode> With --codex-hooks --dry-run, or shown in the interactive plan: requested hook enforcement (strict, advisory, git-boundary, skills-only)
  --json              Output JSON result
  --no-interactive    Skip terminal selection (defaults to core only)
  --help, -h          Show this help menu
`)
    return 0
  }

  const isUpdate = args.includes('--update') || args[0] === 'update'
  const hookPreviews = Object.keys(hookPreviewAdapters).filter((agent) => args.includes('--' + agent + '-hooks'))
  if (hookPreviews.length > 1) throw new Error('Select one adapter for the hook preview')
  const [hookPreview] = hookPreviews
  const enforcementArg = optionValue(args, ['enforcement'])
  if (hookPreview && (!args.includes('--dry-run') || args.includes('--selection-only') || isUpdate)) {
    const label = hookPreview === 'claude' ? 'Claude' : hookPreviewAdapters[hookPreview][0]
    throw new Error('--' + hookPreview + '-hooks previews setup only; use --dry-run and the standalone ' + label + ' adapter to apply')
  }
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
  const presetArg = optionValue(args, ['preset', 'pack'])
  const skillsArg = args.includes('--all') ? 'all' : optionValue(args, ['skills', 'plugins', 'modules'])
  const overwrite = args.includes('--overwrite')
  const updateInstructions = args.includes('--update-instructions')
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

  const removeArg = optionValue(args, ['remove'])
  if (removeArg !== null) {
    if (hookPreview) throw new Error('--remove cannot be combined with a hook preview')
    if (selectionOnly) throw new Error('--remove cannot be combined with --selection-only')
    if (skillsArg || presetArg) throw new Error('--remove cannot be combined with --skills or --preset')
    return runRemoval({ skill: removeArg, scope: scopeArg, agents: selectedAgents, dryRun, jsonMode })
  }

  const availableSkills = listAvailableSkills()
  let selectedSkills
  if (presetArg !== null) {
    const presetSkills = resolvePreset(presetArg, availableSkills)
    if (skillsArg) {
      const explicitSkills = resolveSkillSelection(skillsArg, availableSkills)
      selectedSkills = [CORE_SKILL, ...new Set([...presetSkills, ...explicitSkills].filter((s) => s !== CORE_SKILL))]
    } else {
      selectedSkills = presetSkills
    }
  } else {
    selectedSkills = resolveSkillSelection(skillsArg ?? 'core', availableSkills)
  }

  let targets = resolveTargets(scopeArg, selectedAgents)
  let resolvedScope = scopeArg

  const promptOutput = selectionOnly ? process.stderr : process.stdout
  const canPrompt = !dryRun && !jsonMode && !process.env.CI && !args.includes('--no-interactive')
    && skillsArg == null && presetArg == null && promptOutput.isTTY
  if (enforcementArg && !hookPreview && !canPrompt) {
    throw new Error('--enforcement requires a hook preview (for example --codex-hooks with --dry-run)')
  }
  let terminalInput
  if (canPrompt && !process.stdin.isTTY && process.platform !== 'win32') {
    const ttyPath = process.env.ANTI_SLOP_TTY_PATH || '/dev/tty'
    let fd
    try {
      fd = fs.openSync(ttyPath, 'r')
      if (tty.isatty(fd)) {
        terminalInput = new tty.ReadStream(fd)
        fd = undefined
      }
    } catch (error) {
      if (!['EACCES', 'ENXIO', 'ENODEV', 'ENOENT', 'ENOTTY'].includes(error.code)) throw error
    } finally {
      if (fd !== undefined) fs.closeSync(fd)
    }
  }

  const interactiveInput = canPrompt && (terminalInput || (process.stdin.isTTY && process.stdin))
  const interactive = Boolean(interactiveInput)
  let wizardEnforcement = null
  if (interactive) {
    try {
      const response = await promptForSkills(listAvailableModules(), targets, interactiveInput, promptOutput,
        { scope: resolvedScope, agents: selectedAgents, allowTargetChange: !selectionOnly, enforcement: enforcementArg })
      if (response == null) {
        console.error('Setup cancelled; no installation files were changed')
        return 130
      }
      selectedSkills = response.skills
      targets = response.targets
      resolvedScope = response.scope
      selectedAgents = response.agents
      wizardEnforcement = response.enforcement ?? null
    } finally {
      terminalInput?.destroy()
    }
  }

  if (selectionOnly) {
    console.log(JSON.stringify({ skills: selectedSkills, agents: selectedAgents, scope: resolvedScope }))
    return 0
  }

  for (const t of targets) {
    readSelection(t)
  }

  if (dryRun) {
    const operations = installSkills({ skills: selectedSkills, targets, overwrite, dryRun: true })
    const writes = planWrites({ targets, scope: resolvedScope, skills: selectedSkills })
    const plan = { scope: resolvedScope, agents: selectedAgents, skills: selectedSkills, targets: targets.map((t) => t.path), operations, selections: writes.selections, pointers: writes.pointers }
    if (hookPreview) plan.hookPlan = previewAgentHooks(hookPreview, resolvedScope, selectedAgents, enforcementArg)
    if (jsonMode) console.log(JSON.stringify(plan, null, 2))
    else console.log('Dry-run installation plan:', plan)
    return 0
  }

  const writes = planWrites({ targets, scope: resolvedScope, skills: selectedSkills })
  const consentNeeded = writes.pointers.filter((pointer) => pointer.requiresConsent)
  if (consentNeeded.length && !interactive && !updateInstructions) {
    throw new Error(`Refusing to update tracked instruction file(s) without explicit consent: ${consentNeeded.map((pointer) => pointer.file).join(', ')}. Re-run with --update-instructions to allow the update, or run the installer interactively.`)
  }

  const installed = installSkills({ skills: selectedSkills, targets, overwrite: overwrite || interactive })
  const selections = writeSelections(targets, resolvedScope, selectedSkills)
  const installedSelection = [...new Set(selections.flatMap((state) => state.skills))]
  const pointers = resolvedScope === 'project' ? updatePointers({ targets, skills: installedSelection }) : []

  let enforcementOutcome = null
  if (wizardEnforcement && resolvedScope === 'project' && selectedAgents.includes('codex')) {
    try {
      enforcementOutcome = applyCodexEnforcement(wizardEnforcement)
    } catch (error) {
      throw new Error(`Skills were installed, but applying the Codex enforcement selection failed: ${error.message}`)
    }
  }

  if (jsonMode) {
    console.log(JSON.stringify({ installed, pointers, selections, version: VERSION,
      ...(enforcementOutcome ? { enforcement: enforcementOutcome } : {}) }, null, 2))
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
    if (enforcementOutcome?.applied) {
      console.log(`  Enforcement (${wizardEnforcement}) applied: ${enforcementOutcome.settings} (${enforcementOutcome.status})`)
    } else if (enforcementOutcome) {
      console.log(`  Enforcement (${wizardEnforcement}) not applied: ${enforcementOutcome.reason}`)
    }
  }
  return 0
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  runInstallerCLI().then((code) => {
    process.exitCode = code ?? 0
  }).catch((err) => {
    console.error(`Installer error: ${err.message}`)
    process.exitCode = 1
  })
}
