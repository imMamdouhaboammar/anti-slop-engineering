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
import sys

if not __package__:
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from scripts.diff_lifecycle import load_hooks, run_hook
from scripts.git_changeset import collect_changes, repository_root
from scripts.retry_heuristics import INLINE_FLAT_RETRY, flat_retry_lines

__version__ = '1.10.0'


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
    ('SRE_SCALE_FLAT_RETRY', 'review', INLINE_FLAT_RETRY),
    ('SRE_SCALE_SLEEP_BAND_AID', 'review', r'(?i)\b(?:time\.sleep\s*\(\s*(?:0?\.[1-9]|[1-9])\d*\s*\)|thread\.sleep\s*\(\s*\d+\s*\)|setTimeout\s*\([^,]+,\s*(?:100|200|500|1000|2000|5000)\s*\))'),
    ('SRE_SCALE_UNBOUNDED_CONCURRENCY', 'review', r'(?i)(?:Promise\.all\s*\(\s*(?:\w+|\w+\.[a-zA-Z0-9_]+)\.map\s*\(|asyncio\.gather\s*\(\s*\*\s*(?:\[|\w))'),
    ('SRE_YAGNI_SPECULATIVE_CODE', 'review', r'(?i)(?:#|//|/\*)\s*(?:TODO\s*\(\s*(?:future|later|v2|next)\s*\)|placeholder for (?:future|upcoming|v2)|will be (?:supported|implemented|used) (?:later|in v2)|reserved for future use)'),
    ('SRE_YAGNI_DEAD_FLAG', 'blocker', r'(?i)(?:if\s+False\s*:|if\s*\(\s*false\s*\)|if\s*\(\s*0\s*\))\s*(?:#|//.*)?$'),
    ('DECORATIVE_COMMENT_BANNER', 'review', r'(?i)^\s*(?://|#|/\*)\s*(?:[=\-~*#]{5,}|[=\-~*#]{3,}\s*[A-Z0-9\s]{3,}\s*[=\-~*#]{3,})'),
    ('GENERIC_AI_GRADIENT_CLICHE', 'review', r'(?i)(?:bg-gradient-to-r\s+from-(?:blue|indigo|purple|violet)-500\s+(?:via-(?:purple|pink|cyan|indigo)-500\s+)?to-(?:purple|pink|cyan|violet)-500|radial-gradient\([^)]*(?:#7c3aed|#8b5cf6|#a855f7|purple|violet)[^)]*\))'),
    ('AI_MARKETING_HYPE_COPY', 'review', r'(?i)<(?:p|span|h[1-6]|div|button)[^>]*>[^<]*(?:\b(?:unleash the (?:full )?power of ai|revolutionize your (?:workflow|business|experience)|next-gen(?:eration)? ai(?:-powered)? platform|supercharge your (?:productivity|development)|all-in-one ai solution)\b)[^<]*</'),
]
COMPILED = [(rule_key, rule_lvl, re.compile(rule_str)) for rule_key, rule_lvl, rule_str in PATTERNS]
TEST_PATH = re.compile(r'(?i)(?:^|/)(?:tests?|__tests__|specs?)(?:/|$)|(?:^|/)(?:test_[^/]+\.py|[^/]+[._](?:test|spec)\.[a-z0-9]+)$')
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


def audit_file_metadata(file_counts, untracked, max_lines):
    """Audit diff metadata: test modifications, speculative docs, and line thresholds."""
    findings = []
    changed_test = []
    new_test = [p for p in untracked if TEST_PATH.search(p)]

    for path, _, _, exists in file_counts:
        if TEST_PATH.search(path):
            if exists:
                changed_test.append(path)
                findings.append({'id': 'TEST_CHANGE_REVIEW', 'severity': 'review', 'file': path,
                                 'evidence': 'Previously committed test file changed relative to base.',
                                 'action': 'Compare old/new assertions with independently approved behavior; do not auto-rebaseline.'})
            else:
                new_test.append(path)
        if SPECULATIVE_DOC_PATH.search(path):
            if not exists:
                findings.append({'id': 'SPECULATIVE_DOC_CANDIDATE', 'severity': 'review', 'file': path,
                                 'evidence': f'New speculative submission dossier or platform guide: {path}',
                                 'action': 'Verify whether this documentation file was explicitly authorized; avoid unprompted submission dossiers.'})

    added_total = sum(added for _, added, _, _ in file_counts)
    deleted_total = sum(deleted for _, _, deleted, _ in file_counts)
    if added_total > max_lines:
        findings.append({'id': 'LARGE_DIFF_REVIEW', 'severity': 'review', 'file': None,
                         'evidence': f'{added_total} added lines > configurable review prompt {max_lines}.',
                         'action': 'Justify scope or split into coherent, independently reviewable changes; not an automatic failure.'})

    return findings, changed_test, new_test, added_total, deleted_total


def audit_patch_lines(added_lines):
    """Audit added source lines against heuristic patterns."""
    findings = []
    seen = set()

    for raw_path, new_line, raw_line in added_lines:
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if GENERATED_PATH.search(path):
            continue
        code_line = raw_line.decode("utf-8", "replace").removesuffix("\r")
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
            continue

        for key, level, pattern in COMPILED:
            if key in ('SKIPPED_TEST', 'WEAK_ASSERTION') and not TEST_PATH.search(path):
                continue
            if key in ('DEV_NOTE_IN_UI', 'PATRONIZING_UI_COPY', 'GENERIC_AI_GRADIENT_CLICHE', 'AI_MARKETING_HYPE_COPY') and not UI_PATH.search(path):
                continue
            if key in ('TRIVIAL_COMMENT_NARRATION', 'DECORATIVE_COMMENT_BANNER', 'SRE_SCALE_SLEEP_BAND_AID', 'SRE_SCALE_FLAT_RETRY',
                       'SRE_YAGNI_SPECULATIVE_CODE', 'SRE_SCALE_UNBOUNDED_CONCURRENCY') and (
                TEST_PATH.search(path) or re.search(r'(?i)(?:^|/)references/', path)
            ):
                continue
            if pattern.search(code_line) and (key, path, new_line) not in seen:
                seen.add((key, path, new_line))
                findings.append({'id': key, 'severity': level, 'file': path, 'line': new_line,
                                 'evidence': code_line.strip()[:180],
                                 'action': 'Inspect context and justify or fix; regex match is not proof of a defect.'})

    return findings


def audit_multiline_retries(root, files, added_lines):
    added_by_file = {}
    for raw_path, number, _ in added_lines:
        added_by_file.setdefault(raw_path, set()).add(number)

    findings = []
    for change in files:
        path = change["new_path"]
        if path is None or path["text"] is None or change["new_mode"] not in {"100644", "100755"}:
            continue
        name = path["text"]
        changed = added_by_file.get(name.encode("utf-8"))
        if not changed or any(pattern.search(name) for pattern in (GENERATED_PATH, DOC_PATH, TEST_PATH)):
            continue
        if re.search(r'(?i)(?:^|/)references/', name):
            continue
        target = root / name
        try:
            if target.is_symlink() or not target.is_file() or not target.resolve().is_relative_to(root):
                continue
            lines = target.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for header, sleep in flat_retry_lines(lines):
            if header not in changed and sleep not in changed:
                continue
            findings.append({
                'id': 'SRE_SCALE_FLAT_RETRY',
                'severity': 'review',
                'file': name,
                'line': header if header in changed else sleep,
                'evidence': f"{lines[header - 1].strip()} -> {lines[sleep - 1].strip()}"[:180],
                'action': 'Inspect the retry loop and replace the fixed sleep with bounded backoff and jitter.',
            })
    return findings


def scan(repo, base, max_lines=400, *, hooks_dir=None):
    root = repository_root(repo)
    hooks = load_hooks(hooks_dir, root) if hooks_dir is not None else {}
    run_hook(hooks.get("pre_scan"), "pre_scan", root, base, {"review_lines": max_lines})
    added_lines = []
    evidence = collect_changes(root, base, added_lines=added_lines, detect_renames=False)
    file_counts = []
    undecodable = 0
    for change in evidence["files"]:
        path = change["new_path"] or change["old_path"]
        name = path["text"]
        if name is None:
            undecodable += 1
            name = bytes.fromhex(path["raw_hex"]).decode("utf-8", "replace")
        file_counts.append((name, change["added"] or 0, change["deleted"] or 0, change["old_path"] is not None))

    untracked = [path["text"] for path in evidence["untracked"] if path["text"] is not None]
    limitations = ['Heuristic review hints only; no semantic or runtime validation performed.']
    if evidence["untracked"]:
        limitations.append(
            f'Untracked files ({len(evidence["untracked"])}) are excluded from diff scanning; stage them for complete analysis.'
        )
    if undecodable:
        limitations.append(f"Added-line scanning omitted {undecodable} non-UTF-8 Git path(s).")

    meta_findings, changed_test, new_test, added_total, deleted_total = audit_file_metadata(
        file_counts, untracked, max_lines
    )
    patch_findings = audit_patch_lines(added_lines)
    patch_findings.extend(audit_multiline_retries(pathlib.Path(root).resolve(), evidence["files"], added_lines))
    findings = meta_findings + patch_findings

    report = {
        'base': base,
        'summary': {'changed_files': len(evidence["files"]), 'added_lines': added_total, 'deleted_lines': deleted_total,
                    'changed_test_files': len(changed_test), 'new_test_files': len(new_test),
                    'untracked_files_not_scanned': len(evidence["untracked"])},
        'findings': findings,
        'limitations': limitations,
        'status': 'review-required' if findings else 'no-heuristic-findings'
    }
    run_hook(hooks.get("post_scan"), "post_scan", root, base, {"summary": report["summary"]})
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--version', action='version', version=f'%(prog)s {__version__}')
    p.add_argument('--repo', default='.', help='Path to Git repository')
    p.add_argument('--base', default='HEAD', help='Existing commit to compare against, ideally merge-base with target branch')
    p.add_argument('--json', action='store_true', help='Machine-readable JSON output')
    p.add_argument('--review-lines', type=int, default=400, help='Added-line count prompting scope review, not failure')
    p.add_argument('--fail-on-blocker', action='store_true', help='Exit 2 for candidate test-disable patterns pending review')
    p.add_argument(
        '--hooks-dir', type=pathlib.Path, metavar='ABSOLUTE_DIR',
        help='Run trusted pre_scan.py and/or post_scan.py once from an external directory.',
    )
    a = p.parse_args()
    try:
        report = scan(pathlib.Path(a.repo).resolve(), a.base, a.review_lines, hooks_dir=a.hooks_dir)
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
