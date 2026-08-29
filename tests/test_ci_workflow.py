from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"
GITATTRIBUTES = ROOT / ".gitattributes"


def _load_ci_workflow() -> dict:
    return yaml.load(CI_WORKFLOW.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def _checkout_step(job: dict) -> dict:
    return next(
        step for step in job["steps"] if step.get("uses", "").startswith("actions/checkout@")
    )


def test_nothing_depends_on_git_lfs_any_more() -> None:
    """The sound pack travels in git, so no job may wait on an LFS fetch.

    A build that shipped pointer files instead of the pack would produce a
    silent game, which is why the packaging jobs used to force `lfs: true`.
    The pack is an ordinary blob now (see .gitattributes), so a plain checkout
    already has it -- and an `lfs: pull` step left behind would be worse than
    redundant: it reintroduces a dependency on a budget that ran out, and a
    quota failure would look like a code failure.
    """
    assert "filter=lfs" not in GITATTRIBUTES.read_text(encoding="utf-8"), (
        "something is tracked by Git LFS again; the pack was moved out of it "
        "because an exhausted budget turned every run red at checkout"
    )
    for workflow in (CI_WORKFLOW, BUILD_WORKFLOW):
        assert "git lfs pull" not in workflow.read_text(encoding="utf-8"), workflow.name


def test_the_test_job_gets_the_sound_pack_from_a_plain_checkout() -> None:
    """The audio guards must not be able to pass against a pointer.

    This assertion has been through three shapes. It began as `lfs: true` on
    the test job, so the audio tests could not quietly pass against a pointer.
    A full fetch on both matrix runners on every push then spent about half a
    gigabyte of LFS bandwidth per commit, which exhausted the repository's
    budget and turned every run red at checkout, before a single test ran
    (2026-08-23); the job dropped to fetching sounds.pak alone. Once the
    budget was gone outright that fetch returned a pointer too, and the tests
    skipped themselves -- green, having checked nothing.

    So the pack is committed as an ordinary blob and the checkout is plain.
    The invariant that survived all three is the one asserted here: whatever
    the job does, it must end up holding a real pack.
    """
    test_job = _load_ci_workflow()["jobs"]["test"]
    checkout = _checkout_step(test_job)
    assert "lfs" not in (checkout.get("with") or {}), (
        "the pack is not an LFS object any more; an lfs flag here is a "
        "leftover that will read as though it were"
    )
    assert not any("lfs" in (step.get("run") or "") for step in test_job["steps"]), (
        "no LFS fetch step: a plain checkout already carries the pack"
    )


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
