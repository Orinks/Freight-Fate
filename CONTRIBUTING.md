# Contributing to Freight Fate

Thanks for helping make Freight Fate better. This project is audio-first and
accessibility-first, so contributions should keep blind and low-vision players
at the center of every change.

## Branch Targets

- Open feature, fix, data, and documentation pull requests against `dev`.
- Use `main` only for stable release, hotfix, or release-sync work.
- If your PR targets the wrong branch, a maintainer may retarget it before
  review.

## Before Opening a Pull Request

- Keep practical code files at or below 1000 lines. Split large code or test
  files into cohesive modules instead of adding more to an oversized file.
- Run `uv sync --group dev` before tests in a fresh checkout or worktree.
- Run focused tests for the area you changed. For broad or shared behavior,
  run the full suite with `uv run pytest`.
- Run `uv run ruff check src tests tools` and
  `uv run python -m compileall src tests tools`.
- For user-facing changes, include how you checked the spoken text, keyboard
  flow, or other accessibility impact.
- For player-facing changes, add a `CHANGELOG.md` entry (see Changelog
  Entries below); CI enforces this.

## Accessibility Expectations

- Every gameplay path must remain usable by keyboard and screen reader.
- Speech text should be clear, player-facing, and free of maintainer or CI
  jargon.
- Do not replace spoken information with visual-only cues.
- If you add or change menu items, driving prompts, warnings, settings, or
  status text, test the spoken result.

## World And Route Data

World data changes are welcome. Please keep them deterministic and offline:

- Route data must load without network access during normal play.
- Add sources or source notes for real-world facilities, stops, speed limits,
  tolls, interchanges, or other mapped data.
- Do not include experimental regions in playable data unless the index or
  loader explicitly enables them.
- Avoid raw OpenStreetMap tags or source-only text in player-facing names.
- After data changes, run the world and route tests, such as:

  ```powershell
  uv run pytest tests/test_world.py tests/test_world_overlay.py
  ```

## Changelog Entries

Nightly and stable release notes are built only from the curated entries in
`CHANGELOG.md` -- never from commit subjects -- so a player-facing change
without an entry ships silently. CI fails a pull request that changes
user-facing paths (`src/`, `docs/`, `CHANGELOG.md`, `README.md`, and the
release tooling) without adding one.

- Add a bullet under `## Unreleased` in the fitting section (`Added`,
  `Changed`, `Fixed`, and so on).
- Write for players, not maintainers: a bold lead sentence, then plain
  language about what they will hear or notice in the game. Match the voice
  of the existing entries; they are read aloud by screen readers, so avoid
  jargon, tables, and decorative symbols.
- A change with nothing player-facing in it (internal refactors, CI, tests,
  tooling) can skip the entry by putting `[skip changelog]` or
  `changelog: none` in every commit message of the pull request.

## Pull Request Notes

In your PR body, briefly say:

- what changed and why;
- what players or maintainers will notice;
- what tests or manual checks you ran;
- any accessibility impact.

Small PRs are easiest to review, but cohesive data restructures are fine when
the tests show the playable world still loads and routes correctly.
