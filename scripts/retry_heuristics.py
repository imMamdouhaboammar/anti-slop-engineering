# SPDX-License-Identifier: MIT
"""Identify bounded patterns used by the heuristic retry guards."""
import re

RETRY_HEADER = (
    r'(?:while\s+True\s*:|while\s*\(\s*true\s*\)'
    r'|while\s+\w+\s*<\s*\d+\s*:'
    r'|for\s+(?:attempt|retry|i)\s+in\s+range\s*\(\s*\d+\s*\):)'
)
FIXED_SLEEP = r'\bsleep\s*\(\s*[1-9]\d*\s*\)'
INLINE_FLAT_RETRY = rf'(?i){RETRY_HEADER}.*{FIXED_SLEEP}'
HEADER = re.compile(rf'^\s*{RETRY_HEADER}', re.IGNORECASE)
SLEEP = re.compile(FIXED_SLEEP, re.IGNORECASE)


def flat_retry_lines(lines):
    """Yield the header and fixed-sleep lines for a multiline retry."""
    for number, line in enumerate(lines, 1):
        if not HEADER.search(line):
            continue
        indent = len(line) - len(line.lstrip())
        for sleep_line, body in enumerate(lines[number:number + 10], number + 1):
            statement = body.lstrip()
            if not statement or statement.startswith(('#', '//', '/*', '*')):
                continue
            if len(body) - len(statement) <= indent:
                break
            if SLEEP.search(statement):
                yield number, sleep_line
                break
