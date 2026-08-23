#!/bin/bash
# SessionStart hook for Claude Code on the web.
#
# Brings a fresh cloud container up to the same state a contributor's
# checkout is in after `uv sync --group dev`, so `uv run pytest` and
# `uv run ruff check` work in the first turn of a session, and exports the
# headless environment the game needs when there is no display, no sound
# card, and no screen reader.
set -euo pipefail

# Local machines already have a working checkout; only the disposable cloud
# container needs provisioning.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}"

# Headless defaults, matching .github/workflows/ci.yml. Written to
# CLAUDE_ENV_FILE so every command in the session inherits them, not just
# this script.
if [ -n "${CLAUDE_ENV_FILE:-}" ]; then
  cat >> "$CLAUDE_ENV_FILE" << 'ENV'
export SDL_VIDEODRIVER=dummy
export SDL_AUDIODRIVER=dummy
export FREIGHT_FATE_NO_SPEECH=1
export COVERAGE_CORE=sysmon
ENV
fi

# uv manages the interpreter as well as the packages, so the pinned Python
# in .python-version is fetched here rather than assumed to be present.
if ! command -v uv > /dev/null 2>&1; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# sound_lib resolves from a git URL, so a missing git surfaces here as a
# resolution failure rather than anything obviously git-shaped.
if ! command -v git > /dev/null 2>&1; then
  echo "git is required: the sound_lib dependency installs from a git repository." >&2
  exit 1
fi

uv python install
uv sync --group dev
