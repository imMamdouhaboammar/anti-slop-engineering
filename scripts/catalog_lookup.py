#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Lazy Searchable Anti-Pattern Catalog Lookup & Indexing Engine.

Indexes references/anti-pattern-catalog.md on demand without prompt context inflation.
Provides exact ID retrieval, keyword relevance search, and actionable skill mapping.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
CATALOG_PATH = ROOT_DIR / "references" / "anti-pattern-catalog.md"

CATALOG_LINE_RE = re.compile(
    r"^\- \*\*([A-Z]+-[0-9]+)\s*\|\s*([^\*]+?)\*\*\.?\s*(.*)$",
    re.MULTILINE,
)

CATEGORY_NAMES: Dict[str, str] = {
    "REQ": "Requirements, scope, and product correctness",
    "ARC": "Architecture, boundaries, and repository consistency",
    "SIM": "Simplicity, duplication, and code readability",
    "DAT": "Database design, migrations, and data reliability",
    "SEC": "Security, privacy, and trust boundaries",
    "OPS": "Error handling, observability, and operations",
    "CON": "Concurrency, asynchronous work, and resource lifecycle",
    "API": "API contracts, types, and interoperability",
    "TST": "Tests, regression safety, and fake confidence",
    "UI": "Frontend, UX, accessibility, and browser performance",
    "CI": "Dependencies, builds, CI/CD, and supply chain",
    "REV": "Repository hygiene, review, and engineering process",
    "AGT": "Agent-specific workflow and autonomy failures",
    "SRE": "Google SRE Invariants (KISS, DRY, YAGNI, Scale & Toil)",
}

CATEGORY_DEFAULT_SKILLS: Dict[str, str] = {
    "REQ": "anti-slop-engineering",
    "ARC": "anti-slop-engineering",
    "SIM": "anti-slop-engineering",
    "DAT": "privacy-and-data-lineage-gate",
    "SEC": "paranoid-principal-architect",
    "OPS": "observability-and-slo-architect",
    "CON": "deterministic-simulation-and-property-testing",
    "API": "api-ergonomics-and-contract-governor",
    "TST": "mandela-guard",
    "UI": "ui-and-copy-discipline",
    "CI": "pr-boundary-guard",
    "REV": "tagore-guard",
    "AGT": "cognitive-load-and-attention-governor",
    "SRE": "anti-slop-engineering",
}

PATTERN_SKILL_OVERRIDES: Dict[str, str] = {
    "ARC-16": "decision-guard",
    "ARC-17": "root-fix-gate",
    "ARC-18": "future-scale-gate",
    "SIM-08": "anti-slop-engineering",
    "TST-01": "demock-guard",
    "TST-02": "deterministic-simulation-and-property-testing",
    "UI-01": "styleseed-guard",
    "UI-02": "styleseed-guard",
    "UI-03": "styleseed-guard",
    "UI-04": "ui-and-copy-discipline",
    "REV-01": "tagore-guard",
    "REV-02": "tagore-guard",
    "REV-03": "tagore-guard",
    "REV-04": "tagore-guard",
    "REV-05": "tagore-guard",
    "REV-06": "pr-boundary-guard",
    "REV-07": "pr-boundary-guard",
    "REV-08": "pr-boundary-guard",
    "REV-09": "pr-boundary-guard",
    "REV-10": "pr-boundary-guard",
    "AGT-01": "cognitive-load-and-attention-governor",
    "AGT-02": "re0-handoff-guard",
    "AGT-03": "house-tell-guard",
    "AGT-04": "backprop-guard",
}

_CACHED_INDEX: Optional[Dict[str, Dict[str, Any]]] = None


def get_catalog_index() -> Dict[str, Dict[str, Any]]:
    """Lazily load and index all 217 anti-patterns from markdown catalog."""
    global _CACHED_INDEX
    if _CACHED_INDEX is not None:
        return _CACHED_INDEX

    index: Dict[str, Dict[str, Any]] = {}
    if not CATALOG_PATH.is_file():
        return index

    text = CATALOG_PATH.read_text(encoding="utf-8")
    for match in CATALOG_LINE_RE.finditer(text):
        pat_id, raw_title, raw_desc = match.groups()
        cat_code = pat_id.split("-")[0]
        cat_name = CATEGORY_NAMES.get(cat_code, "General Engineering")
        title = raw_title.strip().rstrip(".")
        desc = raw_desc.strip()

        assigned_skill = PATTERN_SKILL_OVERRIDES.get(pat_id) or CATEGORY_DEFAULT_SKILLS.get(
            cat_code, "anti-slop-engineering"
        )
        skill_path = f"skills/{assigned_skill}/SKILL.md"

        index[pat_id] = {
            "id": pat_id,
            "title": title,
            "description": desc,
            "category_code": cat_code,
            "category_name": cat_name,
            "skill": assigned_skill,
            "skill_path": skill_path,
        }

    _CACHED_INDEX = index
    return index


def lookup_catalog_entry(pattern_id: str) -> Dict[str, Any]:
    """Look up a specific catalog anti-pattern by ID."""
    clean_id = pattern_id.strip().upper()
    index = get_catalog_index()

    if clean_id in index:
        entry = dict(index[clean_id])
        entry["found"] = True
        return entry

    return {
        "found": False,
        "id": clean_id,
        "message": f"Catalog pattern '{clean_id}' not found in anti-pattern-catalog.md.",
        "available_categories": list(CATEGORY_NAMES.keys()),
    }


def search_catalog(query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search catalog entries matching keyword or phrase across ID, title, and description."""
    q = query.strip().lower()
    index = get_catalog_index()
    scored_matches: List[tuple[int, Dict[str, Any]]] = []

    for pat_id, entry in index.items():
        score = 0
        if pat_id.lower() == q:
            score += 100
        elif pat_id.lower().startswith(q):
            score += 50
        elif q in pat_id.lower():
            score += 30

        if q in entry["title"].lower():
            score += 40

        if q in entry["description"].lower():
            score += 20

        if q in entry["category_name"].lower():
            score += 10

        if score > 0:
            scored_matches.append((score, entry))

    scored_matches.sort(key=lambda x: x[0], reverse=True)
    return [match[1] for match in scored_matches[:limit]]


def format_catalog_entry(entry: Dict[str, Any]) -> str:
    """Format catalog entry adhering strictly to Direct Payload Invariant with zero fluff."""
    if not entry.get("found", True):
        return f"Error: {entry.get('message', 'Not found')}"

    return (
        f"Pattern:     {entry['id']} | {entry['title']}\n"
        f"Category:    {entry['category_name']} ({entry['category_code']})\n"
        f"Skill:       {entry['skill']} ({entry['skill_path']})\n"
        f"Remedy:      {entry['description']}"
    )


def format_search_results(results: List[Dict[str, Any]], query: str) -> str:
    """Format search match list compactly."""
    if not results:
        return f"No catalog patterns matched query: '{query}'"

    lines = [f"Found {len(results)} catalog patterns matching '{query}':"]
    for r in results:
        lines.append(f"  • {r['id']:8} | {r['title']:35} [{r['skill']}]")
    return "\n".join(lines)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Query and search anti-pattern catalog")
    parser.add_argument("id", nargs="?", default="", help="Exact pattern ID (e.g. SIM-08, REQ-01)")
    parser.add_argument("--search", default="", help="Keyword search across catalog")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--limit", type=int, default=5, help="Maximum search results")

    args = parser.parse_args(argv if argv is not None else sys.argv[1:])

    if args.search:
        results = search_catalog(args.search, limit=args.limit)
        if args.json:
            print(json.dumps({"query": args.search, "count": len(results), "results": results}, indent=2))
        else:
            print(format_search_results(results, args.search))
        return 0

    if args.id:
        entry = lookup_catalog_entry(args.id)
        if args.json:
            print(json.dumps(entry, indent=2))
        else:
            print(format_catalog_entry(entry))
        return 0 if entry.get("found", False) else 1

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
