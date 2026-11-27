#!/usr/bin/env python3
"""Repo Fortress Scaffolder: Autonomous Zero-Tolerance Quality Shield Setup.

Detects project toolchains (Bun/Node, Python, Go, Rust, Docker) and scaffolds:
- Tier 1: Local lightning git hooks (Lefthook) with Anti-Suppression & secrets check + Commitlint
- Tier 2: GitHub Actions Strict CI Quality Gate (lint-gate.yml) with PR diff anti-suppression check
- Tier 3: Automated SemVer & Release Please workflow with multi-arch containerization
"""

import argparse
import json
import os
from pathlib import Path
import shutil
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = SCRIPT_DIR.parent / "references" / "templates"


def detect_stack(root: Path) -> dict:
    has_package_json = (root / "package.json").is_file()
    has_bun = (root / "bun.lock").is_file() or (root / "bun.lockb").is_file()
    has_pnpm = (root / "pnpm-lock.yaml").is_file()
    has_yarn = (root / "yarn.lock").is_file()
    has_python = (root / "pyproject.toml").is_file() or (root / "requirements.txt").is_file()
    has_rust = (root / "Cargo.toml").is_file()
    has_go = (root / "go.mod").is_file()
    has_docker = (root / "Dockerfile").is_file()

    js_pm = "bun" if has_bun else ("pnpm" if has_pnpm else ("yarn" if has_yarn else "npm"))

    return {
        "js": has_package_json,
        "js_pm": js_pm,
        "python": has_python,
        "rust": has_rust,
        "go": has_go,
        "docker": has_docker,
    }


def write_file_safe(path: Path, content: str, dry_run: bool, force: bool = False) -> bool:
    if path.exists() and not force:
        print(f"  [SKIP] {path} already exists (use --force to overwrite)")
        return False
    if dry_run:
        print(f"  [DRY-RUN] Would write: {path}")
        return True
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"  [CREATED] {path}")
    return True


def scaffold_hooks(root: Path, stack: dict, dry_run: bool, force: bool) -> None:
    print("\n[Tier 1: Local Quality Hooks]")
    # 1. lefthook.yml
    lefthook_src = TEMPLATES_DIR / "lefthook.yml"
    if lefthook_src.is_file():
        content = lefthook_src.read_text(encoding="utf-8")
        write_file_safe(root / "lefthook.yml", content, dry_run, force)

    # 2. commitlint.config.mjs
    commitlint_src = TEMPLATES_DIR / "commitlint.config.mjs"
    if commitlint_src.is_file():
        content = commitlint_src.read_text(encoding="utf-8")
        write_file_safe(root / "commitlint.config.mjs", content, dry_run, force)

    # If package.json exists, update scripts
    pkg_path = root / "package.json"
    if pkg_path.is_file() and not dry_run:
        try:
            pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
            scripts = pkg_data.setdefault("scripts", {})
            if "prepare" not in scripts:
                scripts["prepare"] = "lefthook install"
                pkg_path.write_text(json.dumps(pkg_data, indent=2) + "\n", encoding="utf-8")
                print("  [UPDATED] package.json -> added 'prepare': 'lefthook install'")
        except Exception as e:
            print(f"  [WARN] Failed to inspect package.json: {e}")


def scaffold_ci(root: Path, stack: dict, dry_run: bool, force: bool) -> None:
    print("\n[Tier 2: Remote CI Quality Gate]")
    ci_src = TEMPLATES_DIR / "lint-gate.yml"
    if ci_src.is_file():
        content = ci_src.read_text(encoding="utf-8")
        write_file_safe(root / ".github" / "workflows" / "lint-gate.yml", content, dry_run, force)


def scaffold_release(root: Path, stack: dict, dry_run: bool, force: bool) -> None:
    print("\n[Tier 3: Automated SemVer & Release Please]")
    # release-please-config.json
    cfg_src = TEMPLATES_DIR / "release-please-config.json"
    if cfg_src.is_file():
        write_file_safe(root / "release-please-config.json", cfg_src.read_text(encoding="utf-8"), dry_run, force)

    # .release-please-manifest.json
    manifest_src = TEMPLATES_DIR / "release-please-manifest.json"
    if manifest_src.is_file():
        # Read current version from package.json if possible
        version = "0.1.0"
        pkg_path = root / "package.json"
        if pkg_path.is_file():
            try:
                pkg_data = json.loads(pkg_path.read_text(encoding="utf-8"))
                version = pkg_data.get("version", "0.1.0")
            except Exception as e:
                print(f"  [WARN] Failed to read version from package.json: {e}")
        manifest_content = json.dumps({".": version}, indent=2) + "\n"
        write_file_safe(root / ".release-please-manifest.json", manifest_content, dry_run, force)

    # .github/workflows/release-please.yml
    workflow_src = TEMPLATES_DIR / "release-please.yml"
    if workflow_src.is_file():
        write_file_safe(root / ".github" / "workflows" / "release-please.yml", workflow_src.read_text(encoding="utf-8"), dry_run, force)


def scaffold_docker(root: Path, stack: dict, dry_run: bool, force: bool) -> None:
    print("\n[Containerization: Multi-Arch Hardened Docker]")
    # Dockerfile
    df_src = TEMPLATES_DIR / "Dockerfile.polyglot"
    if df_src.is_file():
        write_file_safe(root / "Dockerfile", df_src.read_text(encoding="utf-8"), dry_run, force)

    # docker-compose.yml
    dc_src = TEMPLATES_DIR / "docker-compose.yml"
    if dc_src.is_file():
        write_file_safe(root / "docker-compose.yml", dc_src.read_text(encoding="utf-8"), dry_run, force)

    # .dockerignore
    di_src = TEMPLATES_DIR / "dockerignore.template"
    if di_src.is_file():
        write_file_safe(root / ".dockerignore", di_src.read_text(encoding="utf-8"), dry_run, force)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Repo Fortress: Autonomous Zero-Tolerance Repository Quality Shield Scaffolder"
    )
    parser.add_argument("--root", type=str, default=".", help="Root directory of target project")
    parser.add_argument("--all", action="store_true", help="Scaffold all 3 tiers (hooks, CI, release, docker)")
    parser.add_argument("--hooks", action="store_true", help="Scaffold Tier 1 (Lefthook + Commitlint)")
    parser.add_argument("--ci", action="store_true", help="Scaffold Tier 2 (GitHub Actions lint-gate.yml)")
    parser.add_argument("--release", action="store_true", help="Scaffold Tier 3 (Release Please)")
    parser.add_argument("--docker", action="store_true", help="Scaffold production Docker & Compose")
    parser.add_argument("--dry-run", action="store_true", help="Show proposed actions without writing")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")

    args = parser.parse_args()

    target_root = Path(args.root).resolve()
    if not target_root.is_dir():
        print(f"Error: Target path {target_root} is not a directory.")
        return 1

    print(f"=== 🏰 Repo Fortress Scaffolder ===")
    print(f"Target: {target_root}")
    stack = detect_stack(target_root)
    detected_langs = [k for k, v in stack.items() if v and k != "js_pm"]
    print(f"Detected stack components: {', '.join(detected_langs) if detected_langs else 'Generic'}")
    if stack["js"]:
        print(f"JavaScript/TypeScript package manager: {stack['js_pm']}")

    # If no flags passed, default to --all
    do_all = args.all or not (args.hooks or args.ci or args.release or args.docker)

    if do_all or args.hooks:
        scaffold_hooks(target_root, stack, args.dry_run, args.force)

    if do_all or args.ci:
        scaffold_ci(target_root, stack, args.dry_run, args.force)

    if do_all or args.release:
        scaffold_release(target_root, stack, args.dry_run, args.force)

    if do_all or args.docker:
        scaffold_docker(target_root, stack, args.dry_run, args.force)

    print("\n✅ Repo Fortress scaffolding complete.")
    if stack["js"]:
        print(f"👉 Next steps: Run `{stack['js_pm']} add -D lefthook @commitlint/cli @commitlint/config-conventional` and `{stack['js_pm']}x lefthook install`.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
