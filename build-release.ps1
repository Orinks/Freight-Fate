$ErrorActionPreference = "Stop"

if (-not (Get-Command rustc -ErrorAction SilentlyContinue)) {
    throw "Freight Fate needs rustc before it can build. See README.md under Build a standalone copy."
}
if (-not (Get-Command cargo -ErrorAction SilentlyContinue)) {
    throw "Freight Fate needs cargo before it can build. See README.md under Build a standalone copy."
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "Freight Fate needs uv before it can build. See README.md under Build a standalone copy."
}

uv sync --group dev --group build
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

uv run python tools/build_release.py --rust --smoke @args
exit $LASTEXITCODE
