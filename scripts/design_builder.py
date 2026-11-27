"""Build deterministic, unsigned review packages from explicit design inputs."""

import hashlib
import json
import shutil
import struct
import zlib
from pathlib import Path

if __package__:
    from . import design_integrity_guard as core
    from .design_policy import BASELINE_PREFIX, IDENTIFIER, POLICY_PATH, validate_policy
    from .design_reference import import_tokens
else:
    import design_integrity_guard as core
    from design_policy import BASELINE_PREFIX, IDENTIFIER, POLICY_PATH, validate_policy
    from design_reference import import_tokens

REQUIRED = {
    "schema_version",
    "repository_id",
    "token_file",
    "components",
    "surfaces",
    "allowed_classes",
    "browser",
    "artifacts",
    "scenarios",
}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_CAPTURE_TOTAL = 100 * core.MAX_RECORD


def require(condition):
    if not condition:
        raise ValueError("Invalid builder input")


def encoded(value):
    data = (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")
    require(len(data) <= core.MAX_RECORD)
    return data


def digest(data):
    return hashlib.sha256(data).hexdigest()


def output_path(workspace, relative):
    path = core.safe_path(workspace, relative)
    parent = workspace / core.PROPOSALS
    require(path.parent == parent and IDENTIFIER.fullmatch(path.name))
    require(parent.is_dir() and not path.exists())
    return path


def read_spec(workspace, relative):
    data = core.read_regular(core.safe_path(workspace, relative))
    spec = core.parse_record(data)
    require(REQUIRED <= set(spec) <= REQUIRED | {"extension"})
    require(type(spec["schema_version"]) is int and spec["schema_version"] == 1)
    require(isinstance(spec["token_file"], str))
    require(core.string_list(spec["artifacts"]) and len(spec["artifacts"]) <= 100)
    require(isinstance(spec["scenarios"], list) and 0 < len(spec["scenarios"]) <= 100)
    return spec, data


def artifact_hashes(workspace, spec):
    names = set(spec["artifacts"]) | {"PRODUCT.md", "DESIGN.md", spec["token_file"]}
    hashes = {}
    total = 0
    for name in sorted(names):
        require(name.casefold() in {"product.md", "design.md"} or not core.protected(name))
        require(
            not name.casefold().startswith(core.PROPOSALS)
            and name.casefold() not in {core.MANIFEST, core.SIGNATURE, POLICY_PATH}
        )
        data = core.read_regular(core.safe_path(workspace, name), core.MAX_ARTIFACT)
        total += len(data)
        require(data and total <= MAX_CAPTURE_TOTAL)
        hashes[name] = digest(data)
    return hashes


def policy_for(spec):
    scenarios = []
    for item in spec["scenarios"]:
        require(isinstance(item, dict) and "baseline" not in item)
        identifier = item.get("id")
        require(isinstance(identifier, str) and IDENTIFIER.fullmatch(identifier))
        scenarios.append(dict(item, baseline=BASELINE_PREFIX + identifier + ".png"))
    require(len({item["id"].casefold() for item in scenarios}) == len(scenarios))
    policy = {
        "schema_version": 1,
        "allowed_classes": spec["allowed_classes"],
        "browser": spec["browser"],
        "scenarios": scenarios,
    }
    if "extension" in spec:
        policy["extension"] = spec["extension"]
    return policy


def validate_png(data, viewport):
    """Check PNG framing, checksums and dimensions; not pixel provenance."""
    require(len(data) >= 33 and data.startswith(PNG_MAGIC))
    require(data[8:16] == b"\0\0\0\rIHDR" and list(struct.unpack(">II", data[16:24])) == viewport)
    offset = 8
    saw_data = False
    while offset + 12 <= len(data):
        length = struct.unpack_from(">I", data, offset)[0]
        end = offset + length + 12
        require(end <= len(data))
        kind = data[offset + 4 : offset + 8]
        require(zlib.crc32(data[offset + 4 : end - 4]) == struct.unpack_from(">I", data, end - 4)[0])
        require(kind != b"IHDR" or offset == 8)
        saw_data = saw_data or (kind == b"IDAT" and length > 0)
        if kind == b"IEND":
            require(length == 0 and saw_data and end == len(data))
            return
        offset = end
    raise ValueError("Incomplete PNG")


def captured_images(workspace, capture_dir, scenarios):
    if capture_dir is None:
        return {}
    root = Path(capture_dir)
    require(root.is_absolute() and root.resolve() == root and root.is_dir() and not root.is_relative_to(workspace))
    expected = {item["id"] + ".png" for item in scenarios}
    require({path.name for path in root.iterdir()} == expected)
    images = {}
    total = 0
    for item in scenarios:
        name = item["id"] + ".png"
        data = core.read_regular(core.safe_path(root, name), core.MAX_ARTIFACT)
        total += len(data)
        require(total <= MAX_CAPTURE_TOTAL)
        validate_png(data, item["viewport"])
        images[name] = data
    return images


def write_package(path, files):
    # Reserve a new directory; never replace an existing proposal.
    path.mkdir(mode=0o700, exist_ok=False)
    try:
        for name, data in files.items():
            with (path / name).open("xb") as stream:
                stream.write(data)
    except (OSError, ValueError):
        shutil.rmtree(path)
        raise


def build(workspace, file, output, capture_dir=None):
    path = output_path(workspace, output)
    spec, source = read_spec(workspace, file)
    artifacts = artifact_hashes(workspace, spec)
    token_data = core.read_regular(core.safe_path(workspace, spec["token_file"]))
    require(digest(token_data) == artifacts[spec["token_file"]])
    tokens = import_tokens(core.parse_record(token_data))
    policy = policy_for(spec)
    policy_data = encoded(policy)
    artifacts[POLICY_PATH] = digest(policy_data)
    for scenario in policy["scenarios"]:
        artifacts[scenario["baseline"]] = "0" * 64
    manifest = {
        "schema_version": 3,
        "repository_id": spec["repository_id"],
        "tokens": tokens,
        "components": spec["components"],
        "surfaces": spec["surfaces"],
        "artifacts": artifacts,
    }
    core.validate_manifest(encoded(manifest))
    validate_policy(policy, manifest)
    images = captured_images(workspace, capture_dir, policy["scenarios"])
    for name, data in images.items():
        artifacts[BASELINE_PREFIX + name] = digest(data)
    manifest_data = encoded(manifest)
    missing = [item["id"] for item in policy["scenarios"] if item["id"] + ".png" not in images]
    report = {
        "schema_version": 1,
        "decision": "allow",
        "approved": False,
        "state": "DRAFT" if missing else "READY_FOR_REVIEW",
        "source_sha256": digest(source),
        "manifest_sha256": digest(manifest_data),
        "policy_sha256": digest(policy_data),
        "missing_baselines": missing,
        "output": output,
    }
    files = {"candidate.json": manifest_data, "policy.json": policy_data, "receipt.json": encoded(report)}
    write_package(path, dict(files, **images))
    return report
