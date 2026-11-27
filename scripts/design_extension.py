"""Restricted MV3 fixture-page verification in a disposable Chromium profile."""

import base64
import hashlib
import json
import re
import tempfile
from pathlib import Path

if __package__:
    from . import design_runtime as runtime
    from .design_policy import PolicyError
else:
    import design_runtime as runtime
    from design_policy import PolicyError

INVALID = "UI_EXTENSION_INVALID"
ALLOWED_FIELDS = {
    "manifest_version",
    "name",
    "short_name",
    "version",
    "version_name",
    "description",
    "key",
    "permissions",
    "icons",
    "action",
    "side_panel",
    "options_ui",
    "options_page",
}
ENTRY = re.compile(r"[A-Za-z0-9_-]+(?:/[A-Za-z0-9_-]+)*\.html\Z")


def require(condition):
    runtime.ensure(condition, INVALID)


def unique(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def validate_tree(root):
    require(root.is_absolute() and root.resolve() == root and root.is_dir())
    require("," not in str(root))
    total = 0
    for index, path in enumerate(root.rglob("*")):
        require(index < 5000 and not path.is_symlink())
        require(path.is_file() or path.is_dir())
        if path.is_file():
            total += path.stat().st_size
            require(total <= 200 * 1024 * 1024)


def extension_id(metadata):
    key = metadata.get("key")
    require(isinstance(key, str) and len(key) <= 8192)
    der = base64.b64decode(key, validate=True)
    require(der and der[0] == 0x30)
    return hashlib.sha256(der).hexdigest()[:32].translate(str.maketrans("0123456789abcdef", "abcdefghijklmnop"))


def declared_entries(metadata):
    entries = {}
    action = metadata.get("action", {})
    side = metadata.get("side_panel", {})
    options = metadata.get("options_ui", {})
    require(all(isinstance(value, dict) for value in (action, side, options)))
    if "default_popup" in action:
        entries["popup"] = action["default_popup"]
    if "default_path" in side:
        entries["side-panel"] = side["default_path"]
        require("sidePanel" in metadata.get("permissions", []))
    if "page" in options:
        require("options_page" not in metadata)
        entries["options"] = options["page"]
    if "options_page" in metadata:
        entries["options"] = metadata["options_page"]
    return entries


def validate_extension(root, policy):
    try:
        validate_tree(root)
        path = root / "manifest.json"
        require(path.is_file() and path.stat().st_size <= 1024 * 1024)
        metadata = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique)
        require(
            isinstance(metadata, dict) and set(metadata) <= ALLOWED_FIELDS and metadata.get("manifest_version") == 3
        )
        permissions = metadata.get("permissions", [])
        require(isinstance(permissions, list) and set(permissions) <= {"sidePanel"})
        ext_id = extension_id(metadata)
        require(ext_id == policy["extension"]["id"])
        entries = declared_entries(metadata)
        require(bool(entries))
        require(set(entries) == {s["surface"] for s in policy["scenarios"]})
        for surface, name in entries.items():
            require(isinstance(name, str) and ENTRY.fullmatch(name) and (root / name).is_file())
            require(all(s["path"] == "/" + name for s in policy["scenarios"] if s["surface"] == surface))
        return ext_id
    except (OSError, ValueError, TypeError, KeyError, RuntimeError) as exc:
        raise PolicyError(INVALID) from exc


def run_case(pw, root, scenario, origin, manifest, policy, output):
    # Fresh profile and initial page per case; no shared extension storage or
    # background tabs and no viewport resize after page creation.
    with tempfile.TemporaryDirectory(prefix="design-crx-profile-") as profile:
        context = pw.chromium.launch_persistent_context(
            profile,
            channel="chromium",
            headless=True,
            **runtime.browser_options(scenario),
            args=[f"--disable-extensions-except={root}", f"--load-extension={root}"],
        )
        try:
            return verify_case(context, scenario, origin, manifest, policy, output)
        finally:
            context.close()


def verify_case(context, scenario, origin, manifest, policy, output):
    runtime.ensure(
        context.browser is not None and context.browser.version == policy["browser"]["version"],
        "UI_BROWSER_ENVIRONMENT_MISMATCH",
    )
    blocked = []

    def route_request(route):
        if route.request.url.startswith(origin + "/"):
            route.continue_()
        else:
            blocked.append(True)
            route.abort()

    context.route("**/*", route_request)
    context.route_web_socket("**/*", lambda socket: socket.close())
    page = context.pages[0] if context.pages else context.new_page()
    page.bring_to_front()
    url = origin + scenario["path"]
    page.goto(url, wait_until="load", timeout=10000)
    runtime.ensure(page.url == url, "UI_RENDER_EVIDENCE_MISSING")
    page.locator("[data-design-surface]").first.wait_for(state="visible", timeout=runtime.TIMEOUT)
    runtime.inspect_page(page, scenario, manifest, policy)
    page.wait_for_function(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve(true))))",
        timeout=runtime.TIMEOUT,
    )
    image = runtime.screenshot_bytes(page)
    runtime.inspect_keyboard(page, scenario["checks"].get("keyboard", []))
    runtime.ensure(not blocked, "UI_RENDER_EVIDENCE_MISSING")
    return runtime.screenshot_receipt(image, scenario, manifest, output)


def run_extension_scenarios(root, manifest, policy, output=None):
    ext_id = validate_extension(root, policy)
    origin = "chrome-extension://" + ext_id
    Error, sync_playwright = runtime.playwright_api()
    try:
        with sync_playwright() as pw:
            return runtime.run_cases(
                policy["scenarios"], lambda scenario: run_case(pw, root, scenario, origin, manifest, policy, output)
            )
    except (Error, OSError) as exc:
        raise PolicyError("UI_RENDER_EVIDENCE_MISSING") from exc
