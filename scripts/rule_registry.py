#!/usr/bin/env python3
# SPDX-License-Identifier: MIT

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CATALOG_PATH = ROOT / "references" / "anti-pattern-catalog.md"
EVIDENCE_RUBRIC = "references/engineering-judgment.md"
REGISTRY_VERSION = 1
OUTCOMES = ("tp", "fp", "tn", "fn")
SEVERITY_GUIDANCE = {
    "OPS-01": "Escalate when evidence shows the swallowed error hides a required operation or trust-boundary failure.",
    "SRE-01": "Treat nesting as review evidence. Escalate only for a demonstrated impact beyond readability.",
}


@dataclass(frozen=True)
class Rule:
    engine: str
    engine_code: str
    catalog_id: str
    skill: str = "anti-slop-engineering"

    @property
    def evidence_key(self):
        return f"{self.engine}:{self.engine_code}"


RULES = (
    Rule("diff_guard", "ERROR_SWALLOW_CANDIDATE", "OPS-01"),
    Rule("sre_guard", "SCALE_TOIL_ERROR_SWALLOW", "OPS-01"),
    Rule("rust", "STS-H02", "OPS-01"),
    Rule("go", "SRE-SCALE-SWALLOW", "OPS-01"),
    Rule("sre_guard", "KISS_DEEP_NESTING", "SRE-01"),
    Rule("go", "SRE-KISS-NESTING", "SRE-01"),
)
BY_CODE = {rule.engine_code: rule for rule in RULES}


def iter_catalog(path=CATALOG_PATH):
    seen = set()
    with path.open(encoding="utf-8") as stream:
        for number, line in enumerate(stream, start=1):
            if not line.startswith("- **"):
                continue
            label, _, remediation = line[4:].partition("**")
            catalog_id, separator, title = label.partition(" | ")
            prefix, _, number_text = catalog_id.partition("-")
            if not (prefix.isascii() and prefix.isalpha() and prefix.isupper()
                    and number_text[:1].isdigit()):
                continue
            if not (separator and number_text.isascii() and number_text.isdecimal()
                    and title.strip() and remediation.strip()):
                raise ValueError(f"Malformed catalog entry at {path}:{number}")
            remediation = remediation.strip()
            if catalog_id in seen:
                raise ValueError(f"Duplicate catalog ID {catalog_id} at {path}:{number}")
            seen.add(catalog_id)
            yield {"catalog_id": catalog_id, "title": title.rstrip("."), "remediation": remediation}


def validate_registry(rules):
    entries = {entry["catalog_id"] for entry in iter_catalog()}
    codes = set()
    for rule in rules:
        if rule.engine_code in codes:
            raise ValueError(f"Duplicate engine code: {rule.engine_code}")
        if rule.catalog_id not in entries:
            raise ValueError(f"Unknown catalog ID: {rule.catalog_id}")
        if not (ROOT / "skills" / rule.skill / "SKILL.md").is_file():
            raise ValueError(f"Unknown remediation skill: {rule.skill}")
        codes.add(rule.engine_code)


def finding_metadata(engine_code, engine):
    rule = BY_CODE.get(engine_code)
    if rule is None or rule.engine != engine:
        return {"catalog_id": None, "skill": None, "skill_path": None, "mapped": False}
    return {
        "catalog_id": rule.catalog_id,
        "skill": rule.skill,
        "skill_path": f"skills/{rule.skill}/SKILL.md",
        "mapped": True,
    }


def describe_entry(entry, rule=None):
    related = [item for item in RULES if item.catalog_id == entry["catalog_id"]]
    skill = related[0].skill if related else None
    return {
        "found": True,
        **entry,
        "engine_code": rule.engine_code if rule else None,
        "related_rules": [
            {"engine": item.engine, "engine_code": item.engine_code} for item in related
        ],
        "skill": skill,
        "skill_path": f"skills/{skill}/SKILL.md" if skill else None,
        "mapped": bool(related),
        "evidence_rubric": EVIDENCE_RUBRIC,
        "severity_guidance": SEVERITY_GUIDANCE.get(entry["catalog_id"]),
        "registry_version": REGISTRY_VERSION,
    }


def lookup(query, path=CATALOG_PATH):
    identifier = query.strip().upper()
    rule = BY_CODE.get(identifier)
    catalog_id = rule.catalog_id if rule else identifier
    for entry in iter_catalog(path):
        if entry["catalog_id"] == catalog_id:
            return describe_entry(entry, rule)
    return {"found": False, "query": query, "mapped": False, "registry_version": REGISTRY_VERSION}


def search_catalog(query, limit):
    phrase = query.casefold()
    matches = []
    for entry in iter_catalog():
        haystack = " ".join(entry.values()).casefold()
        if phrase in haystack and len(matches) < limit:
            matches.append(entry)
    return matches


def build_coverage(observations):
    counts = dict.fromkeys(("automatic", "manual-review", "out-of-scope", "planned"), 0)
    patterns = {}
    for entry in iter_catalog():
        catalog_id = entry["catalog_id"]
        rules = [rule for rule in RULES if rule.catalog_id == catalog_id]
        fixtures = {rule.evidence_key: observations[rule.evidence_key] for rule in rules
                    if rule.evidence_key in observations}
        verified = any(result["tp"] and (result["tn"] + result["fp"]) for result in fixtures.values())
        status = "automatic" if verified else "manual-review"
        counts[status] += 1
        patterns[catalog_id] = {
            "status": status,
            "related_rules": [rule.evidence_key for rule in rules],
            "fixtures": fixtures,
            "severity_guidance": SEVERITY_GUIDANCE.get(catalog_id),
        }
    return {
        "registry_version": REGISTRY_VERSION,
        "total_patterns": len(patterns),
        "counts": counts,
        "patterns": patterns,
        "scope": "Fixture observations for curated detector mappings only",
        "fixture_precision": {
            key: result["tp"] / (result["tp"] + result["fp"])
            if (result["tp"] + result["fp"]) and (result["tn"] + result["fp"]) else None
            for key, result in observations.items()
        },
    }


def coverage_main(argv):
    parser = argparse.ArgumentParser(description="Summarize observed detector fixture coverage")
    parser.add_argument("--observations", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        observations = json.loads(args.observations.read_text(encoding="utf-8"))
        approved_keys = {rule.evidence_key for rule in RULES}
        if not isinstance(observations, dict) or set(observations).difference(approved_keys):
            raise ValueError("Unexpected detector observations")
        for result in observations.values():
            if (not isinstance(result, dict) or set(result) != set(OUTCOMES)
                    or any(type(value) is not int or value < 0 for value in result.values())):
                raise ValueError("Detector observations require nonnegative integer tp/fp/tn/fn counts")
        validate_registry(RULES)
        report = build_coverage(observations)
        args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError) as error:
        parser.error(str(error))
    return 0


def print_explanation(result):
    print(f"{result['catalog_id']} | {result['title']}")
    if result["engine_code"]:
        print(f"Engine code: {result['engine_code']}")
    if result["related_rules"]:
        names = ", ".join(f"{rule['engine']}:{rule['engine_code']}" for rule in result["related_rules"])
        print(f"Related rules: {names}")
        print(f"Remediation skill: {result['skill_path']}")
    else:
        print("Related rules: no verified detector mapping")
    print(f"Remediation: {result['remediation']}")
    print(f"Evidence rubric: {result['evidence_rubric']}")
    if result["severity_guidance"]:
        print(f"Severity guidance: {result['severity_guidance']}")


def explain_cli(argv):
    parser = argparse.ArgumentParser(description="Explain catalog and emitted engine rule IDs")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("identifier", nargs="?", help="Catalog ID or emitted engine code")
    selection.add_argument("--search", help="Search catalog IDs, titles, and guidance")
    parser.add_argument("--limit", type=int, default=5, help="Search results, from 1 to 50")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    query = (args.search if args.search is not None else args.identifier).strip()
    if not query or not 1 <= args.limit <= 50:
        parser.error("Supply a nonempty query and a limit from 1 to 50")
    try:
        if args.search is not None:
            entries = search_catalog(query, args.limit)
            if args.json:
                print(json.dumps({"query": query, "count": len(entries), "results": entries}, indent=2))
            elif entries:
                print("\n".join(f"{entry['catalog_id']} | {entry['title']}" for entry in entries))
            return 0
        result = lookup(query)
    except (OSError, ValueError) as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(result, indent=2))
    elif result["found"]:
        print_explanation(result)
    else:
        print(f"Unknown catalog or engine ID: {query}", file=sys.stderr)
    return 0 if result["found"] else 1


if __name__ == "__main__":
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "coverage":
        sys.exit(coverage_main(arguments[1:]))
    sys.exit(explain_cli(arguments))
