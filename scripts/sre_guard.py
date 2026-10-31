#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Google Site Reliability Engineering (SRE) Guard for AI Coding Agents.

Enforces Google SRE principles in code and Git diffs:
- KISS: Simplicity, bounded nesting depth, function size limits, shallow indirection.
- DRY: Single source of truth, elimination of duplicated logic blocks and divergent schemas.
- YAGNI: Zero speculative engineering, unused knobs, dead flags, and ghost extension points.
- Fix Issues at Scale: Elimination of operational toil, exponential backoff with jitter,
  bounded concurrency, circuit breakers, idempotency, and structured error telemetry.

Zero external dependencies: Python 3.9+ standard library only.
"""
import argparse
import collections
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys

# File types subject to SRE code analysis
CODE_EXTENSIONS = {
    '.py', '.ts', '.tsx', '.js', '.jsx', '.go', '.rs',
    '.java', '.c', '.cpp', '.h', '.hpp', '.cs', '.rb', '.php'
}

TEST_PATH_RE = re.compile(
    r'(?i)(?:^|/)(?:tests?|__tests__|specs?)(?:/|$)|(?:^|/)(?:test_[^/]+\.py|[^/]+[._](?:test|spec)\.[a-z0-9]+)$'
)
GENERATED_PATH_RE = re.compile(
    r'(?i)(?:^|/)(?:node_modules|vendor|dist|build|\.next|coverage|generated)(?:/|$)|(?:\.min\.js|\.lock)$'
)

# SRE Heuristic Patterns (Category, Key, Severity, Regex, Remediation)
SRE_PATTERNS = [
    # YAGNI: Speculative comments and placeholders
    (
        'YAGNI',
        'YAGNI_SPECULATIVE_COMMENT',
        'review',
        re.compile(
            r'(?i)(?:#|//|/\*)\s*(?:TODO\s*\(\s*(?:future|later|v2|next)\s*\)|'
            r'placeholder for (?:future|upcoming|v2)|will be (?:supported|implemented|used) (?:later|in v2)|'
            r'reserved for future use|not yet used\b)'
        ),
        'YAGNI violation: Speculative code or placeholder comment detected. Implement only what is required by current specifications.'
    ),
    # YAGNI: Dead speculative feature toggles
    (
        'YAGNI',
        'YAGNI_DEAD_SPECULATIVE_FLAG',
        'blocker',
        re.compile(r'(?i)(?:if\s+False\s*:|if\s*\(\s*false\s*\)|if\s*\(\s*0\s*\))\s*(?:#|//.*)?$'),
        'YAGNI violation: Hardcoded dead conditional branch detected. Remove dead speculative branches; version control is the archive.'
    ),
    # YAGNI: Speculative parameter patterns
    (
        'YAGNI',
        'YAGNI_SPECULATIVE_PARAMETER',
        'review',
        re.compile(r'\b(?:future_kwargs|unused_arg|' + '_unused_param' + r'|reserved_flag)\b'),
        'YAGNI violation: Speculative or reserved parameter detected. Keep interface surfaces minimal and concrete.'
    ),
    # SCALE: Sleep as a race-condition synchronization band-aid
    (
        'SCALE',
        'SCALE_SLEEP_BAND_AID',
        'review',
        re.compile(r'(?i)\b(?:time\.sleep\s*\(\s*(?:0?\.[1-9]|[1-9])\d*\s*\)|thread\.sleep\s*\(\s*\d+\s*\)|setTimeout\s*\([^,]+,\s*(?:100|200|500|1000|2000|5000)\s*\))'),
        'SCALE violation: Hardcoded sleep synchronization band-aid detected. Replace arbitrary sleeps with deterministic condition variables, latches, or polling with bounded timeout.'
    ),
    # SCALE: Unbounded or flat retry without exponential backoff & jitter
    (
        'SCALE',
        'SCALE_UNBOUNDED_OR_FLAT_RETRY',
        'blocker',
        re.compile(r'(?i)(?:while\s+True\s*:|while\s*\(\s*true\s*\)|for\s+(?:attempt|retry|i)\s+in\s+range\s*\(\s*\d+\s*\):).*(?:sleep\s*\(\s*[1-9]\d*\s*\))'),
        'SCALE violation: Flat retry without exponential backoff and jitter detected. Under service degradation, flat retries trigger thundering herds and retry storms. Implement exponential backoff with full jitter.'
    ),
    # SCALE: Unbounded concurrency / missing backpressure
    (
        'SCALE',
        'SCALE_UNBOUNDED_CONCURRENCY',
        'review',
        re.compile(r'(?i)(?:Promise\.all\s*\(\s*(?:\w+|\w+\.[a-zA-Z0-9_]+)\.map\s*\(|asyncio\.gather\s*\(\s*\*\s*\[)'),
        'SCALE violation: Unbounded concurrency mapping detected without pool, concurrency limiter, or chunking. Constrain parallel operations with a semaphore or worker queue to prevent resource starvation.'
    ),
    # SCALE: Swallowed exceptions causing operational toil
    (
        'SCALE',
        'SCALE_TOIL_ERROR_SWALLOW',
        'blocker',
        re.compile(r'(?i)(?:except\s+(?:Exception|BaseException)?\s*:\s*pass\b|catch\s*\([^)]*\)\s*\{\s*\}|\.catch\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\))'),
        'SCALE violation: Swallowed exception detected. Silent failures create untracked fleet-wide failures and manual operational toil. Log structured telemetry with error codes and correlation IDs, or propagate.'
    ),
    # SCALE: Misleading health check returning unconditional OK
    (
        'SCALE',
        'SCALE_MISLEADING_HEALTH_CHECK',
        'review',
        re.compile(r'(?i)(?:def\s+(?:healthz?|liveness|readiness)\s*\([^)]*\)\s*:\s*return\s+(?:\{["\']status["\']:\s*["\']ok["\']\}|["\']ok["\']|200\b)|\b(?:app|router)\.get\s*\(\s*["\']/(?:healthz?|live|ready)["\']\s*,\s*(?:lambda|async\s+lambda)?\s*(?:=>)?\s*200\b)'),
        'SCALE violation: Static health check detected without dependency probe. Distinguish liveness from readiness, and verify critical dependencies before returning ready status.'
    ),
]


def git_exec(repo, *args):
    """Execute git command in repo directory."""
    p = subprocess.run(['git', '-C', str(repo), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip() or f"git {' '.join(args)} failed with code {p.returncode}")
    return p.stdout


def safe_read_file(path_obj):
    """Read UTF-8 text from file without silent failure."""
    try:
        return path_obj.read_text(encoding='utf-8', errors='replace')
    except (OSError, UnicodeError) as exc:
        sys.stderr.write(f"[sre-guard] Warning: could not read {path_obj}: {exc}\n")
        return None


def normalize_line(line):
    """Strip whitespace, comments, and import statements for DRY duplicate detection."""
    stripped = line.strip()
    if not stripped or stripped.startswith(('#', '//', '/*', '*', 'import ', 'from ', 'package ', 'use ')):
        return ''
    if re.fullmatch(r'''(?:"[^"]*"|'[^']*'),?''', stripped):
        return ''
    if stripped in ('{', '}', '(', ')', '};', '];', ');', 'return', ']', '['):
        return ''
    return stripped


def check_kiss_nesting(content, max_nesting=4):
    """Analyze code nesting depth. Returns list of (line_num, depth, line_snippet)."""
    violations = []
    lines = content.splitlines()
    bracket_depth = 0

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', '//', '/*', '*')):
            continue

        in_bracket = bracket_depth > 0
        bracket_depth += line.count('(') - line.count(')')
        bracket_depth += line.count('[') - line.count(']')
        bracket_depth += line.count('{') - line.count('}')
        bracket_depth = max(0, bracket_depth)

        # Do not flag multiline continuation lines inside open parentheses or brackets
        if in_bracket:
            continue

        leading_spaces = len(line) - len(line.lstrip(' '))
        leading_tabs = len(line) - len(line.lstrip('\t'))
        indent_level = max(leading_spaces // 4, leading_tabs)

        if indent_level > max_nesting:
            violations.append((idx, indent_level, stripped[:100]))

    return violations


def check_kiss_function_length(content, max_lines=80):
    """Analyze function length bloat. Returns list of (func_name, line_num, length)."""
    violations = []
    lines = content.splitlines()

    func_re = re.compile(
        r'(?i)^\s*(?:async\s+)?(?:def\s+([a-zA-Z0-9_]+)|function\s+([a-zA-Z0-9_]+)|const\s+([a-zA-Z0-9_]+)\s*=\s*(?:async\s*)?\([^)]*\)\s*=>)'
    )

    current_func = None
    current_start = 0
    current_count = 0
    current_indent = 0

    for idx, line in enumerate(lines, 1):
        stripped = line.strip()
        leading_spaces = len(line) - len(line.lstrip(' '))

        match = func_re.match(line)
        if match:
            if current_func and current_count > max_lines:
                violations.append((current_func, current_start, current_count))
            current_func = match.group(1) or match.group(2) or match.group(3) or 'anonymous'
            current_start = idx
            current_count = 0
            current_indent = leading_spaces
        elif current_func and stripped:
            is_block_exit = (leading_spaces <= current_indent and not stripped.startswith((')', '}', ']', '#', '//')))
            if not is_block_exit:
                current_count += 1
                continue
            if current_count > max_lines:
                violations.append((current_func, current_start, current_count))
            current_func = None
            current_count = 0

    if current_func and current_count > max_lines:
        violations.append((current_func, current_start, current_count))

    return violations


def check_dry_duplication(file_contents_map, min_dup_lines=4):
    """Detect duplicated code blocks across files using a sliding window of normalized lines."""
    block_index = collections.defaultdict(list)

    for file_path, content in file_contents_map.items():
        if TEST_PATH_RE.search(file_path):
            continue

        lines = content.splitlines()
        normalized = [(idx, normalize_line(line)) for idx, line in enumerate(lines, 1)]
        code_lines = [(idx, line) for idx, line in normalized if line]

        if len(code_lines) < min_dup_lines:
            continue

        for i in range(len(code_lines) - min_dup_lines + 1):
            window = code_lines[i:i + min_dup_lines]
            block_text = '\n'.join(line for _, line in window)
            if len(set(line for _, line in window)) <= 1:
                continue
            block_hash = hashlib.sha256(block_text.encode('utf-8')).hexdigest()[:16]
            start_line = window[0][0]
            block_index[block_hash].append((file_path, start_line, block_text))

    duplicates = []
    seen_pairs = set()

    for occurrences in block_index.values():
        if len(occurrences) <= 1:
            continue
        first_file, first_line, sample = occurrences[0]
        for other_file, other_line, _ in occurrences[1:]:
            pair = tuple(sorted([(first_file, first_line), (other_file, other_line)]))
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            duplicates.append({
                'category': 'DRY',
                'id': 'DRY_CODE_DUPLICATION',
                'severity': 'review',
                'file': other_file,
                'line': other_line,
                'evidence': f'Duplicated {min_dup_lines}-line block matches {first_file}:{first_line}: {sample[:120]}...',
                'action': 'DRY violation: Consolidate duplicated logic into a shared single source of truth or canonical helper.'
            })

    return duplicates


def get_next_code_line(lines, current_idx):
    """Retrieve the line number and text of the next non-empty, non-comment line."""
    for i in range(current_idx, len(lines)):
        s = lines[i].strip()
        if s and not s.startswith(('#', '//', '/*', '*')):
            return i + 1, s
    return None, None


def add_finding(findings, seen, category, key, severity, file_path, line_idx, evidence, action):
    """Record a deduplicated finding."""
    if (key, line_idx) not in seen:
        seen.add((key, line_idx))
        findings.append({
            'category': category,
            'id': key,
            'severity': severity,
            'file': str(file_path),
            'line': line_idx,
            'evidence': evidence,
            'action': action
        })


def scan_file_sre(file_path, content, max_nesting=4, max_function_lines=80, is_test_file=False):
    """Scan a single file for SRE violations."""
    if is_test_file:
        return []

    findings = []
    seen = set()
    lines = content.splitlines()
    is_self_script = str(file_path).endswith('sre_guard.py')

    for line_idx, line in enumerate(lines, 1):
        if is_self_script and ('SRE_PATTERNS' in line or 're.compile' in line):
            continue

        for category, key, severity, pattern, action in SRE_PATTERNS:
            if pattern.search(line):
                add_finding(findings, seen, category, key, severity, file_path, line_idx, line.strip()[:180], action)

        next_line_idx, next_line_text = get_next_code_line(lines, line_idx)
        if next_line_text:
            is_py_swallow = bool(re.search(r'^\s*except(?:\s+[^:]*)?:\s*$', line) and re.match(r'^(?:pass|\.\.\.)\b', next_line_text))
            is_js_swallow = bool(re.search(r'^\s*catch\s*(?:\([^)]*\))?\s*\{\s*$', line) and next_line_text.startswith('}'))
            if is_py_swallow or is_js_swallow:
                add_finding(
                    findings, seen, 'SCALE', 'SCALE_TOIL_ERROR_SWALLOW', 'blocker',
                    file_path, line_idx, f"{line.strip()} -> {next_line_text}",
                    'SCALE violation: Swallowed exception detected. Silent failures create untracked fleet-wide failures and manual operational toil. Log structured telemetry with error codes and correlation IDs, or propagate.'
                )

            is_static_probe = bool(re.search(r'(?i)^\s*(?:async\s+)?def\s+(?:healthz?|liveness|readiness)\s*\(', line) and re.search(r'(?i)return\s+(?:\{["\']status["\']:\s*["\']ok["\']\}|["\']ok["\']|200\b)', next_line_text))
            if is_static_probe:
                add_finding(
                    findings, seen, 'SCALE', 'SCALE_MISLEADING_HEALTH_CHECK', 'review',
                    file_path, line_idx, f"{line.strip()} -> {next_line_text}",
                    'SCALE violation: Static health check detected without dependency probe. Distinguish liveness from readiness, and verify critical dependencies before returning ready status.'
                )

    nesting_violations = check_kiss_nesting(content, max_nesting=max_nesting)
    for line_idx, depth, snippet in nesting_violations:
        add_finding(
            findings, seen, 'KISS', 'KISS_DEEP_NESTING', 'review',
            file_path, line_idx, f'Indentation/nesting depth ({depth}) exceeds limit ({max_nesting}): {snippet}',
            'KISS violation: Excessive nesting depth makes code hard to test and reason about. Flatten with early-return guard clauses.'
        )

    func_violations = check_kiss_function_length(content, max_lines=max_function_lines)
    for func_name, start_line, length in func_violations:
        add_finding(
            findings, seen, 'KISS', 'KISS_FUNCTION_BLOAT', 'review',
            file_path, start_line, f"Function '{func_name}' is {length} lines (> {max_function_lines} limit).",
            'KISS violation: Large function concentrates multiple responsibilities. Decompose into focused single-responsibility sub-routines.'
        )

    return findings


def scan_contents_map(file_contents, max_nesting=4, min_dup_lines=4, max_function_lines=80):
    """Scan in-memory file contents mapping for SRE violations."""
    findings = []
    for f, content in file_contents.items():
        is_test = bool(TEST_PATH_RE.search(f))
        findings.extend(scan_file_sre(
            f, content,
            max_nesting=max_nesting,
            max_function_lines=max_function_lines,
            is_test_file=is_test
        ))
    findings.extend(check_dry_duplication(file_contents, min_dup_lines=min_dup_lines))
    return findings


def build_sre_summary(file_count, findings, base=None):
    """Construct canonical SRE report dictionary."""
    report = {
        'summary': {
            'scanned_files': file_count,
            'total_findings': len(findings),
            'blockers': sum(1 for f in findings if f['severity'] == 'blocker'),
            'reviews': sum(1 for f in findings if f['severity'] == 'review'),
            'categories': {
                'KISS': sum(1 for f in findings if f.get('category') == 'KISS'),
                'DRY': sum(1 for f in findings if f.get('category') == 'DRY'),
                'YAGNI': sum(1 for f in findings if f.get('category') == 'YAGNI'),
                'SCALE': sum(1 for f in findings if f.get('category') == 'SCALE'),
            }
        },
        'findings': findings
    }
    if base is not None:
        report['base'] = base
    return report


def scan_git_diff(repo, base='HEAD', max_nesting=4, min_dup_lines=4, max_function_lines=80):
    """Analyze Git diff against base commit for SRE violations."""
    git_exec(repo, 'rev-parse', '--verify', f'{base}^{{commit}}')

    diff_stat = git_exec(repo, 'diff', '--no-ext-diff', '--name-only', base, '--').splitlines()
    changed_files = [f for f in diff_stat if any(f.endswith(ext) for ext in CODE_EXTENSIONS)]

    file_contents = {}
    for f in changed_files:
        full_path = pathlib.Path(repo) / f
        if full_path.is_file() and not GENERATED_PATH_RE.search(f):
            content = safe_read_file(full_path)
            if content is not None:
                file_contents[f] = content

    findings = scan_contents_map(file_contents, max_nesting, min_dup_lines, max_function_lines)

    # Parse diff patch to filter findings to changed/added lines
    patch = git_exec(repo, 'diff', '--no-ext-diff', '--unified=0', base, '--')
    diff_added_lines = collections.defaultdict(set)
    current_file = None

    for line in patch.splitlines():
        if line.startswith('+++ b/'):
            current_file = line[6:]
        elif line.startswith('@@') and current_file:
            m = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if m:
                start = int(m.group(1))
                count = int(m.group(2)) if m.group(2) else 1
                for l in range(start, start + count):
                    diff_added_lines[current_file].add(l)

    for f in findings:
        file_path = f.get('file')
        line_num = f.get('line')
        if file_path and line_num and file_path in diff_added_lines:
            f['in_active_diff'] = line_num in diff_added_lines[file_path]
        else:
            f['in_active_diff'] = False

    return build_sre_summary(len(file_contents), findings, base=base)


def scan_paths(paths, max_nesting=4, min_dup_lines=4, max_function_lines=80):
    """Scan arbitrary filesystem paths (files or directories) for SRE violations."""
    file_contents = {}

    for p in paths:
        target = pathlib.Path(p).resolve()
        if target.is_file() and any(str(target).endswith(ext) for ext in CODE_EXTENSIONS):
            if not GENERATED_PATH_RE.search(str(target)):
                content = safe_read_file(target)
                if content is not None:
                    file_contents[str(target)] = content
        elif target.is_dir():
            for root, _, files in os.walk(target):
                for f in files:
                    if any(f.endswith(ext) for ext in CODE_EXTENSIONS):
                        rel = os.path.relpath(os.path.join(root, f))
                        if not GENERATED_PATH_RE.search(rel):
                            fp = pathlib.Path(root) / f
                            content = safe_read_file(fp)
                            if content is not None:
                                file_contents[str(fp)] = content

    findings = scan_contents_map(file_contents, max_nesting, min_dup_lines, max_function_lines)
    return build_sre_summary(len(file_contents), findings)


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument('--repo', default='.', help='Path to Git repository (default: current directory)')
    p.add_argument('--base', help='Git base commit/branch to analyze diff against (e.g. HEAD, origin/main)')
    p.add_argument('--files', nargs='*', help='Explicit file paths or directories to analyze')
    p.add_argument('--json', action='store_true', help='Output machine-readable JSON report')
    p.add_argument('--strict', '--fail-on-violation', dest='strict', action='store_true',
                   help='Exit code 2 if any SRE blocker is identified')
    p.add_argument('--max-nesting', type=int, default=4, help='Max allowed nesting depth for KISS check (default: 4)')
    p.add_argument('--min-dup-lines', type=int, default=4, help='Min consecutive lines to flag as DRY duplicate (default: 4)')
    p.add_argument('--max-function-lines', type=int, default=80, help='Max lines for single function (default: 80)')

    args = p.parse_args()

    try:
        common_kwargs = {
            'max_nesting': args.max_nesting,
            'min_dup_lines': args.min_dup_lines,
            'max_function_lines': args.max_function_lines
        }
        if args.files:
            report = scan_paths(args.files, **common_kwargs)
        else:
            base = args.base or 'HEAD'
            report = scan_git_diff(
                pathlib.Path(args.repo).resolve(),
                base=base,
                **common_kwargs
            )
    except (RuntimeError, ValueError) as exc:
        if args.json:
            print(json.dumps({'error': str(exc)}))
        else:
            print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        s = report['summary']
        print(f"--- Google SRE Guard Report ---")
        print(f"Scanned files: {s['scanned_files']} | Total findings: {s['total_findings']} (Blockers: {s['blockers']}, Reviews: {s['reviews']})")
        print(f"Breakdown: KISS: {s['categories']['KISS']} | DRY: {s['categories']['DRY']} | YAGNI: {s['categories']['YAGNI']} | SCALE: {s['categories']['SCALE']}")
        print()
        for f in report['findings']:
            cat = f.get('category', 'SRE')
            sev = f.get('severity', 'review').upper()
            loc = f"{f.get('file', '-')}:{f.get('line', '-')}"
            print(f"[{sev}][{cat}] {f['id']} at {loc}")
            print(f"  Evidence: {f.get('evidence', '')}")
            print(f"  Action:   {f.get('action', '')}")
            print()

    if args.strict and report['summary']['blockers'] > 0:
        return 2

    return 0


if __name__ == '__main__':
    sys.exit(main())
