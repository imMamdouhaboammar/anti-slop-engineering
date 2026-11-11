#!/usr/bin/env node
// SPDX-License-Identifier: MIT
// Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

import fs from 'node:fs'
import path from 'node:path'
import os from 'node:os'
import { spawnSync } from 'node:child_process'
import { randomUUID } from 'node:crypto'
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

export function listAvailableSkills() {
  const dir = skillSourceDir()
  if (!dir) return [CORE_SKILL]
  const entries = fs.readdirSync(dir, { withFileTypes: true })
    .filter((e) => e.isDirectory() && fs.existsSync(path.join(dir, e.name, 'SKILL.md')))
    .map((e) => e.name)
  if (!entries.includes(CORE_SKILL)) entries.unshift(CORE_SKILL)
  return entries
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

function safeCopy(src, dest, version) {
  const helper = path.join(rootDir, 'scripts', 'safe_install.py')
  const candidates = process.platform === 'win32' ? [['py', '-3'], ['python', '']] : [['python3', '']]
  for (const [executable, flag] of candidates) {
    const args = [...(flag ? [flag] : []), helper, '--source', src, '--dest', dest]
    if (version) args.push('--version', version)
    const result = spawnSync(executable, args, { encoding: 'utf8' })
    if (result.error?.code === 'ENOENT') continue
    if (result.error || result.status !== 0) {
      throw new Error(result.stderr?.trim() || result.error?.message || `Safe installer exited ${result.status}`)
    }
    return JSON.parse(result.stdout)
  }
  throw new Error('Python 3 is required for safe file installation')
}

export function installSkills({ skills, targets, overwrite = false }) {
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
      let src = null
      if (skill === CORE_SKILL) {
        // Core skill may live at root or .agents/skills/anti-slop-engineering
        const candidate1 = path.join(rootDir, '.agents', 'skills', CORE_SKILL)
        const candidate2 = path.join(rootDir, 'skills', CORE_SKILL)
        if (fs.existsSync(candidate1)) src = candidate1
        else if (fs.existsSync(candidate2)) src = candidate2
        else src = rootDir // has root SKILL.md
      } else if (source) {
        src = path.join(source, skill)
      }
      if (!src || !fs.existsSync(src)) throw new Error(`Missing skill source: ${skill}`)

      const dest = path.join(t.path, skill)
      if (fs.existsSync(dest) && !overwrite) {
        written.push({ skill, agents: t.agents.map((a) => a.id), path: dest, status: 'skipped' })
        continue
      }
      const outcome = safeCopy(src, dest, VERSION)
      written.push({ skill, agents: t.agents.map((a) => a.id), path: dest, ...outcome })
    }
  }
  return written
}

const POINTER_START = '<!-- anti-slop-engineering:start -->'
const POINTER_END = '<!-- anti-slop-engineering:end -->'

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
  for (let current = path.resolve(entry); ; current = path.dirname(current)) {
    try {
      if (fs.lstatSync(current).isSymbolicLink()) {
        throw new Error(`Refusing symbolic link in agent instruction path: ${current}`)
      }
    } catch (err) {
      if (err.code !== 'ENOENT') throw err
    }
    if (current === path.dirname(current)) break
  }
  let existing = ''
  try {
    existing = fs.readFileSync(entry, 'utf8')
  } catch (err) {
    if (err && err.code !== 'ENOENT') throw err
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

  const temporary = `${entry}.${process.pid}.${randomUUID()}.tmp`
  try {
    fs.writeFileSync(temporary, body + eol, { mode: fs.existsSync(entry) ? fs.statSync(entry).mode : 0o644 })
    fs.renameSync(temporary, entry)
  } finally {
    if (fs.existsSync(temporary)) fs.unlinkSync(temporary)
  }
}

export function updatePointers({ targets, skills }) {
  const entries = new Map()
  for (const t of targets) {
    for (const a of t.agents) {
      if (!entries.has(a.entry)) entries.set(a.entry, new Map())
      const skillPaths = entries.get(a.entry)
      for (const skill of skills) {
        const file = path.join(t.path, skill, 'SKILL.md')
        if (!skillPaths.has(skill) && fs.existsSync(file)) {
          skillPaths.set(skill, path.relative(process.cwd(), file).split(path.sep).join('/'))
        }
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
      const skills = allAvailable.filter((s) => fs.existsSync(path.join(target.path, s)))
      if (skills.length === 0) continue
      const entries = installSkills({ skills, targets: [target], overwrite: true })
      const changes = Object.fromEntries(
        ['installed', 'updated', 'preserved', 'skipped', 'conflicted'].map(
          (status) => [status, entries.flatMap((entry) => entry[status] || [])]
        )
      )
      results.push({ location, path: target.path, agents: target.agents.map((a) => a.id),
        skills, version: VERSION, changes, entries })
      if (location === 'project') projectTargets.push(target)
    }
  }

  const pointers = projectTargets.length > 0
    ? updatePointers({ targets: projectTargets, skills: allAvailable })
    : []
  return { results, pointers }
}

export async function runInstallerCLI(args = process.argv.slice(2)) {
  if (args.includes('--help') || args.includes('-h')) {
    console.log(`
📦 Anti-Slop Engineering Universal Multi-Agent Installer (v${VERSION})

Usage:
  bunx anti-slop-engineering install [options]
  bunx anti-slop-engineering update
  bunx anti-slop-engineering setup

Options:
  --agent <names>     Target agents (comma-separated, or 'all'). Default: detected agents
  --scope <scope>     Install scope: 'project' (default) or 'global'
  --skills <skills>   Skills to install: 'all', 'core', or comma-separated names
  --overwrite         Overwrite existing installed skills
  --dry-run           Simulate installation without writing files
  --json              Output JSON result
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

  const scopeArg = args.find((a) => a.startsWith('--scope='))?.split('=')[1] || (args.includes('--global') ? 'global' : 'project')
  const agentArg = args.find((a) => a.startsWith('--agent='))?.split('=')[1]
  const skillsArg = args.find((a) => a.startsWith('--skills='))?.split('=')[1] || 'all'
  const overwrite = args.includes('--overwrite')
  const dryRun = args.includes('--dry-run')
  const jsonMode = args.includes('--json')

  const detected = detectAgents(scopeArg)
  let selectedAgents = []
  if (agentArg === 'all') {
    selectedAgents = AGENTS.map((a) => a.id)
  } else if (agentArg) {
    selectedAgents = agentArg.split(',').map((s) => s.trim().toLowerCase())
  } else {
    selectedAgents = detected.length > 0 ? detected : ['antigravity', 'claude', 'cursor']
  }

  const availableSkills = listAvailableSkills()
  let selectedSkills = []
  if (skillsArg === 'core') {
    selectedSkills = [CORE_SKILL]
  } else if (skillsArg === 'all') {
    selectedSkills = availableSkills
  } else {
    selectedSkills = skillsArg.split(',').map((s) => s.trim())
  }

  const targets = resolveTargets(scopeArg, selectedAgents)

  if (dryRun) {
    const plan = { scope: scopeArg, agents: selectedAgents, skills: selectedSkills, targets: targets.map((t) => t.path) }
    if (jsonMode) console.log(JSON.stringify(plan, null, 2))
    else console.log('Dry-run installation plan:', plan)
    return 0
  }

  const installed = installSkills({ skills: selectedSkills, targets, overwrite })
  const pointers = scopeArg === 'project' ? updatePointers({ targets, skills: selectedSkills }) : []

  if (jsonMode) {
    console.log(JSON.stringify({ installed, pointers, version: VERSION }, null, 2))
  } else {
    const changed = installed.filter((item) => item.installed?.length || item.updated?.length)
    console.log(`\n✅ Installed or updated ${changed.length} skill entries across ${targets.length} agent target(s).`)
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
  runInstallerCLI().catch((err) => {
    console.error(`Installer error: ${err.message}`)
    process.exit(1)
  })
}
