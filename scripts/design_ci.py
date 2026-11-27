"""Verify an independently signed build fixture without executing candidate build scripts."""

import hashlib
import mimetypes
import re
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

if __package__:
    from . import design_integrity_guard as core
    from .design_runtime import run_scenarios
    from .design_extension import run_extension_scenarios
else:
    import design_integrity_guard as core
    from design_runtime import run_scenarios
    from design_extension import run_extension_scenarios

BUILD_NAMESPACE = "anti-slop-design-build-v1"
COMMIT = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})\Z")
MAX_TOTAL = 200 * core.MAX_RECORD


def require(condition):
    if not condition:
        raise ValueError("Invalid build evidence")


def external(workspace, name):
    path = Path(name)
    require(path.is_absolute() and path.resolve() == path and not path.is_relative_to(workspace))
    return path


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fixture_files(root, expected):
    require(root.is_dir() and isinstance(expected, dict) and 0 < len(expected) <= 5000)
    require(len({name.casefold() for name in expected}) == len(expected))
    actual = set()
    for count, path in enumerate(root.rglob("*")):
        require(count < 10000 and not path.is_symlink() and (path.is_file() or path.is_dir()))
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(expected))
    files = {}
    total = 0
    for name, digest in sorted(expected.items()):
        require(core.valid_digest(digest))
        data = core.read_regular(core.safe_path(root, name), core.MAX_ARTIFACT)
        total += len(data)
        require(total <= MAX_TOTAL and sha(data) == digest)
        files[name] = data
    return files


def verified_build(workspace, args, trust, candidate):
    try:
        root = external(workspace, args.fixture_dir)
        receipt = external(workspace, args.build_receipt)
        key = external(workspace, args.build_key)
        signature = external(workspace, str(receipt) + ".sig")
        require(all(not path.is_relative_to(root) for path in (receipt, key, signature)))
        parts = core.read_regular(key).decode("ascii").split()
        public_key = " ".join(parts[:2])
        require(core.PUBLIC_KEY.fullmatch(public_key) and public_key != trust["public_key"])
        raw = core.read_regular(receipt)
        core.verify_signature(raw, core.read_regular(signature), public_key, namespace=BUILD_NAMESPACE)
        record = core.parse_record(raw)
        require(
            set(record) == {"schema_version", "repository_id", "candidate_sha", "base_sha", "manifest_sha256", "files"}
        )
        require(type(record["schema_version"]) is int and record["schema_version"] == 1)
        require(
            record["repository_id"] == trust["repository_id"] and record["manifest_sha256"] == trust["manifest_sha256"]
        )
        require(all(record[name] == value for name, value in candidate.items()))
        return fixture_files(root, record["files"]), sha(raw)
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as exc:
        raise core.DesignRejection("UI_BUILD_EVIDENCE_INVALID") from exc


def web_fixture(files, manifest, policy):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            name = unquote(urlsplit(self.path).path).lstrip("/")
            if not name or name.endswith("/"):
                name += "index.html"
            if name not in files:
                self.send_error(404)
                return
            data = files[name]
            guessed = mimetypes.guess_type("fixture" + Path(name).suffix.lower())[0] or "application/octet-stream"
            content_type = guessed.replace("\r", "").replace("\n", "")
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *_args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            return run_scenarios(f"http://127.0.0.1:{server.server_port}", manifest, policy)
        finally:
            server.shutdown()
            thread.join(timeout=5)


def extension_fixture(files, manifest, policy):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory).resolve()
        for name, data in files.items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return run_extension_scenarios(root, manifest, policy)


def independent_ci(workspace, args):
    if not COMMIT.fullmatch(args.candidate) or not COMMIT.fullmatch(args.base):
        raise core.DesignRejection("UI_CANDIDATE_UNVERIFIED")
    trust = core.load_trust(workspace, args.trust)
    manifest = core.verify_manifest(workspace, trust)
    if manifest["schema_version"] != 3:
        raise core.DesignRejection("UI_POLICY_INVALID")
    candidate = core.committed_candidate(workspace, manifest, args.base)
    if candidate != {"candidate_sha": args.candidate, "base_sha": args.base}:
        raise core.DesignRejection("UI_CANDIDATE_UNVERIFIED")
    try:
        core.git_output(workspace, ["merge-base", "--is-ancestor", args.base, args.candidate])
    except (OSError, core.subprocess.SubprocessError) as exc:
        raise core.DesignRejection("UI_CANDIDATE_UNVERIFIED") from exc
    core.check_changed_files(workspace, core.changed_paths(workspace, args.base), manifest, trust["non_ui_paths"])
    files, build_digest = verified_build(workspace, args, trust, candidate)
    identity = dict(candidate, build_receipt_sha256=build_digest, manifest_sha256=trust["manifest_sha256"])
    if args.preflight:
        return dict(core.result("UI_INDEPENDENT_PREFLIGHT", True), approved=False, **identity)
    policy = core.read_policy(workspace, manifest)
    receipts = (
        extension_fixture(files, manifest, policy) if "extension" in policy else web_fixture(files, manifest, policy)
    )
    if core.committed_candidate(workspace, manifest, args.base) != candidate:
        raise core.DesignRejection("UI_CANDIDATE_UNVERIFIED")
    failed = next((item for item in receipts if item["status"] != "pass"), None)
    return dict(
        core.result(failed["reason_code"] if failed else "UI_RUNTIME_VERIFIED", not failed),
        approved=not failed,
        scenarios=receipts,
        **identity,
    )
