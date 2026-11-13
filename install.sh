#!/usr/bin/env bash
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 Mamdouh Aboammar <mamdouhfces1997@gmail.com> and contributors
# Universal Multi-Agent Installer for Anti-Slop Engineering
set -e

REPO_URL="https://github.com/imMamdouhaboammar/anti-slop-engineering.git"
TARGET_NAME="anti-slop-engineering"
TEMP_DIR=""

cleanup() {
  if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    rm -rf "$TEMP_DIR"
  fi
}
trap cleanup EXIT

echo "🛡️  Anti-Slop Engineering - Universal Agent Installer"
echo "======================================================"

# Determine source directory (local clone or fresh clone via curl | bash)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd || echo "")"
SOURCE_DIR="$SCRIPT_DIR"

if [ -z "$SOURCE_DIR" ] || [ ! -f "$SOURCE_DIR/SKILL.md" ]; then
  echo "📥 Fetching latest release from GitHub..."
  TEMP_DIR="$(mktemp -d)"
  git clone --depth 1 "$REPO_URL" "$TEMP_DIR/repo" >/dev/null 2>&1
  SOURCE_DIR="$TEMP_DIR/repo"
fi

if [ "${1:-}" = "--help" ] || [ "${1:-}" = "-h" ]; then
  echo "Usage: bash install.sh [--skills=core|all|id1,id2] [--local|--project]"
  echo "Use 'anti-slop-engineering setup' for interactive agent and scope selection."
  exit 0
fi

BASH_DRY_RUN=0
for argument in "$@"; do
  case "$argument" in
    --dry-run) BASH_DRY_RUN=1 ;;
    --json)
      echo "Installer error: use 'anti-slop-engineering install --json' for structured JSON output" >&2
      exit 2 ;;
    --agent*|--scope*)
      echo "Installer error: agent/scope flags require 'anti-slop-engineering setup'; the Bash installer keeps its legacy target locations" >&2
      exit 2 ;;
  esac
done

# The JavaScript installer owns the plugin catalog and the terminal picker.
# A minimal Bash-only environment still gets the mandatory core.
SELECTED_MODULES=""
if command -v node >/dev/null 2>&1 && [ -f "$SOURCE_DIR/scripts/installer.mjs" ]; then
  if ! setup_selection="$(node "$SOURCE_DIR/scripts/installer.mjs" --selection-only --scope=global "$@")"; then
    echo "Installer error: plugin selection failed; no files were installed" >&2
    exit 2
  fi
  SELECTED_MODULES="$(python3 -c '
import json, re, sys
data = json.loads(sys.argv[1])
for skill in data["skills"]:
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", skill):
        raise ValueError("Invalid plugin ID in selection")
    if skill != "anti-slop-engineering":
        print(skill)
' "$setup_selection")"
else
  case " $* " in
    *--skills*|*--plugins*|*--modules*|*--all*)
      echo "Installer error: Node.js is needed to select optional plugins; core-only Bash installation is available" >&2
      exit 2 ;;
  esac
fi

report_install() {
  local result="$1"
  local label="$2"
  local dest="$3"
  python3 -c '
import json, sys
r = json.loads(sys.argv[1])
print("  Installed {installed}, updated {updated}, preserved {preserved}, skipped {skipped}, conflicted {conflicted}: {label} -> {dest}".format(
    **{key: len(r[key]) for key in ("installed", "updated", "preserved", "skipped", "conflicted")},
    label=sys.argv[2], dest=sys.argv[3]))
if r["conflicted"]:
    print("  Conflicts retained: " + ", ".join(r["conflicted"]))
if r["backup"]:
    print("  Recovery backup: " + r["backup"])
' "$result" "$label" "$dest"
}

install_to() {
  local dest="$1"
  local label="$2"
  local result
  local preview=()
  if [ "$BASH_DRY_RUN" -eq 1 ]; then preview=(--dry-run); fi
  result="$(python3 "$SOURCE_DIR/scripts/safe_install.py" --source "$SOURCE_DIR" --dest "$dest" "${preview[@]}")"
  report_install "$result" "$label" "$dest"
  # Install only the optional skills selected from the authoritative catalog.
  local module
  for module in $SELECTED_MODULES; do
    if [ ! -f "$SOURCE_DIR/skills/$module/SKILL.md" ]; then
      echo "Installer error: selected plugin source disappeared: $module" >&2
      return 2
    fi
    local module_dest="$(dirname "$dest")/$module"
    result="$(python3 "$SOURCE_DIR/scripts/safe_install.py" --source "$SOURCE_DIR/skills/$module" --dest "$module_dest" "${preview[@]}")"
    report_install "$result" "$module" "$module_dest"
  done
}

INSTALLED_COUNT=0

# 1. Claude Code & Claude Desktop
if [ -d "$HOME/.claude" ] || command -v claude >/dev/null 2>&1; then
  install_to "$HOME/.claude/skills/${TARGET_NAME}" "Claude Code"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
fi

# 2. Antigravity & Gemini CLI
if [ -d "$HOME/.gemini" ]; then
  install_to "$HOME/.gemini/config/skills/${TARGET_NAME}" "Antigravity / Gemini CLI"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
fi

# 3. Codex & OpenCode
if [ -d "$HOME/.codex" ] || command -v codex >/dev/null 2>&1; then
  install_to "$HOME/.codex/skills/${TARGET_NAME}" "Codex / OpenCode"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
fi

# 4. Universal Agent Kernel (~/.agents/skills)
install_to "$HOME/.agents/skills/${TARGET_NAME}" "Universal Agent Kernel (~/.agents/skills)"
INSTALLED_COUNT=$((INSTALLED_COUNT + 1))

# 5. Local project installation if --local or --project is requested
if [ "$1" = "--local" ] || [ "$1" = "--project" ]; then
  install_to "$PWD/.agents/skills/${TARGET_NAME}" "Local Project (.agents/skills)"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
fi

# 6. Resolve an installed, executable CLI before creating user-owned links.
select_cli_target() {
  local candidate
  for candidate in \
    "$HOME/.gemini/config/skills/${TARGET_NAME}/bin/cli.js" \
    "$HOME/.codex/skills/${TARGET_NAME}/bin/cli.js" \
    "$HOME/.agents/skills/${TARGET_NAME}/bin/cli.js" \
    "$HOME/.claude/skills/${TARGET_NAME}/bin/cli.js" \
    "$PWD/.agents/skills/${TARGET_NAME}/bin/cli.js"; do
    if [ -f "$candidate" ] && [ -x "$candidate" ] && "$candidate" --help >/dev/null 2>&1; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done
  return 1
}

link_installed_cli() {
  local bin_dir="$HOME/.local/bin"
  if [ -L "$HOME/.local" ] || [ -L "$bin_dir" ]; then
    echo "Installer error: symbolic link in CLI directory path; leaving existing links untouched" >&2
    return 2
  fi
  local target
  if ! target="$(select_cli_target)"; then
    echo "No executable CLI target found; installed skills are available without global CLI links" >&2
    return 0
  fi
  mkdir -p "$bin_dir"
  local bin_name link
  for bin_name in anti-slop-engineering diff-guard sre-guard rust-guard toil-guard; do
    link="$bin_dir/$bin_name"
    if [ -L "$link" ] || [ -e "$link" ]; then
      if [ -L "$link" ] && [ "$(readlink "$link")" = "$target" ]; then
        echo "  Existing verified CLI link: $link"
      else
        echo "  CLI link conflict preserved: $link"
      fi
      continue
    fi
    ln -s "$target" "$link"
    if [ ! -L "$link" ] || [ ! -x "$link" ]; then
      rm "$link"
      echo "Installer error: created CLI link cannot execute: $link" >&2
      return 2
    fi
    echo "  Linked CLI: $link -> $target"
  done
}

if [ "$BASH_DRY_RUN" -eq 0 ]; then
  link_installed_cli
fi

echo ""
if [ "$BASH_DRY_RUN" -eq 1 ]; then
  echo "Dry-run complete: planned ${INSTALLED_COUNT} agent environment(s); no files changed"
else
  echo "🎉 Installation complete! Installed into ${INSTALLED_COUNT} agent environment(s)."
fi
echo "  Required core: $TARGET_NAME"
echo "  Optional modules: ${SELECTED_MODULES:-none}"
echo ""
echo "Quick Verifications:"
echo "  • CLI triage:    npx anti-slop-engineering --base HEAD"
echo "  • Python script: python3 ~/.agents/skills/${TARGET_NAME}/scripts/diff_guard.py --base HEAD"
echo "  • Skill docs:    cat ~/.agents/skills/${TARGET_NAME}/SKILL.md"
