# SPDX-License-Identifier: MIT
"""Literal and comment spans for structural source checks."""

from bisect import bisect_right
from io import StringIO
from itertools import accumulate
from pathlib import Path
import tokenize

from scripts.ast_slop_guard import JS_TS_EXTS, _mask_string_literals


def python_trivia_spans(content: str):
    offsets = list(accumulate((len(line) + 1 for line in content.split("\n")), initial=0))
    spans = []
    try:
        for token in tokenize.generate_tokens(StringIO(content).readline):
            if token.type == tokenize.STRING:
                # Python 3.9–3.11 emit one token for a complete f-string.
                body = token.string.lstrip("rRbBuUfFtT")
                prefix = token.string[:len(token.string) - len(body)].lower()
                if "f" in prefix or "t" in prefix:
                    continue
            elif token.type != tokenize.COMMENT and tokenize.tok_name[token.type] not in {
                "FSTRING_MIDDLE", "TSTRING_MIDDLE",
            }:
                continue
            start_line, start_col = token.start
            end_line, end_col = token.end
            spans.append((offsets[start_line - 1] + start_col, offsets[end_line - 1] + end_col))
    except (tokenize.TokenError, IndentationError):
        return spans
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
