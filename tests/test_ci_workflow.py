from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"


def _load_ci_workflow() -> dict:
    return yaml.load(CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _checkout_step(job: dict) -> dict:
    return next(
        step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
    )


def test_packaging_checkouts_fetch_git_lfs_objects() -> None:
    ci = _load_ci_workflow()
    build = yaml.load(BUILD_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert _checkout_step(ci["jobs"]["test"])["with"]["lfs"] == "true"
    assert _checkout_step(ci["jobs"]["build"])["with"]["lfs"] == "true"
    assert _checkout_step(build["jobs"]["build"])["with"]["lfs"] == "true"


def test_nightly_recovery_is_not_a_pull_request_check() -> None:
    workflow = _load_ci_workflow()

    assert "recover-nightly" not in workflow["jobs"]
    build = workflow["jobs"]["build"]
    assert build["needs"] == ["test", "changelog"]
    assert "needs.test.result == 'success'" in build["if"]


def test_build_keeps_dev_push_nightly_recovery() -> None:
    workflow = _load_ci_workflow()
    steps = workflow["jobs"]["build"]["steps"]
    recovery = next(step for step in steps if step.get("name") == "Retry today's failed snapshot")

    condition = recovery["if"]
    assert "github.event_name == 'push'" in condition
    assert "github.ref == 'refs/heads/dev'" in condition
    assert "needs.changelog.result == 'success'" in condition
    assert "!cancelled()" in condition

    script = recovery["run"]
    assert 'gh run list --repo "$GITHUB_REPOSITORY"' in script
    assert "--workflow Build --event schedule" in script
    assert '"$CONCLUSION" != "failure"' in script
    assert 'gh workflow run Build --repo "$GITHUB_REPOSITORY" --ref dev -f dry_run=false' in script
