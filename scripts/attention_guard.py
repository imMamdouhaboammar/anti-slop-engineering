#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Cognitive Bandwidth & Attention Economy Guard (Zero-Dependency Python >=3.9)
Enforces human-agent attention economy invariants:
1. Scannability & Time-to-Point (TTP)
2. Blocking-Question Placement (terminal position + line 1 flag)
3. Deliverable Purity (stripping wrapper framing, openers, and closers)
4. Working Memory Limits (Miller's Law list chunking <= 5)
5. Non-Regression Constraint Preservation (protecting exact numbers and risks)
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

_WORD = re.compile(r"\b[\w'-]+\b")
_ANCHOR_LINE = re.compile(r"^\s*(?:[-*→#>]|\d+\s*[.)→])", re.M)
_BOLD = re.compile(r"\*\*.+?\*\*", re.S)

# Opener wrapper patterns (Deliverable Impurity)
_OPENERS = re.compile(
    r"^\s*(\**)(?:here'?s|here is|sure|certainly|of course|below is|i'?ve\s+"
    r"(?:drafted|written|put together|got)|this is|the following|a quick|"
    r"absolutely|happy to|got it|no problem|okay|ok[,!]|alright)\b",
    re.IGNORECASE,
)

# Closer offer patterns (Deliverable Impurity)
_CLOSERS = re.compile(
    r"\b(?:let me know if you|want me to|happy to (?:adjust|tweak|revise|change|"
    r"shorten|expand|help)|i can (?:adjust|tweak|revise|shorten|expand)|"
    r"does this work for you|if you'?d like me to|just say the word|"
    r"hope this helps|feel free to (?:adjust|tweak|use|customize|edit))\b",
    re.IGNORECASE,
)

# Preamble line ending in colon or period immediately before a code block or quote
_LEAD_IN_TO_BLOCK = re.compile(r"[:.]\s*\n+\s*(?:>|```|\*\*|\")", re.S)

# Flag words indicating line one points to a blocking decision/ask
_FLAG_WORDS = re.compile(
    r"\b(?:before I|need|confirm|sign[- ]?off|go[- ]?ahead|one thing|"
    r"should I|want me|wait|hold off|your call)\b",
    re.IGNORECASE,
)

# Decisive verdict opener satisfying line-one intent
_VERDICT_OPENER = re.compile(
    r"^\**\s*(?:→\s*)?\**\s*"
    r"(?:no\b|don'?t\b|do not\b|stop\b|hold\b|wait\b|i can'?t\b|cannot\b|"
    r"not (?:as-is|yet|until))",
    re.IGNORECASE,
)

# Imperative blocking asks requiring reader response before an action
_IMPERATIVE_ASK = re.compile(
    r"\b(?:confirm|approve|paste|tell me|let me know|say (?:yes|no)|answer)\b"
    r"[^.?!]*\b(?:before I|and I'?ll|then I'?ll|first|if you)\b",
    re.IGNORECASE,
)

# Options list affordances following a question
_OPT_LINE = re.compile(
    r"^\s*(?:[-*]\s+|\d+[.)]\s+)?"
    r"(?:yes|no|y|n|maybe|ok|okay|cancel|abort|go|stop|proceed|skip|"
    r"hold|wait|yep|nope|y/n)\b",
    re.IGNORECASE,
)

# List item detector for working memory bounding
_LIST_ITEM_LINE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+(.+)$")


def count_words(text: str) -> int:
    return len(_WORD.findall(text))


def split_paragraphs(text: str) -> List[str]:
    """Split text into blank-line-separated blocks, stripping empties."""
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


def has_anchor(paragraph: str) -> bool:
    """Paragraph contains a scannable anchor (bold, list item, arrow, heading, quote, code)."""
    if _ANCHOR_LINE.search(paragraph) or _BOLD.search(paragraph):
        return True
    if paragraph.startswith("```") or paragraph.startswith("#") or paragraph.startswith(">"):
        return True
    return False


def calculate_scannability_metrics(text: str) -> Dict[str, Any]:
    """Compute mathematical scannability metrics (text shape vs raw vocabulary)."""
    words = count_words(text)
    paras = split_paragraphs(text)
    
    # Words to first bold anchor (headline: time-to-point)
    bold_match = _BOLD.search(text)
    if bold_match:
        ttp = count_words(text[: bold_match.start()])
    else:
        ttp = words

    # Answer first: line 1 starts with bold statement or heading
    lines = [ln.strip() for ln in text.strip().splitlines() if ln.strip()]
    first_line = lines[0] if lines else ""
    answer_first = bool(first_line.startswith("**") or first_line.startswith("#") or _VERDICT_OPENER.match(first_line))

    # Longest unbroken wall of prose without anchors
    walls = [count_words(p) for p in paras if not has_anchor(p)]
    longest_wall = max(walls, default=0)

    # Wall word fraction
    wall_word_total = sum(count_words(p) for p in paras if not has_anchor(p))
    wall_fraction = round(wall_word_total / words, 3) if words > 0 else 0.0

    # Landing anchors per 100 words
    bold_count = len(_BOLD.findall(text))
    anchor_lines = len(_ANCHOR_LINE.findall(text))
    landing_per_100w = round(100.0 * (bold_count + anchor_lines) / words, 2) if words > 0 else 0.0

    # Mean paragraph length
    mean_para_words = round(sum(count_words(p) for p in paras) / len(paras), 1) if paras else 0.0

    return {
        "word_count": words,
        "words_to_emphasis": ttp,
        "answer_first": answer_first,
        "longest_wall_words": longest_wall,
        "landing_per_100w": landing_per_100w,
        "wall_word_fraction": wall_fraction,
        "mean_para_words": mean_para_words,
    }


def check_deliverable_purity(text: str) -> Tuple[bool, List[str]]:
    """Determine if a deliverable has preamble wrappers, closer offers, or framing."""
    t = text.strip()
    if not t:
        return True, []
    
    reasons = []
    lines = [l.strip() for l in t.splitlines() if l.strip()]
    first_line = lines[0] if lines else ""

    if _OPENERS.search(first_line):
        reasons.append("opener-wrapper")

    if _CLOSERS.search(t):
        reasons.append("closer-offer")

    head = t[:250]
    if _LEAD_IN_TO_BLOCK.search(head) and _OPENERS.search(first_line):
        reasons.append("lead-in-to-block")

    return (len(reasons) == 0), reasons


def is_options_list_paragraph(para: str) -> bool:
    """Paragraph contains a concise list of options/yes-no affordances for a question."""
    if count_words(para) > 20:
        return False
    lines = [ln.strip() for ln in para.splitlines() if ln.strip()]
    if not lines:
        return False
    return all(_OPT_LINE.match(ln) is not None for ln in lines)


def paragraph_has_ask(para: str) -> bool:
    """Paragraph contains an explicit question (?) or an imperative blocking ask."""
    for ln in para.splitlines():
        trimmed = ln.rstrip(" *_`")
        if trimmed.endswith("?"):
            return True
    return bool(_IMPERATIVE_ASK.search(para))


def check_blocking_placement(text: str) -> Tuple[bool, Dict[str, Any]]:
    """Validate that blocking questions/go-aheads are terminal and flagged on line 1."""
    paras = split_paragraphs(text)
    if not paras:
        return True, {"has_ask": False, "is_terminal": True, "line_one_flagged": True}

    has_ask = any(paragraph_has_ask(p) for p in paras)
    if not has_ask:
        return True, {"has_ask": False, "is_terminal": True, "line_one_flagged": True}

    # Locate last paragraph containing an ask
    last_ask_idx = -1
    for idx, p in enumerate(paras):
        if paragraph_has_ask(p):
            last_ask_idx = idx

    is_terminal = True
    if last_ask_idx != -1:
        # Paragraphs following the ask must be options-list affordances only
        for p in paras[last_ask_idx + 1:]:
            if not is_options_list_paragraph(p):
                is_terminal = False
                break

        # If the ask ends with '?', no substantive prose may trail inside the same paragraph
        qp = paras[last_ask_idx]
        if "?" in qp:
            qpos = qp.rfind("?")
            tail = qp[qpos + 1:].strip(" *_`\n\r")
            if tail and not is_options_list_paragraph(tail):
                is_terminal = False

    # Check line one flag
    first_line = ""
    for ln in text.strip().splitlines():
        if ln.strip():
            first_line = ln.strip()
            break

    line_one_flagged = bool(
        "?" in first_line
        or _VERDICT_OPENER.match(first_line)
        or _FLAG_WORDS.search(first_line)
    )

    is_short = count_words(text) < 40
    # Short replies waive line 1 flag
    passed = is_terminal and (line_one_flagged or is_short)

    return passed, {
        "has_ask": has_ask,
        "is_terminal": is_terminal,
        "line_one_flagged": line_one_flagged,
        "short_reply": is_short,
    }


def check_working_memory_bounds(text: str) -> Tuple[int, List[Dict[str, Any]]]:
    """Flag unchunked lists exceeding Miller's Law limit (> 5 items)."""
    max_list_len = 0
    violations = []
    lines = text.splitlines()

    current_list_start = -1
    current_items: List[int] = []

    for line_idx, line in enumerate(lines, start=1):
        m = _LIST_ITEM_LINE.match(line)
        if m:
            if current_list_start == -1:
                current_list_start = line_idx
            current_items.append(line_idx)
        else:
            if current_items:
                length = len(current_items)
                if length > max_list_len:
                    max_list_len = length
                if length > 5:
                    violations.append({
                        "start_line": current_list_start,
                        "count": length,
                    })
                current_list_start = -1
                current_items = []

    if current_items:
        length = len(current_items)
        if length > max_list_len:
            max_list_len = length
        if length > 5:
            violations.append({
                "start_line": current_list_start,
                "count": length,
            })

    return max_list_len, violations


def audit_text(
    text: str,
    target_name: str = "input",
    check_deliverable: bool = False,
    check_blocking: bool = True,
    max_wall_words: int = 60,
    max_ttp: int = 25,
) -> Dict[str, Any]:
    """Run full cognitive bandwidth audit on text and produce an RFC 9457 record."""
    scannability = calculate_scannability_metrics(text)
    pure, purity_reasons = check_deliverable_purity(text)
    blocking_ok, blocking_meta = check_blocking_placement(text)
    max_list_items, list_violations = check_working_memory_bounds(text)

    findings: List[Dict[str, Any]] = []

    # 1. Check Scannability: Long unbroken walls of text
    if scannability["longest_wall_words"] > max_wall_words:
        findings.append({
            "severity": "blocker" if scannability["longest_wall_words"] > 100 else "review",
            "category": "COGNITIVE-SCANNABILITY",
            "rule": "RULE-01-MAX-WALL-WORDS",
            "message": f"Paragraph contains unbroken wall of {scannability['longest_wall_words']} words without visual anchors (limit: {max_wall_words}).",
            "evidence": f"Longest wall = {scannability['longest_wall_words']} words, wall fraction = {scannability['wall_word_fraction']}",
        })

    # 2. Check Scannability: Time-to-point delay
    if scannability["word_count"] >= 30 and scannability["words_to_emphasis"] > max_ttp and not scannability["answer_first"]:
        findings.append({
            "severity": "review",
            "category": "COGNITIVE-TIME-TO-POINT",
            "rule": "RULE-02-FRONT-LOAD-ANSWER",
            "message": f"Answer buried: {scannability['words_to_emphasis']} words before first bold anchor or verdict (limit: {max_ttp}).",
            "evidence": f"words_to_emphasis = {scannability['words_to_emphasis']}, answer_first = False",
        })

    # 3. Check Blocking-Question Placement
    if check_blocking and blocking_meta["has_ask"]:
        if not blocking_meta["is_terminal"]:
            findings.append({
                "severity": "blocker",
                "category": "COGNITIVE-BURIED-ASK",
                "rule": "RULE-03-TERMINAL-BLOCKING-QUESTION",
                "message": "Blocking question or confirmation is buried mid-reply before trailing status prose.",
                "evidence": "has_ask = True, is_terminal = False. Question must sit in the last non-empty block.",
            })
        if not blocking_meta["short_reply"] and not blocking_meta["line_one_flagged"]:
            findings.append({
                "severity": "review",
                "category": "COGNITIVE-LINE-ONE-UNFLAGGED",
                "rule": "RULE-04-LINE-ONE-FLAG-ASK",
                "message": "Reply carries a blocking question but line 1 does not flag it (skimmers will miss the ask).",
                "evidence": "line_one_flagged = False in a long reply (> 40 words).",
            })

    # 4. Check Deliverable Purity (if requested or standalone artifact)
    if check_deliverable and not pure:
        findings.append({
            "severity": "blocker",
            "category": "COGNITIVE-DELIVERABLE-IMPURITY",
            "rule": "RULE-05-DELIVERABLE-PURITY",
            "message": f"Standalone deliverable contains meta conversational wrapper framing: {', '.join(purity_reasons)}.",
            "evidence": f"purity_reasons = {purity_reasons}",
        })

    # 5. Check Working Memory List Bounding
    for v in list_violations:
        findings.append({
            "severity": "review",
            "category": "COGNITIVE-WORKING-MEMORY",
            "rule": "RULE-06-CHUNKED-LIST-BOUNDS",
            "message": f"Unchunked list of {v['count']} items exceeds working memory capacity (limit: 5 items).",
            "evidence": f"List at line {v['start_line']} with {v['count']} items.",
        })

    # Determine status & code
    status = 200
    code = "NO_ATTENTION_FINDINGS"
    detail = "All cognitive bandwidth, scannability, deliverable purity, and blocking placement gates passed clean."
    action = "NO_ACTION_REQUIRED"
    guidance = "Maintain direct payloads, scannable anchors, and terminal blocking placement."

    if any(f["category"] == "COGNITIVE-BURIED-ASK" for f in findings):
        status = 422
        code = "ERR_BURIED_BLOCKING_QUESTION"
        detail = "Blocking questions must sit in the terminal block with line 1 flagged."
        action = "MOVE_BLOCKING_ASK_TO_TERMINUS"
        guidance = "Move the decision question to the very last block; flag 'Confirm before I proceed' on line 1."
    elif any(f["category"] == "COGNITIVE-DELIVERABLE-IMPURITY" for f in findings):
        status = 422
        code = "ERR_DELIVERABLE_IMPURITY"
        detail = "Deliverable contains conversational wrapper fluff or closer offers."
        action = "STRIP_WRAPPER_FRAMING"
        guidance = "Remove 'Here is...', 'Hope this helps!', and transitional lead-ins. Deliver raw artifact only."
    elif any(f["category"] == "COGNITIVE-SCANNABILITY" for f in findings):
        status = 422
        code = "ERR_EXCESSIVE_WALL_OF_TEXT"
        detail = "Text contains unbroken prose walls that exceed human cognitive scanning thresholds."
        action = "BREAK_WALL_WITH_ANCHORS"
        guidance = "Break long paragraphs into blank-line-separated points with bold anchors or '→' bullet markers."
    elif any(f["category"] == "COGNITIVE-WORKING-MEMORY" for f in findings):
        status = 422
        code = "ERR_WORKING_MEMORY_OVERFLOW"
        detail = "Flat lists exceed Miller's Law working memory capacity."
        action = "CHUNK_UNBOUNDED_LISTS"
        guidance = "Group lists into <= 5 items per section, or provide top 3 with progressive disclosure."
    elif findings:
        status = 422
        code = "ERR_ATTENTION_BUDGET_EXCEEDED"
        detail = "Review cognitive findings before proceeding."
        action = "FRONT_LOAD_ANSWER"
        guidance = "Put bottom-line on line 1 and prune tangential narrative."

    return {
        "type": "https://anti-slop-engineering.org/errors/attention-budget",
        "title": "Cognitive Bandwidth & Attention Audit",
        "status": status,
        "code": code,
        "detail": detail,
        "instance": f"anti-slop://attention/{target_name}",
        "metrics": {
            "word_count": scannability["word_count"],
            "words_to_emphasis": scannability["words_to_emphasis"],
            "answer_first": scannability["answer_first"],
            "longest_wall_words": scannability["longest_wall_words"],
            "landing_per_100w": scannability["landing_per_100w"],
            "wall_word_fraction": scannability["wall_word_fraction"],
            "mean_para_words": scannability["mean_para_words"],
            "deliverable_pure": pure,
            "blocking_placed_correctly": blocking_ok,
            "list_max_items": max_list_items,
        },
        "findings": findings,
        "remediation": {
            "action": action,
            "guidance": guidance,
        },
    }


def audit_git_diff_markdown(base: str = "HEAD", repo_root: Optional[str] = None) -> Dict[str, Any]:
    """Audit newly added markdown files or lines in a git diff."""
    cmd = ["git", "diff", base]
    try:
        proc = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
        diff_text = proc.stdout
    except Exception:
        diff_text = ""

    # Extract added lines from markdown or doc diffs
    added_blocks: List[str] = []
    current_file = ""
    is_doc = False

    for line in diff_text.splitlines():
        if line.startswith("+++ b/"):
            current_file = line[6:]
            is_doc = current_file.endswith(".md") or current_file.endswith(".txt") or "doc" in current_file.lower()
        elif is_doc and line.startswith("+") and not line.startswith("+++"):
            added_blocks.append(line[1:])

    text_to_audit = "\n".join(added_blocks)
    if not text_to_audit.strip():
        # Fallback to auditing README.md if diff is empty
        readme_path = os.path.join(repo_root or ".", "README.md")
        if os.path.exists(readme_path):
            with open(readme_path, "r", encoding="utf-8") as f:
                text_to_audit = f.read()

    return audit_text(text_to_audit, target_name="git-diff")


def main():
    parser = argparse.ArgumentParser(description="Cognitive Bandwidth & Attention Economy Guard")
    parser.add_argument("--file", "-f", help="Path to markdown or text file to audit")
    parser.add_argument("--text", "-t", help="Raw text string to audit directly")
    parser.add_argument("--base", default="HEAD", help="Git base to check modified docs against")
    parser.add_argument("--check-deliverable", action="store_true", help="Enforce 100% deliverable purity (zero openers/closers)")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--fail-on-blocker", action="store_true", help="Exit code 2 if blocker findings exist")

    args = parser.parse_args()

    if args.text:
        record = audit_text(args.text, target_name="cli-text", check_deliverable=args.check_deliverable)
    elif args.file and os.path.exists(args.file):
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        record = audit_text(content, target_name=os.path.basename(args.file), check_deliverable=args.check_deliverable)
    else:
        record = audit_git_diff_markdown(base=args.base)

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"\n🧠  Anti-Slop Attention Economy Guard — Result: {record['code']}")
        print(f"Metrics: words={record['metrics']['word_count']} | TTP={record['metrics']['words_to_emphasis']} | max_wall={record['metrics']['longest_wall_words']} | anchors/100w={record['metrics']['landing_per_100w']} | answer_first={record['metrics']['answer_first']}")
        print(f"Deliverable Pure: {record['metrics']['deliverable_pure']} | Blocking Placed: {record['metrics']['blocking_placed_correctly']}")
        if record["findings"]:
            print(f"Findings ({len(record['findings'])}):")
            for f in record["findings"]:
                print(f"  [{f['severity'].upper()}] {f['category']} ({f['rule']}): {f['message']}")
                print(f"    Evidence: {f['evidence']}")
            print(f"\nRemediation: [{record['remediation']['action']}] {record['remediation']['guidance']}")
        else:
            print("  ✅ All cognitive bandwidth and scannability invariants passed clean.")

    if args.fail_on_blocker and any(f["severity"] == "blocker" for f in record["findings"]):
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
