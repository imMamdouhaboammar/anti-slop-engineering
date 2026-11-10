#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
PR Boundary & Git Topology Guard (Zero-Dependency Python >=3.9)
Enforces Git provenance, branch topology, PR template contracts, and logorrhea bounds.
Operates seamlessly offline on local git diff/log or online in CI.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

# Conventional Commits regex pattern for commit subjects and PR titles
CONVENTIONAL_SUBJECT_PATTERN = re.compile(r"^(\w+)(?:\([^)]+\))?!?:\s.+")

# Common code token pattern in markdown text (e.g. `foo()`, `Class::method()`, `path/to/file.ext`)
CODE_TOKEN_PATTERN = re.compile(r"`[^`]+`|(?:[\w@.-]+/)+[\w.-]+\.\w{1,10}|\b\w{3,}\(\)")

# Common markdown heading regex
HEADING_REGEX = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)

# Markdown checkbox regex
CHECKBOX_REGEX = re.compile(r"^\s*(?:>\s*)*-\s+\[([ xX])\]\s+(.+)$", re.MULTILINE)

# Standard Unicode ranges for emoji, pictographs, and dingbats (Pure stdlib, no \p escapes)
EMOJI_UNICODE_RANGES: List[Tuple[int, int]] = [
    (0x1F300, 0x1F5FF),  # Misc Symbols and Pictographs
    (0x1F600, 0x1F64F),  # Emoticons
    (0x1F680, 0x1F6FF),  # Transport and Map Symbols
    (0x1F700, 0x1F77F),  # Alchemical Symbols
    (0x1F780, 0x1F7FF),  # Geometric Shapes Extended
    (0x1F800, 0x1F8FF),  # Supplemental Arrows-C
    (0x1F900, 0x1F9FF),  # Supplemental Symbols and Pictographs
    (0x1FA00, 0x1FA6F),  # Chess Symbols
    (0x1FA70, 0x1FAFF),  # Symbols and Pictographs Extended-A
    (0x2600, 0x26FF),    # Misc Symbols
    (0x2700, 0x27BF),    # Dingbats
]

SHORTCODE_EMOJI_PATTERN = re.compile(r"(?<!\w):[a-zA-Z0-9_+-]+:(?!\w)")


def count_emojis(text: str) -> int:
    """Count Unicode emojis and markdown shortcode emojis."""
    if not text:
        return 0
    unicode_count = sum(
        1 for ch in text if any(start <= ord(ch) <= end for start, end in EMOJI_UNICODE_RANGES)
    )
    shortcodes = SHORTCODE_EMOJI_PATTERN.findall(text)
    return unicode_count + len(shortcodes)


def count_code_references(text: str) -> int:
    """Count inline code blocks and function/file references in markdown text."""
    if not text:
        return 0
    return len(CODE_TOKEN_PATTERN.findall(text))


def run_git(args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """Execute git command and return (code, stdout, stderr)."""
    try:
        proc = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except Exception as exc:
        return 1, "", str(exc)


def is_shallow_clone(repo_root: Optional[str] = None) -> bool:
    """Check if the git repository is a shallow clone."""
    code, out, _ = run_git(["rev-parse", "--is-shallow-repository"], cwd=repo_root)
    return code == 0 and out.strip().lower() == "true"


def is_detached_head(repo_root: Optional[str] = None) -> bool:
    """Check if HEAD is detached."""
    code, _, _ = run_git(["symbolic-ref", "-q", "HEAD"], cwd=repo_root)
    return code != 0


def resolve_base_ref(base: str, repo_root: Optional[str] = None) -> str:
    """Resolve base ref safely against local and remote references."""
    candidates = [base, f"origin/{base}"]
    for candidate in candidates:
        code, _, _ = run_git(["rev-parse", "--verify", candidate], cwd=repo_root)
        if code == 0:
            return candidate

    # Try merge-base with origin/main or origin/master if base is missing
    for default_branch in ["origin/main", "origin/master", "HEAD~1"]:
        code, _, _ = run_git(["rev-parse", "--verify", default_branch], cwd=repo_root)
        if code == 0:
            return default_branch

    return "HEAD"


def get_commit_list(base_ref: str, repo_root: Optional[str] = None) -> List[Dict[str, str]]:
    """Retrieve commits between base_ref and HEAD."""
    if base_ref == "HEAD":
        # Inspect top commit only
        log_range = ["-1"]
    else:
        log_range = [f"{base_ref}..HEAD"]

    code, out, _ = run_git(
        ["log"] + log_range + ["--format=%H%x1f%an%x1f%ae%x1f%s%x1f%b%x1e"], cwd=repo_root
    )
    if code != 0 or not out:
        # Fallback to inspecting current HEAD commit
        code, out, _ = run_git(
            ["log", "-1", "--format=%H%x1f%an%x1f%ae%x1f%s%x1f%b%x1e"], cwd=repo_root
        )
        if code != 0 or not out:
            return []

    commits = []
    raw_records = out.strip().split("\x1e")
    for rec in raw_records:
        rec = rec.strip()
        if not rec:
            continue
        parts = rec.split("\x1f")
        if len(parts) >= 4:
            commits.append({
                "sha": parts[0],
                "author_name": parts[1],
                "author_email": parts[2],
                "subject": parts[3],
                "body": parts[4] if len(parts) > 4 else "",
            })
    return commits


def parse_markdown_sections(text: str) -> List[Dict[str, Any]]:
    """Parse top-level and nested markdown headings and their checkbox states."""
    sections: List[Dict[str, Any]] = []
    matches = list(HEADING_REGEX.finditer(text))
    if not matches:
        return sections

    for i, m in enumerate(matches):
        heading_line = m.group(0).strip()
        heading_text = m.group(2).strip()
        start_pos = m.end()
        end_pos = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        content = text[start_pos:end_pos].strip()

        checkboxes = []
        for cb_match in CHECKBOX_REGEX.finditer(content):
            checked = cb_match.group(1).lower() == "x"
            label = cb_match.group(2).strip()
            checkboxes.append({"label": label, "checked": checked})

        sections.append({
            "heading": heading_line,
            "title": heading_text,
            "content": content,
            "checkboxes": checkboxes,
        })
    return sections


def audit_pr_boundary(
    base: str = "HEAD",
    repo_root: Optional[str] = None,
    pr_title: Optional[str] = None,
    pr_body: Optional[str] = None,
    template_content: Optional[str] = None,
    max_subject_length: int = 100,
    max_desc_length: int = 2500,
    max_emojis: int = 3,
    max_code_refs: int = 15,
    require_conventional: bool = False,
    blocked_source_branches: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Execute PR boundary and Git topology audit."""
    if blocked_source_branches is None:
        blocked_source_branches = ["main", "master"]

    findings: List[Dict[str, Any]] = []
    shallow = is_shallow_clone(repo_root)
    detached = is_detached_head(repo_root)
    resolved_base = resolve_base_ref(base, repo_root)

    # Resolve Head Reference
    head_branch = "HEAD"
    if not detached:
        _, out, _ = run_git(["branch", "--show-current"], cwd=repo_root)
        head_branch = out.strip() or "HEAD"
    else:
        # Check CI env variables
        head_branch = os.environ.get("GITHUB_HEAD_REF") or os.environ.get("GITHUB_REF_NAME") or "HEAD"

    # 1. Branch Topology Checks
    if head_branch in blocked_source_branches:
        findings.append({
            "rule": "BLOCKED_SOURCE_BRANCH",
            "severity": "review",
            "message": f"PR originates directly from default branch '{head_branch}'. Feature branches are required.",
            "evidence": f"branch={head_branch}",
        })

    # 2. Git Commit History Checks
    commits = get_commit_list(resolved_base, repo_root)
    unique_authors: Set[str] = set()

    for commit in commits:
        author_key = f"{commit['author_name']} <{commit['author_email']}>"
        unique_authors.add(author_key)
        subject = commit["subject"]

        if subject.startswith("Merge "):
            continue

        if len(subject) > max_subject_length:
            findings.append({
                "rule": "COMMIT_SUBJECT_LENGTH",
                "severity": "review",
                "message": f"Commit subject exceeds {max_subject_length} characters ({len(subject)} chars).",
                "evidence": f"sha={commit['sha'][:8]} subject={subject[:60]}...",
            })

        if require_conventional and not CONVENTIONAL_SUBJECT_PATTERN.match(subject):
            findings.append({
                "rule": "COMMIT_CONVENTIONAL_FORMAT",
                "severity": "review",
                "message": f"Commit subject does not follow Conventional Commits format.",
                "evidence": f"sha={commit['sha'][:8]} subject={subject}",
            })

    if len(unique_authors) > 1 and len(commits) > 1:
        findings.append({
            "rule": "COMMIT_AUTHOR_COHERENCE",
            "severity": "review",
            "message": f"Multiple commit authors found in branch diff ({len(unique_authors)} distinct authors).",
            "evidence": ", ".join(list(unique_authors)[:3]),
        })

    # 3. Path Fencing & Metadata Spam Checks
    code, changed_files_out, _ = run_git(["diff", "--name-only", resolved_base, "HEAD"], cwd=repo_root)
    if code == 0 and changed_files_out:
        changed_files = [f.strip() for f in changed_files_out.splitlines() if f.strip()]
        metadata_paths = {"README.md", "LICENSE", "SECURITY.md", "CODE_OF_CONDUCT.md"}
        if all(os.path.basename(f) in metadata_paths for f in changed_files):
            # Check diff size
            code, diff_numstat, _ = run_git(["diff", "--numstat", resolved_base, "HEAD"], cwd=repo_root)
            total_added = sum(
                int(line.split()[0])
                for line in diff_numstat.splitlines()
                if line.split() and line.split()[0].isdigit()
            )
            if total_added <= 3:
                findings.append({
                    "rule": "METADATA_ONLY_MICRO_EDIT",
                    "severity": "review",
                    "message": "PR contains only micro-edits (<=3 lines) to metadata documentation files. Verify contributor authenticity.",
                    "evidence": f"files={changed_files} added_lines={total_added}",
                })

    # 4. PR Metadata & Description Checks (if supplied)
    emoji_count = 0
    code_refs = 0
    desc_len = 0
    radio_checked = 0

    if pr_title and require_conventional and not CONVENTIONAL_SUBJECT_PATTERN.match(pr_title):
        findings.append({
            "rule": "PR_TITLE_CONVENTIONAL",
            "severity": "review",
            "message": "PR title does not follow Conventional Commits format (e.g. feat:, fix:).",
            "evidence": f"title={pr_title}",
        })

    if pr_body is not None:
        desc_len = len(pr_body.strip())
        emoji_count = count_emojis(pr_body) + (count_emojis(pr_title) if pr_title else 0)
        code_refs = count_code_references(pr_body)

        if desc_len == 0:
            findings.append({
                "rule": "PR_DESCRIPTION_EMPTY",
                "severity": "review",
                "message": "PR description is empty. Meaningful rationale is required.",
                "evidence": "length=0",
            })
        elif desc_len > max_desc_length:
            findings.append({
                "rule": "PR_DESCRIPTION_BLOAT",
                "severity": "review",
                "message": f"PR description exceeds maximum length ({desc_len} > {max_desc_length} chars). Potential AI logorrhea.",
                "evidence": f"length={desc_len}",
            })

        if emoji_count > max_emojis:
            findings.append({
                "rule": "EXCESSIVE_EMOJIS",
                "severity": "review",
                "message": f"PR contains excessive emojis ({emoji_count} > {max_emojis}).",
                "evidence": f"count={emoji_count}",
            })

        if code_refs > max_code_refs:
            findings.append({
                "rule": "EXCESSIVE_CODE_REFERENCES",
                "severity": "review",
                "message": f"PR description contains excessive inline code tokens ({code_refs} > {max_code_refs}). Potential LLM filler.",
                "evidence": f"references={code_refs}",
            })

        # Radio-Button Template Structure Checks
        if template_content:
            tpl_sections = parse_markdown_sections(template_content)
            body_sections = parse_markdown_sections(pr_body)
            body_headings = {s["title"].lower(): s for s in body_sections}

            # Check radio-button groups: if template section has >1 checkboxes, exactly 1 should be checked
            for tpl_sec in tpl_sections:
                if len(tpl_sec["checkboxes"]) > 1:
                    matching_sec = body_headings.get(tpl_sec["title"].lower())
                    if matching_sec:
                        checked_in_sec = sum(1 for cb in matching_sec["checkboxes"] if cb["checked"])
                        radio_checked += checked_in_sec
                        if checked_in_sec > 1:
                            findings.append({
                                "rule": "RADIO_BUTTON_TEMPLATE_VIOLATION",
                                "severity": "review",
                                "message": f"Section '{tpl_sec['title']}' is mutually exclusive but has {checked_in_sec} options checked.",
                                "evidence": f"section={tpl_sec['title']} checked={checked_in_sec}",
                            })

            # Check for hallucinated extra sections
            tpl_titles = {s["title"].lower() for s in tpl_sections}
            extra_sections = [s["title"] for s in body_sections if s["title"].lower() not in tpl_titles]
            if len(extra_sections) > 2:
                findings.append({
                    "rule": "HALLUCINATED_EXTRA_SECTIONS",
                    "severity": "review",
                    "message": f"PR description introduces {len(extra_sections)} unprompted sections not present in repo template.",
                    "evidence": f"extra={extra_sections[:3]}",
                })

    has_blockers = any(f["severity"] == "blocker" for f in findings)
    status_code = 400 if has_blockers else (200 if not findings else 200)
    problem_code = (
        "ERR_PR_TOPOLOGY_INVALID" if has_blockers
        else ("ERR_METADATA_BLOAT_DETECTED" if findings else "NO_PR_BOUNDARY_FINDINGS")
    )

    return {
      "type": "https://anti-slop.org/problem/pr-boundary",
      "title": "PR Boundary & Git Topology Evaluation",
      "status": status_code,
      "code": problem_code,
      "detail": (
          f"Found {len(findings)} boundary findings across git topology and metadata."
          if findings else "PR boundary and Git topology conform to clean-room standards."
      ),
      "git_topology": {
          "base_ref": resolved_base,
          "head_ref": head_branch,
          "commit_count": len(commits),
          "is_shallow": shallow,
          "is_detached_head": detached,
      },
      "pr_metadata": {
          "title": pr_title or "",
          "description_length": desc_len,
          "emoji_count": emoji_count,
          "code_references": code_refs,
          "radio_sections_checked": radio_checked,
      },
      "findings": findings,
      "remediation": {
          "action": "PR_BOUNDARY_REMEDIATION",
          "guidance": (
              "Address commit subject length, branch topology, or template checkbox contracts."
              if findings else "No action required."
          ),
      },
    }


def main():
    parser = argparse.ArgumentParser(description="PR Boundary & Git Topology Guard")
    parser.add_argument("--base", default="HEAD", help="Base commit or branch to compare against")
    parser.add_argument("--repo", default=None, help="Path to Git repository")
    parser.add_argument("--pr-title", default=None, help="PR title text")
    parser.add_argument("--pr-body-file", default=None, help="Path to file containing PR body markdown")
    parser.add_argument("--template-file", default=None, help="Path to repo PR template markdown file")
    parser.add_argument("--require-conventional", action="store_true", help="Require conventional commits")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--fail-on-blocker", action="store_true", help="Exit code 2 if blocker findings exist")

    args = parser.parse_args()

    pr_body = None
    if args.pr_body_file and os.path.exists(args.pr_body_file):
        with open(args.pr_body_file, "r", encoding="utf-8") as f:
            pr_body = f.read()

    template_content = None
    if args.template_file and os.path.exists(args.template_file):
        with open(args.template_file, "r", encoding="utf-8") as f:
            template_content = f.read()

    record = audit_pr_boundary(
        base=args.base,
        repo_root=args.repo,
        pr_title=args.pr_title,
        pr_body=pr_body,
        template_content=template_content,
        require_conventional=args.require_conventional,
    )

    if args.json:
        print(json.dumps(record, indent=2))
    else:
        print(f"\n🛡️  Anti-Slop PR Boundary Guard — Result: {record['code']}")
        print(f"Topology: base={record['git_topology']['base_ref']} head={record['git_topology']['head_ref']} commits={record['git_topology']['commit_count']}")
        if record["findings"]:
            print(f"Findings ({len(record['findings'])}):")
            for f in record["findings"]:
                print(f"  [{f['severity'].upper()}] {f['rule']}: {f['message']}")
                print(f"    Evidence: {f['evidence']}")
        else:
            print("  ✅ All PR boundary and Git topology checks passed clean.")

    if args.fail_on_blocker and any(f["severity"] == "blocker" for f in record["findings"]):
        sys.exit(2)
    sys.exit(0)


if __name__ == "__main__":
    main()
