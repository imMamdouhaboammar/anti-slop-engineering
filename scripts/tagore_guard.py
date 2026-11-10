#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors

"""
Tagore Engineering Discourse & Substance Guard (Zero-Dependency Python >=3.9)
Inspired by Rabindranath Tagore's philosophy of literary restraint, empirical
specificity, and authentic voice over statistical predictability and mechanical puffery.

Fuses the 29-pattern AI prose catalog with software engineering discourse invariants:
- Dual-Vector Slop Analysis: Inflated Puffery vs. Flattened Soulless Slop
- 8-Dimension Scoring Rubric: 5 Mechanics (50 pts, floor 35) + 3 Substance (30 pts, floor 21)
- Pass Threshold: >= 56/80 with strict subtotal floors enforced
- Repository Voice Calibration & Empirical Grounding
- RFC 9457 Problem Details compliant output and suggested deslopping rewrites
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Optional, Tuple

# Word extractor
_WORD_RE = re.compile(r"\b[\w'-]+\b")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_EMPIRICAL_TOKEN_RE = re.compile(
    r"\b(?:\d+(?:\.\d+)?(?:%|ms|s|us|ns|kb|mb|gb|tb|hz|khz|mhz|ghz)?|"
    r"0x[0-9a-fA-F]+|[0-9a-f]{7,40}|"
    r"(?:CVE-\d{4}-\d+|BK-[A-Z]+-\d+|PR-\d+|ADR-\d+)|"
    r"[\w.-]+\.(?:ts|js|py|rs|go|json|md|ya?ml|toml|sql))\b",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Vector A: The 29 Cataloged Tells (adapted for Engineering Discourse)
# ---------------------------------------------------------------------------

TELLS_CATALOG: List[Dict[str, Any]] = [
    {
        "id": "T01_SIGNIFICANCE_INFLATION",
        "category": "Content",
        "name": "Significance & Legacy Inflation",
        "regex": re.compile(
            r"\b(?:stands?|serves?)\s+as\s+(?:an?\s+)?(?:enduring\s+)?(?:testament|beacon|reminder|monument)\b|"
            r"\b(?:pivotal|vital|crucial|groundbreaking)\s+(?:moment|role|milestone|shift|turning\s+point)\b|"
            r"\bunderscores?\s+(?:the\s+)?(?:vital\s+)?importance\b|"
            r"\bmarks?\s+a\s+(?:pivotal|significant|major)\s+shift\b|"
            r"\bsetting\s+the\s+stage\s+for\b|"
            r"\b(?:indelible\s+mark|evolving\s+landscape)\b",
            re.IGNORECASE,
        ),
        "message": "Significance inflation detected: AI puffery elevates routine engineering into historic milestones.",
        "replacement": "State the technical change directly without inflation.",
    },
    {
        "id": "T02_NOTABILITY_PUFFERY",
        "category": "Content",
        "name": "Undue Emphasis on Notability",
        "regex": re.compile(
            r"\b(?:independent\s+coverage|active\s+social\s+media\s+presence|leading\s+expert|industry\s+leader)\b",
            re.IGNORECASE,
        ),
        "message": "Notability puffery detected: artificial elevation of authority or media coverage.",
        "replacement": "Cite specific technical sources, papers, or benchmark data.",
    },
    {
        "id": "T03_SUPERFICIAL_ING_CHAINS",
        "category": "Content",
        "name": "Superficial Participle (-ing) Chaining",
        "regex": re.compile(
            r"(?:,\s*(?:highlighting|underscoring|emphasizing|ensuring|reflecting|"
            r"fostering|enhancing|facilitating|cultivating|showcasing)\s+[^,\n]+){2,}",
            re.IGNORECASE,
        ),
        "message": "Superficial -ing participle chain: AI tacks trailing participle phrases to fake depth.",
        "replacement": "Break into active, declarative sentences naming the concrete actor or mechanism.",
    },
    {
        "id": "T04_PROMOTIONAL_VOCABULARY",
        "category": "Content",
        "name": "Promotional & Marketing Hype",
        "regex": re.compile(
            r"\b(?:groundbreaking|game-changer|revolutionary|unparalleled|seamless(?:ly)?|"
            r"best-in-class|cutting-edge|next-level|unlock(?:ing)?\s+(?:the\s+power|creativity|potential)|"
            r"nestled\s+at\s+the\s+intersection)\b",
            re.IGNORECASE,
        ),
        "message": "Promotional vocabulary: Marketing puffery inappropriate for engineering documentation.",
        "replacement": "Use restrained, precise engineering terminology.",
    },
    {
        "id": "T05_VAGUE_ATTRIBUTIONS",
        "category": "Content",
        "name": "Vague Attributions & Weasel Words",
        "regex": re.compile(
            r"\b(?:industry\s+observers?\s+(?:note|suggest)|experts?\s+agree|"
            r"studies\s+(?:have\s+)?show(?:n)?|widely\s+considered\s+to\s+be|"
            r"it\s+is\s+generally\s+believed)\b",
            re.IGNORECASE,
        ),
        "message": "Vague attribution: Unsubstantiated collective authority gestures.",
        "replacement": "Name the specific author, paper, RFC, benchmark, or telemetry source.",
    },
    {
        "id": "T06_FORMULAIC_CHALLENGES",
        "category": "Content",
        "name": "Formulaic Challenges & Outlook Section",
        "regex": re.compile(
            r"\b(?:despite\s+(?:these\s+)?challenges.*(?:continues?\s+to\s+thrive|future\s+looks\s+bright)|"
            r"challenges\s+and\s+future\s+outlook|journey\s+toward\s+excellence)\b",
            re.IGNORECASE,
        ),
        "message": "Formulaic challenges trope: boilerplate narrative structure typical of chatbot outputs.",
        "replacement": "Document concrete operational trade-offs and unresolved failure modes.",
    },
    {
        "id": "T07_AI_VOCABULARY",
        "category": "Language",
        "name": "Overused AI Vocabulary",
        "regex": re.compile(
            r"\b(?:delve|delving|tapestry|beacon|testament|intricate|intricacies|"
            r"interplay|garner|fostering|pivotal|vibrant)\b",
            re.IGNORECASE,
        ),
        "message": "High-frequency AI vocabulary token detected.",
        "replacement": "Replace with plain, direct engineering terminology (explore, structure, interaction).",
    },
    {
        "id": "T08_COPULA_AVOIDANCE",
        "category": "Language",
        "name": "Copula Avoidance",
        "regex": re.compile(
            r"\b(?:serves?\s+as|stands?\s+as|functions?\s+as)\s+(?:an?\s+)?(?:robust|comprehensive|vital|powerful)\b|"
            r"\b(?:boasts?|features?)\s+(?:an?\s+)?(?:impressive|unmatched|array|suite\s+of)\b",
            re.IGNORECASE,
        ),
        "message": "Copula avoidance: Elaborate verb substitutions avoiding simple 'is', 'are', or 'has'.",
        "replacement": "Use simple copula verbs ('is', 'are', 'has', 'contains').",
    },
    {
        "id": "T09_NEGATIVE_PARALLELISM",
        "category": "Language",
        "name": "Negative Parallelisms & Tailing Negations",
        "regex": re.compile(
            r"\b(?:it'?s\s+not\s+(?:just|merely|only)\s+about\s+[^,;]+[,;]\s*it'?s\s+about)|"
            r"\b(?:not\s+only\s+does\s+[^,;]+but\s+it\s+also)\b|"
            r",\s*(?:no\s+guessing|no\s+wasted\s+motion|no\s+compromises?)\.?$",
            re.IGNORECASE | re.M,
        ),
        "message": "Negative parallelism or clipped tailing negation detected.",
        "replacement": "State the affirmative technical fact directly without dramatic contrasting.",
    },
    {
        "id": "T10_RULE_OF_THREE",
        "category": "Language",
        "name": "Rule of Three Overuse",
        "regex": re.compile(
            r"\b(\w+ing),\s+(\w+ing),\s+and\s+(\w+ing)\b|"
            r"\b([a-z]+),\s+([a-z]+),\s+and\s+([a-z]+)\s+(?:experience|solutions?|tools?|capabilities)\b",
            re.IGNORECASE,
        ),
        "message": "Rule of three formulaic phrasing: chatbot attempts to sound complete by grouping triads.",
        "replacement": "State the primary one or two essential elements.",
    },
    {
        "id": "T11_ELEGANT_VARIATION",
        "category": "Language",
        "name": "Elegant Variation (Synonym Cycling)",
        "regex": re.compile(
            r"\b(?:catalyst.*partner.*foundation|solution.*framework.*architecture|system.*tool.*platform)\b",
            re.IGNORECASE,
        ),
        "message": "Synonym cycling: Excessive synonym variation across adjacent sentences.",
        "replacement": "Use consistent, canonical naming for technical entities.",
    },
    {
        "id": "T12_FALSE_RANGES",
        "category": "Language",
        "name": "False Ranges",
        "regex": re.compile(
            r"\bfrom\s+[\w\s]+\s+to\s+[\w\s]+,\s+from\s+[\w\s]+\s+to\s+[\w\s]+\b",
            re.IGNORECASE,
        ),
        "message": "False range construction: 'from X to Y, from A to B' on non-scalar dimensions.",
        "replacement": "List the concrete components covered.",
    },
    {
        "id": "T13_PASSIVE_SUBJECTLESS",
        "category": "Language",
        "name": "Passive Voice & Subjectless Fragments",
        "regex": re.compile(
            r"^(?:no\s+(?:configuration|setup|installation)\s+(?:is\s+)?needed|"
            r"the\s+results?\s+(?:are|is)\s+preserved\s+automatically)\.?$",
            re.IGNORECASE | re.M,
        ),
        "message": "Subjectless fragment hiding the active actor or subsystem.",
        "replacement": "Name the active actor (e.g., 'You do not configure X' or 'The guard preserves results').",
    },
    {
        "id": "T14_EM_DASH_OVERUSE",
        "category": "Style",
        "name": "Em Dash (—) Overuse",
        "regex": re.compile(r"[—–]"),
        "message": "Em dash detected in engineering prose: often used to mimic punchy sales copy.",
        "replacement": "Use commas, parentheses, or separate sentences.",
    },
    {
        "id": "T15_OVERUSE_OF_BOLDFACE",
        "category": "Style",
        "name": "Mechanical Boldface Overuse",
        "regex": re.compile(r"\*\*[^*]+\*\*\s*,\s*\*\*[^*]+\*\*\s*,\s*and\s*\*\*[^*]+\*\*"),
        "message": "Mechanical bolding of lists or nouns.",
        "replacement": "Reserve boldface strictly for key metrics, errors, or breaking invariants.",
    },
    {
        "id": "T16_INLINE_HEADER_VERTICAL_LISTS",
        "category": "Style",
        "name": "Inline-Header Vertical Lists",
        "regex": re.compile(r"^\s*[-*]\s+\*\*[A-Z][\w\s]+:\*\*\s+", re.M),
        "message": "Formulaic bullet list with bolded prefix headers and colons.",
        "replacement": "Write a cohesive paragraph or standard table when presenting specifications.",
    },
    {
        "id": "T17_TITLE_CASE_HEADINGS",
        "category": "Style",
        "name": "Title Case in Section Headings",
        "regex": re.compile(r"^#{2,4}\s+[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b", re.M),
        "message": "Title case in section heading: preference for sentence case in technical docs.",
        "replacement": "Use sentence case for headings (e.g. '## Cache invalidation policies').",
    },
    {
        "id": "T18_EMOJIS_IN_ENGINEERING_DOCS",
        "category": "Style",
        "name": "Gratuitous Emojis in Engineering Prose",
        "regex": re.compile(r"[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F900-\U0001F9FF]"),
        "message": "Gratuitous emojis detected in technical discourse.",
        "replacement": "Remove decorative emojis to preserve serious engineering tone.",
    },
    {
        "id": "T19_CURLY_QUOTES",
        "category": "Style",
        "name": "Curly Quotes (Smart Punctuation)",
        "regex": re.compile(r"[“”‘’]"),
        "message": "Curly/smart quotation marks: artifact of word processors or LLM post-processing.",
        "replacement": "Use standard straight ASCII quotes (' or \").",
    },
    {
        "id": "T20_COLLABORATIVE_COMMUNICATION",
        "category": "Communication",
        "name": "Chatbot Preambles & Closers",
        "regex": re.compile(
            r"\b(?:i\s+hope\s+this\s+helps|of\s+course!?|certainly!?|you'?re\s+absolutely\s+right!?|"
            r"would\s+you\s+like\s+me\s+to|let\s+me\s+know\s+if\s+you|here\s+is\s+an?\s+(?:overview|explanation))",
            re.IGNORECASE,
        ),
        "message": "Conversational chatbot artifact leaked into technical deliverable.",
        "replacement": "Delete preamble/closer entirely per Direct Payload Invariant.",
    },
    {
        "id": "T21_KNOWLEDGE_CUTOFF_HEDGING",
        "category": "Communication",
        "name": "Knowledge Cutoff & Incomplete Info Hedging",
        "regex": re.compile(
            r"\b(?:as\s+of\s+my\s+(?:last\s+)?(?:knowledge|training)\s+cutoff|"
            r"while\s+specific\s+details\s+are\s+(?:limited|scarce)|"
            r"based\s+on\s+available\s+information)\b",
            re.IGNORECASE,
        ),
        "message": "Knowledge cutoff disclaimer: LLM hedge rather than verified repo reality.",
        "replacement": "Verify current codebase files or state the verified boundary.",
    },
    {
        "id": "T22_SYCOPHANTIC_TONE",
        "category": "Communication",
        "name": "Sycophantic / Servile Tone",
        "regex": re.compile(
            r"\b(?:great\s+question!?|excellent\s+point!?|that'?s\s+a\s+fantastic\s+idea!?)",
            re.IGNORECASE,
        ),
        "message": "Sycophantic cheerleading phrase.",
        "replacement": "Address the technical merit directly without flattery.",
    },
    {
        "id": "T23_FILLER_PHRASES",
        "category": "Filler",
        "name": "Bloated Filler Phrases",
        "regex": re.compile(
            r"\b(?:in\s+order\s+to|due\s+to\s+the\s+fact\s+that|at\s+this\s+point\s+in\s+time|"
            r"in\s+the\s+event\s+that|it\s+is\s+important\s+to\s+note\s+that|"
            r"has\s+the\s+ability\s+to)\b",
            re.IGNORECASE,
        ),
        "message": "Bloated filler phrase: dilutes technical density.",
        "replacement": "Use concise equivalents ('to', 'because', 'now', 'if', 'the data shows', 'can').",
    },
    {
        "id": "T24_EXCESSIVE_HEDGING",
        "category": "Filler",
        "name": "Excessive Hedging",
        "regex": re.compile(
            r"\b(?:it\s+could\s+(?:potentially|possibly)\s+(?:be\s+argued\s+that)?|"
            r"might\s+perhaps\s+seem\s+to)\b",
            re.IGNORECASE,
        ),
        "message": "Excessive hedging: over-qualification reveals lack of conviction or empirical proof.",
        "replacement": "State the empirical probability or verified behavior directly.",
    },
    {
        "id": "T25_GENERIC_POSITIVE_CONCLUSION",
        "category": "Filler",
        "name": "Generic Upbeat Conclusions",
        "regex": re.compile(
            r"\b(?:the\s+future\s+looks\s+bright|exciting\s+times\s+lie\s+ahead|"
            r"represents\s+a\s+major\s+step\s+in\s+the\s+right\s+direction|"
            r"continues\s+its\s+journey\s+toward\s+excellence)\b",
            re.IGNORECASE,
        ),
        "message": "Generic positive conclusion: hollow upbeat ending.",
        "replacement": "State next concrete milestones or verification criteria.",
    },
    {
        "id": "T26_HYPHENATED_WORD_PAIR_OVERUSE",
        "category": "Filler",
        "name": "Uniform Hyphenated Word Pair Overuse",
        "regex": re.compile(
            r"\b(?:third-party|cross-functional|client-facing|data-driven|decision-making|well-known)\b",
            re.IGNORECASE,
        ),
        "message": "High-frequency uniform hyphenated buzzword pair.",
        "replacement": "Vary usage or write out the specific entity/protocol.",
    },
    {
        "id": "T27_PERSUASIVE_AUTHORITY_TROPES",
        "category": "Filler",
        "name": "Persuasive Authority Tropes",
        "regex": re.compile(
            r"\b(?:the\s+real\s+question\s+is|at\s+its\s+core|what\s+really\s+matters|"
            r"the\s+heart\s+of\s+the\s+matter|fundamentally)\b",
            re.IGNORECASE,
        ),
        "message": "Persuasive authority trope: rhetorical pretense of cutting through noise.",
        "replacement": "Cut the ceremonial framing and state the point directly.",
    },
    {
        "id": "T28_SIGNPOSTING_ANNOUNCEMENTS",
        "category": "Filler",
        "name": "Signposting & Process Announcements",
        "regex": re.compile(
            r"\b(?:let'?s\s+dive\s+in|let'?s\s+explore|let'?s\s+break\s+this\s+down|"
            r"here'?s\s+what\s+you\s+need\s+to\s+know|without\s+further\s+ado)\b",
            re.IGNORECASE,
        ),
        "message": "Signposting announcement: announcing what you are about to do instead of doing it.",
        "replacement": "Transition directly into the payload.",
    },
    {
        "id": "T29_FRAGMENTED_WARMUP_HEADERS",
        "category": "Filler",
        "name": "Fragmented Warmup Headers",
        "regex": re.compile(r"^#{1,4}\s+[^\n]+\n+\s*[A-Z][\w\s]{5,30}\.\n+\s*[A-Z]", re.M),
        "message": "Fragmented warmup header: heading followed by a one-line tautological throat-clearing sentence.",
        "replacement": "Delete the rhetorical warm-up and start directly with the technical content.",
    },
]

# ---------------------------------------------------------------------------
# Vector B: Flattened Soulless Slop & Mechanical Checklists
# ---------------------------------------------------------------------------

PASSIVE_VOICE_INDICATORS = [
    re.compile(r"\b(?:is|are|was|were|been|being)\s+([a-z]+ed)\b", re.IGNORECASE),
    re.compile(r"\b(?:is|are|was|were)\s+(?:calculated|performed|implemented|configured|executed)\s+by\b", re.IGNORECASE),
]

TECHNICAL_STAKES_KEYWORDS = {
    "trade-off", "tradeoff", "latency", "throughput", "concurrency", "race",
    "deadlock", "memory", "leak", "failure", "bottleneck", "rollback",
    "breaking", "regression", "timeout", "jitter", "retry", "idempotency",
    "invariant", "benchmark", "p99", "cpu", "io", "heap", "disk", "cache"
}

# ---------------------------------------------------------------------------
# Scoring Algorithms
# ---------------------------------------------------------------------------

def calculate_sentence_metrics(text: str) -> Tuple[float, float, float]:
    """Calculate mean sentence length, stddev, and passive voice ratio."""
    sentences = [s.strip() for s in _SENTENCE_RE.split(text) if len(_WORD_RE.findall(s)) >= 2]
    if not sentences:
        return 0.0, 0.0, 0.0
    
    lengths = [len(_WORD_RE.findall(s)) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
    stddev_len = math.sqrt(variance)

    passive_count = 0
    for s in sentences:
        if any(p.search(s) for p in PASSIVE_VOICE_INDICATORS):
            passive_count += 1
    passive_ratio = passive_count / len(sentences)

    return mean_len, stddev_len, passive_ratio


def evaluate_tagore_prose(text: str, filename: str = "<input>") -> Dict[str, Any]:
    """
    Execute full 8-dimension Tagore evaluation on engineering text.
    Returns complete metrics, findings, dimension scores, and RFC 9457 problem detail.
    """
    words = _WORD_RE.findall(text)
    word_count = len(words)
    if word_count == 0:
        return {
            "type": "https://antislop.dev/problems/empty-input",
            "title": "Empty Prose Input",
            "status": 400,
            "code": "ERR_TAGORE_EMPTY_INPUT",
            "detail": "Input text contains zero words to audit.",
            "metrics": {},
            "findings": [],
            "remediation": {"action": "NO_ACTION_REQUIRED", "guidance": "Provide non-empty text."}
        }

    mean_sentence_len, stddev_sentence_len, passive_ratio = calculate_sentence_metrics(text)
    empirical_tokens = _EMPIRICAL_TOKEN_RE.findall(text)
    empirical_density = (len(empirical_tokens) / max(1, word_count)) * 100.0

    # Scan for 29 tells
    findings = []
    tells_hit_set = set()
    lines = text.splitlines()

    for idx, line in enumerate(lines, 1):
        for tell in TELLS_CATALOG:
            m = tell["regex"].search(line)
            if m:
                tells_hit_set.add(tell["id"])
                findings.append({
                    "file": filename,
                    "line": idx,
                    "severity": "blocker" if tell["category"] in ("Content", "Communication") else "review",
                    "category": tell["category"],
                    "pattern_id": tell["id"],
                    "rule": tell["name"],
                    "message": tell["message"],
                    "evidence": m.group(0),
                    "suggested_replacement": tell["replacement"],
                })

    catalog_tells_count = len(findings)

    # -----------------------------------------------------------------------
    # Dimension Scoring (1-10 per dimension)
    # -----------------------------------------------------------------------
    # Mechanics (50 pts, floor 35)
    # 1. Directness: Deduct for throat-clearing, signposting, announcements
    directness_penalties = sum(1 for f in findings if f["pattern_id"] in (
        "T20_COLLABORATIVE_COMMUNICATION", "T28_SIGNPOSTING_ANNOUNCEMENTS",
        "T27_PERSUASIVE_AUTHORITY_TROPES", "T29_FRAGMENTED_WARMUP_HEADERS"
    ))
    score_directness = max(1, 10 - min(9, directness_penalties * 3))

    # 2. Rhythm: Sentence length variance (stddev). Varied rhythm = 10, metronomic = low
    if stddev_sentence_len >= 7.0:
        score_rhythm = 10
    elif stddev_sentence_len >= 5.0:
        score_rhythm = 8
    elif stddev_sentence_len >= 3.5:
        score_rhythm = 6
    else:
        score_rhythm = max(2, int(stddev_sentence_len * 1.5))
    if any(f["pattern_id"] == "T14_EM_DASH_OVERUSE" for f in findings):
        score_rhythm = max(1, score_rhythm - 2)

    # 3. Trust: Zero affordance narration, zero hand-holding
    trust_penalties = sum(1 for f in findings if f["pattern_id"] in (
        "T21_KNOWLEDGE_CUTOFF_HEDGING", "T22_SYCOPHANTIC_TONE", "T24_EXCESSIVE_HEDGING"
    ))
    score_trust = max(1, 10 - min(9, trust_penalties * 3))

    # 4. Authenticity: Clean of AI vocabulary, copula avoidance, negative parallelisms
    auth_penalties = sum(1 for f in findings if f["pattern_id"] in (
        "T07_AI_VOCABULARY", "T08_COPULA_AVOIDANCE", "T09_NEGATIVE_PARALLELISM",
        "T10_RULE_OF_THREE", "T11_ELEGANT_VARIATION", "T19_CURLY_QUOTES"
    ))
    score_authenticity = max(1, 10 - min(9, auth_penalties * 2))

    # 5. Density: Free of filler phrases, passive clutter, bolding abuse
    density_penalties = sum(1 for f in findings if f["pattern_id"] in (
        "T23_FILLER_PHRASES", "T13_PASSIVE_SUBJECTLESS", "T15_OVERUSE_OF_BOLDFACE",
        "T16_INLINE_HEADER_VERTICAL_LISTS", "T18_EMOJIS_IN_ENGINEERING_DOCS"
    ))
    if passive_ratio > 0.35:
        density_penalties += 2
    score_density = max(1, 10 - min(9, density_penalties * 2))

    mechanics_subtotal = (
        score_directness + score_rhythm + score_trust +
        score_authenticity + score_density
    )

    # Substance (30 pts, floor 21)
    # 6. Specificity: Empirical density (numbers, versions, files, metrics)
    if empirical_density >= 4.0:
        score_specificity = 10
    elif empirical_density >= 2.5:
        score_specificity = 8
    elif empirical_density >= 1.0:
        score_specificity = 6
    else:
        score_specificity = max(1, int(empirical_density * 4))
    if any(f["pattern_id"] == "T05_VAGUE_ATTRIBUTIONS" for f in findings):
        score_specificity = max(1, score_specificity - 3)

    # 7. Restraint: Actual size, zero puffery or significance inflation
    restraint_penalties = sum(1 for f in findings if f["pattern_id"] in (
        "T01_SIGNIFICANCE_INFLATION", "T02_NOTABILITY_PUFFERY",
        "T04_PROMOTIONAL_VOCABULARY", "T25_GENERIC_POSITIVE_CONCLUSION"
    ))
    score_restraint = max(1, 10 - min(9, restraint_penalties * 3))

    # 8. Technical Voice / POV: Presence of technical stakes, trade-offs, and critical stance
    text_lower = text.lower()
    stakes_hits = sum(1 for kw in TECHNICAL_STAKES_KEYWORDS if kw in text_lower)
    if stakes_hits >= 4:
        score_voice = 10
    elif stakes_hits >= 2:
        score_voice = 8
    elif stakes_hits >= 1:
        score_voice = 6
    else:
        score_voice = 4
    if any(f["pattern_id"] == "T06_FORMULAIC_CHALLENGES" for f in findings):
        score_voice = max(1, score_voice - 2)

    substance_subtotal = score_specificity + score_restraint + score_voice
    total_score = mechanics_subtotal + substance_subtotal

    # Slop-to-Substance Ratio (SSR)
    # (Catalog tells + passive sentence count) / (empirical tokens + stakes count + 1)
    slop_indicators = catalog_tells_count + (passive_ratio * max(1, len(lines)))
    substance_indicators = len(empirical_tokens) + stakes_hits + 1
    ssr = round(slop_indicators / substance_indicators, 2)

    # Discourse Vector classification
    if total_score >= 56 and mechanics_subtotal >= 35 and substance_subtotal >= 21:
        discourse_vector = "clean"
    elif mechanics_subtotal < 35 and substance_subtotal >= 21:
        discourse_vector = "inflated"  # high substance, but slop-shaped
    elif mechanics_subtotal >= 35 and substance_subtotal < 21:
        discourse_vector = "flattened"  # sterile, passive, lacks stakes
    else:
        discourse_vector = "mixed"

    # Verdict determination
    if total_score >= 56 and mechanics_subtotal >= 35 and substance_subtotal >= 21:
        verdict = "PROCEED"
        status_code = 200
        err_code = "NO_TAGORE_FINDINGS" if not findings else "PROCEED_WITH_WARNINGS"
        remediation_action = "NO_ACTION_REQUIRED"
        guidance = "Prose satisfies Tagore substance floors (>=21/30) and mechanics floors (>=35/50)."
    elif mechanics_subtotal >= 35 and substance_subtotal < 21:
        verdict = "REVISE_SUBSTANCE"
        status_code = 422
        err_code = "ERR_TAGORE_SUBSTANCE_FLOOR_FAILED"
        remediation_action = "INJECT_ENGINEERING_SUBSTANCE"
        guidance = (
            f"Clean but soulless: Mechanics passed ({mechanics_subtotal}/50) but Substance failed "
            f"({substance_subtotal}/30 < 21 floor). Inject empirical measurements, exact file paths, "
            f"and explicit engineering trade-offs/failure modes."
        )
    elif substance_subtotal >= 21 and mechanics_subtotal < 35:
        verdict = "REVISE_MECHANICS"
        status_code = 422
        err_code = "ERR_TAGORE_MECHANICS_FLOOR_FAILED"
        remediation_action = "SCRUB_INFLATED_TELLS"
        guidance = (
            f"Substance present but slop-shaped: Substance passed ({substance_subtotal}/30) but Mechanics failed "
            f"({mechanics_subtotal}/50 < 35 floor). Scrub the {catalog_tells_count} catalog tells, "
            f"eliminate copula avoidance, and break participle chains."
        )
    else:
        verdict = "REFUSE"
        status_code = 422
        err_code = "ERR_TAGORE_SCORE_BELOW_THRESHOLD"
        remediation_action = "SCRUB_INFLATED_TELLS"
        guidance = (
            f"Total score {total_score}/80 fell below the 56 pass threshold. Both mechanics and substance "
            f"require fundamental clean-room rewriting."
        )

    metrics = {
        "total_score": total_score,
        "mechanics_subtotal": mechanics_subtotal,
        "substance_subtotal": substance_subtotal,
        "dimensions": {
            "directness": score_directness,
            "rhythm": score_rhythm,
            "trust": score_trust,
            "authenticity": score_authenticity,
            "density": score_density,
            "specificity": score_specificity,
            "restraint": score_restraint,
            "voice": score_voice,
        },
        "discourse_vector": discourse_vector,
        "slop_to_substance_ratio": ssr,
        "passive_voice_ratio": round(passive_ratio, 3),
        "mean_sentence_length": round(mean_sentence_len, 1),
        "sentence_length_stddev": round(stddev_sentence_len, 2),
        "empirical_token_density": round(empirical_density, 2),
        "catalog_tells_count": catalog_tells_count,
        "checklist_violations_count": len([f for f in findings if f["severity"] == "blocker"]),
        "verdict": verdict,
    }

    return {
        "type": "https://antislop.dev/problems/tagore-discourse-deficit",
        "title": "Tagore Engineering Discourse Audit",
        "status": status_code,
        "code": err_code,
        "detail": guidance,
        "instance": filename,
        "metrics": metrics,
        "findings": findings,
        "remediation": {
            "action": remediation_action,
            "guidance": guidance,
        },
    }

# ---------------------------------------------------------------------------
# Repository Voice Profiling
# ---------------------------------------------------------------------------

def profile_voice(sample_text: str) -> Dict[str, Any]:
    """Compute statistical voice profile from authentic sample text."""
    words = _WORD_RE.findall(sample_text)
    word_count = len(words)
    mean_len, stddev_len, passive_ratio = calculate_sentence_metrics(sample_text)
    empirical_tokens = _EMPIRICAL_TOKEN_RE.findall(sample_text)

    commas = sample_text.count(",")
    semicolons = sample_text.count(";")
    dashes = len(re.findall(r"[—–-]", sample_text))

    unique_words = len(set(w.lower() for w in words))
    ttr = round(unique_words / max(1, word_count), 3)

    return {
        "word_count": word_count,
        "mean_sentence_length": round(mean_len, 1),
        "sentence_length_stddev": round(stddev_len, 2),
        "passive_voice_ratio": round(passive_ratio, 3),
        "empirical_token_ratio": round(len(empirical_tokens) / max(1, word_count), 3),
        "comma_density_per_100w": round((commas / max(1, word_count)) * 100, 2),
        "semicolon_density_per_100w": round((semicolons / max(1, word_count)) * 100, 2),
        "dash_density_per_100w": round((dashes / max(1, word_count)) * 100, 2),
        "type_token_ratio": ttr,
    }

# ---------------------------------------------------------------------------
# CLI & Command Runners
# ---------------------------------------------------------------------------

def run_git_diff_prose(base_ref: str = "HEAD") -> str:
    """Extract added prose lines from git diff on markdown, text, and doc files."""
    try:
        cmd = ["git", "diff", base_ref, "--", "*.md", "*.txt", "*.rst", "docs/"]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        added_lines = []
        for line in res.stdout.splitlines():
            if line.startswith("+") and not line.startswith("+++"):
                added_lines.append(line[1:])
        return "\n".join(added_lines)
    except Exception:
        return ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tagore Engineering Discourse & Substance Guard (Anti-Slop Suite)"
    )
    parser.add_argument("--file", "-f", help="Path to markdown/text file to audit")
    parser.add_argument("--text", "-t", help="Inline prose text string to audit")
    parser.add_argument("--base", "-b", help="Git base ref to audit added prose from diff (default: HEAD)")
    parser.add_argument("--stdin", action="store_true", help="Read prose from standard input")
    parser.add_argument("--calibrate", help="Extract and save repository voice profile from sample file")
    parser.add_argument("--profile", action="store_true", help="Display active repository voice profile")
    parser.add_argument("--suggest", action="store_true", help="Output inline deslopped rewrites and suggestions")
    parser.add_argument("--json", action="store_true", help="Output RFC 9457 JSON Problem Details record")
    parser.add_argument("--toon", action="store_true", help="Output TOON formatted record")
    parser.add_argument("--selftest", action="store_true", help="Run internal self-tests and validation")

    args = parser.parse_args()

    if args.selftest:
        # Run self-test
        sample_clean = (
            "The memory leak was caused by un-cleared event listeners in the worker loop. "
            "Under 10k req/s load, resident set size grew by 45MB every 10 minutes. "
            "We replaced the global emitter with an AbortSignal-scoped listener. "
            "Benchmark results in tests/perf_test.rs show memory stabilized at 12MB over 24 hours. "
            "Trade-off: older Node versions without AbortSignal now require polyfills."
        )
        res_clean = evaluate_tagore_prose(sample_clean, "selftest_clean.md")
        assert res_clean["metrics"]["verdict"] == "PROCEED", f"Clean sample failed: {res_clean}"
        assert res_clean["metrics"]["total_score"] >= 56

        sample_slop = (
            "Great question! Here is an overview. I hope this helps!\n"
            "This pull request serves as an enduring testament to the transformative potential of our "
            "groundbreaking architecture, marking a pivotal milestone in our evolving landscape. "
            "It streamlines workflows, enhancing performance while fostering collaboration. "
            "At its core, it's not just about speed, it's about unlocking developer joy. "
            "- **Efficiency:** Performance is maximized.\n"
            "- **Resilience:** Security is strengthened.\n"
            "The future looks bright as we continue our journey toward excellence."
        )
        res_slop = evaluate_tagore_prose(sample_slop, "selftest_slop.md")
        assert res_slop["metrics"]["verdict"] in ("REVISE_MECHANICS", "REVISE_SUBSTANCE", "REFUSE")
        assert res_slop["metrics"]["catalog_tells_count"] >= 5

        print("Self-test passed: Tagore Engineering Discourse Guard operational.")
        return 0

    if args.calibrate:
        if not os.path.exists(args.calibrate):
            sys.stderr.write(f"Error: calibration file '{args.calibrate}' not found.\n")
            return 1
        with open(args.calibrate, "r", encoding="utf-8") as f:
            content = f.read()
        vp = profile_voice(content)
        profile_path = os.path.join(".anti-slop", "voice-profile.json")
        os.makedirs(".anti-slop", exist_ok=True)
        with open(profile_path, "w", encoding="utf-8") as f:
            json.dump(vp, f, indent=2)
        print(f"Calibrated voice profile saved to {profile_path}")
        print(json.dumps(vp, indent=2))
        return 0

    if args.profile:
        profile_path = os.path.join(".anti-slop", "voice-profile.json")
        if os.path.exists(profile_path):
            with open(profile_path, "r", encoding="utf-8") as f:
                print(f.read())
        else:
            print("No voice profile calibrated yet. Run --calibrate <sample-file>.")
        return 0

    # Determine input text
    target_name = "<unspecified>"
    raw_text = ""
    if args.stdin:
        raw_text = sys.stdin.read()
        target_name = "stdin"
    elif args.file:
        if not os.path.exists(args.file):
            sys.stderr.write(f"Error: File '{args.file}' not found.\n")
            return 1
        with open(args.file, "r", encoding="utf-8") as f:
            raw_text = f.read()
        target_name = args.file
    elif args.text:
        raw_text = args.text
        target_name = "inline_text"
    elif args.base:
        raw_text = run_git_diff_prose(args.base)
        target_name = f"git_diff_{args.base}"
    else:
        # Default: check git diff against HEAD
        raw_text = run_git_diff_prose("HEAD")
        target_name = "git_diff_HEAD"

    if not raw_text.strip():
        # Clean diff or empty
        record = {
            "type": "https://antislop.dev/problems/clean",
            "title": "Tagore Engineering Discourse Audit",
            "status": 200,
            "code": "NO_TAGORE_FINDINGS",
            "detail": "Zero prose changes detected or input is clean.",
            "instance": target_name,
            "metrics": {
                "total_score": 80,
                "mechanics_subtotal": 50,
                "substance_subtotal": 30,
                "dimensions": {
                    "directness": 10, "rhythm": 10, "trust": 10, "authenticity": 10,
                    "density": 10, "specificity": 10, "restraint": 10, "voice": 10
                },
                "discourse_vector": "clean",
                "slop_to_substance_ratio": 0.0,
                "passive_voice_ratio": 0.0,
                "mean_sentence_length": 0.0,
                "sentence_length_stddev": 0.0,
                "empirical_token_density": 0.0,
                "catalog_tells_count": 0,
                "checklist_violations_count": 0,
                "verdict": "PROCEED",
            },
            "findings": [],
            "remediation": {"action": "NO_ACTION_REQUIRED", "guidance": "No changes to review."},
        }
    else:
        record = evaluate_tagore_prose(raw_text, target_name)

    if args.json:
        print(json.dumps(record, indent=2))
    elif args.toon:
        m = record["metrics"]
        dims = m.get("dimensions", {})
        print(f"```toon [TagoreDiscourseRecord]\n"
              f"total_score: {m.get('total_score', 0)}/80\n"
              f"mechanics_subtotal: {m.get('mechanics_subtotal', 0)}/50 (floor: 35)\n"
              f"substance_subtotal: {m.get('substance_subtotal', 0)}/30 (floor: 21)\n"
              f"verdict: {m.get('verdict', 'UNKNOWN')}\n"
              f"vector: {m.get('discourse_vector', 'UNKNOWN')}\n"
              f"ssr: {m.get('slop_to_substance_ratio', 0.0)}\n"
              f"findings_count: {len(record.get('findings', []))}\n"
              f"```")
    else:
        m = record["metrics"]
        print(f"\n=======================================================")
        print(f"  Tagore Engineering Discourse & Substance Audit")
        print(f"=======================================================")
        print(f"  Target:            {record['instance']}")
        print(f"  Verdict:           {m['verdict']}")
        print(f"  Total Score:       {m['total_score']}/80  (Pass: >=56)")
        print(f"  Mechanics:         {m['mechanics_subtotal']}/50 (Floor: >=35)")
        print(f"  Substance:         {m['substance_subtotal']}/30 (Floor: >=21)")
        print(f"  Discourse Vector:  {m['discourse_vector'].upper()}")
        print(f"  Slop/Substance:    {m['slop_to_substance_ratio']}")
        print(f"  Catalog Tells:     {m['catalog_tells_count']}")
        print(f"-------------------------------------------------------")
        print(f"  Remediation:       {record['remediation']['action']}")
        print(f"  Guidance:          {record['remediation']['guidance']}")
        print(f"=======================================================\n")

        if record["findings"]:
            print(f"Findings ({len(record['findings'])}):")
            for f in record["findings"][:15]:
                print(f"  [{f['severity'].upper()}] Line {f['line']}: {f['rule']}")
                print(f"    Evidence: \"{f['evidence']}\"")
                if args.suggest:
                    print(f"    Suggestion: {f['suggested_replacement']}")
            if len(record["findings"]) > 15:
                print(f"  ... and {len(record['findings']) - 15} more findings.")

    return 0 if record["metrics"]["verdict"] == "PROCEED" else 1


if __name__ == "__main__":
    sys.exit(main())
