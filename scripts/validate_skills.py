#!/usr/bin/env python3
"""Validate bundled Agent Skills frontmatter, clean-checkout links, and CLI contracts."""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

ALLOWED_PATH_PREFIXES = (
    ".agents/skills/",
    "skills/",
    "scripts/",
    "references/",
    "schemas/",
    "services/",
)


def is_valid_skill_name(name: str) -> bool:
    """Validate Agent Skills directory/frontmatter identifier format."""
    if not name or name.startswith("-") or name.endswith("-") or "--" in name:
        return False
    return all((ch.isascii() and (ch.islower() or ch.isdigit())) or ch == "-" for ch in name)


def parse_frontmatter(text: str) -> Optional[Dict[str, str]]:
    """Extract simple YAML key/value fields from leading SKILL.md frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end_idx = None
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            end_idx = idx
            break
    if end_idx is None:
        return None

    fields: Dict[str, str] = {}
    current_key: Optional[str] = None
    multiline_parts: List[str] = []
    for raw_line in lines[1:end_idx]:
        if not raw_line.strip():
            continue
        if current_key and raw_line[:1].isspace():
            multiline_parts.append(raw_line.strip())
            continue
        if current_key and multiline_parts:
            fields[current_key] = " ".join(multiline_parts).strip()
            multiline_parts = []
        current_key = None
        if ":" not in raw_line or raw_line[:1].isspace():
            continue
        key, raw_val = raw_line.split(":", 1)
        key = key.strip()
        value = raw_val.strip()
        if not key:
            continue
        if value in {"|", "|-", ">", ">-"}:
            current_key = key
            multiline_parts = []
            fields[key] = ""
        else:
            fields[key] = value.strip("\"'")
    if current_key and multiline_parts:
        fields[current_key] = " ".join(multiline_parts).strip()
    return fields


def _extract_quoted_after(text: str, marker: str) -> Set[str]:
    """Extract simple CLI token strings immediately following a literal marker."""
    found: Set[str] = set()
    start = 0
    while True:
        idx = text.find(marker, start)
        if idx == -1:
            break
        end = text.find('"', idx + len(marker))
        if end == -1:
            break
        token = text[idx + len(marker) : end]
        if token and all(ch.isalnum() or ch == "-" for ch in token):
            found.add(token)
        start = end + 1
    return found


def extract_cli_commands(cli_js_path: Path) -> Set[str]:
    """Return subcommand names handled by bin/cli.js."""
    if not cli_js_path.is_file():
        return set()
    content = cli_js_path.read_text(encoding="utf-8")
    commands: Set[str] = set()
    for marker in ('cmd === "', 'subcmd === "', 'case "'):
        commands.update(_extract_quoted_after(content, marker))
    return commands


def _iter_markdown_links(text: str) -> List[str]:
    """Extract targets from inline markdown links [label](target)."""
    targets: List[str] = []
    idx = 0
    n = len(text)
    while idx < n:
        open_bracket = text.find("[", idx)
        if open_bracket == -1:
            break
        close_bracket = text.find("]", open_bracket + 1)
        if close_bracket == -1:
            break
        if close_bracket + 1 < n and text[close_bracket + 1] == "(":
            close_paren = text.find(")", close_bracket + 2)
            if close_paren != -1 and "\n" not in text[close_bracket + 2 : close_paren]:
                targets.append(text[close_bracket + 2 : close_paren].strip())
                idx = close_paren + 1
                continue
        idx = open_bracket + 1
    return targets


def _iter_backtick_tokens(text: str) -> List[str]:
    """Extract inline single-backtick spans without newlines."""
    tokens: List[str] = []
    idx = 0
    n = len(text)
    while idx < n:
        open_tick = text.find("`", idx)
        if open_tick == -1:
            break
        if open_tick + 2 < n and text[open_tick : open_tick + 3] == "```":
            close_fence = text.find("```", open_tick + 3)
            idx = n if close_fence == -1 else close_fence + 3
            continue
        close_tick = text.find("`", open_tick + 1)
        if close_tick == -1:
            break
        span = text[open_tick + 1 : close_tick]
        if "\n" not in span and span.strip():
            tokens.append(span.strip())
        idx = close_tick + 1
    return tokens


def _is_external_or_anchor(target: str) -> bool:
    return target.startswith(("http://", "https://", "#", "mailto:"))


def _resolve_repo_target(repo_root: Path, base_dir: Path, raw_target: str) -> bool:
    clean_target = raw_target.split("#", 1)[0].strip()
    if not clean_target or "<" in clean_target or "*" in clean_target:
        return True
    repo_resolved = repo_root.resolve()
    for candidate_base in (base_dir, repo_root):
        candidate = (candidate_base / clean_target).resolve()
        try:
            candidate.relative_to(repo_resolved)
        except ValueError:
            continue
        if candidate.exists():
            return True
    return False


def _validate_markdown_pointers(
    repo_root: Path,
    doc_path: Path,
    text: str,
    check_backtick_paths: bool,
) -> List[str]:
    errors: List[str] = []
    rel_doc = doc_path.relative_to(repo_root).as_posix()
    for target in _iter_markdown_links(text):
        if _is_external_or_anchor(target):
            continue
        if not _resolve_repo_target(repo_root, doc_path.parent, target):
            errors.append(f"{rel_doc}: broken markdown link '{target}'")
    if check_backtick_paths:
        for token in _iter_backtick_tokens(text):
            if " " in token or not token.startswith(ALLOWED_PATH_PREFIXES):
                continue
            if not _resolve_repo_target(repo_root, doc_path.parent, token):
                errors.append(f"{rel_doc}: broken repo path '{token}'")
    return errors


def _extract_advertised_tokens(text: str) -> Tuple[List[str], List[str]]:
    """Return (python_scripts, cli_subcommands) referenced in markdown text."""
    scripts: List[str] = []
    cli_cmds: List[str] = []
    words = text.replace("`", " ").split()
    for idx, word in enumerate(words):
        if word in {"python", "python3"} and idx + 1 < len(words):
            nxt = words[idx + 1].rstrip(".,;:)")
            if nxt.startswith("scripts/") and nxt.endswith(".py"):
                scripts.append(nxt)
        if word in {"npx", "bunx"} and idx + 2 < len(words) and words[idx + 1] == "anti-slop-engineering":
            sub = words[idx + 2].rstrip(".,;:)")
            if sub and not sub.startswith("-"):
                cli_cmds.append(sub)
    return scripts, cli_cmds


def _validate_advertised_commands(
    repo_root: Path,
    doc_path: Path,
    text: str,
    cli_commands: Set[str],
) -> Tuple[List[str], List[Dict[str, str]]]:
    errors: List[str] = []
    missing_cli: List[Dict[str, str]] = []
    rel_doc = doc_path.relative_to(repo_root).as_posix()
    scripts, advertised_cmds = _extract_advertised_tokens(text)

    for script_rel in dict.fromkeys(scripts):
        if not (repo_root / script_rel).is_file():
            errors.append(f"{rel_doc}: missing referenced script '{script_rel}'")

    for cmd in dict.fromkeys(advertised_cmds):
        if cmd not in cli_commands:
            missing_cli.append({"file": rel_doc, "command": f"anti-slop-engineering {cmd}"})
    return errors, missing_cli


def validate_skill_dir(
    repo_root: Path,
    skill_dir: Path,
    cli_commands: Set[str],
) -> Tuple[List[str], List[Dict[str, str]]]:
    """Validate a single skill directory without requiring optional subdirectories."""
    errors: List[str] = []
    missing_cli: List[Dict[str, str]] = []
    skill_md = skill_dir / "SKILL.md"
    rel_dir = skill_dir.relative_to(repo_root).as_posix()
    if not skill_md.is_file():
        return [f"{rel_dir}: missing required SKILL.md"], missing_cli

    text = skill_md.read_text(encoding="utf-8")
    fields = parse_frontmatter(text)
    if fields is None:
        errors.append(f"{rel_dir}/SKILL.md: missing YAML frontmatter")
    else:
        name = fields.get("name", "")
        description = fields.get("description", "")
        if not is_valid_skill_name(name):
            errors.append(f"{rel_dir}/SKILL.md: invalid or missing frontmatter 'name'")
        elif name != skill_dir.name:
            errors.append(
                f"{rel_dir}/SKILL.md: frontmatter name '{name}' does not match directory '{skill_dir.name}'"
            )
        if not description:
            errors.append(f"{rel_dir}/SKILL.md: missing frontmatter 'description'")

    errors.extend(_validate_markdown_pointers(repo_root, skill_md, text, check_backtick_paths=False))
    cmd_errors, cmd_missing = _validate_advertised_commands(repo_root, skill_md, text, cli_commands)
    errors.extend(cmd_errors)
    missing_cli.extend(cmd_missing)
    return errors, missing_cli


def validate_repository(repo_root: Path, strict_cli: bool = False) -> Dict[str, object]:
    """Validate AGENTS.md pointers, all skills/*/SKILL.md files, and CLI contracts."""
    repo_root = repo_root.resolve()
    skills_root = repo_root / "skills"
    cli_commands = extract_cli_commands(repo_root / "bin" / "cli.js")
    errors: List[str] = []
    missing_cli: List[Dict[str, str]] = []

    agents_md = repo_root / "AGENTS.md"
    if not agents_md.is_file():
        errors.append("AGENTS.md: missing repository instruction file")
    else:
        agents_text = agents_md.read_text(encoding="utf-8")
        errors.extend(
            _validate_markdown_pointers(repo_root, agents_md, agents_text, check_backtick_paths=True)
        )
        cmd_errors, cmd_missing = _validate_advertised_commands(
            repo_root, agents_md, agents_text, cli_commands
        )
        errors.extend(cmd_errors)
        missing_cli.extend(cmd_missing)

    skills_checked = 0
    if not skills_root.is_dir():
        errors.append("skills/: missing skills directory")
    else:
        for entry in sorted(skills_root.iterdir()):
            if not entry.is_dir():
                continue
            skills_checked += 1
            dir_errors, dir_missing = validate_skill_dir(repo_root, entry, cli_commands)
            errors.extend(dir_errors)
            missing_cli.extend(dir_missing)

    if strict_cli:
        for item in missing_cli:
            errors.append(f"{item['file']}: unrouted CLI command '{item['command']}'")

    return {
        "ok": len(errors) == 0,
        "skills_checked": skills_checked,
        "errors": errors,
        "missing_cli_handlers": missing_cli,
    }


def main(argv: Optional[List[str]] = None) -> int:
    """CLI entrypoint for bundled skill and instruction pointer validation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--strict-cli",
        action="store_true",
        help="Treat advertised anti-slop-engineering subcommands missing from bin/cli.js as errors",
    )
    args = parser.parse_args(argv)
    report = validate_repository(args.repo, strict_cli=args.strict_cli)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Skills checked: {report['skills_checked']}")
        for err in report["errors"]:
            print(f"ERROR: {err}", file=sys.stderr)
        for item in report["missing_cli_handlers"]:
            print(f"WARN (unrouted CLI): {item['file']} -> {item['command']}")
        status = "PASSED" if report["ok"] else "FAILED"
        print(
            f"Skill validation {status}: {len(report['errors'])} error(s), "
            f"{len(report['missing_cli_handlers'])} unrouted CLI command(s)."
        )
    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
