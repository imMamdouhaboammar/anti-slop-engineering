"""Direct browser verification of owner-approved design scenarios."""

import hashlib
import re
from collections import Counter
from pathlib import Path
from urllib.parse import urlsplit

if __package__:
    from .contrast_guard import calculate_contrast_ratio
    from .design_policy import PolicyError
else:
    from contrast_guard import calculate_contrast_ratio
    from design_policy import PolicyError

TARGETS = 'button,a[href],input:not([type="hidden"]),select,textarea,[role="button"]'
RGB = re.compile(r"rgb\(\s*(\d+),\s*(\d+),\s*(\d+)\s*\)")
ALIAS = re.compile(r"var\(\s*(--[a-z][a-z0-9-]*)\s*\)")
TIMEOUT = 5000


def ensure(condition, code):
    if not condition:
        raise PolicyError(code)


def one(page, selector, code="UI_GEOMETRY_INVARIANT_FAILED"):
    locator = page.locator(selector)
    ensure(locator.count() == 1 and locator.is_visible(), code)
    return locator


def box(page, selector):
    bounds = one(page, selector).bounding_box(timeout=TIMEOUT)
    ensure(bounds is not None and bounds["width"] > 0 and bounds["height"] > 0, "UI_GEOMETRY_INVARIANT_FAILED")
    return bounds


def edge(bounds, name):
    if name == "right":
        return bounds["x"] + bounds["width"]
    if name == "bottom":
        return bounds["y"] + bounds["height"]
    return bounds["x" if name == "left" else "y"]


def overlaps(a, b):
    return (
        min(edge(a, "right"), edge(b, "right")) > max(a["x"], b["x"]) + 0.5
        and min(edge(a, "bottom"), edge(b, "bottom")) > max(a["y"], b["y"]) + 0.5
    )


def inspect_structure(page, scenario, manifest, policy):
    root = one(page, "[data-design-surface]", "UI_REQUIRED_STATE_MISSING")
    ensure(
        root.get_attribute("data-design-surface") == scenario["surface"]
        and root.get_attribute("data-design-state") == scenario["state"],
        "UI_REQUIRED_STATE_MISSING",
    )
    ensure(
        root.evaluate(
            "(e) => e.checkVisibility({opacityProperty:true, visibilityProperty:true, contentVisibilityAuto:true})"
        )
        and root.evaluate("(e) => getComputedStyle(e).direction") == scenario["direction"],
        "UI_REQUIRED_STATE_MISSING",
    )
    ensure(
        len(page.frames) == 1 and page.locator("iframe,frame,object,embed").count() == 0, "UI_RENDER_EVIDENCE_MISSING"
    )
    tags = page.locator("[data-design-component]").evaluate_all(
        """(es) => es.map(e => [
            e.getAttribute('data-design-component'),
            e.checkVisibility({opacityProperty:true, visibilityProperty:true, contentVisibilityAuto:true}),
            !!e.closest('[data-design-surface]')
        ])"""
    )
    counts = Counter(name for name, visible, inside in tags if visible and inside)
    ensure(
        all(inside and name in manifest["components"] and name in scenario["components"] for name, _, inside in tags),
        "UI_UNAPPROVED_COMPONENT",
    )
    for name, (lower, upper) in scenario["components"].items():
        ensure(lower <= counts[name] <= upper, "UI_COMPONENT_COUNT_MISMATCH")
    classes = page.locator("[class]").evaluate_all("(es) => es.flatMap(e => [...e.classList])")
    ensure(set(classes) <= set(policy["allowed_classes"]), "UI_UNAPPROVED_UTILITY")


def inspect_geometry(page, checks):
    if checks["no_horizontal_overflow"]:
        ensure(page.evaluate("document.documentElement.scrollWidth <= innerWidth + 1"), "UI_GEOMETRY_INVARIANT_FAILED")
    for rule in checks["align"]:
        values = [edge(box(page, selector), rule["edge"]) for selector in rule["selectors"]]
        ensure(max(values) - min(values) <= rule["epsilon"], "UI_GEOMETRY_INVARIANT_FAILED")
    for first, second in checks["no_overlap"]:
        ensure(not overlaps(box(page, first), box(page, second)), "UI_GEOMETRY_INVARIANT_FAILED")


def resolve_token(tokens, name):
    visited = set()
    while name in tokens and name not in visited:
        visited.add(name)
        value = tokens[name]
        alias = ALIAS.fullmatch(value.strip())
        if not alias:
            ensure("var(" not in value, "UI_POLICY_INVALID")
            return value
        name = alias.group(1)
    raise PolicyError("UI_POLICY_INVALID")


def inspect_computed(page, checks, tokens):
    for rule in checks["computed"]:
        locator = one(page, rule["selector"], "UI_COMPUTED_STYLE_MISMATCH")
        expected = resolve_token(tokens, rule["token"])
        matches = locator.evaluate(
            """(el, [property, value]) => {
            if (!CSS.supports(property, value)) return false;
            const actual = getComputedStyle(el).getPropertyValue(property).trim();
            const probe = document.createElement('span');
            probe.style.setProperty('all', 'initial', 'important');
            probe.style.setProperty('position', 'absolute', 'important');
            probe.style.setProperty('visibility', 'hidden', 'important');
            probe.style.setProperty(property, value, 'important');
            el.parentElement.appendChild(probe);
            try { return actual === getComputedStyle(probe).getPropertyValue(property).trim(); }
            finally { probe.remove(); }
        }""",
            [rule["property"], expected],
        )
        ensure(matches, "UI_COMPUTED_STYLE_MISMATCH")


def opaque_rgb(value):
    match = RGB.fullmatch(value)
    ensure(match is not None, "UI_ACCESSIBILITY_FAILED")
    return tuple(int(part) for part in match.groups())


def inspect_accessibility(page, checks):
    targets = page.locator(TARGETS)
    ensure(targets.count() <= 1000, "UI_RENDER_EVIDENCE_MISSING")
    for locator in targets.all():
        if locator.is_visible() and locator.is_enabled():
            rect = locator.bounding_box(timeout=TIMEOUT)
            ensure(
                rect is not None and min(rect["width"], rect["height"]) >= checks["min_target"],
                "UI_ACCESSIBILITY_FAILED",
            )
    for rule in checks.get("contrast", []):
        foreground = one(page, rule["foreground"], "UI_ACCESSIBILITY_FAILED")
        background = one(page, rule["background"], "UI_ACCESSIBILITY_FAILED")
        fg = foreground.evaluate("(e) => getComputedStyle(e).color")
        bg = background.evaluate("(e) => getComputedStyle(e).backgroundColor")
        flat = background.evaluate("(e) => getComputedStyle(e).backgroundImage === 'none'")
        ensure(
            flat and calculate_contrast_ratio(opaque_rgb(fg), opaque_rgb(bg)) >= rule["minimum"],
            "UI_ACCESSIBILITY_FAILED",
        )


def focus_evidence(locator):
    return locator.evaluate(r"""(e) => {
        const s = getComputedStyle(e);
        const visibleColor = value => {
            const canvas = document.createElement('canvas');
            canvas.width = canvas.height = 1;
            const ctx = canvas.getContext('2d');
            ctx.fillStyle = value;
            ctx.fillRect(0, 0, 1, 1);
            return ctx.getImageData(0, 0, 1, 1).data[3] > 0;
        };
        const outline = s.outlineStyle !== 'none' && s.outlineStyle !== 'hidden' &&
            parseFloat(s.outlineWidth) > 0 && visibleColor(s.outlineColor);
        const shadow = s.boxShadow !== 'none' &&
            s.boxShadow.split(/,(?![^(]*\))/).some(layer =>
                [...layer.matchAll(/rgba?\([^)]*\)/g)].some(m => visibleColor(m[0])) &&
                [...layer.matchAll(/(-?[0-9.]+)px/g)].some(m => Number(m[1]) !== 0)
            );
        return {
            focused: e === document.activeElement,
            visible: e.checkVisibility({opacityProperty:true, visibilityProperty:true}),
            outline: outline ? [s.outlineStyle, s.outlineWidth, s.outlineColor, s.outlineOffset].join('|') : '',
            shadow: shadow ? s.boxShadow : ''
        };
    }""")


def inspect_keyboard(page, selectors):
    for selector in selectors:
        locator = one(page, selector, "UI_ACCESSIBILITY_FAILED")
        before = focus_evidence(locator)
        page.keyboard.press("Tab")
        after = focus_evidence(locator)
        ensure(
            after["focused"]
            and after["visible"]
            and any(after[key] and after[key] != before[key] for key in ("outline", "shadow")),
            "UI_ACCESSIBILITY_FAILED",
        )


def inspect_page(page, scenario, manifest, policy):
    inspect_structure(page, scenario, manifest, policy)
    checks = scenario["checks"]
    inspect_geometry(page, checks)
    inspect_computed(page, checks, manifest["tokens"])
    inspect_accessibility(page, checks)


def screenshot_bytes(page):
    page.wait_for_function("document.fonts.status === 'loaded'", timeout=TIMEOUT)
    return page.screenshot(animations="disabled", caret="hide", scale="css", timeout=TIMEOUT)


def screenshot_digest(page):
    return hashlib.sha256(screenshot_bytes(page)).hexdigest()


def compare_screenshot(page, approved_digest):
    actual = screenshot_digest(page)
    ensure(actual == approved_digest, "UI_VISUAL_DRIFT")
    return actual


def checked_origin(origin):
    try:
        parsed = urlsplit(origin)
        ensure(
            parsed.scheme == "http" and parsed.hostname == "127.0.0.1" and parsed.port is not None,
            "UI_RENDER_EVIDENCE_MISSING",
        )
        ensure(
            parsed.netloc == f"127.0.0.1:{parsed.port}"
            and not parsed.path
            and not parsed.query
            and not parsed.fragment,
            "UI_RENDER_EVIDENCE_MISSING",
        )
        return origin
    except ValueError as exc:
        raise PolicyError("UI_RENDER_EVIDENCE_MISSING") from exc


def browser_options(scenario):
    width, height = scenario["viewport"]
    return {
        "viewport": {"width": width, "height": height},
        "device_scale_factor": 1,
        "locale": "en-US",
        "timezone_id": "UTC",
        "reduced_motion": "reduce",
    }


def screenshot_receipt(image, scenario, manifest, output):
    digest = hashlib.sha256(image).hexdigest()
    if output is None:
        ensure(digest == manifest["artifacts"][scenario["baseline"]], "UI_VISUAL_DRIFT")
    else:
        with (output / (scenario["id"] + ".png")).open("xb") as stream:
            stream.write(image)
    return {"id": scenario["id"], "status": "pass", "sha256": digest}


def run_cases(scenarios, capture):
    receipts = []
    for scenario in scenarios:
        try:
            receipts.append(capture(scenario))
        except PolicyError as exc:
            receipts.append({"id": scenario["id"], "status": "block", "reason_code": exc.code})
            break
    return receipts


def playwright_api():
    try:
        from playwright.sync_api import Error, sync_playwright
    except ImportError as exc:
        raise PolicyError("UI_RENDER_EVIDENCE_MISSING") from exc
    return Error, sync_playwright


def capture_scenario(browser, origin, scenario, manifest, policy, output):
    from playwright.sync_api import Error

    context = browser.new_context(**browser_options(scenario), service_workers="block")
    blocked = []

    def route_request(route):
        parsed = urlsplit(route.request.url)
        if f"{parsed.scheme}://{parsed.netloc}" != origin:
            blocked.append(True)
            route.abort()
            return
        response = None
        try:
            response = route.fetch(max_redirects=0, timeout=TIMEOUT)
            if 300 <= response.status < 400:
                blocked.append(True)
                route.abort()
                return
            route.fulfill(response=response)
        except Error:
            # Playwright may report a cancelled request during context shutdown.
            blocked.append(True)
            route.abort()
        finally:
            if response is not None:
                response.dispose()

    try:
        context.route("**/*", route_request)
        context.route_web_socket("**/*", lambda socket: socket.close())
        page = context.new_page()
        url = origin + scenario["path"]
        response = page.goto(url, wait_until="load", timeout=10000)
        ensure(response is not None and response.ok and page.url == url, "UI_RENDER_EVIDENCE_MISSING")
        page.locator("[data-design-surface]").first.wait_for(state="visible", timeout=TIMEOUT)
        inspect_page(page, scenario, manifest, policy)
        image = screenshot_bytes(page)
        inspect_keyboard(page, scenario["checks"].get("keyboard", []))
        ensure(not blocked, "UI_RENDER_EVIDENCE_MISSING")
        return screenshot_receipt(image, scenario, manifest, output)
    finally:
        context.close()


def run_scenarios(origin, manifest, policy, output=None):
    origin = checked_origin(origin)
    Error, sync_playwright = playwright_api()
    try:
        with sync_playwright() as pw:
            channel = policy["browser"]["channel"]
            browser = pw.chromium.launch(channel=None if channel == "chromium" else channel, headless=True)
            try:
                ensure(browser.version == policy["browser"]["version"], "UI_BROWSER_ENVIRONMENT_MISMATCH")
                return run_cases(
                    policy["scenarios"],
                    lambda scenario: capture_scenario(browser, origin, scenario, manifest, policy, output),
                )
            finally:
                browser.close()
    except (Error, OSError) as exc:
        raise PolicyError("UI_RENDER_EVIDENCE_MISSING") from exc
