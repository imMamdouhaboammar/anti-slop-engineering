#!/usr/bin/env python3
"""StyleSeed Synthesis Engine: Cognitive Grammar, 4-Tier Token DAG, Spatial Rhythm & S1 Drift Guard.

Standard-library zero-dependency Python (>=3.9) implementation.
Audits:
1. Cognitive Job Output Grammars (operations-console, consumer-service, technical-instrument, etc.)
2. 4-Tier Token Layering DAG (Primitive -> Semantic -> Spatial/Type -> Component) & Anti-Leakage
3. 18-Role Semantic Role Graph & 11 Pairwise Mathematical Contrast Gates
4. 6-Role Spatial Rhythm Contract & Spatial Slop (Inversion anomalies, ad-hoc margins)
5. S1 Fifth-Screen Longitudinal Multi-Screen Drift Metric
6. Design Decisions & Exceptions Ledger (Invariants cannot be waived)
7. TOON protocol inter-agent serialization & JSON output
"""

from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCHEMA_VERSION = "1.0.0"

# 12-Axis Cognitive Job Output Grammars
CANONICAL_GRAMMARS = {
    "operations-console": {
        "density": "compact",
        "containment": "bordered",
        "primary_action_dominance": "peer",
        "allowed_control_heights": [28, 32, 36],
        "monospace_numerical_alignment": True,
        "max_border_radius": 6,
    },
    "technical-instrument": {
        "density": "compact",
        "containment": "flat",
        "primary_action_dominance": "subordinate",
        "allowed_control_heights": [28, 32],
        "monospace_numerical_alignment": True,
        "max_border_radius": 4,
    },
    "editorial-reading": {
        "density": "spacious",
        "containment": "flat",
        "primary_action_dominance": "subordinate",
        "allowed_control_heights": [40, 48],
        "monospace_numerical_alignment": False,
        "max_border_radius": 8,
    },
    "commerce-conversion": {
        "density": "balanced",
        "containment": "raised",
        "primary_action_dominance": "singular",
        "allowed_control_heights": [44, 48, 56],
        "monospace_numerical_alignment": False,
        "max_border_radius": 12,
    },
    "consumer-service": {
        "density": "balanced",
        "containment": "raised",
        "primary_action_dominance": "singular",
        "allowed_control_heights": [36, 40, 44],
        "monospace_numerical_alignment": False,
        "max_border_radius": 16,
    },
    "institutional-service": {
        "density": "balanced",
        "containment": "bordered",
        "primary_action_dominance": "singular",
        "allowed_control_heights": [40, 44, 48],
        "monospace_numerical_alignment": False,
        "max_border_radius": 8,
    },
    "expressive-marketing": {
        "density": "spacious",
        "containment": "raised",
        "primary_action_dominance": "singular",
        "allowed_control_heights": [44, 52, 60],
        "monospace_numerical_alignment": False,
        "max_border_radius": 24,
    },
}

# The 18 canonical semantic roles required by the token role graph
CANONICAL_SEMANTIC_ROLES = [
    "background", "surface", "chrome",
    "foreground", "mutedForeground", "chromeForeground", "border",
    "primary", "primaryForeground", "accent", "accentForeground", "focus",
    "success", "successForeground", "warning", "warningForeground", "danger", "dangerForeground",
]

# The 11 Pairwise Mathematical Contrast Gates (WCAG 2.2 AA)
CONTRAST_GATES = [
    ("foreground", "background", 4.5),
    ("mutedForeground", "background", 4.5),
    ("foreground", "surface", 4.5),
    ("chromeForeground", "chrome", 4.5),
    ("primaryForeground", "primary", 4.5),
    ("accentForeground", "accent", 4.5),
    ("successForeground", "success", 4.5),
    ("warningForeground", "warning", 4.5),
    ("dangerForeground", "danger", 4.5),
    ("focus", "background", 3.0),
    ("focus", "surface", 3.0),
]

# The 6 Canonical Spatial Roles
CANONICAL_SPATIAL_ROLES = [
    "pageInset", "sectionGap", "groupGap", "stackGap", "inlineGap", "componentInset"
]

# Regex patterns for token aliases and ad-hoc CSS / Tailwind values
ALIAS_PATTERN = re.compile(r"^\{([^{}]+)\}$|^\$([A-Za-z0-9_.-]+)$")
HEX_COLOR_PATTERN = re.compile(r"^#([0-9A-Fa-f]{3}|[0-9A-Fa-f]{4}|[0-9A-Fa-f]{6}|[0-9A-Fa-f]{8})$")
INLINE_HEX_PATTERN = re.compile(r"#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{8}|[0-9A-Fa-f]{3})\b")
AD_HOC_SPATIAL_CLASS_PATTERN = re.compile(r"\b(m|p|gap|space-[xy])-(\[[0-9]+(\.[0-9]+)?px\])")


def normalize_hex_color(color_str: str) -> Optional[Tuple[float, float, float]]:
    """Convert a hex string to normalized RGB float components in [0.0, 1.0]."""
    if not isinstance(color_str, str):
        return None
    match = HEX_COLOR_PATTERN.match(color_str.strip())
    if not match:
        return None
    digits = match.group(1)
    if len(digits) in (3, 4):
        digits = "".join(d + d for d in digits[:3])
    elif len(digits) == 8:
        digits = digits[:6]
    try:
        r = int(digits[0:2], 16) / 255.0
        g = int(digits[2:4], 16) / 255.0
        b = int(digits[4:6], 16) / 255.0
        return (r, g, b)
    except ValueError:
        return None


def srgb_channel_to_linear(c: float) -> float:
    """Convert sRGB gamma-compressed channel to linear light value."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: Tuple[float, float, float]) -> float:
    """Compute relative luminance according to WCAG 2.2."""
    r_lin = srgb_channel_to_linear(rgb[0])
    g_lin = srgb_channel_to_linear(rgb[1])
    b_lin = srgb_channel_to_linear(rgb[2])
    return 0.2126 * r_lin + 0.7152 * g_lin + 0.0722 * b_lin


def calculate_contrast_ratio(hex1: str, hex2: str) -> float:
    """Calculate the contrast ratio between two hex colors."""
    rgb1 = normalize_hex_color(hex1)
    rgb2 = normalize_hex_color(hex2)
    if not rgb1 or not rgb2:
        return 1.0
    l1 = relative_luminance(rgb1)
    l2 = relative_luminance(rgb2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def color_euclidean_distance(hex1: str, hex2: str) -> float:
    """Compute normalized Euclidean color distance in sRGB space."""
    rgb1 = normalize_hex_color(hex1)
    rgb2 = normalize_hex_color(hex2)
    if not rgb1 or not rgb2:
        return 1.0
    dr = rgb1[0] - rgb2[0]
    dg = rgb1[1] - rgb2[1]
    db = rgb1[2] - rgb2[2]
    return math.sqrt(dr * dr + dg * dg + db * db) / math.sqrt(3.0)


class StyleSeedAuditor:
    """Audits design tokens, spatial rhythm, output grammars, S1 drift, and decisions ledgers."""

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def audit_token_layers(
        self, tokens_data: Dict[str, Any], scan_sources: bool = True
    ) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
        """Audit token dictionary for 4-tier layering DAG and check for source code primitive leakage."""
        summary = {
            "primitive_tokens_count": 0,
            "semantic_tokens_count": 0,
            "spatial_type_tokens_count": 0,
            "component_tokens_count": 0,
            "primitive_leakage_violations_count": 0,
            "circular_alias_violations_count": 0,
            "contrast_gate_violations_count": 0,
        }
        findings: List[Dict[str, Any]] = []

        # Flatten tokens to inspect layers and aliases
        tokens: Dict[str, Any] = {}
        layer_map: Dict[str, str] = {}
        alias_map: Dict[str, str] = {}

        def register_leaf(prefix: str, val: Any):
            tokens[prefix] = val
            if prefix.startswith("primitive.") or prefix.startswith("primitives.") or prefix.startswith("color."):
                layer_map[prefix] = "primitive"
                summary["primitive_tokens_count"] += 1
            elif prefix.startswith("semantic.") or prefix.startswith("semantics."):
                layer_map[prefix] = "semantic"
                summary["semantic_tokens_count"] += 1
            elif prefix.startswith("space.") or prefix.startswith("spacing.") or prefix.startswith("type."):
                layer_map[prefix] = "spatial_type"
                summary["spatial_type_tokens_count"] += 1
            elif prefix.startswith("component.") or prefix.startswith("components."):
                layer_map[prefix] = "component"
                summary["component_tokens_count"] += 1
            else:
                parts = prefix.split(".")
                if len(parts) <= 2:
                    layer_map[prefix] = "primitive"
                    summary["primitive_tokens_count"] += 1
                else:
                    layer_map[prefix] = "semantic"
                    summary["semantic_tokens_count"] += 1

            if isinstance(val, str):
                m = ALIAS_PATTERN.match(val.strip())
                if m:
                    target = (m.group(1) or m.group(2)).strip()
                    alias_map[prefix] = target

        def walk(obj: Any, prefix: str):
            if not isinstance(obj, dict):
                register_leaf(prefix, obj)
                return
            if "$value" in obj or "value" in obj:
                val = obj.get("$value", obj.get("value"))
                register_leaf(prefix, val)
                return

            for k, v in obj.items():
                if k.startswith("$") and k != "$value":
                    continue
                next_prefix = f"{prefix}.{k}" if prefix else k
                walk(v, next_prefix)

        walk(tokens_data, "")

        # Check aliases: prevent circular aliases and upward aliasing
        for src, tgt in alias_map.items():
            src_layer = layer_map.get(src, "unknown")
            # Trace alias chain for cycles
            visited = {src}
            curr = tgt
            while curr in alias_map:
                if curr in visited:
                    summary["circular_alias_violations_count"] += 1
                    findings.append({
                        "id": f"STYLESEED-TOKEN-CIRCULAR-{len(findings)+1}",
                        "class": "UPWARD_CIRCULAR_ALIAS",
                        "severity": "BLOCKING",
                        "evidence": f"Token alias cycle detected: {src} -> {tgt} -> ... -> {curr}",
                        "recommendation": "Remove circular reference in token definition.",
                    })
                    break
                visited.add(curr)
                curr = alias_map[curr]

            tgt_layer = layer_map.get(tgt, "unknown")
            # Semantic token referencing component token is an upward aliasing error
            if src_layer == "semantic" and tgt_layer == "component":
                summary["circular_alias_violations_count"] += 1
                findings.append({
                    "id": f"STYLESEED-TOKEN-UPWARD-{len(findings)+1}",
                    "class": "UPWARD_CIRCULAR_ALIAS",
                    "severity": "BLOCKING",
                    "evidence": f"Upward alias: semantic token '{src}' cannot alias component token '{tgt}'.",
                    "recommendation": "Semantic tokens must only alias primitive tokens.",
                })

        # Check 18 Semantic Role Graph completeness
        semantic_keys = {k.split(".")[-1]: v for k, v in tokens.items() if layer_map.get(k) == "semantic"}
        resolved_roles: Dict[str, str] = {}
        for role in CANONICAL_SEMANTIC_ROLES:
            val = semantic_keys.get(role)
            if not val:
                # Search anywhere in tokens
                matching = [v for k, v in tokens.items() if k.endswith(f".{role}") or k.endswith(f".{role}.base")]
                if matching:
                    val = matching[0]
            if val:
                # If alias, resolve to terminal value
                term = val
                while isinstance(term, str) and term in alias_map:
                    term = tokens.get(alias_map[term], term)
                if isinstance(term, str) and normalize_hex_color(term):
                    resolved_roles[role] = term
            else:
                findings.append({
                    "id": f"STYLESEED-ROLE-MISSING-{len(findings)+1}",
                    "class": "SEMANTIC_ROLE_GRAPH_INCOMPLETE",
                    "severity": "WARNING",
                    "evidence": f"Missing canonical semantic role '{role}' in token graph.",
                    "recommendation": f"Add semantic definition for role '{role}' in theme tokens.",
                })

        # Check 11 Pairwise Mathematical Contrast Gates
        for fg_role, bg_role, min_ratio in CONTRAST_GATES:
            fg_hex = resolved_roles.get(fg_role)
            bg_hex = resolved_roles.get(bg_role)
            if fg_hex and bg_hex:
                ratio = calculate_contrast_ratio(fg_hex, bg_hex)
                if ratio < min_ratio:
                    summary["contrast_gate_violations_count"] += 1
                    findings.append({
                        "id": f"STYLESEED-CONTRAST-DEFICIT-{len(findings)+1}",
                        "class": "PAIRWISE_CONTRAST_DEFICIT",
                        "severity": "BLOCKING",
                        "evidence": f"Semantic contrast deficit: {fg_role} ({fg_hex}) on {bg_role} ({bg_hex}) is {ratio:.2f}:1, requires >={min_ratio}:1.",
                        "recommendation": f"Adjust lightness of {fg_role} or {bg_role} to achieve minimum {min_ratio}:1 contrast ratio.",
                    })

        # Scan component sources for primitive leakage (e.g. hardcoded hex or raw primitive classes)
        if scan_sources and self.project_root.exists():
            for root, _, files in os.walk(self.project_root):
                if any(ignored in root for ignored in [".git", "node_modules", ".anti-slop", "target", "dist"]):
                    continue
                for file_name in files:
                    if file_name.endswith((".tsx", ".jsx", ".vue", ".svelte", ".css")):
                        file_path = Path(root) / file_name
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            continue
                        lines = content.splitlines()
                        for idx, line in enumerate(lines, 1):
                            # Skip comment lines or test files
                            stripped = line.strip()
                            if stripped.startswith("//") or stripped.startswith("/*") or "test" in file_name.lower():
                                continue
                            # Search for raw hex values in styling properties
                            hex_matches = INLINE_HEX_PATTERN.findall(stripped)
                            for hx in hex_matches:
                                # Ignore 000/fff in reset or svg attributes if justified
                                if hx.lower() in ["000", "fff", "000000", "ffffff"]:
                                    continue
                                summary["primitive_leakage_violations_count"] += 1
                                findings.append({
                                    "id": f"STYLESEED-PRIMITIVE-LEAKAGE-{len(findings)+1}",
                                    "file": str(file_path),
                                    "line": idx,
                                    "class": "PRIMITIVE_TOKEN_LEAKAGE",
                                    "severity": "BLOCKING",
                                    "evidence": f"Direct primitive color hex '#{hx}' leaked in component code. Use semantic design tokens instead.",
                                    "recommendation": "Replace hardcoded hex code with semantic CSS variable (e.g. var(--fg-muted) or var(--bg-surface)).",
                                })
                                break

        return summary, findings

    def audit_spatial_rhythm(
        self, spacing_config: Dict[str, Any], scan_sources: bool = True
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Audit spatial roles and detect spatial slop and inversion anomalies."""
        roles_dict = spacing_config.get("roles", {})
        roles_defined = list(roles_dict.keys())
        roles_missing = [r for r in CANONICAL_SPATIAL_ROLES if r not in roles_defined]

        inversions_count = 0
        ad_hoc_count = 0
        findings: List[Dict[str, Any]] = []

        # Check for missing roles
        for missing in roles_missing:
            findings.append({
                "id": f"STYLESEED-SPATIAL-MISSING-{len(findings)+1}",
                "class": "MISSING_SPATIAL_ROLE",
                "severity": "WARNING",
                "evidence": f"Missing canonical spatial role '{missing}' in spacing configuration.",
                "recommendation": f"Define '{missing}' with base/wide responsive dimensions.",
            })

        # Helper to extract numeric pixel value
        def get_pixel_value(val: Any) -> Optional[float]:
            if isinstance(val, (int, float)):
                return float(val)
            if isinstance(val, dict):
                return get_pixel_value(val.get("base"))
            if isinstance(val, str) and val.endswith("px"):
                try:
                    return float(val[:-2])
                except ValueError:
                    return None
            return None

        # Check Inversion Anomalies: stackGap must not exceed sectionGap or groupGap
        stack_val = get_pixel_value(roles_dict.get("stackGap"))
        section_val = get_pixel_value(roles_dict.get("sectionGap"))
        group_val = get_pixel_value(roles_dict.get("groupGap"))

        if stack_val is not None and section_val is not None and stack_val > section_val:
            inversions_count += 1
            findings.append({
                "id": f"STYLESEED-SPATIAL-INVERSION-{len(findings)+1}",
                "class": "SPATIAL_INVERSION_ANOMALY",
                "severity": "BLOCKING",
                "evidence": f"Spatial inversion anomaly: stackGap ({stack_val}px) exceeds sectionGap ({section_val}px). Inner sibling gap cannot exceed outer section gap.",
                "recommendation": "Reduce stackGap or increase sectionGap to preserve visual rhythm hierarchy.",
            })

        if stack_val is not None and group_val is not None and stack_val > group_val:
            inversions_count += 1
            findings.append({
                "id": f"STYLESEED-SPATIAL-INVERSION-{len(findings)+1}",
                "class": "SPATIAL_INVERSION_ANOMALY",
                "severity": "BLOCKING",
                "evidence": f"Spatial inversion anomaly: stackGap ({stack_val}px) exceeds groupGap ({group_val}px).",
                "recommendation": "Align groupGap to be strictly larger than stackGap.",
            })

        # Scan component code for ad-hoc arbitrary spatial classes: e.g. p-[17px], mt-[23px]
        if scan_sources and self.project_root.exists():
            for root, _, files in os.walk(self.project_root):
                if any(ignored in root for ignored in [".git", "node_modules", ".anti-slop"]):
                    continue
                for file_name in files:
                    if file_name.endswith((".tsx", ".jsx", ".html")):
                        file_path = Path(root) / file_name
                        try:
                            content = file_path.read_text(encoding="utf-8", errors="ignore")
                        except Exception:
                            continue
                        lines = content.splitlines()
                        for idx, line in enumerate(lines, 1):
                            if "test" in file_name.lower():
                                continue
                            matches = AD_HOC_SPATIAL_CLASS_PATTERN.findall(line)
                            for match in matches:
                                ad_hoc_count += 1
                                findings.append({
                                    "id": f"STYLESEED-SPATIAL-ADHOC-{len(findings)+1}",
                                    "file": str(file_path),
                                    "line": idx,
                                    "class": "AD_HOC_SPATIAL_SLOP",
                                    "severity": "BLOCKING",
                                    "evidence": f"Ad-hoc arbitrary spatial class '{match[0]}-{match[1]}' found in component. Violates 6-role spatial scale.",
                                    "recommendation": "Replace arbitrary pixel class with canonical spatial role token (pageInset, sectionGap, stackGap, etc.).",
                                })
                                break

        summary = {
            "roles_defined": roles_defined,
            "roles_missing": roles_missing,
            "inversion_anomalies_count": inversions_count,
            "ad_hoc_spacing_violations_count": ad_hoc_count,
        }
        return summary, findings

    def audit_cognitive_grammar(
        self, grammar_name: str, component_metrics: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Verify that UI component composition matches declared output grammar requirements."""
        grammar = CANONICAL_GRAMMARS.get(grammar_name)
        findings: List[Dict[str, Any]] = []

        if not grammar:
            return (
                {
                    "grammar": grammar_name or "unspecified",
                    "density": "balanced",
                    "containment": "flat",
                    "primary_action_dominance": "singular",
                },
                [],
            )

        # Check control heights
        obs_heights = component_metrics.get("observed_control_heights", [])
        allowed_heights = grammar.get("allowed_control_heights", [])
        if obs_heights and allowed_heights:
            for h in obs_heights:
                if h not in allowed_heights:
                    findings.append({
                        "id": f"STYLESEED-GRAMMAR-HEIGHT-{len(findings)+1}",
                        "class": "COGNITIVE_GRAMMAR_MISMATCH",
                        "severity": "WARNING",
                        "evidence": f"Control height {h}px violates grammar '{grammar_name}' allowed heights: {allowed_heights}.",
                        "recommendation": f"Adjust control height to one of {allowed_heights}.",
                    })

        # Check max border radius
        obs_radius = component_metrics.get("observed_border_radius")
        max_radius = grammar.get("max_border_radius")
        if obs_radius is not None and max_radius is not None:
            if obs_radius > max_radius:
                findings.append({
                    "id": f"STYLESEED-GRAMMAR-RADIUS-{len(findings)+1}",
                    "class": "COGNITIVE_GRAMMAR_MISMATCH",
                    "severity": "WARNING",
                    "evidence": f"Border radius {obs_radius}px exceeds grammar '{grammar_name}' maximum allowed radius ({max_radius}px).",
                    "recommendation": f"Reduce border radius to <= {max_radius}px for {grammar_name} coherence.",
                })

        profile = {
            "grammar": grammar_name,
            "density": grammar.get("density", "balanced"),
            "containment": grammar.get("containment", "flat"),
            "primary_action_dominance": grammar.get("primary_action_dominance", "singular"),
        }
        return profile, findings

    def audit_s1_drift(
        self, screen_probes: List[Dict[str, Any]], max_drift_threshold: float = 0.25
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """Compute the S1 fifth-screen longitudinal multi-screen drift metric against Screen 1 baseline."""
        if not screen_probes or len(screen_probes) < 2:
            return (
                {
                    "baseline_screen": screen_probes[0].get("id", "none") if screen_probes else "none",
                    "screens_evaluated_count": len(screen_probes),
                    "max_s1_drift_distance": 0.0,
                    "status": "NOT_EVALUATED",
                },
                [],
            )

        baseline = screen_probes[0]
        baseline_id = baseline.get("id", "screen-1")
        base_accent = baseline.get("accent_color", "#3B82F6")
        base_radius = baseline.get("border_radius", 8)
        base_font = baseline.get("font_family", "sans-serif")
        base_control_h = baseline.get("control_height", 40)

        max_drift = 0.0
        findings: List[Dict[str, Any]] = []

        for idx, screen in enumerate(screen_probes[1:], start=2):
            s_id = screen.get("id", f"screen-{idx}")
            s_accent = screen.get("accent_color", base_accent)
            s_radius = screen.get("border_radius", base_radius)
            s_font = screen.get("font_family", base_font)
            s_control_h = screen.get("control_height", base_control_h)

            # Normalized distance components
            d_color = color_euclidean_distance(base_accent, s_accent)
            d_radius = min(1.0, abs(base_radius - s_radius) / 24.0)
            d_font = 0.0 if base_font.lower() == s_font.lower() else 0.5
            d_height = min(1.0, abs(base_control_h - s_control_h) / 20.0)

            drift_score = 0.4 * d_color + 0.2 * d_radius + 0.2 * d_font + 0.2 * d_height
            max_drift = max(max_drift, drift_score)

            if drift_score > max_drift_threshold:
                findings.append({
                    "id": f"STYLESEED-S1-DRIFT-{len(findings)+1}",
                    "class": "S1_LONGITUDINAL_DRIFT_EXCEEDED",
                    "severity": "BLOCKING",
                    "evidence": f"Screen '{s_id}' S1 longitudinal drift index ({drift_score:.3f}) exceeds threshold ({max_drift_threshold:.3f}) compared to baseline '{baseline_id}'.",
                    "recommendation": f"Re-anchor '{s_id}' tokens and geometry to baseline '{baseline_id}' design choices.",
                })

        summary = {
            "baseline_screen": baseline_id,
            "screens_evaluated_count": len(screen_probes),
            "max_s1_drift_distance": round(max_drift, 4),
            "status": "DRIFTING" if any(f["severity"] == "BLOCKING" for f in findings) else "ANCHORED",
        }
        return summary, findings

    def audit_decisions_ledger(
        self, ledger_data: Dict[str, Any]
    ) -> Tuple[Dict[str, int], List[Dict[str, Any]]]:
        """Audit decisions ledger and enforce: Exceptions NEVER waive Invariants."""
        decisions = ledger_data.get("decisions", [])
        decisions_count = 0
        approved_exceptions_count = 0
        invalid_exceptions_count = 0
        invariant_waive_count = 0
        findings: List[Dict[str, Any]] = []

        for entry in decisions:
            d_id = entry.get("id", "D-UNKNOWN")
            kind = entry.get("kind", "decision")
            rule = entry.get("rule", "")
            target_axis = entry.get("axis", "")

            if kind == "decision":
                decisions_count += 1
            elif kind == "exception":
                # INVARIANT: Exceptions NEVER apply to invariants (INV-*)
                if rule.startswith("INV-") or "invariant" in rule.lower():
                    invariant_waive_count += 1
                    invalid_exceptions_count += 1
                    findings.append({
                        "id": f"STYLESEED-DECISION-WAIVER-{len(findings)+1}",
                        "class": "ILLEGAL_INVARIANT_WAIVER",
                        "severity": "BLOCKING",
                        "evidence": f"Decision exception '{d_id}' attempts to waive invariant rule '{rule}'. Exceptions can only waive catalog default craft rules.",
                        "recommendation": "Invariants bind unconditionally. Remove exception against invariant.",
                    })
                    continue

                # An exception must have a scope
                scope = entry.get("scope", {})
                if not scope or (not scope.get("screens") and not scope.get("artifacts")):
                    invalid_exceptions_count += 1
                    findings.append({
                        "id": f"STYLESEED-DECISION-UNSCOPED-{len(findings)+1}",
                        "class": "UNSCOPED_DECISION_EXCEPTION",
                        "severity": "WARNING",
                        "evidence": f"Decision exception '{d_id}' has no explicit screen or artifact scope.",
                        "recommendation": "Scope exception to named screens or artifacts (e.g. scope: { screens: ['billing'] }).",
                    })
                else:
                    approved_exceptions_count += 1

        summary = {
            "decisions_count": decisions_count,
            "approved_exceptions_count": approved_exceptions_count,
            "invalid_exceptions_count": invalid_exceptions_count,
            "invariant_waive_attempts_count": invariant_waive_count,
        }
        return summary, findings


def generate_toon_payload(report: Dict[str, Any]) -> str:
    """Serialize the audit report into the TOON protocol for inter-agent handoff."""
    lines = [
        f"styleseed-audit[v{report['schema_version']}]:",
        f"  verdict: {report['verdict']}",
        f"  grammar: {report['grammar_profile'].get('grammar', 'unspecified')} (density: {report['grammar_profile'].get('density')})",
        f"  token-layers: {{ primitive: {report['token_layers_summary']['primitive_tokens_count']}, semantic: {report['token_layers_summary']['semantic_tokens_count']}, contrast-deficits: {report['token_layers_summary']['contrast_gate_violations_count']}, leakage: {report['token_layers_summary']['primitive_leakage_violations_count']} }}",
        f"  spatial-rhythm: {{ roles: {len(report['spatial_rhythm_summary']['roles_defined'])}, inversions: {report['spatial_rhythm_summary']['inversion_anomalies_count']}, ad-hoc: {report['spatial_rhythm_summary']['ad_hoc_spacing_violations_count']} }}",
        f"  s1-drift: {{ status: {report['s1_drift_summary']['status']}, max-dist: {report['s1_drift_summary']['max_s1_drift_distance']} }}",
        f"  decisions-ledger: {{ decisions: {report['decisions_ledger_summary']['decisions_count']}, approved-exceptions: {report['decisions_ledger_summary']['approved_exceptions_count']}, invalid-exceptions: {report['decisions_ledger_summary']['invalid_exceptions_count']} }}",
        f"  findings-count: [{report['findings_count']}]",
    ]
    for idx, f in enumerate(report["findings"][:10], start=1):
        lines.append(f"    finding[{idx}]: {f['severity']} {f['class']} -> {f['evidence']}")
    return "\n".join(lines)


def run_selftest() -> None:
    """Hermetic self-test validating all StyleSeed guard features."""
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        auditor = StyleSeedAuditor(root)

        # 1. Test clean tokens
        clean_tokens = {
            "primitive": {
                "color": {
                    "slate": { "900": "#0F172A", "500": "#64748B", "100": "#F1F5F9" },
                    "blue": { "600": "#2563EB", "50": "#EFF6FF" },
                }
            },
            "semantic": {
                "background": "#FFFFFF",
                "surface": "#F8FAFC",
                "chrome": "#E2E8F0",
                "foreground": "#0F172A",
                "mutedForeground": "#64748B",
                "chromeForeground": "#0F172A",
                "border": "#CBD5E1",
                "primary": "#2563EB",
                "primaryForeground": "#FFFFFF",
                "accent": "#2563EB",
                "accentForeground": "#FFFFFF",
                "focus": "#2563EB",
                "success": "#15803D",
                "successForeground": "#FFFFFF",
                "warning": "#B45309",
                "warningForeground": "#FFFFFF",
                "danger": "#DC2626",
                "dangerForeground": "#FFFFFF",
            }
        }
        token_sum, token_find = auditor.audit_token_layers(clean_tokens, scan_sources=False)
        assert token_sum["primitive_tokens_count"] == 5
        assert token_sum["semantic_tokens_count"] == 18
        assert token_sum["contrast_gate_violations_count"] == 0

        # 2. Test contrast deficit
        deficit_tokens = {
            "semantic": {
                "background": "#FFFFFF",
                "foreground": "#E2E8F0", # Low contrast against white!
            }
        }
        _, def_find = auditor.audit_token_layers(deficit_tokens, scan_sources=False)
        assert any(f["class"] == "PAIRWISE_CONTRAST_DEFICIT" for f in def_find)

        # 3. Test spatial inversion anomaly
        inverted_spacing = {
            "roles": {
                "sectionGap": 16,
                "stackGap": 32, # stackGap > sectionGap!
            }
        }
        sp_sum, sp_find = auditor.audit_spatial_rhythm(inverted_spacing, scan_sources=False)
        assert sp_sum["inversion_anomalies_count"] == 1
        assert any(f["class"] == "SPATIAL_INVERSION_ANOMALY" for f in sp_find)

        # 4. Test decisions ledger: rejecting invariant waiver
        illegal_ledger = {
            "decisions": [
                {
                    "id": "D-001",
                    "kind": "exception",
                    "rule": "INV-04-controls-operable",
                    "statement": "Waiving button hit targets on mobile",
                    "scope": { "screens": ["home"] }
                }
            ]
        }
        dec_sum, dec_find = auditor.audit_decisions_ledger(illegal_ledger)
        assert dec_sum["invariant_waive_attempts_count"] == 1
        assert any(f["class"] == "ILLEGAL_INVARIANT_WAIVER" for f in dec_find)

        # 5. Test S1 drift metric
        probes = [
            { "id": "screen-1", "accent_color": "#2563EB", "border_radius": 8, "font_family": "Inter", "control_height": 40 },
            { "id": "screen-2", "accent_color": "#2563EB", "border_radius": 8, "font_family": "Inter", "control_height": 40 },
            { "id": "screen-5", "accent_color": "#F43F5E", "border_radius": 24, "font_family": "Comic Sans", "control_height": 60 },
        ]
        s1_sum, s1_find = auditor.audit_s1_drift(probes, max_drift_threshold=0.20)
        assert s1_sum["status"] == "DRIFTING"
        assert any(f["class"] == "S1_LONGITUDINAL_DRIFT_EXCEEDED" for f in s1_find)

    print("PASS: StyleSeed guard selftest green.")


def evaluate_styleseed(
    project_root: Path,
    tokens_path: Optional[Path] = None,
    spacing_path: Optional[Path] = None,
    grammar_name: str = "unspecified",
    screens_path: Optional[Path] = None,
    decisions_path: Optional[Path] = None,
    scan_sources: bool = True,
) -> Dict[str, Any]:
    """Execute full StyleSeed evaluation across tokens, spatial rhythm, grammar, S1 drift, and decisions."""
    auditor = StyleSeedAuditor(project_root)
    all_findings: List[Dict[str, Any]] = []

    # 1. Tokens
    tokens_data: Dict[str, Any] = {}
    if tokens_path and tokens_path.exists():
        try:
            tokens_data = json.loads(tokens_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    token_sum, token_find = auditor.audit_token_layers(tokens_data, scan_sources=scan_sources)
    all_findings.extend(token_find)

    # 2. Spacing
    spacing_data: Dict[str, Any] = {}
    if spacing_path and spacing_path.exists():
        try:
            spacing_data = json.loads(spacing_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    spatial_sum, spatial_find = auditor.audit_spatial_rhythm(spacing_data, scan_sources=scan_sources)
    all_findings.extend(spatial_find)

    # 3. Grammar
    grammar_prof, grammar_find = auditor.audit_cognitive_grammar(grammar_name, {})
    all_findings.extend(grammar_find)

    # 4. S1 Drift
    screen_probes: List[Dict[str, Any]] = []
    if screens_path and screens_path.exists():
        try:
            screen_probes = json.loads(screens_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    s1_sum, s1_find = auditor.audit_s1_drift(screen_probes)
    all_findings.extend(s1_find)

    # 5. Decisions Ledger
    decisions_data: Dict[str, Any] = {}
    if decisions_path and decisions_path.exists():
        try:
            decisions_data = json.loads(decisions_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    dec_sum, dec_find = auditor.audit_decisions_ledger(decisions_data)
    all_findings.extend(dec_find)

    # Compute verdict
    verdict = "PROCEED"
    if any(f["severity"] == "BLOCKING" for f in all_findings):
        verdict = "REJECT"
    elif all_findings:
        verdict = "WARNING"

    report = {
        "schema_version": SCHEMA_VERSION,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "verdict": verdict,
        "grammar_profile": grammar_prof,
        "token_layers_summary": token_sum,
        "spatial_rhythm_summary": spatial_sum,
        "s1_drift_summary": s1_sum,
        "decisions_ledger_summary": dec_sum,
        "findings_count": len(all_findings),
        "findings": all_findings,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="StyleSeed Cognitive Grammar, Token Canon DAG & Spatial Rhythm Guard."
    )
    parser.add_argument("--scan", type=str, default=".", help="Root directory to scan for components")
    parser.add_argument("--tokens", type=str, help="Path to tokens.json (DTCG or Tokens Studio)")
    parser.add_argument("--spacing", type=str, help="Path to spacing config JSON")
    parser.add_argument("--grammar", type=str, default="unspecified", help="Output grammar name (e.g. operations-console)")
    parser.add_argument("--screens", type=str, help="Path to screen probes JSON for S1 drift calculation")
    parser.add_argument("--decisions", type=str, help="Path to design decisions ledger JSON")
    parser.add_argument("--no-scan-sources", action="store_true", help="Skip scanning source code for primitive leakage")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON")
    parser.add_argument("--toon", action="store_true", help="Output TOON protocol payload for inter-agent handoff")
    parser.add_argument("--strict", action="store_true", help="Treat WARNING as REJECT (exit code 1)")
    parser.add_argument("--selftest", action="store_true", help="Run hermetic self-test")

    args = parser.parse_args()

    if args.selftest:
        run_selftest()
        return 0

    root = Path(args.scan).resolve()
    tokens_p = Path(args.tokens).resolve() if args.tokens else None
    spacing_p = Path(args.spacing).resolve() if args.spacing else None
    screens_p = Path(args.screens).resolve() if args.screens else None
    decisions_p = Path(args.decisions).resolve() if args.decisions else None

    report = evaluate_styleseed(
        project_root=root,
        tokens_path=tokens_p,
        spacing_path=spacing_p,
        grammar_name=args.grammar,
        screens_path=screens_p,
        decisions_path=decisions_p,
        scan_sources=not args.no_scan_sources,
    )

    if args.json:
        print(json.dumps(report, indent=2))
    elif args.toon:
        print(generate_toon_payload(report))
    else:
        print(f"StyleSeed Guard Verdict: {report['verdict']}")
        print(f"Grammar: {report['grammar_profile'].get('grammar', 'unspecified')}")
        print(f"Token Layers: {report['token_layers_summary']['primitive_tokens_count']} primitives, {report['token_layers_summary']['semantic_tokens_count']} semantic")
        print(f"Spatial Rhythm Inversions: {report['spatial_rhythm_summary']['inversion_anomalies_count']}")
        print(f"S1 Drift: {report['s1_drift_summary']['status']} (max: {report['s1_drift_summary']['max_s1_drift_distance']})")
        print(f"Decisions / Exceptions: {report['decisions_ledger_summary']['decisions_count']} decisions, {report['decisions_ledger_summary']['approved_exceptions_count']} exceptions")
        print(f"Total Findings: {report['findings_count']}")
        for f in report["findings"][:15]:
            print(f"  [{f['severity']}] {f['class']}: {f['evidence']}")

    if report["verdict"] == "REJECT" or (args.strict and report["verdict"] == "WARNING"):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
