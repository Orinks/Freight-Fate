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
    """Anything that PACKAGES the game takes the whole payload.

    A build that shipped pointer files instead of the packs would produce a
    silent game, so this is not negotiable for the jobs that release.
    """
    ci = _load_ci_workflow()
    build = yaml.load(BUILD_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)

    assert _checkout_step(ci["jobs"]["build"])["with"]["lfs"] == "true"
    assert _checkout_step(build["jobs"]["build"])["with"]["lfs"] == "true"


def test_the_test_job_takes_the_sound_pack_and_not_the_music_pack() -> None:
    """Testing is not packaging, and the difference is 250 megabytes.

    This assertion used to include the test job, added when the pack first
    shipped so the audio tests could not quietly pass against a pointer. The
    intent was right and is kept -- but a full fetch on both matrix runners
    on every push spent about half a gigabyte of LFS bandwidth per commit,
    which exhausted the repository's budget and turned every run red at
    checkout, before a single test ran (2026-08-23).

    So the test job takes sounds.pak, which the suite genuinely reaches for,
    and leaves music.pak alone. The original worry is answered better than it
    was: a pack that is not materialised now SKIPS its tests rather than
    passing them, because ``asset_helpers.pack_available`` can tell a pointer
    from a pack -- a pointer is a file that exists, which is exactly how this
    would have gone unnoticed.
    """
    test_job = _load_ci_workflow()["jobs"]["test"]

    assert _checkout_step(test_job)["with"]["lfs"] == "false"

    pull = next(
        step for step in test_job["steps"] if step.get("name") == "Fetch the sound pack only"
    )
    assert "sounds.pak" in pull["run"]
    assert "music.pak" not in pull["run"]
    # A quota failure must leave the pack unmaterialised, not fail the run:
    # the tests that need it skip, and everything else still gets to run.
    assert pull["continue-on-error"] == "true"


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
