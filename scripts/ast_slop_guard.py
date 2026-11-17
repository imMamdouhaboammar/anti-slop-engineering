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
import sys

if not __package__:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scripts.git_changeset import git

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
        'pattern': None,
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


TOKEN_RE = re.compile(
    r"""//.*|/\*.*?\*/|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|"""
    r"""`(?:\\.|[^`\\])*`|\.\.\.|\?\.|\?\?|[^\s]"""
)
NEVER_ASSIGNMENT_RE = re.compile(r'const\s+[A-Za-z_$][\w$]*\s*:\s*never\s*=\s*([A-Za-z_$][\w$]*)\s*;?')
THROW_ASSERTION_RE = re.compile(r'throw\s+new\s+[\w$.]+\s*\(\s*([A-Za-z_$][\w$]*)\s+as\s+[A-Z]\w*\s*\)\s*;?')


def has_never_proof(line, previous_line, branch_line):
    if branch_line != 'default:':
        return False
    proof = NEVER_ASSIGNMENT_RE.fullmatch(previous_line)
    thrown = THROW_ASSERTION_RE.fullmatch(line)
    return bool(proof and thrown and proof[1] == thrown[1])


def object_groups(line):
    # Preserve lexical boundaries so a nested comma or ternary cannot end the spread.
    pairs = {')': '(', ']': '[', '}': '{'}
    stack = [('', [])]
    for match in TOKEN_RE.finditer(line):
        token = match[0]
        if token.startswith(('//', '/*')):
            continue
        if token in pairs.values():
            group = (token, [])
            stack[-1][1].append(group)
            stack.append(group)
        elif token in pairs:
            opening, children = stack[-1]
            if opening != pairs[token]:
                if not opening and token == '}' and children[:1] == ['...']:
                    yield children
                stack = [('', [])]
                continue
            stack.pop()
            if opening == '{':
                yield children
        else:
            stack[-1][1].append(token)
    for opening, children in stack:
        # Added lines may begin or end inside a surrounding object literal.
        if opening == '{' or (not opening and children[:1] == ['...']):
            yield children


def unwrap_parentheses(expression):
    while len(expression) == 1 and isinstance(expression[0], tuple) and expression[0][0] == '(':
        expression = expression[0][1]
    return expression


def is_conditional_empty_spread(expression):
    expression = unwrap_parentheses(expression)
    if '?' not in expression:
        return False

    question = expression.index('?')
    nested = 0
    for colon in range(question + 1, len(expression)):
        token = expression[colon]
        if token == '?':
            nested += 1
        elif token == ':':
            if not nested:
                empty = [('{', [])]
                return (
                    unwrap_parentheses(expression[question + 1:colon]) == empty
                    or unwrap_parentheses(expression[colon + 1:]) == empty
                )
            nested -= 1
    return False


def has_conditional_empty_spread(line):
    if '...' not in line or '?' not in line:
        return False
    for group in object_groups(line):
        start = 0
        for end, token in enumerate(group + [',']):
            if token in (',', ';'):
                if group[start:start + 1] == ['...'] and is_conditional_empty_spread(group[start + 1:end]):
                    return True
                start = end + 1
    return False


def is_eligible_file(path_str):
    """Check if file is a non-ignored JS/TS file."""
    p = pathlib.Path(path_str)
    if p.suffix.lower() not in JS_TS_EXTS:
        return False
    if IGNORE_DIR_RE.search(path_str):
        return False
    return True


def audit_source_lines(lines, file_path, changed_lines=None):
    """Audit lines of code in a single file with line numbers."""
    findings = []
    is_test = bool(TEST_PATH_RE.search(file_path))

    for idx, line in lines.items():
        if changed_lines is not None and idx not in changed_lines:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith('//') or stripped.startswith('/*') or stripped.startswith('*'):
            continue

        for rule in RULES:
            if rule.get('test_only') and not is_test:
                continue
            if rule.get('exclude_tests') and is_test:
                continue

            pattern = rule['pattern']
            matched = has_conditional_empty_spread(stripped) if pattern is None else pattern.search(stripped)
            if matched:
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
                prev_line = lines.get(idx - 1, '').strip()
                branch_line = lines.get(idx - 2, '').strip()
                if has_never_proof(stripped, prev_line, branch_line):
                    continue
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
        return audit_source_lines(dict(enumerate(content.splitlines(), 1)), str(file_path))
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


def _flush_diff_lines(current_file, source_lines, changed_lines, findings):
    if current_file and is_eligible_file(current_file) and changed_lines:
        findings.extend(audit_source_lines(source_lines, current_file, changed_lines))


def scan_diff(repo, base):
    """Scan working changes for HEAD, or committed changes for a named base."""
    findings = []
    try:
        target = 'HEAD'
        if base != target:
            revision = git(repo, 'rev-parse', '--verify', '--end-of-options', f'{base}^{{commit}}')
            target = f"{revision.decode('ascii').strip()}...HEAD"
        patch = git(
            repo, 'diff', '-U2', '--inter-hunk-context=0', '--no-color',
            '--no-ext-diff', '--no-textconv', '--src-prefix=a/', '--dst-prefix=b/', target, '--',
        )
    except RuntimeError as error:
        raise RuntimeError(f'Cannot scan Git changes against {base!r}: {error}') from error

    current_file = None
    current_line_num = None
    source_lines = {}
    changed_lines = set()
    for line in patch.decode('utf-8', 'replace').splitlines():
        if line.startswith('diff --git '):
            _flush_diff_lines(current_file, source_lines, changed_lines, findings)
            current_file = current_line_num = None
            source_lines = {}
            changed_lines = set()
        elif current_line_num is None and line.startswith('+++ b/'):
            current_file = line[6:].rstrip('\t')
        elif line.startswith('@@ '):
            match = re.match(r'^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@', line)
            current_line_num = int(match[1]) if match else None
        elif current_line_num is not None and line.startswith(('+', ' ')):
            source_lines[current_line_num] = line[1:]
            if line.startswith('+'):
                changed_lines.add(current_line_num)
            current_line_num += 1

    _flush_diff_lines(current_file, source_lines, changed_lines, findings)
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

    if args.base is not None or not args.path:
        base = args.base if args.base is not None else 'HEAD'
        try:
            findings = scan_diff(args.repo, base)
        except RuntimeError as error:
            if args.json:
                print(json.dumps({'error': str(error)}))
            else:
                print(f'ERROR: {error}', file=sys.stderr)
            sys.exit(1)
        report = build_report(findings, 'diff', base)
    else:
        target = pathlib.Path(args.path)
        if target.is_dir():
            findings = scan_directory(target)
            report = build_report(findings, 'directory', target)
        else:
            findings = scan_file(target)
            report = build_report(findings, 'file', target)

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
