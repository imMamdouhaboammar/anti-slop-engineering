"""Import a bounded DTCG 2025.10 token subset as an unapproved CSS proposal."""

import json
import math
import re

if __package__:
    from .design_policy import PolicyError
else:
    from design_policy import PolicyError

NAME = re.compile(r"[a-z][a-z0-9-]*\Z")
ALIAS = re.compile(r"\{([a-z][a-z0-9.-]*)\}\Z")
SUPPORTED = frozenset({"color", "dimension", "number", "duration", "fontFamily", "fontWeight"})
META = frozenset({"$schema", "$description", "$extensions", "$deprecated", "$type"})
SPACES = frozenset({"srgb", "srgb-linear", "display-p3", "a98-rgb", "prophoto-rgb", "rec2020"})


def require(condition):
    if not condition:
        raise PolicyError("UI_REFERENCE_UNSUPPORTED")


def numeric(value):
    require(type(value) in (int, float) and math.isfinite(value) and abs(value) <= 1000000)
    return format(value, ".15g")


def collect(node, prefix, inherited, leaves, depth=0):
    require(isinstance(node, dict) and depth <= 16 and len(leaves) < 5000)
    kind = node.get("$type", inherited)
    if "$value" in node:
        require(prefix and kind in SUPPORTED and not (set(node) - META - {"$value"}))
        leaves[".".join(prefix)] = (kind, node["$value"])
        return
    for name, child in node.items():
        if name in META:
            continue
        require(NAME.fullmatch(name))
        collect(child, (*prefix, name), kind, leaves, depth + 1)


def css_name(path):
    return "--" + path.replace(".", "-")


def color(value):
    require(isinstance(value, dict) and not (set(value) - {"colorSpace", "components", "alpha", "hex"}))
    space = value.get("colorSpace")
    components = value.get("components")
    alpha = value.get("alpha", 1)
    require(space in SPACES and isinstance(components, list) and len(components) == 3)
    require(type(alpha) in (int, float) and 0 <= alpha <= 1)
    values = " ".join(numeric(component) for component in components)
    return f"color({space} {values} / {numeric(alpha)})"


def dimension(value, units):
    require(isinstance(value, dict) and set(value) == {"value", "unit"} and value["unit"] in units)
    return numeric(value["value"]) + value["unit"]


def font_family(value):
    families = [value] if isinstance(value, str) else value
    require(isinstance(families, list) and 0 < len(families) <= 20)
    for family in families:
        require(
            isinstance(family, str) and 0 < len(family) <= 128 and not any(ord(c) < 32 or c in "\\;{}" for c in family)
        )
    generic = {
        "serif",
        "sans-serif",
        "monospace",
        "cursive",
        "fantasy",
        "system-ui",
        "ui-serif",
        "ui-sans-serif",
        "ui-monospace",
        "ui-rounded",
    }
    return ", ".join(f if f in generic else json.dumps(f, ensure_ascii=False) for f in families)


def primitive(kind, value):
    if kind == "color":
        return color(value)
    if kind == "dimension":
        return dimension(value, {"px", "rem"})
    if kind == "duration":
        return dimension(value, {"ms", "s"})
    if kind == "fontFamily":
        return font_family(value)
    if kind == "fontWeight" and isinstance(value, str):
        weights = {
            "thin": 100,
            "extra-light": 200,
            "light": 300,
            "normal": 400,
            "medium": 500,
            "semi-bold": 600,
            "bold": 700,
            "extra-bold": 800,
            "black": 900,
        }
        require(value in weights)
        value = weights[value]
    if kind == "fontWeight":
        require(type(value) in (int, float) and 1 <= value <= 1000)
    return numeric(value)


def import_tokens(record):
    leaves = {}
    collect(record, (), None, leaves)
    require(bool(leaves))
    names = {path: css_name(path) for path in leaves}
    require(len(set(names.values())) == len(names))
    tokens = {}
    for path, (kind, value) in leaves.items():
        alias = ALIAS.fullmatch(value) if isinstance(value, str) else None
        if alias:
            target = alias.group(1)
            require(target in leaves and leaves[target][0] == kind)
            tokens[names[path]] = f"var({names[target]})"
        else:
            tokens[names[path]] = primitive(kind, value)
    for path in leaves:
        seen = set()
        while isinstance(leaves[path][1], str) and ALIAS.fullmatch(leaves[path][1]):
            require(path not in seen)
            seen.add(path)
            path = ALIAS.fullmatch(leaves[path][1]).group(1)
    return dict(sorted(tokens.items()))
