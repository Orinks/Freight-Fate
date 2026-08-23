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

# The release-note gate resolves its base by measuring the branch point
# against origin/dev and origin/main. A cloud container clones only the
# branch it starts on, so without this the gate cannot see dev, silently
# falls back to main, and counts dev's existing bullets as missing. Not
# fatal on its own -- a container with no network still gets a usable
# checkout, just a noisier gate.
git fetch --quiet origin dev main || \
  echo "warning: could not fetch dev/main; the release-note gate may pick the wrong base." >&2

# Both stages: ruff lint/format and the world_data sync check on commit,
# the release-note gate on push. Every hook is language: system, so this
# only writes .git/hooks -- there are no per-hook environments to build.
uv run pre-commit install --hook-type pre-commit --hook-type pre-push
