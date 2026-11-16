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
        'pattern': re.compile(r'\btypeof\s+[a-zA-Z0-9_$.]+\s*===\s*(["\'])(?:object|string|number|boolean)\1'),
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


_QUOTE_TO_STATE = {"'": 'single', '"': 'double', '`': 'template'}
_STATE_TO_QUOTE = {v: k for k, v in _QUOTE_TO_STATE.items()}
_REGEX_KEYWORDS = {
    'return', 'throw', 'case', 'typeof', 'void', 'delete',
    'await', 'yield', 'in', 'of', 'instanceof', 'new', 'else', 'do',
}
_REGEX_PRECEDERS = set('=({[,:;?&|^~+-*%')


def _find_regex_end(line, start):
    """Return index of closing '/' if line[start:] begins a regex literal."""
    j, n, in_class = start + 1, len(line), False
    while j < n:
        ch = line[j]
        if ch == '\\':
            if j + 1 >= n:
                return None
            j += 2
        elif ch == '[':
            in_class = True
            j += 1
        elif ch == ']':
            in_class = False
            j += 1
        elif ch == '/' and not in_class:
            return j
        else:
            j += 1
    return None


def _is_regex_start(out, idx):
    """Check whether '/' at idx can start a JS/TS regex literal."""
    prefix = ''.join(out[:idx]).rstrip()
    if not prefix:
        return True
    if prefix.endswith(('++', '--')):
        return False
    last = prefix[-1]
    if last in _REGEX_PRECEDERS:
        return True
    if last == '!':
        return len(prefix) == 1 or not (prefix[-2].isalnum() or prefix[-2] in '_$)]')
    m = re.search(r'[A-Za-z_$][A-Za-z0-9_$]*$', prefix)
    return bool(m and m.group(0) in _REGEX_KEYWORDS)


def _step_code_char(line, out, i, interp):
    """Advance one token from 'code' state, returning (new_state, next_index)."""
    ch, nxt = line[i], line[i + 1] if i + 1 < len(line) else ''
    if ch == '/' and nxt == '/':
        safety_match = SAFETY_COMMENT_RE.match(line, i)
        if safety_match:
            return 'line_comment', safety_match.end()
        out[i] = out[i + 1] = ' '
        return 'line_comment', i + 2
    if ch == '/' and nxt == '*':
        out[i] = out[i + 1] = ' '
        return 'block_comment', i + 2
    if ch == '/' and _is_regex_start(out, i):
        regex_end = _find_regex_end(line, i)
        if regex_end is not None:
            out[i + 1:regex_end] = [' '] * (regex_end - i - 1)
            return 'code', regex_end + 1
    if ch in _QUOTE_TO_STATE:
        return _QUOTE_TO_STATE[ch], i + 1
    if ch == '{' and interp:
        interp[-1] += 1
    elif ch == '}' and interp:
        interp[-1] -= 1
        if interp[-1] == 0:
            interp.pop()
            return 'template', i + 1
    return 'code', i + 1


def _mask_string_literals(lines):
    """Return lines with string, comment, and regex contents replaced by spaces.

    Delimiters are preserved and each masked character becomes one space,
    so lengths/columns are unchanged. Handles single/double/template
    literals, regex literals, escapes, ``${...}`` interpolation (code inside
    is kept), and ``//`` / ``/* */`` comments. Template literals and block
    comments may span lines; single/double literals reset at end of line.
    """
    masked_lines, state, interp = [], 'code', []
    for line in lines:
        out, i, n = list(line), 0, len(line)
        while i < n:
            ch, nxt = line[i], line[i + 1] if i + 1 < n else ''
            if state in _STATE_TO_QUOTE and ch == '\\' and nxt:
                out[i] = out[i + 1] = ' '
                i += 2
            elif state == 'code':
                state, i = _step_code_char(line, out, i, interp)
            elif state == 'block_comment' and ch == '*' and nxt == '/':
                out[i] = out[i + 1] = ' '
                state, i = 'code', i + 2
            elif state in _STATE_TO_QUOTE and ch == _STATE_TO_QUOTE[state]:
                state, i = 'code', i + 1
            elif state == 'template' and ch == '$' and nxt == '{':
                interp.append(1)
                state, i = 'code', i + 2
            else:
                out[i] = ' '
                i += 1
        if state in ('line_comment', 'single', 'double'):
            state = 'code'
        masked_lines.append(''.join(out))
    return masked_lines


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
    masked_lines = _mask_string_literals(lines)

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        masked = masked_lines[idx - 1].strip()
        if not masked:
            continue

        for rule in RULES:
            if rule.get('test_only') and not is_test:
                continue
            if rule.get('exclude_tests') and is_test:
                continue

            if rule['id'] == 'RUNTIME_TYPEOF_AD_HOC':
                raw_masked = masked_lines[idx - 1]
                matched = any(
                    raw_masked[m.start():m.start() + 6] == 'typeof'
                    and raw_masked[m.end() - 1] == line[m.end() - 1]
                    for m in rule['pattern'].finditer(line)
                )
            else:
                matched = bool(rule['pattern'].search(masked))

            if matched:
                findings.append({
                    'id': rule['id'],
                    'severity': rule['severity'],
                    'file': file_path,
                    'line': idx,
                    'evidence': stripped[:160],
                    'action': rule['action']
                })

        if (
            file_path.endswith(('.ts', '.tsx'))
            and not is_test
            and TYPE_ASSERTION_RE.search(masked)
            and not masked.startswith('import ')
        ):
            prev_masked = masked_lines[idx - 2] if idx >= 2 else ''
            has_safety = bool(SAFETY_COMMENT_RE.search(masked) or SAFETY_COMMENT_RE.search(prev_masked))
            if not has_safety:
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


def _audit_hunk(current_file, hunk):
    """Audit a single contiguous diff hunk and remap line numbers."""
    file_findings = audit_source_lines([code for _, code in hunk], current_file)
    for finding in file_findings:
        rel_idx = finding['line'] - 1
        if 0 <= rel_idx < len(hunk):
            finding['line'] = hunk[rel_idx][0]
    return file_findings


def _audit_diff_file(repo, current_file, added_lines):
    """Audit added diff lines using full file context when available."""
    repo_file = pathlib.Path(repo) / current_file
    full_lines = None
    if repo_file.is_file():
        try:
            candidate = repo_file.read_text(encoding='utf-8', errors='replace').splitlines()
            if all(1 <= ln <= len(candidate) and candidate[ln - 1] == code for ln, code in added_lines):
                full_lines = candidate
        except OSError:
            full_lines = None

    if full_lines is not None:
        added_nums = {ln for ln, _ in added_lines}
        return [f for f in audit_source_lines(full_lines, current_file) if f['line'] in added_nums]

    findings, hunk = [], []
    for ln, code in added_lines:
        if hunk and ln != hunk[-1][0] + 1:
            findings.extend(_audit_hunk(current_file, hunk))
            hunk = []
        hunk.append((ln, code))
    if hunk:
        findings.extend(_audit_hunk(current_file, hunk))
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
                findings.extend(_audit_diff_file(repo, current_file, added_lines))
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
        findings.extend(_audit_diff_file(repo, current_file, added_lines))

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
