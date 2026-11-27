"""Signed design policy validation and bounded source checks."""

import re
from pathlib import Path
from urllib.parse import urlsplit

POLICY_PATH = ".anti-slop/design/policy.json"
BASELINE_PREFIX = ".anti-slop/design/baselines/"
IDENTIFIER = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,127}\Z")
PROPERTIES = frozenset(
    {
        "color",
        "background-color",
        "font-family",
        "font-size",
        "font-weight",
        "line-height",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "gap",
        "row-gap",
        "column-gap",
        "border-radius",
        "margin-top",
        "margin-left",
    }
)


class PolicyError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


def require(condition):
    if not condition:
        raise PolicyError("UI_POLICY_INVALID")


def text(value):
    return isinstance(value, str) and 0 < len(value) <= 512 and not any(ord(c) < 32 for c in value)


def number(value, lower, upper):
    return type(value) in (float, int) and lower <= value <= upper


def exact(value, fields):
    return isinstance(value, dict) and set(value) == set(fields)


def distinct(values):
    return isinstance(values, list) and all(text(v) for v in values) and len(values) == len(set(values))


def validate_checks(checks, tokens):
    mandatory = {"min_target", "no_horizontal_overflow", "align", "no_overlap", "computed"}
    require(isinstance(checks, dict) and mandatory <= set(checks) <= mandatory | {"contrast", "keyboard"})
    require(distinct(checks.get("keyboard", [])) and len(checks.get("keyboard", [])) <= 100)
    contrast = checks.get("contrast", [])
    require(isinstance(contrast, list) and len(contrast) <= 100)
    for rule in contrast:
        require(exact(rule, ("foreground", "background", "minimum")))
        require(text(rule["foreground"]) and text(rule["background"]) and number(rule["minimum"], 3, 21))
    require(number(checks["min_target"], 24, 64) and type(checks["no_horizontal_overflow"]) is bool)
    for field in ("align", "no_overlap", "computed"):
        require(isinstance(checks[field], list) and len(checks[field]) <= 100)
    for item in checks["align"]:
        require(exact(item, ("selectors", "edge", "epsilon")))
        require(distinct(item["selectors"]) and 2 <= len(item["selectors"]) <= 20)
        require(item["edge"] in ("left", "right", "top", "bottom") and number(item["epsilon"], 0, 2))
    for item in checks["no_overlap"]:
        require(distinct(item) and len(item) == 2)
    for item in checks["computed"]:
        require(exact(item, ("selector", "property", "token")))
        require(text(item["selector"]) and item["property"] in PROPERTIES and item["token"] in tokens)


def validate_scenario(scenario, manifest):
    require(
        exact(scenario, ("id", "surface", "path", "viewport", "direction", "state", "components", "baseline", "checks"))
    )
    require(text(scenario["id"]) and IDENTIFIER.fullmatch(scenario["id"]))
    require(scenario["surface"] in manifest["surfaces"] and text(scenario["state"]))
    path = scenario["path"]
    require(text(path) and path.startswith("/") and not path.startswith("//") and "\\" not in path)
    parsed = urlsplit(path)
    require(not parsed.netloc and not parsed.scheme and not parsed.fragment)
    viewport = scenario["viewport"]
    require(
        isinstance(viewport, list) and len(viewport) == 2 and all(type(v) is int and 240 <= v <= 4096 for v in viewport)
    )
    require(scenario["direction"] in ("ltr", "rtl"))
    components = scenario["components"]
    require(isinstance(components, dict) and components and set(components) <= set(manifest["components"]))
    for bounds in components.values():
        require(
            isinstance(bounds, list) and len(bounds) == 2 and all(type(v) is int and 0 <= v <= 1000 for v in bounds)
        )
        require(bounds[0] <= bounds[1])
    baseline = scenario["baseline"]
    require(
        text(baseline)
        and baseline.startswith(BASELINE_PREFIX)
        and baseline.endswith(".png")
        and baseline in manifest["artifacts"]
    )
    validate_checks(scenario["checks"], manifest["tokens"])


def validate_extension_policy(policy, manifest):
    extension = policy["extension"]
    require(manifest["schema_version"] == 3)
    require(
        exact(extension, ("id",)) and isinstance(extension["id"], str) and re.fullmatch(r"[a-p]{32}", extension["id"])
    )
    require(policy["browser"]["channel"] == "chromium")
    require(set(manifest["surfaces"]) <= {"popup", "side-panel", "options"})


def validate_policy(policy, manifest):
    try:
        required = {"schema_version", "allowed_classes", "scenarios", "browser"}
        require(isinstance(policy, dict) and required <= set(policy) <= required | {"extension"})
        if "extension" in policy:
            validate_extension_policy(policy, manifest)
        require(type(policy["schema_version"]) is int and policy["schema_version"] == 1)
        require(
            distinct(policy["allowed_classes"])
            and all(not any(c.isspace() for c in v) for v in policy["allowed_classes"])
        )
        browser = policy["browser"]
        require(
            exact(browser, ("channel", "version"))
            and browser["channel"] in ("chrome", "chromium")
            and text(browser["version"])
        )
        scenarios = policy["scenarios"]
        require(isinstance(scenarios, list) and 0 < len(scenarios) <= 100)
        for scenario in scenarios:
            validate_scenario(scenario, manifest)
        require(
            distinct([s["id"].casefold() for s in scenarios])
            and distinct([s["baseline"].casefold() for s in scenarios])
        )
        require({s["surface"] for s in scenarios} == set(manifest["surfaces"]))
        return policy
    except (TypeError, ValueError, KeyError) as exc:
        raise PolicyError("UI_POLICY_INVALID") from exc


# Deliberately lexical. Complex source expressions require owner-signed artifacts or a later AST adapter.
COMPONENT = re.compile(r"<\s*([A-Z][\w]*(?:\.[A-Z][\w]*)*)\b")
ATTRIBUTE = re.compile(r"\b(className|class|style|data-design-component)\s*=\s*")
LITERAL = re.compile(r"""(?:\{\s*)?(["'])(.*?)\1\s*(\})?""", re.S)
JS_COMMENT = re.compile(r"/\*.*?\*/|<!--[\s\S]*?-->")
SPREAD = re.compile(r"\{\s*\.\.\.")


def check_source(content, manifest, policy):
    content = JS_COMMENT.sub("", content)
    allowed = set(manifest["components"])
    if any(component not in allowed for component in COMPONENT.findall(content)):
        raise PolicyError("UI_UNAPPROVED_COMPONENT")
    if SPREAD.search(content):
        raise PolicyError("UI_STYLE_UNVERIFIED")
    for match in ATTRIBUTE.finditer(content):
        attr = match.group(1)
        if attr == "style":
            raise PolicyError("UI_STYLE_UNVERIFIED")
        value = LITERAL.match(content, match.end())
        if value is None or (content[match.end()] == "{" and value.group(3) != "}"):
            raise PolicyError("UI_STYLE_UNVERIFIED")
        literal = value.group(2)
        if attr == "data-design-component":
            if literal not in allowed:
                raise PolicyError("UI_UNAPPROVED_COMPONENT")
        elif not set(literal.split()) <= set(policy["allowed_classes"]):
            raise PolicyError("UI_UNAPPROVED_UTILITY")


def source_kind(path):
    return Path(path).suffix.lower() in {".tsx", ".jsx", ".html", ".vue", ".svelte"}
