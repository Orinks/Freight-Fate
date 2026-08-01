<!-- Thanks for contributing! See CONTRIBUTING.md for branch targets,
     test commands, and accessibility expectations.

     Target the `dev` branch, not `main`. GitHub defaults new PRs to
     `main`, but `main` is only for stable release work -- change the
     base branch to `dev` before opening this PR.

     Heads up: the 1.8 line is in maintenance until 1.9 preview snapshots
     begin, so only major and minor bug fixes are being accepted for now.
     Have a feature in mind? Open an issue for it instead and it can be
     picked up for 1.9. See "What Is Being Accepted Right Now" in
     CONTRIBUTING.md. -->

## What changed and why

## What players or maintainers will notice

## Tests and checks run

<!-- e.g. uv run pytest, uv run ruff check src tests tools,
     plus any manual spoken-text or keyboard checks. -->

## Accessibility impact

<!-- Every gameplay path must stay usable by keyboard and screen reader.
     Say how you checked spoken text or keyboard flow, or why this change
     has no accessibility impact. -->

## Changelog

CI requires a `CHANGELOG.md` entry when user-facing paths (such as `src/`
or `docs/`) change. Check one:

- [ ] I added a player-facing bullet under `## Unreleased` in
      `CHANGELOG.md`, written in plain player language and matching the
      style of the existing entries.
- [ ] This change is not player-facing, and every commit message in this
      PR includes `[skip changelog]`.
