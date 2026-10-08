from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
# The packaging workflow, which is where an LFS fetch would do the damage.
# This was build.yml until the 1.9 cutover deleted it with the 1.8 line.
BUILD_WORKFLOW = ROOT / ".github" / "workflows" / "build-career-1.9.yml"
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


def test_ci_does_not_dispatch_the_retired_build_workflow() -> None:
    """build.yml went with the 1.8 line, so a CI job dispatching `Build`
    can only fail, and it failed every push to dev. Nightly recovery is
    retry-failed-nightly.yml's job, against the Career 1.9 snapshot."""
    workflow = _load_ci_workflow()

    assert "build" not in workflow["jobs"]
    assert "--workflow Build" not in CI_WORKFLOW.read_text(encoding="utf-8")


WORKFLOWS = ROOT / ".github" / "workflows"
RUST_WORKFLOW = WORKFLOWS / "rust.yml"
CHANGELOG_WORKFLOW = WORKFLOWS / "changelog.yml"


def _load(path: Path) -> dict:
    return yaml.load(path.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)


def test_rust_ci_skips_pushes_and_prs_that_cannot_affect_it() -> None:
    """A docs-only merge to dev used to rebuild the Rust workspace on two
    Windows runners: only the PR trigger was path filtered. Push and PR now
    share one list."""
    triggers = _load(RUST_WORKFLOW)["on"]
    push_paths = triggers["push"]["paths"]
    assert triggers["pull_request"]["paths"] == push_paths
    for needed in ("crates/**", "Cargo.lock", "data/**", "assets/**", ".github/workflows/rust.yml"):
        assert needed in push_paths, needed
    assert "workflow_dispatch" in triggers, "the manual full-suite run must stay"


def test_python_ci_skips_its_work_without_skipping_its_required_checks() -> None:
    """The two `test` matrix checks are required, and a required check that a
    trigger path filter skips never reports, which would block every
    Rust-only PR. So ci.yml triggers on everything, and a `changes` job
    gates the test steps instead."""
    workflow = _load(CI_WORKFLOW)
    for event in ("push", "pull_request"):
        trigger = workflow["on"][event]
        assert "paths" not in trigger and "paths-ignore" not in trigger, event

    changes = workflow["jobs"]["changes"]
    filter_step = next(
        step for step in changes["steps"] if step.get("uses", "").startswith("dorny/paths-filter@")
    )
    python_inputs = yaml.safe_load(filter_step["with"]["filters"])["python"]
    for needed in ("tools/**", "tests/**", "pyproject.toml", "uv.lock", ".github/workflows/**"):
        assert needed in python_inputs, needed

    test_job = workflow["jobs"]["test"]
    assert test_job["needs"] == "changes"
    gated = [step for step in test_job["steps"] if "skipping" not in step.get("name", "")]
    assert gated
    for step in gated:
        assert step.get("if") == "needs.changes.outputs.python != 'false'", step


def test_ci_cancels_superseded_runs() -> None:
    concurrency = _load(CI_WORKFLOW)["concurrency"]
    assert "github.ref" in concurrency["group"]
    assert concurrency["cancel-in-progress"] == "true"


def test_one_unfiltered_changelog_gate_covers_every_branch_the_builds_did() -> None:
    """The gate must see every change, so it cannot sit in a path-filtered
    workflow. It runs once, from changelog.yml, on every branch either build
    workflow used to gate."""
    for path in (CI_WORKFLOW, RUST_WORKFLOW):
        assert "changelog" not in _load(path)["jobs"], path.name

    workflow = _load(CHANGELOG_WORKFLOW)
    triggers = workflow["on"]
    for event in ("push", "pull_request"):
        assert "paths" not in triggers[event], event
        assert "paths-ignore" not in triggers[event], event
        covered = set(triggers[event]["branches"])
        for path in (CI_WORKFLOW, RUST_WORKFLOW):
            assert set(_load(path)["on"][event]["branches"]) <= covered, (event, path.name)

    run = "\n".join(step.get("run", "") for step in workflow["jobs"]["changelog"]["steps"])
    assert "tools/release_notes.py check" in run
