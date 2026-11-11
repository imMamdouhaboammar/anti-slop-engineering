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
  result="$(python3 "$SOURCE_DIR/scripts/safe_install.py" --source "$SOURCE_DIR" --dest "$dest")"
  report_install "$result" "$label" "$dest"
  # Install each bundled module as a discoverable top-level skill.
  for module in decision-guard root-fix-gate future-scale-gate paranoid-principal-architect install-anti-slop; do
    if [ -d "$SOURCE_DIR/skills/$module" ]; then
      local module_dest="$(dirname "$dest")/$module"
      result="$(python3 "$SOURCE_DIR/scripts/safe_install.py" --source "$SOURCE_DIR/skills/$module" --dest "$module_dest")"
      report_install "$result" "$module" "$module_dest"
    fi
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

link_installed_cli

echo ""
echo "🎉 Installation complete! Installed into ${INSTALLED_COUNT} agent environment(s)."
echo ""
echo "Quick Verifications:"
echo "  • CLI triage:    npx anti-slop-engineering --base HEAD"
echo "  • Python script: python3 ~/.agents/skills/${TARGET_NAME}/scripts/diff_guard.py --base HEAD"
echo "  • Skill docs:    cat ~/.agents/skills/${TARGET_NAME}/SKILL.md"
