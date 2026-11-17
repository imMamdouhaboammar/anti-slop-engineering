# SPDX-License-Identifier: MIT
"""Literal and comment spans for structural source checks."""

from bisect import bisect_right
from pathlib import Path

from scripts.ast_slop_guard import JS_TS_EXTS, _mask_string_literals


def python_trivia_spans(content: str):
    """Return (start, end) spans of string literals and comments.

    Pattern text inside a literal or comment is data — the guard's own
    pattern catalog, bad-pattern fixtures, or documentation — not live
    code. Pattern matches that start inside one of these spans are
    ignored by the scanner.
    """
    spans = []
    i, n = 0, len(content)
    while i < n:
        ch = content[i]
        if ch in ("'", '"'):
            if content.startswith(ch * 3, i):
                delim = ch * 3
                j = i + 3
                while j < n:
                    if content[j] == "\\":
                        j += 2
                        continue
                    if content.startswith(delim, j):
                        break
                    j += 1
                end = j + 3 if j < n else n
            else:
                j = i + 1
                while j < n:
                    if content[j] == "\\":
                        j += 2
                        continue
                    if content[j] == ch or content[j] == "\n":
                        break
                    j += 1
                end = j + 1 if j < n and content[j] == ch else j
            spans.append((i, end))
            i = end
        elif ch == "#":
            close = content.find("\n", i)
            end = n if close == -1 else close
            spans.append((i, end))
            i = end
        else:
            i += 1
    return spans


def inside_source_trivia(pos: int, spans) -> bool:
    index = bisect_right(spans, (pos, float("inf"))) - 1
    return index >= 0 and pos < spans[index][1]


def source_trivia(path: str, content: str):
    """Return a predicate for offsets inside source literals and comments."""
    suffix = Path(path).suffix.lower()
    if suffix in JS_TS_EXTS:
        lines = content.splitlines(keepends=True)
        code_lines = _mask_string_literals(line.rstrip("\r\n") for line in lines)
        code = "".join(masked + line[len(masked):] for line, masked in zip(lines, code_lines))
        return lambda offset: code[offset] != content[offset]
    if suffix in {".py", ".pyi"}:
        spans = python_trivia_spans(content)
        return lambda offset: inside_source_trivia(offset, spans)
    return lambda offset: False
