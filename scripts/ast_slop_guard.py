#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Zero-dependency AST and Type Slop Guard for anti-slop-engineering.

Inspired by dmmulroy/anti-slop Oxlint rules and adapted for universal,
zero-dependency static diff and source verification in Python stdlib.
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

__version__ = '1.0.0'

JS_TS_EXTS = {'.ts', '.tsx', '.js', '.jsx', '.mjs', '.cjs'}
TEST_PATH_RE = re.compile(r'(?i)(?:^|/)(?:tests?|__tests__|specs?)(?:/|$)|(?:^|/)(?:test_[^/]+\.[a-z0-9]+|[^/]+[._](?:test|spec)\.[a-z0-9]+)$')
IGNORE_DIR_RE = re.compile(r'(?i)(?:^|/)(?:node_modules|vendor|dist|build|\.next|coverage|\.git|tools/oxlint)(?:/|$)')

RULES = [
    {
        'id': 'CHAINED_TYPE_ASSERTION',
        'severity': 'blocker',
        'pattern': re.compile(r'(?i)\bas\s+(?:unknown|any|object)\s+as\b|<\s*(?:any|unknown)\s*><'),
        'test_only': False,
        'action': 'Chained type assertion detected. Do not fabricate evidence by widening and reasserting; validate schema at the system boundary.',
    },
    {
        'id': 'CONDITIONAL_EMPTY_SPREAD',
        'severity': 'review',
        'pattern': re.compile(r'\.\.\.\s*\([^?]+\?[^:]+:\s*\{\}\)|\.\.\.\s*[a-zA-Z0-9_$.]+\s*\?\s*\{[^}]*\}\s*:\s*\{\}'),
        'test_only': False,
        'action': 'Conditional empty object spread detected. Spreading `{}` allocates throwaways and deoptimizes V8 hidden classes. Use explicit property assignments.',
    },
    {
        'id': 'ARRAY_FILTER_MAP_CHAIN',
        'severity': 'review',
        'pattern': re.compile(r'\.(?:filter|map)\s*\([^)]*\)\s*\.(?:map|filter)\s*\('),
        'test_only': False,
        'action': 'Adjacent eager array filter/map pass detected. Creates redundant intermediate arrays. Prefer lazy iterator helpers (`.values().filter().map().toArray()`), a single `flatMap()`, or a mutating reducer.',
    },
    {
        'id': 'REDUCE_ACCUMULATOR_COPY',
        'severity': 'blocker',
        'pattern': re.compile(r'(?i)\.reduce(?:Right)?\s*\(.*?(?:Object\.assign\s*\(\s*\{\}\s*,|(?:\bacc|accumulator)\.(?:concat|slice|toSpliced|toSorted|toReversed)\s*\()'),
        'test_only': False,
        'action': 'Reducer accumulator copy detected. Copying an accumulator inside a reducer causes quadratic O(N^2) complexity and memory bloat. Mutate the local accumulator and return it.',
    },
    {
        'id': 'MODULE_MOCKING_ORACLE_EROSION',
        'severity': 'blocker',
        'pattern': re.compile(r'(?i)\b(?:vi|jest)\.(?:mock|doMock|unstable_mockModule)\s*\('),
        'test_only': True,
        'action': 'Module mocking detected in tests. Mocking whole modules erodes test fidelity and creates assertion theater. Use real dependency seams, in-memory fakes, or dependency injection.',
    },
    {
        'id': 'RUNTIME_TYPEOF_AD_HOC',
        'severity': 'review',
        'pattern': re.compile(r'\btypeof\s+[a-zA-Z0-9_$.]+\s*===\s*["\'](?:object|string|number|boolean)["\']'),
        'test_only': False,
        'exclude_tests': True,
        'action': 'Ad-hoc runtime typeof narrowing detected. External input must be parsed into branded domain types at the I/O boundary using schema validation (Zod, ArkType, Valibot, Effect Schema).',
    },
    {
        'id': 'METANAME_SHAPE_SLOP',
        'severity': 'review',
        'pattern': re.compile(r'\b(?:interface|type)\s+[A-Z]\w*Shape\b'),
        'test_only': False,
        'action': 'Meta-naming slop "Shape" detected in type/interface identifier. Name domain models after the business concept (e.g. `User`, `UserDTO`), not implementation metadata.',
    },
    {
        'id': 'EFFECT_MANUAL_TAG_SLOP',
        'severity': 'review',
        'pattern': re.compile(r'\._tag\s*===|\._tag\s*!=='),
        'test_only': False,
        'action': 'Manual Effect `_tag` comparison detected. Use Effect `Match.value()`, `Predicate.isTagged()`, or `Effect.catchTag()` instead of manual tag checking.',
    },
]

SAFETY_COMMENT_RE = re.compile(r'(?i)//\s*(?:SAFETY|INVARIANT)\s*:')
TYPE_ASSERTION_RE = re.compile(r'\bas\s+(?!const\b)[A-Z]\w*\b')


def is_eligible_file(path_str):
    """Check if file is a non-ignored JS/TS file."""
    p = pathlib.Path(path_str)
    if p.suffix.lower() not in JS_TS_EXTS:
        return False
    if IGNORE_DIR_RE.search(path_str):
        return False
    return True


def audit_source_lines(lines, file_path):
    """Audit lines of code in a single file with line numbers."""
    findings = []
    is_test = bool(TEST_PATH_RE.search(file_path))

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue

        for rule in RULES:
            if rule.get('test_only') and not is_test:
                continue
            if rule.get('exclude_tests') and is_test:
                continue

            if rule['pattern'].search(stripped):
                findings.append({
                    'id': rule['id'],
                    'severity': rule['severity'],
                    'file': file_path,
                    'line': idx,
                    'evidence': stripped[:160],
                    'action': rule['action']
                })

        # Check for ungrounded type assertions in non-test TS files
        if file_path.endswith(('.ts', '.tsx')) and not is_test:
            if TYPE_ASSERTION_RE.search(stripped) and not stripped.startswith('import '):
                # Look backwards for SAFETY comment on previous line
                prev_line = lines[idx - 2].strip() if idx >= 2 else ''
                curr_has_safety = bool(SAFETY_COMMENT_RE.search(stripped))
                prev_has_safety = bool(SAFETY_COMMENT_RE.search(prev_line))
                if not (curr_has_safety or prev_has_safety):
                    findings.append({
                        'id': 'UNJUSTIFIED_TYPE_ASSERTION',
                        'severity': 'review',
                        'file': file_path,
                        'line': idx,
                        'evidence': stripped[:160],
                        'action': 'Type assertion without invariant justification. Non-const type assertions must be preceded by a "// SAFETY: <reason>" comment.'
                    })

    return findings


def scan_file(file_path):
    """Scan a single file from disk."""
    try:
        content = pathlib.Path(file_path).read_text(encoding='utf-8', errors='replace')
        return audit_source_lines(content.splitlines(), str(file_path))
    except Exception as err:
        return [{
            'id': 'READ_ERROR',
            'severity': 'review',
            'file': str(file_path),
            'line': 0,
            'evidence': str(err),
            'action': 'Verify file permissions.'
        }]


def scan_directory(dir_path):
    """Walk directory and scan eligible files."""
    findings = []
    root = pathlib.Path(dir_path)
    for p in root.rglob('*'):
        if p.is_file() and is_eligible_file(str(p)):
            findings.extend(scan_file(p))
    return findings


def scan_diff(repo, base):
    """Scan added lines from git diff."""
    findings = []
    try:
        cmd = ['git', '-C', str(repo), 'diff', '-U0', f'{base}...HEAD']
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        diff_text = res.stdout
    except subprocess.CalledProcessError:
        # Fall back to 2-dot diff
        cmd = ['git', '-C', str(repo), 'diff', '-U0', base]
        res = subprocess.run(cmd, capture_output=True, text=True)
        diff_text = res.stdout

    current_file = None
    current_line_num = 0
    added_lines = []

    for line in diff_text.splitlines():
        if line.startswith('+++ b/'):
            if current_file and is_eligible_file(current_file) and added_lines:
                # Audit accumulated lines
                text_lines = [l for _, l in added_lines]
                file_findings = audit_source_lines(text_lines, current_file)
                # Remap line numbers to diff line numbers
                for f in file_findings:
                    relative_idx = f['line'] - 1
                    if 0 <= relative_idx < len(added_lines):
                        f['line'] = added_lines[relative_idx][0]
                findings.extend(file_findings)
            current_file = line[6:].strip()
            added_lines = []
            continue

        if line.startswith('@@'):
            m = re.search(r'\+(\d+)', line)
            current_line_num = int(m.group(1)) if m else 0
            continue

        if line.startswith('+') and not line.startswith('+++'):
            code = line[1:]
            added_lines.append((current_line_num, code))
            current_line_num += 1

    if current_file and is_eligible_file(current_file) and added_lines:
        text_lines = [l for _, l in added_lines]
        file_findings = audit_source_lines(text_lines, current_file)
        for f in file_findings:
            relative_idx = f['line'] - 1
            if 0 <= relative_idx < len(added_lines):
                f['line'] = added_lines[relative_idx][0]
        findings.extend(file_findings)

    return findings


def build_report(findings, mode, target):
    """Construct deterministic JSON report."""
    blockers = [f for f in findings if f['severity'] == 'blocker']
    reviews = [f for f in findings if f['severity'] == 'review']
    verdict = 'FAIL' if blockers else ('REVIEW' if reviews else 'PASS')

    return {
        'tool': 'anti-slop-ast-guard',
        'version': __version__,
        'mode': mode,
        'target': str(target),
        'verdict': verdict,
        'summary': {
            'total_findings': len(findings),
            'blockers': len(blockers),
            'reviews': len(reviews),
        },
        'findings': findings,
    }


def main():
    parser = argparse.ArgumentParser(description='AST & Type Slop Guard for anti-slop-engineering.')
    parser.add_argument('path', nargs='?', default=None, help='File or directory to scan directly.')
    parser.add_argument('--repo', default='.', help='Git repository path (default: current dir).')
    parser.add_argument('--base', default=None, help='Git base ref to diff against (e.g. HEAD or origin/main).')
    parser.add_argument('--json', action='store_true', help='Output JSON report.')
    parser.add_argument('--strict', action='store_true', help='Exit code 2 on any blocker finding.')
    parser.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    args = parser.parse_args()

    if args.base:
        findings = scan_diff(args.repo, args.base)
        report = build_report(findings, 'diff', args.base)
    elif args.path:
        target = pathlib.Path(args.path)
        if target.is_dir():
            findings = scan_directory(target)
            report = build_report(findings, 'directory', target)
        else:
            findings = scan_file(target)
            report = build_report(findings, 'file', target)
    else:
        # Default to diff against HEAD
        findings = scan_diff(args.repo, 'HEAD')
        report = build_report(findings, 'diff', 'HEAD')

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"--- Anti-Slop AST Guard (v{__version__}) ---")
        print(f"Mode: {report['mode']} | Target: {report['target']} | Verdict: {report['verdict']}")
        print(f"Total findings: {report['summary']['total_findings']} (Blockers: {report['summary']['blockers']}, Reviews: {report['summary']['reviews']})")
        if report['findings']:
            print("\nFindings:")
            for f in report['findings']:
                print(f"  [{f['severity'].upper()}] {f['id']} at {f['file']}:{f['line']}")
                print(f"    Evidence: {f['evidence']}")
                print(f"    Action:   {f['action']}")

    if args.strict and report['summary']['blockers'] > 0:
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
