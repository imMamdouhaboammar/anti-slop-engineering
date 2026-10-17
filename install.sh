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

install_to() {
  local dest="$1"
  local label="$2"
  mkdir -p "$(dirname "$dest")"
  rm -rf "$dest"
  mkdir -p "$dest"
  cp -R "$SOURCE_DIR/"* "$dest/"
  # Ensure scripts are executable
  chmod +x "$dest/bin/cli.js" 2>/dev/null || true
  chmod +x "$dest/scripts/diff_guard.py" 2>/dev/null || true
  chmod +x "$dest/install.sh" 2>/dev/null || true
  echo "  ✅ Installed for ${label} -> ${dest}"
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
  install_to "./.agents/skills/${TARGET_NAME}" "Local Project (.agents/skills)"
  INSTALLED_COUNT=$((INSTALLED_COUNT + 1))
fi

echo ""
echo "🎉 Installation complete! Installed into ${INSTALLED_COUNT} agent environment(s)."
echo ""
echo "Quick Verifications:"
echo "  • CLI triage:    npx anti-slop-engineering --base HEAD"
echo "  • Python script: python3 ~/.agents/skills/${TARGET_NAME}/scripts/diff_guard.py --base HEAD"
echo "  • Skill docs:    cat ~/.agents/skills/${TARGET_NAME}/SKILL.md"
