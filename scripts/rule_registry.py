#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
"""Canonical Versioned Rule Registry & Engine-to-Catalog-to-Skill Mapping Engine.

Closes the feedback loop between engine findings (Rust, Go, Python guards)
and actionable remediation skills with stable catalog identifiers.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

RULE_REGISTRY_VERSION = "1.0.0"

ROOT_DIR = Path(__file__).resolve().parent.parent
CATALOG_FILE = ROOT_DIR / "references" / "anti-pattern-catalog.md"
MAPPING_EXPORT_FILE = ROOT_DIR / "references" / "rule-catalog-mapping.json"
MAPPING_SKILL_EXPORT_FILE = ROOT_DIR / "skills" / "anti-slop-engineering" / "references" / "rule-catalog-mapping.json"

GUARD_TO_SKILL_MAP: Dict[str, Dict[str, str]] = {
    "diff_guard": {"skill": "anti-slop-engineering", "skill_path": "skills/anti-slop-engineering/SKILL.md"},
    "sre_guard": {"skill": "anti-slop-engineering", "skill_path": "skills/anti-slop-engineering/SKILL.md"},
    "ast_slop_guard": {"skill": "type-level-and-ast-slop-gate", "skill_path": "skills/type-level-and-ast-slop-gate/SKILL.md"},
    "comment_budget_guard": {"skill": "comment-budget-guard", "skill_path": "skills/comment-budget-guard/SKILL.md"},
    "attention_guard": {"skill": "cognitive-load-and-attention-governor", "skill_path": "skills/cognitive-load-and-attention-governor/SKILL.md"},
    "demock_guard": {"skill": "demock-guard", "skill_path": "skills/demock-guard/SKILL.md"},
    "mandela_guard": {"skill": "mandela-guard", "skill_path": "skills/mandela-guard/SKILL.md"},
    "tagore_guard": {"skill": "tagore-guard", "skill_path": "skills/tagore-guard/SKILL.md"},
    "forensic_hunter": {"skill": "paranoid-principal-architect", "skill_path": "skills/paranoid-principal-architect/SKILL.md"},
    "contrast_guard": {"skill": "ui-and-copy-discipline", "skill_path": "skills/ui-and-copy-discipline/SKILL.md"},
    "system_drift_guard": {"skill": "design-system-drift-guard", "skill_path": "skills/design-system-drift-guard/SKILL.md"},
    "chroma_drift_guard": {"skill": "chromatic-drift-guard", "skill_path": "skills/chromatic-drift-guard/SKILL.md"},
    "styleseed_guard": {"skill": "styleseed-guard", "skill_path": "skills/styleseed-guard/SKILL.md"},
    "asset_provenance_guard": {"skill": "asset-provenance-guard", "skill_path": "skills/asset-provenance-guard/SKILL.md"},
    "pr_boundary_guard": {"skill": "pr-boundary-guard", "skill_path": "skills/pr-boundary-guard/SKILL.md"},
    "honeypot_trap_guard": {"skill": "honeypot-trap-guard", "skill_path": "skills/honeypot-trap-guard/SKILL.md"},
    "invariant_steward_guard": {"skill": "repo-memory-and-invariant-steward", "skill_path": "skills/repo-memory-and-invariant-steward/SKILL.md"},
    "reduction_guard": {"skill": "reduction-guard", "skill_path": "skills/reduction-guard/SKILL.md"},
    "re0_handoff_guard": {"skill": "re0-handoff-guard", "skill_path": "skills/re0-handoff-guard/SKILL.md"},
    "backprop_guard": {"skill": "backprop-guard", "skill_path": "skills/backprop-guard/SKILL.md"},
    "house_tell_guard": {"skill": "house-tell-guard", "skill_path": "skills/house-tell-guard/SKILL.md"},
    "motion_runtime_guard": {"skill": "motion-runtime-guard", "skill_path": "skills/motion-runtime-guard/SKILL.md"},
    "decision_guard": {"skill": "decision-guard", "skill_path": "skills/decision-guard/SKILL.md"},
    "root_fix_guard": {"skill": "root-fix-gate", "skill_path": "skills/root-fix-gate/SKILL.md"},
    "future_scale_guard": {"skill": "future-scale-gate", "skill_path": "skills/future-scale-gate/SKILL.md"},
    "paranoid_guard": {"skill": "paranoid-principal-architect", "skill_path": "skills/paranoid-principal-architect/SKILL.md"},
    "perf_guard": {"skill": "mechanical-sympathy-and-perf-gate", "skill_path": "skills/mechanical-sympathy-and-perf-gate/SKILL.md"},
    "rollout_guard": {"skill": "safe-evolution-and-rollout-choreographer", "skill_path": "skills/safe-evolution-and-rollout-choreographer/SKILL.md"},
    "simulation_guard": {"skill": "deterministic-simulation-and-property-testing", "skill_path": "skills/deterministic-simulation-and-property-testing/SKILL.md"},
    "privacy_guard": {"skill": "privacy-and-data-lineage-gate", "skill_path": "skills/privacy-and-data-lineage-gate/SKILL.md"},
    "api_contract_guard": {"skill": "api-ergonomics-and-contract-governor", "skill_path": "skills/api-ergonomics-and-contract-governor/SKILL.md"},
    "apple_craft_guard": {"skill": "apple-craft-and-interaction-physics", "skill_path": "skills/apple-craft-and-interaction-physics/SKILL.md"},
    "observability_guard": {"skill": "observability-and-slo-architect", "skill_path": "skills/observability-and-slo-architect/SKILL.md"},
}

def _r(cat_id: str, skill: str, sev: str, category: str, rem: str, aliases: Optional[List[str]] = None) -> Dict[str, Any]:
    return {
        "aliases": aliases or [],
        "catalog_id": cat_id,
        "skill": skill,
        "skill_path": f"skills/{skill}/SKILL.md",
        "severity": sev,
        "category": category,
        "remediation": rem,
    }


CANONICAL_RULE_REGISTRY: Dict[str, Dict[str, Any]] = {
    "SRE-KISS-FUNC-LEN": _r(
        "SRE-01", "anti-slop-engineering", "HIGH", "KISS",
        "Decompose long function into focused single-responsibility units (<=80 lines).",
        ["KISS_FUNCTION_BLOAT", "KISS-FUNC-LEN", "KISS_FUNC_LEN"],
    ),
    "SRE-KISS-NESTING": _r(
        "SRE-01", "anti-slop-engineering", "HIGH", "KISS",
        "Flatten deep branching using early returns and guard clauses (nesting <=4 levels).",
        ["KISS_NESTING", "KISS-NESTING"],
    ),
    "SRE-DRY-DUPLICATE": _r(
        "SRE-03", "anti-slop-engineering", "HIGH", "DRY",
        "Consolidate duplicate logic (>=4 lines) into a shared canonical helper module.",
        ["DRY_CODE_DUPLICATION", "DRY-DUPLICATE"],
    ),
    "SRE-YAGNI-UNUSED-PARAM": _r(
        "SRE-05", "anti-slop-engineering", "MEDIUM", "YAGNI",
        "Remove unused speculative parameters; build only for active verified contracts.",
        ["YAGNI_UNUSED_PARAM", "YAGNI-UNUSED-PARAM"],
    ),
    "SRE-YAGNI-DEAD-BRANCH": _r(
        "SRE-05", "anti-slop-engineering", "HIGH", "YAGNI",
        "Eliminate dead branches or unreachable code blocks.",
        ["YAGNI_DEAD_BRANCH", "YAGNI-DEAD-BRANCH"],
    ),
    "SRE-YAGNI-TODO": _r(
        "REQ-12", "anti-slop-engineering", "HIGH", "YAGNI",
        "Resolve temporary placeholders and TODOs before shipping production changes.",
        ["YAGNI_TODO_PLACEHOLDER", "YAGNI-TODO"],
    ),
    "SRE-SCALE-FLAT-RETRY": _r(
        "SRE-08", "anti-slop-engineering", "BLOCKER", "SCALE",
        "Replace flat retries with exponential backoff and full jitter to prevent thundering herds.",
        ["SCALE_FLAT_RETRY", "SCALE-FLAT-RETRY"],
    ),
    "SRE-SCALE-SLEEP-SYNC": _r(
        "SRE-07", "anti-slop-engineering", "BLOCKER", "SCALE",
        "Replace arbitrary sleep() calls with deterministic event polling or synchronization latches.",
        ["SCALE_SLEEP_SYNC", "SCALE-SLEEP-SYNC"],
    ),
    "SRE-SCALE-SWALLOWED-EXCEPTION": _r(
        "SRE-10", "anti-slop-engineering", "BLOCKER", "SCALE",
        "Do not silently swallow exceptions; log with trace context and fail closed.",
        ["SCALE_SWALLOWED_EXCEPTION", "SCALE-SWALLOWED-EXCEPTION"],
    ),
    "SRE-SCALE-NON-IDEMPOTENT": _r(
        "SRE-11", "anti-slop-engineering", "HIGH", "SCALE",
        "Enforce idempotency keys or unique request tokens on state-changing operations.",
        ["SCALE_NON_IDEMPOTENT_MUTATION", "SCALE-NON-IDEMPOTENT"],
    ),
    "SRE-SCALE-UNBOUNDED-CONCURRENCY": _r(
        "SRE-09", "anti-slop-engineering", "BLOCKER", "SCALE",
        "Bound concurrency using worker pools or semaphores with backpressure signaling.",
        ["SCALE_UNBOUNDED_CONCURRENCY", "SCALE-UNBOUNDED-CONCURRENCY"],
    ),
    "BORING-KISS-01": _r(
        "SIM-08", "anti-slop-engineering", "MEDIUM", "KISS",
        "Use platform native crypto.randomUUID() instead of hand-rolling UUID generation.",
        ["MISSING_BUILTIN_UUID", "BUILTIN-UUID"],
    ),
    "BORING-KISS-02": _r(
        "SIM-08", "anti-slop-engineering", "MEDIUM", "KISS",
        "Use platform native URLSearchParams instead of custom query-string concatenation.",
        ["MISSING_BUILTIN_URLSEARCHPARAMS", "BUILTIN-URLSEARCHPARAMS"],
    ),
    "BORING-DRY-01": _r(
        "SIM-01", "anti-slop-engineering", "HIGH", "DRY",
        "Consolidate duplicated logic passing the 3-point barrier (>=2 call-sites, identical requirements).",
        ["PRACTICAL_DRY_BARRIER"],
    ),
    "DEMOCK-001": _r(
        "TST-01", "demock-guard", "BLOCKER", "CORRECTNESS",
        "Eliminate test doubles on production execution paths; use verified fakes in tests only.",
        ["DEMOCK_PROD_DOUBLE", "PROD_MOCK_DETECTED"],
    ),
    "DEMOCK-002": _r(
        "TST-01", "demock-guard", "BLOCKER", "CORRECTNESS",
        "Fail closed on persistence/DB errors rather than falling back to in-memory or dummy mocks.",
        ["DEMOCK_SILENT_FALLBACK", "SILENT_DUMMY_FALLBACK"],
    ),
    "DEMOCK-003": _r(
        "SEC-02", "demock-guard", "BLOCKER", "SECURITY",
        "Do not fail open on authorization checks; explicitly reject unverified callers.",
        ["DEMOCK_FAIL_OPEN", "FAIL_OPEN_AUTH"],
    ),
    "ATTENTION-WRAPPER-01": _r(
        "AGT-01", "cognitive-load-and-attention-governor", "MEDIUM", "COGNITIVE",
        "Strip conversational lead-in wrappers ('Here is...', 'Below you will find...') for pure deliverables.",
        ["DELIVERABLE_PURITY_WRAPPER"],
    ),
    "ATTENTION-CLOSER-02": _r(
        "AGT-01", "cognitive-load-and-attention-governor", "MEDIUM", "COGNITIVE",
        "Strip conversational sign-off offers ('Hope this helps!', 'Let me know if you need anything else!').",
        ["DELIVERABLE_PURITY_CLOSER"],
    ),
    "BLOCKING_ASK_PLACEMENT": _r(
        "AGT-01", "cognitive-load-and-attention-governor", "HIGH", "COGNITIVE",
        "Position blocking decision asks in the terminal block with zero trailing conversational prose.",
        ["TERMINAL_BLOCKING_ASK"],
    ),
    "STS-I01": _r(
        "ARC-09", "anti-slop-engineering", "HIGH", "ARCHITECTURE",
        "Avoid conjunction-named abstractions ('And', 'Or', 'Manager'); define single cohesive purpose.",
        ["INTENT_VIOLATION_CONJUNCTION"],
    ),
    "STS-S01": _r(
        "ARC-06", "anti-slop-engineering", "BLOCKER", "SCOPE",
        "Do not introduce unrelated infrastructure changes or scope creep into focused pull requests.",
        ["SCOPE_CREEP_CRITICAL_PATH"],
    ),
    "TAGORE-INFLATION-01": _r(
        "REV-01", "tagore-guard", "MEDIUM", "DISCOURSE",
        "State concrete technical facts and impact directly without inflated importance claims.",
        ["TAGORE_SIGNIFICANCE_INFLATION", "SIGNIFICANCE_INFLATION"],
    ),
    "TAGORE-COPULA-02": _r(
        "REV-01", "tagore-guard", "LOW", "DISCOURSE",
        "Use direct copulas ('is', 'are') rather than avoidance verbs ('serves as', 'stands as').",
        ["TAGORE_COPULA_AVOIDANCE", "COPULA_AVOIDANCE"],
    ),
    "TAGORE-PARTICIPLE-03": _r(
        "REV-01", "tagore-guard", "LOW", "DISCOURSE",
        "Break stacked participle clauses into concise, punchy affirmative sentences.",
        ["TAGORE_PARTICIPLE_STACKING"],
    ),
    "TAGORE-HYPE-04": _r(
        "REV-01", "tagore-guard", "MEDIUM", "DISCOURSE",
        "Eliminate marketing hyperbole ('delve', 'testament', 'revolutionize') in technical documentation.",
        ["SUPERLATIVE_BUZZWORD", "HYPE_WORDS"],
    ),
    "TAGORE-SYCOPHANCY-05": _r(
        "REV-01", "tagore-guard", "MEDIUM", "DISCOURSE",
        "Eliminate sycophantic conversational openers; answer directly with facts on Line 1.",
        ["TAGORE_SYCOPHANCY"],
    ),
    "STYLESEED-001": _r(
        "UI-01", "styleseed-guard", "HIGH", "DESIGN",
        "Ground design elements in canonical 4-tier design tokens rather than ad-hoc inline styles.",
        ["STYLESEED_TOKEN_CANON"],
    ),
    "STYLESEED-002": _r(
        "UI-01", "styleseed-guard", "MEDIUM", "DESIGN",
        "Enforce spatial rhythm hierarchy with proportional whitespace rather than arbitrary padding.",
        ["STYLESEED_SPATIAL_RHYTHM"],
    ),
    "STYLESEED-003": _r(
        "UI-04", "styleseed-guard", "HIGH", "DESIGN",
        "Ensure pairwise color contrasts pass WCAG 2.2 AA (>=4.5:1 for normal, >=3:1 for large text).",
        ["STYLESEED_CONTRAST_GATE"],
    ),
    "COMMENT-NARRATION-01": _r(
        "SIM-08", "comment-budget-guard", "MEDIUM", "SIMPLICITY",
        "Delete comments narrating obvious syntax; explain 'why' and formal invariants only.",
        ["SYNTAX_NARRATION_COMMENT", "PLAY_BY_PLAY_COMMENT"],
    ),
    "CCR_BUDGET_EXCEEDED": _r(
        "SIM-08", "comment-budget-guard", "HIGH", "SIMPLICITY",
        "Enforce Comment-to-Code Ratio CCR <= 0.35 by removing decorative and narrative comments.",
        ["CCR_OVERFLOW"],
    ),
    "CHAINED_TYPE_ASSERTION": _r(
        "ARC-10", "type-level-and-ast-slop-gate", "BLOCKER", "TYPE_SAFETY",
        "Eliminate chained casts (as unknown as T); validate schema parsing at the system boundary.",
        ["CHAINED-TYPE-ASSERTION"],
    ),
    "UNGROUNDED_TYPE_ASSERTION": _r(
        "ARC-10", "type-level-and-ast-slop-gate", "HIGH", "TYPE_SAFETY",
        "Type assertions (as T) require nearby // SAFETY: invariant justification comment.",
        ["UNGROUNDED-TYPE-ASSERTION"],
    ),
    "QUADRATIC_REDUCER_COPY": _r(
        "SRE-07", "type-level-and-ast-slop-gate", "HIGH", "PERFORMANCE",
        "Mutate accumulator in-place inside reduce loops instead of spreading object copies ({...acc}).",
        ["QUADRATIC-REDUCER-COPY"],
    ),
    "EAGER_ARRAY_CHAINING": _r(
        "SRE-07", "type-level-and-ast-slop-gate", "MEDIUM", "PERFORMANCE",
        "Consolidate chained .filter().map() passes into a single iteration or generator.",
        ["EAGER-ARRAY-CHAINING"],
    ),
    "CONDITIONAL_EMPTY_SPREAD": _r(
        "ARC-10", "type-level-and-ast-slop-gate", "MEDIUM", "TYPE_SAFETY",
        "Use explicit optional property assignment instead of conditional empty object spread (...(c ? {x} : {})).",
        ["CONDITIONAL-EMPTY-SPREAD"],
    ),
    "MODULE_MOCK_ORACLE_EROSION": _r(
        "TST-01", "type-level-and-ast-slop-gate", "BLOCKER", "TEST_INTEGRITY",
        "Replace banned module mocks (vi.mock, jest.mock) with verified in-memory contract fakes.",
        ["MODULE-MOCK-ORACLE-EROSION", "VI_MOCK_DETECTED"],
    ),
    "WCAG_CONTRAST_FAIL": _r(
        "UI-04", "ui-and-copy-discipline", "BLOCKER", "ACCESSIBILITY",
        "Adjust color pairing to meet WCAG 2.2 AA minimum contrast ratio 4.5:1 for normal text.",
        ["WCAG-CONTRAST-FAIL", "LOW_CONTRAST_NORMAL"],
    ),
    "WCAG_CONTRAST_LARGE_FAIL": _r(
        "UI-04", "ui-and-copy-discipline", "HIGH", "ACCESSIBILITY",
        "Adjust color pairing to meet WCAG 2.2 AA minimum contrast ratio 3.0:1 for large text.",
        ["WCAG-CONTRAST-LARGE-FAIL", "LOW_CONTRAST_LARGE"],
    ),
    "PY-01": _r(
        "SEC-01", "paranoid-principal-architect", "CRITICAL", "SECURITY",
        "Extract secrets into environment variables; never commit credentials or tokens to code.",
        ["HARDCODED_SECRETS"],
    ),
    "PY-02": _r(
        "SEC-07", "paranoid-principal-architect", "CRITICAL", "SECURITY",
        "Use safe JSON/Protobuf deserialization; ban pickle or eval on untrusted payloads.",
        ["INSECURE_DESERIALIZATION"],
    ),
    "PY-03": _r(
        "SEC-04", "paranoid-principal-architect", "CRITICAL", "SECURITY",
        "Use parameterized queries with prepared statements; never format user inputs into SQL strings.",
        ["SQL_INJECTION"],
    ),
    "PY-04": _r(
        "SEC-05", "paranoid-principal-architect", "CRITICAL", "SECURITY",
        "Pass arguments as a sequence (['cmd', arg]) with shell=False and check=True.",
        ["COMMAND_INJECTION_SHELL"],
    ),
    "PY-05": _r(
        "SEC-09", "paranoid-principal-architect", "CRITICAL", "SECURITY",
        "Resolve paths against an allowlisted root and verify .resolve().is_relative_to(root).",
        ["PATH_TRAVERSAL"],
    ),
    "PY-06": _r(
        "SEC-06", "paranoid-principal-architect", "CRITICAL", "SECURITY",
        "Constrain outgoing HTTP destinations using an IP/host allowlist; block internal metadata IPs.",
        ["SSRF_UNCONSTRAINED"],
    ),
    "PY-07": _r(
        "SEC-12", "paranoid-principal-architect", "CRITICAL", "SECURITY",
        "Always verify TLS certificates; enforce strict certificate validation in production HTTP clients.",
        ["TLS_SWITCH_OFF"],
    ),
    "PY-08": _r(
        "SRE-10", "paranoid-principal-architect", "HIGH", "RELIABILITY",
        "Catch specific exception classes and ensure errors are logged or bubbled.",
        ["BROAD_EXCEPTION_SWALLOWING"],
    ),
    "SEVEN_GATES": _r(
        "REQ-10", "anti-slop-engineering", "BLOCKER", "CORRECTNESS",
        "Review and adhere to Seven Gates contracts in SKILL.md before generating changes.",
        ["SEVEN-GATES"],
    ),
    "BLAST_RADIUS": _r(
        "REV-01", "anti-slop-engineering", "HIGH", "SCOPE",
        "Decompose wide diff into focused, independently reviewable pull request stages.",
        ["BLAST-RADIUS", "DIFF_TOO_LARGE"],
    ),
    "DEV_NOTES_LEAKAGE": _r(
        "REQ-12", "anti-slop-engineering", "BLOCKER", "BOUNDARY",
        "Remove internal engineering notes, agent chatter, and TODOs from user-facing surfaces.",
        ["DEV-NOTES-LEAKAGE"],
    ),
    "DIRECT_PAYLOAD": _r(
        "SIM-08", "anti-slop-engineering", "HIGH", "COMMUNICATION",
        "Transition directly from domain headers to technical payloads with zero conversational fluff.",
        ["AFFORDANCE_NARRATION"],
    ),
    "ZERO_OBVIOUSNESS": _r(
        "SIM-08", "anti-slop-engineering", "HIGH", "COMMUNICATION",
        "Strip obvious syntax narration and patronizing UI microcopy beneath self-evident controls.",
        ["ANTI_TRUISM"],
    ),
    "CANONICAL_GROUNDING": _r(
        "ARC-15", "anti-slop-engineering", "BLOCKER", "FOUNDATIONS",
        "Use official CLI installer or starter generators rather than improvising project scaffolding.",
        ["SCAFFOLDING_IMPROVISATION"],
    ),
    "DEPENDENCY_DETERMINISM": _r(
        "SEC-17", "anti-slop-engineering", "HIGH", "DEPENDENCIES",
        "Pin verified latest stable releases from package registry; never guess obsolete versions.",
        ["STALE_DEPENDENCY"],
    ),
    "DECISION_RECORD": _r(
        "ARC-16", "decision-guard", "BLOCKER", "ARCHITECTURE",
        "Formulate structured Decision Guard JSON record comparing independent options and trade-offs.",
        ["DECISION-RECORD"],
    ),
    "ROOT_FIX_RECORD": _r(
        "ARC-17", "root-fix-gate", "BLOCKER", "ARCHITECTURE",
        "Trace earliest causal invariant and document root fix plan rather than distributed patches.",
        ["ROOT-FIX-RECORD"],
    ),
    "FUTURE_SCALE_RECORD": _r(
        "ARC-18", "future-scale-gate", "BLOCKER", "ARCHITECTURE",
        "Demonstrate evolution path and reversal costs before committing to hard-to-reverse foundations.",
        ["FUTURE-SCALE-RECORD"],
    ),
    "PARANOID_RECORD": _r(
        "SEC-03", "paranoid-principal-architect", "BLOCKER", "ARCHITECTURE",
        "Verify 10M concurrent user zero-trust architecture, cursor pagination, and timeouts.",
        ["PARANOID-RECORD"],
    ),
    "PERF_RECORD": _r(
        "SRE-07", "mechanical-sympathy-and-perf-gate", "BLOCKER", "PERFORMANCE",
        "Provide empirical benchmark and flamegraph evidence before claiming performance gains.",
        ["PERF-RECORD"],
    ),
    "ROLLOUT_RECORD": _r(
        "OPS-01", "safe-evolution-and-rollout-choreographer", "BLOCKER", "DEPLOYMENT",
        "Enforce bidirectional wire compatibility (N-1 <-> N+1) and asynchronous dark launches.",
        ["ROLLOUT-RECORD"],
    ),
    "SIMULATION_RECORD": _r(
        "TST-02", "deterministic-simulation-and-property-testing", "BLOCKER", "VERIFICATION",
        "Implement property-based testing and deterministic simulation with reproducible virtual clock seeds.",
        ["SIMULATION-RECORD"],
    ),
    "PRIVACY_RECORD": _r(
        "DAT-01", "privacy-and-data-lineage-gate", "BLOCKER", "PRIVACY",
        "Enforce branded Tainted PII types, crypto-shredding envelope keys, and retention TTLs.",
        ["PRIVACY-RECORD"],
    ),
    "CONTRACT_RECORD": _r(
        "API-01", "api-ergonomics-and-contract-governor", "BLOCKER", "API_DESIGN",
        "Design pit-of-success contracts using discriminated unions and RFC 9457 Problem Details.",
        ["CONTRACT-RECORD"],
    ),
    "APPLE_CRAFT_RECORD": _r(
        "UI-01", "apple-craft-and-interaction-physics", "BLOCKER", "INTERACTION",
        "Enforce 120Hz interaction physics, Zero CLS pre-reservation, and exhaustive state matrices.",
        ["APPLE-CRAFT-RECORD"],
    ),
    "OBSERVABILITY_RECORD": _r(
        "SRE-12", "observability-and-slo-architect", "BLOCKER", "OBSERVABILITY",
        "Propagate unbroken W3C traceparents and gate production alerts on Multi-Window Burn-Rate SLOs.",
        ["OBSERVABILITY-RECORD"],
    ),
    "MOTION_RECORD": _r(
        "UI-04", "motion-runtime-guard", "BLOCKER", "MOTION",
        "Validate DPR-2 retina motion performance, long task bounds, and reduced-motion parity.",
        ["MOTION-RECORD"],
    ),
}

_ALIAS_MAP: Dict[str, str] = {}
for canonical_code, meta in CANONICAL_RULE_REGISTRY.items():
    _ALIAS_MAP[canonical_code.lower()] = canonical_code
    for alias in meta.get("aliases", []):
        _ALIAS_MAP[alias.lower()] = canonical_code


def get_all_rule_mappings() -> Dict[str, Dict[str, Any]]:
    """Return dictionary of all registered canonical rule mappings."""
    return dict(CANONICAL_RULE_REGISTRY)


def resolve_rule_mapping(
    rule_or_code: str,
    fallback_guard: Optional[str] = None,
    fallback_severity: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve an engine finding code or rule into a catalog entry and actionable skill.

    Returns:
        Dictionary with keys:
            - engine_code: canonical rule/code identifier
            - catalog_id: matched catalog identifier (e.g. 'SIM-08') or None
            - skill: assigned remediation skill name or None
            - skill_path: relative path to SKILL.md or None
            - severity: finding severity
            - category: finding category
            - remediation: actionable remediation text
            - mapped: True if matched in registry, False if unmapped fallback
            - version: registry version
    """
    clean_key = rule_or_code.strip()
    norm_key = clean_key.lower().replace("-", "_")
    norm_dash = clean_key.lower().replace("_", "-")

    canonical = (
        _ALIAS_MAP.get(clean_key.lower())
        or _ALIAS_MAP.get(norm_key)
        or _ALIAS_MAP.get(norm_dash)
    )

    if canonical:
        meta = CANONICAL_RULE_REGISTRY[canonical]
        return {
            "engine_code": canonical,
            "catalog_id": meta.get("catalog_id"),
            "skill": meta.get("skill"),
            "skill_path": meta.get("skill_path"),
            "severity": meta.get("severity", fallback_severity or "HIGH"),
            "category": meta.get("category", "GENERAL"),
            "remediation": meta.get("remediation", ""),
            "mapped": True,
            "version": RULE_REGISTRY_VERSION,
        }

    # Fallback for unmapped findings
    default_skill_info = GUARD_TO_SKILL_MAP.get(fallback_guard or "", {})
    return {
        "engine_code": clean_key,
        "catalog_id": None,
        "skill": default_skill_info.get("skill"),
        "skill_path": default_skill_info.get("skill_path"),
        "severity": fallback_severity or "HIGH",
        "category": "UNMAPPED",
        "remediation": f"Unmapped rule '{clean_key}'. Review finding context and follow engineering guidelines.",
        "mapped": False,
        "version": RULE_REGISTRY_VERSION,
    }


def _get_catalog_entry_text(catalog_id: str) -> str:
    """Extract entry description from anti-pattern-catalog.md for a given catalog ID."""
    if not CATALOG_FILE.is_file():
        return ""
    prefix = f"- **{catalog_id} |"
    for line in CATALOG_FILE.read_text(encoding="utf-8").splitlines():
        trimmed = line.strip()
        if trimmed.startswith(prefix):
            return trimmed[len(f"- **{catalog_id}"):].lstrip(" |").strip()
    return ""


def explain_rule(rule_or_code: str) -> Dict[str, Any]:
    """Produce rich diagnostic report explaining an engine code or rule."""
    resolved = resolve_rule_mapping(rule_or_code)
    cat_id = resolved.get("catalog_id")
    catalog_entry = _get_catalog_entry_text(cat_id) if cat_id else ""
    return {
        **resolved,
        "catalog_entry": catalog_entry,
    }


def export_rule_catalog_mapping() -> Dict[str, Any]:
    """Export complete versioned rule registry for manifest publication."""
    return {
        "version": RULE_REGISTRY_VERSION,
        "total_rules": len(CANONICAL_RULE_REGISTRY),
        "rules": CANONICAL_RULE_REGISTRY,
    }


def format_rule_explanation(diag: Dict[str, Any]) -> str:
    """Format explanation dictionary into readable human-facing text."""
    lines = [
        f"Rule Code:     {diag['engine_code']}",
        f"Catalog ID:    {diag['catalog_id'] or 'Unmapped'}",
        f"Skill:         {diag['skill'] or 'None'} ({diag['skill_path'] or 'N/A'})",
        f"Severity:      {diag['severity']}",
        f"Remediation:   {diag['remediation']}",
    ]
    if diag.get("catalog_entry"):
        lines.append(f"Catalog Entry: {diag['catalog_entry']}")
    return "\n".join(lines)


def print_rule_explanation(diag: Dict[str, Any], json_mode: bool = False) -> None:
    """Print formatted or JSON explanation to standard output."""
    if json_mode:
        print(json.dumps(diag, indent=2))
    else:
        print(format_rule_explanation(diag))


def sync_catalog_mapping_files() -> None:
    """Synchronize rule-catalog-mapping.json across repository references."""
    data = export_rule_catalog_mapping()
    content = json.dumps(data, indent=2) + "\n"
    MAPPING_EXPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
    MAPPING_EXPORT_FILE.write_text(content, encoding="utf-8")
    if MAPPING_SKILL_EXPORT_FILE.parent.is_dir():
        MAPPING_SKILL_EXPORT_FILE.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Query and synchronize rule catalog mapping")
    subparsers = parser.add_subparsers(dest="subcommand")

    explain_p = subparsers.add_parser("explain", help="Explain an engine rule or code")
    explain_p.add_argument("code", help="Engine code or rule (e.g. SRE-KISS-FUNC-LEN)")
    explain_p.add_argument("--json", action="store_true", help="Output JSON report")

    list_p = subparsers.add_parser("list", help="List all registered rule mappings")
    list_p.add_argument("--json", action="store_true", help="Output JSON list")

    subparsers.add_parser("sync", help="Synchronize rule-catalog-mapping.json files")

    args = parser.parse_args()

    if args.subcommand == "explain":
        diag = explain_rule(args.code)
        print_rule_explanation(diag, json_mode=args.json)
        return 0
    elif args.subcommand == "list":
        data = export_rule_catalog_mapping()
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"Rule Registry v{RULE_REGISTRY_VERSION} ({data['total_rules']} rules):")
            for code, meta in sorted(data["rules"].items()):
                print(f"  {code:30} -> {meta['catalog_id']:7} | {meta['skill']:35}")
        return 0
    elif args.subcommand == "sync":
        sync_catalog_mapping_files()
        print(f"✓ Synchronized rule-catalog-mapping.json (v{RULE_REGISTRY_VERSION})")
        return 0
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
