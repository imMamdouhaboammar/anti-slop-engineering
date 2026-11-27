#!/usr/bin/env python3
"""Verify an externally approved design manifest and gate structured mutations."""

import argparse
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
from pathlib import Path

if __package__:
    from .design_policy import POLICY_PATH, PolicyError, check_source, source_kind, validate_policy
else:
    from design_policy import POLICY_PATH, PolicyError, check_source, source_kind, validate_policy

TRUST_ENV = "ANTI_SLOP_DESIGN_TRUST"
DIRECTORY = ".anti-slop/design"
MANIFEST = DIRECTORY + "/contract.json"
SIGNATURE = MANIFEST + ".sig"
PROPOSALS = DIRECTORY + "/proposals/"
NAMESPACE = "anti-slop-design-v1"
MAX_RECORD = 1024 * 1024
MAX_ARTIFACT = 50 * MAX_RECORD
DIGEST = re.compile(r"[0-9a-f]{64}\Z")
TOKEN = re.compile(r"--[a-z][a-z0-9-]*\Z")
PUBLIC_KEY = re.compile(r"ssh-ed25519 [A-Za-z0-9+/]+={0,2}\Z")
MESSAGES = {
    "UI_BUILD_EVIDENCE_INVALID": "Independent build receipt or fixture bytes do not match the trusted candidate.",
    "UI_INDEPENDENT_PREFLIGHT": "Candidate and build provenance verified; browser verification has not run.",
    "UI_BUILDER_INVALID": "Builder input, capture files, or proposal destination are invalid.",
    "UI_CONTRACT_MISSING": "No approved manifest. Prepare a proposal and obtain external approval.",
    "UI_TRUST_INVALID": "External trust configuration is absent or invalid.",
    "UI_CONTRACT_INVALID": "Design manifest does not satisfy its versioned contract.",
    "UI_MANIFEST_NOT_APPROVED": "Manifest digest differs from the external approval pin.",
    "UI_SIGNATURE_INVALID": "Manifest signature is missing, invalid, or cannot be verified.",
    "UI_REPOSITORY_MISMATCH": "Manifest repository identity does not match external trust.",
    "UI_ARTIFACT_DRIFT": "An approved artifact is missing, changed, or unsafe to read.",
    "UI_PROTECTED_PATH": "Approval artifacts and enforcement configuration require an external authority.",
    "UI_CANDIDATE_UNVERIFIED": "Strict CI requires a clean candidate commit, complete index, and tracked approval artifacts.",
    "UI_IMPACT_UNKNOWN": "Mutation targets cannot be determined. Use a structured file operation.",
    "UI_NON_UI_PATHS": "All targets are externally approved non-UI paths or proposal files.",
    "UI_CONTRACT_VERIFIED": "Manifest and signed artifacts verified; visual conformance is not certified.",
    "UI_UNAPPROVED_TOKEN": "A CSS token reference, definition, or checked design-property value violates the approved registry.",
    "UI_POLICY_INVALID": "Signed design policy is invalid, incomplete, or references an unsigned baseline.",
    "UI_UNAPPROVED_COMPONENT": "A component is not in the approved component registry.",
    "UI_UNAPPROVED_UTILITY": "A class is not in the approved class registry.",
    "UI_STYLE_UNVERIFIED": "Dynamic or inline styles cannot be proven by the bounded source checker.",
    "UI_RENDER_EVIDENCE_MISSING": "Browser evidence is unavailable or the approved route did not render.",
    "UI_BROWSER_ENVIRONMENT_MISMATCH": "Browser version differs from the approved rendering environment.",
    "UI_REQUIRED_STATE_MISSING": "Required surface, state, or direction is not present.",
    "UI_COMPONENT_COUNT_MISMATCH": "Rendered component counts violate the signed grammar.",
    "UI_GEOMETRY_INVARIANT_FAILED": "Rendered geometry violates an approved layout rule.",
    "UI_COMPUTED_STYLE_MISMATCH": "Computed style differs from an approved design token.",
    "UI_ACCESSIBILITY_FAILED": "A declared target, contrast, or keyboard check failed.",
    "UI_VISUAL_DRIFT": "Rendered screenshot differs from its approved baseline.",
    "UI_RUNTIME_VERIFIED": "All declared browser scenarios and screenshot baselines passed.",
    "UI_CAPTURE_UNAPPROVED": "Browser scenarios captured for review; no approval granted.",
    "UI_REFERENCE_UNSUPPORTED": "Reference is not a supported, unambiguous DTCG token export.",
    "UI_SOURCE_PARSE_FAILED": "Candidate source cannot be parsed by the required AST engine.",
    "UI_PARSER_UNAVAILABLE": "The trusted AST parser or its locked dependencies are unavailable.",
    "UI_EXTENSION_INVALID": "The unpacked extension identity, entry pages, or permissions violate the signed fixture policy.",
    "UI_CONTRACT_VALID": "Manifest structure is valid; approval has not been established.",
}


class DesignRejection(ValueError):
    def __init__(self, code):
        super().__init__(MESSAGES[code])
        self.code = code


def result(code, allowed=False):
    return {
        "schema_version": 1,
        "decision": "allow" if allowed else "block",
        "reason_code": code,
        "message": MESSAGES[code],
    }


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("Duplicate JSON key")
        value[key] = item
    return value


def read_regular(path, limit=MAX_RECORD):
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    with os.fdopen(os.open(path, flags), "rb") as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError("Unsafe file")
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise ValueError("File exceeds limit")
        return data


def parse_record(data):
    record = json.loads(data, object_pairs_hook=unique_object)
    if not isinstance(record, dict):
        raise ValueError("Expected an object")
    return record


def valid_text(value):
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 4096


def string_list(value):
    return isinstance(value, list) and all(valid_text(item) for item in value) and len(set(value)) == len(value)


def valid_token_value(value):
    return (
        valid_text(value)
        and not any(item in value for item in (";", "{", "}", "/*", "*/"))
        and not any(ord(c) < 32 for c in value)
    )


def valid_digest(value):
    return isinstance(value, str) and DIGEST.fullmatch(value) is not None


def canonical_relative(value):
    if not valid_text(value) or "\\" in value or any(ord(c) < 32 for c in value):
        raise ValueError("Invalid relative path")
    path = Path(value)
    if path.is_absolute() or ".." in path.parts or path.as_posix() != value or value == ".":
        raise ValueError("Noncanonical path")
    return value


def safe_path(workspace, relative):
    path = workspace / canonical_relative(relative)
    if path.resolve() != path:
        raise ValueError("Symlink or redirected path")
    return path


def is_proposal(relative):
    return relative.startswith(PROPOSALS) and Path(relative).suffix.lower() in {".json", ".md", ".png"}


def protected(relative):
    folded = relative.casefold()
    if is_proposal(relative):
        return False
    return folded in {
        "product.md",
        "design.md",
        "agents.md",
        ".git",
        ".gitignore",
        ".gitattributes",
        ".github",
        ".anti-slop",
        ".codex",
        ".claude",
        ".agents",
        ".gemini",
        ".cursor",
    } or folded.startswith(
        (
            ".git/",
            ".github/",
            ".codex/",
            ".claude/",
            ".agents/",
            ".gemini/",
            ".cursor/",
            ".anti-slop/",
            "hooks/",
            "scripts/design_integrity_guard.py",
            "scripts/design_policy.py",
            "scripts/design_runtime.py",
            "scripts/design_reference.py",
            "scripts/design_builder.py",
            "scripts/design_ci.py",
            "scripts/design-parser/",
            "scripts/design_extension.py",
            "scripts/exec_guard.py",
            "bin/cli.js",
        )
    )


def load_trust(workspace, trust_path):
    try:
        path = Path(trust_path).expanduser()
        if not path.is_absolute() or path.resolve() != path or path.is_relative_to(workspace):
            raise ValueError("Trust must be external and canonical")
        trust = parse_record(read_regular(path))
        if set(trust) != {"workspace", "repository_id", "manifest_sha256", "public_key", "non_ui_paths"}:
            raise ValueError("Invalid trust fields")
        if trust["workspace"] != str(workspace) or not valid_text(trust["repository_id"]):
            raise ValueError("Wrong workspace")
        if not valid_digest(trust["manifest_sha256"]) or not isinstance(trust["public_key"], str):
            raise ValueError("Invalid approval pin")
        if not PUBLIC_KEY.fullmatch(trust["public_key"]) or not string_list(trust["non_ui_paths"]):
            raise ValueError("Invalid authority or exclusions")
        for relative in trust["non_ui_paths"]:
            if protected(canonical_relative(relative)):
                raise ValueError("Protected path exclusion")
        return trust
    except (OSError, ValueError, RuntimeError, TypeError, RecursionError) as exc:
        raise DesignRejection("UI_TRUST_INVALID") from exc


def validate_manifest(data):
    try:
        manifest = parse_record(data)
        if set(manifest) != {"schema_version", "repository_id", "tokens", "components", "surfaces", "artifacts"}:
            raise ValueError("Invalid manifest fields")
        if type(manifest["schema_version"]) is not int or manifest["schema_version"] not in (1, 2, 3):
            raise ValueError("Unsupported manifest version")
        if not valid_text(manifest["repository_id"]):
            raise ValueError("Invalid repository")
        for field in ("components", "surfaces"):
            if not string_list(manifest[field]) or not manifest[field]:
                raise ValueError("Empty or invalid grammar")
        tokens = manifest["tokens"]
        if (
            not isinstance(tokens, dict)
            or not tokens
            or not all(TOKEN.fullmatch(key) and valid_token_value(value) for key, value in tokens.items())
        ):
            raise ValueError("Invalid token registry")
        artifacts = manifest["artifacts"]
        if not isinstance(artifacts, dict) or not {"PRODUCT.md", "DESIGN.md"}.issubset(artifacts):
            raise ValueError("Missing required artifacts")
        if manifest["schema_version"] >= 2 and POLICY_PATH not in artifacts:
            raise ValueError("Missing signed policy")
        for name, digest in artifacts.items():
            canonical_relative(name)
            if name in {MANIFEST, SIGNATURE} or name.casefold().startswith(PROPOSALS) or not valid_digest(digest):
                raise ValueError("Invalid artifact")
        return manifest
    except (ValueError, TypeError, RecursionError) as exc:
        raise DesignRejection("UI_CONTRACT_INVALID") from exc


def verify_signature(data, signature, public_key, namespace=NAMESPACE):
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            signers = root / "signers"
            signers.write_text("design-owner " + public_key + "\n", encoding="ascii")
            sig = root / "signature"
            sig.write_bytes(signature)
            process = subprocess.run(
                [
                    "ssh-keygen",
                    "-Y",
                    "verify",
                    "-f",
                    str(signers),
                    "-I",
                    "design-owner",
                    "-n",
                    namespace,
                    "-s",
                    str(sig),
                ],
                input=data,
                capture_output=True,
                timeout=10,
                check=False,
            )
            if process.returncode != 0:
                raise ValueError("Signature verification failed")
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        raise DesignRejection("UI_SIGNATURE_INVALID") from exc


def verify_manifest(workspace, trust):
    try:
        data = read_regular(safe_path(workspace, MANIFEST))
    except FileNotFoundError as exc:
        raise DesignRejection("UI_CONTRACT_MISSING") from exc
    except (OSError, ValueError, RuntimeError) as exc:
        raise DesignRejection("UI_CONTRACT_INVALID") from exc
    manifest = validate_manifest(data)
    if manifest["repository_id"] != trust["repository_id"]:
        raise DesignRejection("UI_REPOSITORY_MISMATCH")
    if hashlib.sha256(data).hexdigest() != trust["manifest_sha256"]:
        raise DesignRejection("UI_MANIFEST_NOT_APPROVED")
    try:
        signature = read_regular(safe_path(workspace, SIGNATURE))
    except (OSError, ValueError, RuntimeError) as exc:
        raise DesignRejection("UI_SIGNATURE_INVALID") from exc
    verify_signature(data, signature, trust["public_key"])
    for relative, digest in manifest["artifacts"].items():
        try:
            content = read_regular(safe_path(workspace, relative), MAX_ARTIFACT)
            if not content or hashlib.sha256(content).hexdigest() != digest:
                raise ValueError("Artifact digest mismatch")
        except (OSError, ValueError, RuntimeError) as exc:
            raise DesignRejection("UI_ARTIFACT_DRIFT") from exc
    if manifest["schema_version"] >= 2:
        read_policy(workspace, manifest)
    return manifest


def read_policy(workspace, manifest):
    try:
        data = read_regular(safe_path(workspace, POLICY_PATH))
        if hashlib.sha256(data).hexdigest() != manifest["artifacts"][POLICY_PATH]:
            raise DesignRejection("UI_ARTIFACT_DRIFT")
        return validate_policy(parse_record(data), manifest)
    except DesignRejection:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        raise DesignRejection("UI_POLICY_INVALID") from exc


def relative_targets(workspace, paths):
    try:
        relatives = []
        for target in paths:
            path = Path(target)
            relative = path.relative_to(workspace).as_posix() if path.is_absolute() else target
            if safe_path(workspace, relative).is_dir():
                raise ValueError("Directory mutation cannot be classified")
            relatives.append(relative)
        return relatives
    except (ValueError, OSError, RuntimeError) as exc:
        raise DesignRejection("UI_IMPACT_UNKNOWN") from exc


def check_mutation(workspace, trust_path, operation, paths, pre_tool=True):
    if operation == "read":
        return result("UI_NON_UI_PATHS", True)
    try:
        trust = load_trust(workspace, trust_path)
        if operation != "write" or not paths:
            raise DesignRejection("UI_IMPACT_UNKNOWN")
        relatives = relative_targets(workspace, paths)
        if pre_tool and any(protected(name) for name in relatives):
            raise DesignRejection("UI_PROTECTED_PATH")
        if all(is_proposal(name) for name in relatives):
            return result("UI_NON_UI_PATHS", True)
        non_ui = all(name in trust["non_ui_paths"] or is_proposal(name) for name in relatives)
        if non_ui and not (workspace / MANIFEST).exists() and trust["manifest_sha256"] == "0" * 64:
            return result("UI_NON_UI_PATHS", True)
        manifest = verify_manifest(workspace, trust)
        signed = {name.casefold() for name in manifest["artifacts"]}
        if pre_tool:
            if any(
                name.casefold() == artifact or artifact.startswith(name.casefold() + "/")
                for name in relatives
                for artifact in signed
            ):
                raise DesignRejection("UI_PROTECTED_PATH")
            return result("UI_CONTRACT_VERIFIED", True)
        check_changed_files(workspace, relatives, manifest, trust["non_ui_paths"])
        return result("UI_CONTRACT_VERIFIED", True)
    except (DesignRejection, PolicyError) as exc:
        return result(exc.code)


def check_changed_files(workspace, relatives, manifest, non_ui_paths=()):
    policy = read_policy(workspace, manifest) if manifest["schema_version"] >= 2 else None
    for name in relatives:
        if protected(name) and name not in {MANIFEST, SIGNATURE} and name not in manifest["artifacts"]:
            raise DesignRejection("UI_PROTECTED_PATH")
        if name in manifest["artifacts"] or is_proposal(name):
            continue
        if manifest["schema_version"] == 3:
            check_ast(workspace, name, manifest, policy, non_ui_paths)
            continue
        check_css(workspace, name, manifest["tokens"])
        path = safe_path(workspace, name)
        if not policy or not source_kind(name) or not path.exists():
            continue
        try:
            check_source(read_regular(path, MAX_ARTIFACT).decode("utf-8"), manifest, policy)
        except (OSError, UnicodeError) as exc:
            raise DesignRejection("UI_IMPACT_UNKNOWN") from exc


DATA_MODULE_SUFFIXES = frozenset({".js", ".ts", ".mjs", ".cjs", ".mts", ".cts"})
AST_SUFFIXES = frozenset({".css", ".html", ".htm", ".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs", ".mts", ".cts"})
PARSER = Path(__file__).resolve().parent / "design-parser/check.mjs"


def ast_result(name, source, manifest, policy):
    executable = shutil.which("bun")
    if not executable:
        raise DesignRejection("UI_PARSER_UNAVAILABLE")
    # The launcher and its PATH must be independently trusted. No candidate cwd,
    # imports, env files, auto-install, or inherited JS runtime options.
    env = {"PATH": os.defpath, "LANG": "C.UTF-8"}
    try:
        process = subprocess.run(
            [executable, "--no-install", "--no-env-file", str(PARSER)],
            cwd=PARSER.parent,
            input=json.dumps({"name": name, "source": source, "manifest": manifest, "policy": policy}),
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
            env=env,
        )
        reply = parse_record(process.stdout)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise DesignRejection("UI_PARSER_UNAVAILABLE") from exc
    if reply == {"ok": True}:
        return
    code = reply.get("code")
    if reply.get("ok") is not False or code not in {
        "UI_SOURCE_PARSE_FAILED",
        "UI_STYLE_UNVERIFIED",
        "UI_UNAPPROVED_TOKEN",
        "UI_UNAPPROVED_COMPONENT",
        "UI_UNAPPROVED_UTILITY",
        "UI_IMPACT_UNKNOWN",
    }:
        raise DesignRejection("UI_PARSER_UNAVAILABLE")
    raise DesignRejection(code)


def check_ast(workspace, name, manifest, policy, non_ui_paths):
    try:
        path = safe_path(workspace, name)
        if path.is_dir():
            raise ValueError("Directory is not a source file")
        suffix = path.suffix.lower()
        if name in non_ui_paths and (suffix in DATA_MODULE_SUFFIXES or suffix not in AST_SUFFIXES):
            return
        if suffix not in AST_SUFFIXES:
            raise DesignRejection("UI_IMPACT_UNKNOWN")
        if not path.exists():
            return
        content = read_regular(path, MAX_RECORD).decode("utf-8")
    except DesignRejection:
        raise
    except (OSError, ValueError, RuntimeError) as exc:
        raise DesignRejection("UI_IMPACT_UNKNOWN") from exc
    ast_result(name, content, manifest, policy)


CSS_COMMENT = re.compile(r"/\*.*?\*/", re.S)
CSS_DECLARATION = re.compile(r"(?:^|[;{])\s*([\w-]+)\s*:\s*([^;{}]+)", re.M)
CSS_REFERENCE = re.compile(r"\bvar\(\s*(--[\w-]+)")
CSS_HEX = re.compile(r"#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{4}|[0-9a-fA-F]{3})\b")
CSS_COLOR_FUNCTION = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.I)
CSS_TOKEN_VALUE = re.compile(r"\bvar\(\s*(--[\w-]+)\s*\)", re.I)
CSS_DESIGN_PROPERTY = re.compile(
    r"(?:color|background(?:-color)?|(?:[\w-]+-)?color|fill|stroke|"
    r"(?:margin|padding)(?:-[\w-]+)?|(?:row-|column-)?gap|"
    r"font-(?:family|size|weight)|line-height|letter-spacing|(?:[\w-]+-)?radius|border-radius)"
    r"\Z",
    re.I,
)
CSS_NEUTRAL_VALUES = frozenset(
    {
        "0",
        "auto",
        "none",
        "transparent",
        "currentcolor",
        "inherit",
        "initial",
        "unset",
        "revert",
        "revert-layer",
    }
)


def uses_only_approved_tokens(value, tokens):
    def replace(match):
        return "0" if match.group(1) in tokens else "unapproved-token"

    words = CSS_TOKEN_VALUE.sub(replace, value).lower().split()
    return bool(words) and all(word in CSS_NEUTRAL_VALUES for word in words)


def check_css(workspace, name, tokens):
    path = safe_path(workspace, name)
    if path.suffix.lower() != ".css" or not path.exists():
        return
    try:
        content = CSS_COMMENT.sub("", read_regular(path, MAX_ARTIFACT).decode("utf-8"))
    except (OSError, ValueError) as exc:
        raise DesignRejection("UI_IMPACT_UNKNOWN") from exc
    for reference in CSS_REFERENCE.findall(content):
        if reference not in tokens:
            raise DesignRejection("UI_UNAPPROVED_TOKEN")
    for match in CSS_DECLARATION.finditer(content):
        prop, value = match.groups()
        if prop.startswith("--"):
            if tokens.get(prop) != value.strip():
                raise DesignRejection("UI_UNAPPROVED_TOKEN")
        elif CSS_HEX.search(value) or CSS_COLOR_FUNCTION.search(value):
            raise DesignRejection("UI_UNAPPROVED_TOKEN")
        elif CSS_DESIGN_PROPERTY.fullmatch(prop) and not uses_only_approved_tokens(value, tokens):
            raise DesignRejection("UI_UNAPPROVED_TOKEN")


def git_output(workspace, args):
    return subprocess.run(["git", *args], cwd=workspace, capture_output=True, timeout=20, check=True).stdout


def changed_paths(workspace, base):
    commit = git_output(workspace, ["rev-parse", "--verify", "--end-of-options", base + "^{commit}"]).decode().strip()
    diff = ["diff", "--no-renames", "--no-ext-diff", "--no-textconv", "--name-only", "-z"]

    def paths(args):
        return {os.fsdecode(item) for item in git_output(workspace, args).split(b"\0") if item}

    staged = paths(diff + ["--cached", "--"])
    unstaged = paths(diff + ["--"])
    if staged & unstaged:
        raise DesignRejection("UI_IMPACT_UNKNOWN")
    return sorted(
        paths(diff + [commit, "--"]) | staged | unstaged | paths(["ls-files", "--others", "--exclude-standard", "-z"])
    )


def committed_candidate(workspace, manifest, base):
    try:
        root = Path(os.fsdecode(git_output(workspace, ["rev-parse", "--show-toplevel"])).strip()).resolve()
        if root != workspace:
            raise ValueError("Not the candidate repository root")
        head = git_output(workspace, ["rev-parse", "--verify", "HEAD^{commit}"]).decode().strip()
        base_sha = (
            git_output(workspace, ["rev-parse", "--verify", "--end-of-options", base + "^{commit}"]).decode().strip()
        )
        if git_output(
            workspace, ["status", "--porcelain=v1", "-z", "--untracked-files=all", "--ignore-submodules=none"]
        ):
            raise ValueError("Dirty candidate")
        entries = git_output(workspace, ["ls-files", "-v", "-z"]).split(b"\0")
        if any(entry and entry[:2] != b"H " for entry in entries):
            raise ValueError("Hidden or nonstandard index entry")
        tracked = {os.fsdecode(entry[2:]) for entry in entries if entry}
        if not {MANIFEST, SIGNATURE, *manifest["artifacts"]} <= tracked:
            raise ValueError("Untracked approval artifact")
        return {"candidate_sha": head, "base_sha": base_sha}
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        raise DesignRejection("UI_CANDIDATE_UNVERIFIED") from exc


def discover(workspace):
    raw = git_output(workspace, ["ls-files", "-z", "--cached", "--others", "--exclude-standard"])
    paths = sorted({os.fsdecode(item) for item in raw.split(b"\0") if item and item.lower().endswith(b".css")})
    if len(paths) > 2000:
        raise DesignRejection("UI_IMPACT_UNKNOWN")
    sources = []
    total = 0
    for name in paths:
        path = safe_path(workspace, name)
        if not path.exists():
            continue
        data = read_regular(path, MAX_RECORD)
        total += len(data)
        if total > 20 * MAX_RECORD:
            raise DesignRejection("UI_IMPACT_UNKNOWN")
        tokens = {}
        for match in CSS_DECLARATION.finditer(CSS_COMMENT.sub("", data.decode("utf-8"))):
            prop, value = match.groups()
            if prop.startswith("--"):
                tokens.setdefault(prop, set()).add(value.strip())
        sources.append(
            {
                "path": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "tokens": {key: sorted(values) for key, values in sorted(tokens.items())},
            }
        )
    return {"schema_version": 1, "decision": "allow", "state": "DISCOVERED", "approved": False, "sources": sources}


def proposal(**payload):
    return {"schema_version": 1, "decision": "allow", "state": "PROPOSED", "approved": False, **payload}


def preview(workspace, file=MANIFEST):
    manifest = validate_manifest(read_regular(safe_path(workspace, file)))
    declarations = "\n".join(f"  {name}: {value};" for name, value in sorted(manifest["tokens"].items()))
    return proposal(css=":root {\n" + declarations + "\n}\n")


def browser_command(workspace, args):
    if __package__:
        from .design_runtime import run_scenarios
    else:
        from design_runtime import run_scenarios
    output = None
    candidate = None
    if args.command == "capture":
        manifest = validate_manifest(read_regular(safe_path(workspace, args.file)))
        if manifest["schema_version"] < 2:
            raise DesignRejection("UI_POLICY_INVALID")
        raw = read_regular(safe_path(workspace, args.policy_file))
        if hashlib.sha256(raw).hexdigest() != manifest["artifacts"][POLICY_PATH]:
            raise DesignRejection("UI_ARTIFACT_DRIFT")
        policy = validate_policy(parse_record(raw), manifest)
        output = Path(args.output).expanduser()
        if not output.is_absolute() or output.resolve() != output or output.is_relative_to(workspace):
            raise DesignRejection("UI_PROTECTED_PATH")
        output.mkdir(mode=0o700, exist_ok=False)
    else:
        trust = load_trust(workspace, args.trust)
        manifest = verify_manifest(workspace, trust)
        if manifest["schema_version"] < 2:
            raise DesignRejection("UI_POLICY_INVALID")
        policy = read_policy(workspace, manifest)
        if args.command == "ci":
            if manifest["schema_version"] == 3:
                candidate = committed_candidate(workspace, manifest, args.base)
            base = candidate["base_sha"] if candidate else args.base
            check_changed_files(workspace, changed_paths(workspace, base), manifest, trust["non_ui_paths"])
    if "extension" in policy:
        if not args.extension_dir or args.origin:
            raise DesignRejection("UI_POLICY_INVALID")
        if __package__:
            from .design_extension import run_extension_scenarios
        else:
            from design_extension import run_extension_scenarios
        receipts = run_extension_scenarios(Path(args.extension_dir), manifest, policy, output)
    else:
        if not args.origin or args.extension_dir:
            raise DesignRejection("UI_POLICY_INVALID")
        receipts = run_scenarios(args.origin, manifest, policy, output)
    if candidate and committed_candidate(workspace, manifest, candidate["base_sha"]) != candidate:
        raise DesignRejection("UI_CANDIDATE_UNVERIFIED")
    failed = next((receipt for receipt in receipts if receipt["status"] != "pass"), None)
    if failed:
        report = result(failed["reason_code"])
    else:
        report = result("UI_CAPTURE_UNAPPROVED" if output else "UI_RUNTIME_VERIFIED", True)
    report["approved"] = output is None and not failed
    report["scenarios"] = receipts
    if candidate:
        report.update(candidate)
    return report


def import_reference(workspace, file):
    if __package__:
        from .design_reference import import_tokens
    else:
        from design_reference import import_tokens
    try:
        data = read_regular(safe_path(workspace, file))
        tokens = import_tokens(parse_record(data))
    except (OSError, TypeError, ValueError, RuntimeError, RecursionError) as exc:
        raise DesignRejection("UI_REFERENCE_UNSUPPORTED") from exc
    return proposal(source=file, sha256=hashlib.sha256(data).hexdigest(), tokens=tokens)


def inspect_proposal(workspace, args):
    manifest = validate_manifest(read_regular(safe_path(workspace, args.file)))
    if manifest["schema_version"] != 3:
        raise DesignRejection("UI_POLICY_INVALID")
    policy = validate_policy(parse_record(read_regular(safe_path(workspace, args.policy_file))), manifest)
    paths = sorted(set(args.paths))
    if len(paths) > 2000:
        raise DesignRejection("UI_IMPACT_UNKNOWN")
    findings = []
    for name in paths:
        try:
            if not safe_path(workspace, name).is_file():
                raise DesignRejection("UI_IMPACT_UNKNOWN")
            check_ast(workspace, name, manifest, policy, ())
        except DesignRejection as exc:
            findings.append({"path": name, "reason_code": exc.code})
        except (OSError, ValueError, RuntimeError):
            findings.append({"path": name, "reason_code": "UI_IMPACT_UNKNOWN"})
    report = proposal(
        findings=findings,
        summary={"checked": len(paths), "passed": len(paths) - len(findings), "blocked": len(findings)},
    )
    if findings:
        report["decision"] = "block"
    return report


def build_command(workspace, args):
    if __package__:
        from .design_builder import build
    else:
        from design_builder import build
    try:
        return build(workspace, args.file, args.output, args.capture_dir)
    except (OSError, ValueError, TypeError, RuntimeError, RecursionError, KeyError) as exc:
        code = getattr(exc, "code", "UI_BUILDER_INVALID")
        raise DesignRejection(code if code in MESSAGES else "UI_BUILDER_INVALID") from exc


def browser_transport(parser):
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--origin")
    group.add_argument("--extension-dir")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--trust", default=os.environ.get(TRUST_ENV))
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("verify")
    sub.add_parser("status")
    sub.add_parser("validate").add_argument("--file", default=MANIFEST)
    sub.add_parser("import").add_argument("--file", required=True)
    sub.add_parser("discover")
    sub.add_parser("harvest")
    sub.add_parser("preview").add_argument("--file", default=MANIFEST)
    runtime = sub.add_parser("runtime")
    browser_transport(runtime)
    ci = sub.add_parser("ci")
    browser_transport(ci)
    ci.add_argument("--base", required=True)
    capture = sub.add_parser("capture")
    browser_transport(capture)
    capture.add_argument("--output", required=True)
    capture.add_argument("--file", default=MANIFEST)
    capture.add_argument("--policy-file", default=POLICY_PATH)
    inspect = sub.add_parser("inspect")
    inspect.add_argument("--file", required=True)
    inspect.add_argument("--policy-file", required=True)
    inspect.add_argument("paths", nargs="+")
    independent = sub.add_parser("ci-independent")
    independent.add_argument("--candidate", required=True)
    independent.add_argument("--base", required=True)
    independent.add_argument("--fixture-dir", required=True)
    independent.add_argument("--build-receipt", required=True)
    independent.add_argument("--build-key", required=True)
    independent.add_argument("--preflight", action="store_true")
    builder = sub.add_parser("build")
    builder.add_argument("--file", required=True)
    builder.add_argument("--output", required=True)
    builder.add_argument("--capture-dir")
    check = sub.add_parser("check")
    check.add_argument("paths", nargs="*")
    check.add_argument("--base")
    return parser.parse_args()


def main():
    args = parse_args()
    workspace = Path(args.repo).resolve()
    try:
        if args.command in {"runtime", "ci", "capture"}:
            report = browser_command(workspace, args)
        elif args.command == "ci-independent":
            if __package__:
                from .design_ci import independent_ci
            else:
                from design_ci import independent_ci
            try:
                report = independent_ci(workspace, args)
            except ValueError as exc:
                code = getattr(exc, "code", "UI_BUILD_EVIDENCE_INVALID")
                raise DesignRejection(code if code in MESSAGES else "UI_BUILD_EVIDENCE_INVALID") from exc
        elif args.command == "build":
            report = build_command(workspace, args)
        elif args.command == "inspect":
            report = inspect_proposal(workspace, args)
        elif args.command == "import":
            report = import_reference(workspace, args.file)
        elif args.command in {"discover", "harvest"}:
            report = discover(workspace)
        elif args.command == "preview":
            report = preview(workspace, args.file)
        elif args.command == "validate":
            validate_manifest(read_regular(safe_path(workspace, args.file)))
            report = result("UI_CONTRACT_VALID", True)
        elif args.command == "check":
            paths = args.paths
            if args.base:
                paths += changed_paths(workspace, args.base)
            if args.base and not paths:
                verify_manifest(workspace, load_trust(workspace, args.trust))
                report = result("UI_CONTRACT_VERIFIED", True)
            else:
                report = check_mutation(workspace, args.trust, "write", paths, pre_tool=False)
        else:
            verify_manifest(workspace, load_trust(workspace, args.trust))
            report = result("UI_CONTRACT_VERIFIED", True)
    except (DesignRejection, PolicyError) as exc:
        report = result(exc.code)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError):
        report = result(
            "UI_IMPACT_UNKNOWN" if args.command in {"check", "discover", "harvest"} else "UI_CONTRACT_INVALID"
        )
    print(json.dumps(report))
    return 0 if report["decision"] == "allow" else 2


if __name__ == "__main__":
    raise SystemExit(main())
