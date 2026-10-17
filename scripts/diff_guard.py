#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Read-only, heuristic Git diff triage for the anti-slop-engineering skill.

This is NOT a SAST scanner, semantic reviewer, proof of exploitability, or test runner.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys


PATTERNS = [
    ('SKIPPED_TEST', 'blocker', r'(?i)(?:@pytest\.mark\.(?:skip|xfail)|\b(?:it|test|describe)\.skip\s*\(|\b(?:xit|xdescribe)\s*\(|@Disabled\b|\bpytest\.skip\s*\(|\bskipTest\s*\()'),
    ('WEAK_ASSERTION', 'review', r'(?i)(?:\bassert\s+(?:True|1\s*==\s*1)\b|\bexpect\s*\(\s*true\s*\)\s*\.toBe\s*\(\s*true\s*\))'),
    ('SECURITY_BYPASS_CANDIDATE', 'review', r'(?i)(?:\bverify\s*=\s*False\b|\brejectUnauthorized\s*:\s*false\b|--no-verify\b|\bdisable[_-]?auth\s*=\s*true\b)'),
    ('ERROR_SWALLOW_CANDIDATE', 'review', r'(?i)(?:\bexcept\s+[^:]+:\s*pass\b|\bcatch\s*\([^)]*\)\s*\{\s*\}|\.catch\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\))'),
    ('TYPE_CHECK_SUPPRESSION', 'review', r'(?:@ts-ignore\b|@ts-nocheck\b|type:\s*ignore\b|eslint-disable(?:-next-line)?\b)'),
    ('DYNAMIC_EXECUTION_CANDIDATE', 'review', r'(?i)(?:\beval\s*\(|\bexec\s*\(|\bshell\s*=\s*True\b)'),
    ('DEV_NOTE_IN_UI', 'blocker', r'(?i)<(?:p|span|div|small|Alert|Badge|Text|Label|h[1-6])[^>]*>[^<]*(?:\b(?:note|todo|fixme|agent note|dev note|developer note)\s*:|\bmock data displayed\b|\bplaceholder until\b)[^<]*</'),
    ('PATRONIZING_UI_COPY', 'review', r'(?i)<(?:p|span|small|div|Label|HelperText)[^>]*>[^<]*(?:\b(?:please enter your|click (?:here|this button) to|this (?:modal|form|button) allows you to)\b)[^<]*</'),
    ('TRIVIAL_COMMENT_NARRATION', 'review', r'(?i)^\s*(?://|#)\s*(?:(?:increment|decrement)\s+\w+|(?:return|returns)\s+(?:the\s+)?(?:result|response|value|data|error|promise|true|false)|(?:initialize|init)\s+(?:state|variable|array|object|list|dict)|(?:check|verify)\s+if\s+(?:\w+\s+is\s+)?(?:null|undefined|empty|none)|handle\s+(?:click|change|submit|event|button)|(?:constructor|destructor)\b|import\s+(?:modules?|packages?|react|dependencies)|call\s+(?:the\s+)?\w+\s+function)'),
]
COMPILED = [(key, level, re.compile(regex)) for key, level, regex in PATTERNS]
TEST_PATH = re.compile(r'(?i)(?:^|/)(?:tests?|__tests__|specs?)(?:/|$)|(?:^|/)(?:test_[^/]+\.py|[^/]+\.(?:test|spec)\.[a-z0-9]+)$')
GENERATED_PATH = re.compile(r'(?i)(?:^|/)(?:node_modules|vendor|dist|build|\.next|coverage|generated)(?:/|$)|(?:\.min\.js|\.lock)$')
DOC_PATH = re.compile(r'(?i)(?:\.(?:md|markdown|rst|txt|adoc)$|(?:^|/)(?:docs?|documentation|\.github/ISSUE_TEMPLATE)/)')
UI_PATH = re.compile(r'(?i)\.(?:tsx|jsx|html|vue|svelte|astro)$')
SPECULATIVE_DOC_PATH = re.compile(r'(?i)(?:^|/)docs/.*(?:submission|dossier|reviewer_packet).*\.md$')
HALLUCINATED_DOC_URL = re.compile(r'(?i)(?:https?://(?:platform|developers)\.openai\.com/plugins|\[[^\]]*\]\([^)]*(?:platform|developers)\.openai\.com/plugins[^)]*\))')
META_PREAMBLE_AND_AFFORDANCE_NARRATION = re.compile(
    r'(?i)(?:'
    r'\b(?:without leaving (?:this|the) page|دون مغادرة الصفحة|شاهد (?:التجربة|الفيديو|هنا)|'
    r'click (?:here\s+)?to (?:play|watch|view|expand|collapse|copy|download|see)|'
    r'click on the (?:button|link|chevron|arrow)|'
    r'toggle (?:to|this) (?:reveal|expand)|'
    r'press play to|tap here to)\b|'
    r'^\s*(?:In this section,? we will (?:explore|discuss|explain|cover|learn)|'
    r'The following (?:table|section|code snippet|example|list|guide) (?:outlines|illustrates|shows|describes|provides|details)|'
    r'Below,? you will find (?:a|an|the)|'
    r'Let\'s take a (?:closer )?look at|'
    r'Here is a breakdown of)\b|'
    r'^#{1,6}\s+.*[a-zA-Z]{3,}\s*[·•|/]\s*[\u0600-\u06FF]{3,}|'
    r'^#{1,6}\s+.*[\u0600-\u06FF]{3,}\s*[·•|/]\s*[a-zA-Z]{3,}'
    r')'
)


def git(repo, *args):
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode('utf-8', 'replace').strip() or f'git {args[0]} failed')
    return p.stdout


def scan(repo, base, max_lines=400):
    git(repo, 'rev-parse', '--verify', f'{base}^{{commit}}')
    diff_info = git(repo, 'diff', '--no-ext-diff', '--no-renames', '--numstat', '-z', base, '--')
    file_counts = {}
    for record in diff_info.split(b'\0'):
        if not record:
            continue
        bits = record.split(b'\t', 2)
        if len(bits) == 3:
            a, d, name = bits
            file_counts[name.decode('utf-8', 'replace')] = (int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0)
    untracked = [p.decode('utf-8', 'replace') for p in git(repo, 'ls-files', '--others', '--exclude-standard', '-z').split(b'\0') if p]
    findings = []
    limitations = ['Heuristic review hints only; no semantic or runtime validation performed.']
    if untracked:
        limitations.append(f'Untracked files ({len(untracked)}) are excluded from diff scanning; stage them for complete analysis.')
    changed_test = []
    new_test = [p for p in untracked if TEST_PATH.search(p)]
    for path in file_counts:
        if TEST_PATH.search(path):
            exists = subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', f'{base}:{path}'], capture_output=True).returncode == 0
            if exists:
                changed_test.append(path)
                findings.append({'id': 'TEST_CHANGE_REVIEW', 'severity': 'review', 'file': path,
                                 'evidence': 'Previously committed test file changed relative to base.',
                                 'action': 'Compare old/new assertions with independently approved behavior; do not auto-rebaseline.'})
            else:
                new_test.append(path)
        if SPECULATIVE_DOC_PATH.search(path):
            exists = subprocess.run(['git', '-C', str(repo), 'cat-file', '-e', f'{base}:{path}'], capture_output=True).returncode == 0
            if not exists:
                findings.append({'id': 'SPECULATIVE_DOC_CANDIDATE', 'severity': 'review', 'file': path,
                                 'evidence': f'New speculative submission dossier or platform guide: {path}',
                                 'action': 'Verify whether this documentation file was explicitly authorized; avoid unprompted submission dossiers.'})
    added_total = sum(a for a, _ in file_counts.values())
    deleted_total = sum(d for _, d in file_counts.values())
    if added_total > max_lines:
        findings.append({'id': 'LARGE_DIFF_REVIEW', 'severity': 'review', 'file': None,
                         'evidence': f'{added_total} added lines > configurable review prompt {max_lines}.',
                         'action': 'Justify scope or split into coherent, independently reviewable changes; not an automatic failure.'})
    patch = git(repo, 'diff', '--no-ext-diff', '--no-renames', '--unified=0', base, '--').decode('utf-8', 'replace')
    path = None
    new_line = None
    seen = set()
    for line in patch.splitlines():
        if line.startswith('+++ b/'):
            path = line[6:]
            new_line = None
            continue
        if line.startswith('@@'):
            match = re.search(r'\+(\d+)', line)
            new_line = int(match.group(1)) if match else None
            continue
        if not line.startswith('+') or line.startswith('+++'):
            continue
        if not path or GENERATED_PATH.search(path):
            if new_line is not None:
                new_line += 1
            continue
        code_line = line[1:]
        if not TEST_PATH.search(path) and not re.search(r'(?i)(?:^|/)references/', path) and HALLUCINATED_DOC_URL.search(code_line):
            if ('HALLUCINATED_DOC_URL', path, new_line) not in seen:
                seen.add(('HALLUCINATED_DOC_URL', path, new_line))
                findings.append({'id': 'HALLUCINATED_DOC_URL', 'severity': 'review', 'file': path, 'line': new_line,
                                 'evidence': code_line.strip()[:180],
                                 'action': 'Deprecated or hallucinated platform submission URL detected (e.g. OpenAI plugins are deprecated); verify URL and user intent.'})
        if DOC_PATH.search(path):
            if not TEST_PATH.search(path) and not re.search(r'(?i)(?:^|/)references/', path) and not re.search(r'(?i)(?:^|/)(?:SKILL\.md|AGENTS\.md|CHANGELOG\.md)$', path) and META_PREAMBLE_AND_AFFORDANCE_NARRATION.search(code_line):
                if ('META_PREAMBLE_AND_AFFORDANCE_NARRATION', path, new_line) not in seen:
                    seen.add(('META_PREAMBLE_AND_AFFORDANCE_NARRATION', path, new_line))
                    findings.append({'id': 'META_PREAMBLE_AND_AFFORDANCE_NARRATION', 'severity': 'review', 'file': path, 'line': new_line,
                                     'evidence': code_line.strip()[:180],
                                     'action': 'Violation of Direct Payload Invariant: remove conversational preambles, affordance narration (explaining how to click/play/expand/copy), mechanical hand-holding, or bilingual title-stacking.'})
            if new_line is not None:
                new_line += 1
            continue
        code_line = line[1:]
        for key, level, pattern in COMPILED:
            if key in ('SKIPPED_TEST', 'WEAK_ASSERTION') and not TEST_PATH.search(path):
                continue
            if key in ('DEV_NOTE_IN_UI', 'PATRONIZING_UI_COPY') and not UI_PATH.search(path):
                continue
            if key == 'TRIVIAL_COMMENT_NARRATION' and (TEST_PATH.search(path) or re.search(r'(?i)(?:^|/)references/', path)):
                continue
            if pattern.search(code_line) and (key, path, new_line) not in seen:
                seen.add((key, path, new_line))
                findings.append({'id': key, 'severity': level, 'file': path, 'line': new_line,
                                 'evidence': code_line.strip()[:180],
                                 'action': 'Inspect context and justify or fix; regex match is not proof of a defect.'})
        if new_line is not None:
            new_line += 1
    return {
        'base': base,
        'summary': {'changed_files': len(file_counts), 'added_lines': added_total, 'deleted_lines': deleted_total,
                    'changed_test_files': len(changed_test), 'new_test_files': len(new_test),
                    'untracked_files_not_scanned': len(untracked)},
        'findings': findings,
        'limitations': limitations,
        'status': 'review-required' if findings else 'no-heuristic-findings'
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo', default='.', help='Path to Git repository')
    p.add_argument('--base', default='HEAD', help='Existing commit to compare against, ideally merge-base with target branch')
    p.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    p.add_argument('--review-lines', type=int, default=400, help='Added-line count prompting scope review, not failure')
    p.add_argument('--fail-on-blocker', action='store_true', help='Exit 2 for candidate test-disable patterns pending review')
    a = p.parse_args()
    try:
        report = scan(pathlib.Path(a.repo).resolve(), a.base, a.review_lines)
    except (RuntimeError, ValueError) as exc:
        print(json.dumps({'error': str(exc)}) if a.json else f'ERROR: {exc}')
        return 1
    if a.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        s = report['summary']
        print(f"Compared to {a.base}: {s['changed_files']} tracked files, +{s['added_lines']} / -{s['deleted_lines']} lines")
        for f in report['findings']:
            print(f"[{f['severity']}] {f['id']}: {f.get('file') or 'diff'}:{f.get('line') or '-'} | {f['evidence']}")
        for warning in report['limitations']:
            print(f'LIMITATION: {warning}')
    return 2 if a.fail_on_blocker and any(f['severity'] == 'blocker' for f in report['findings']) else 0


if __name__ == '__main__':
    sys.exit(main())
