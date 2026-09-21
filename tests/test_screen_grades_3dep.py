"""Tests for tools/screen_grades_3dep.py: the 3DEP second opinion on grades.

No network. The sample service is faked at `_post`, which is where the tool's
only HTTP call lives, so the parts worth pinning -- which vertices a span is
read at, how a reading becomes a verdict, and the fact that 3DEP answers out
of order -- are all exercised offline.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load_tool():
    """Import tools/screen_grades_3dep.py by path (tools is not a package)."""
    sys.path.insert(0, str(ROOT / "tools"))
    spec = importlib.util.spec_from_file_location(
        "screen_grades_3dep", ROOT / "tools" / "screen_grades_3dep.py"
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


screen = _load_tool()

FT_PER_M = 1.0 / 3.280839895


def _row(
    profile_pct: float,
    ceiling_pct: float,
    span_mi: float = 1.0,
    highway: str = "US-160",
) -> dict:
    return {
        "leg": "a -> b",
        "highway": highway,
        "start_mi": 0.0,
        "end_mi": span_mi,
        "profile_pct": profile_pct,
        "ceiling_pct": ceiling_pct,
        "points": ["0.0,0.0", "1.0,1.0"],
    }


def _cache_for(grade_pct: float, span_mi: float = 1.0) -> dict[str, float]:
    """Two elevations, in metres, that read as `grade_pct` over the span."""
    rise_ft = grade_pct / 100.0 * span_mi * screen.FEET_PER_MILE
    return {"0.0,0.0": 0.0, "1.0,1.0": rise_ft * FT_PER_M}


def test_a_spike_3dep_flatly_contradicts_is_an_artifact() -> None:
    """The profile's 14 percent on ground 3DEP reads at 2: the clamp was right."""
    row = screen.judged(_row(14.4, 7.0, highway="I-5"), _cache_for(2.0))

    assert row["dep_pct"] == 2.0
    assert row["verdict"] == "artifact, clamp right"


def test_a_steep_grade_3dep_confirms_is_being_clamped_away() -> None:
    """A real climb the terrain ceiling caps: US-160 at 9, held at 6.

    A US route's class ceiling is 10, so 9 is a slope the road can hold and
    both readings agreeing means something.
    """
    row = screen.judged(_row(9.0, 6.0), _cache_for(9.0))

    assert row["verdict"] == "REAL, CLAMPED"


def test_both_models_agreeing_on_an_impossible_grade_is_not_a_confirmation() -> None:
    """13 percent on an interstate, confirmed by 3DEP, is a bridge.

    Both models read the ground; over three tenths of a mile the ground under
    a viaduct is not the road on it. 47 spans in the first full run looked
    exactly like this, and calling them real grades would have argued for
    loosening a clamp that is the only thing catching them.
    """
    row = screen.judged(_row(-13.02, 6.0, highway="I-79"), _cache_for(-13.43))

    assert row["verdict"] == "both models, class forbids"


def test_a_grade_under_the_ceiling_that_agrees_is_just_confirmed() -> None:
    row = screen.judged(_row(5.0, 7.0), _cache_for(5.2))

    assert row["verdict"] == "confirmed"


def test_a_reading_neither_agrees_with_nor_acquits_says_so() -> None:
    """Profile 12, ceiling 7, 3DEP 9: clamped, and 3DEP is over the ceiling too."""
    row = screen.judged(_row(12.0, 7.0, highway="I-5"), _cache_for(9.0))

    assert row["verdict"] == "disagrees"


def test_a_segment_with_nothing_cached_is_dropped_not_guessed() -> None:
    assert screen.judged(_row(14.4, 7.0, highway="I-5"), {}) is None


def test_span_points_reads_the_vertices_inside_the_span() -> None:
    polyline = [(40.0, -105.0, 0.0), (40.1, -105.1, 0.5), (40.2, -105.2, 1.0)]

    points = screen._span_points(polyline, 0.0, 1.0)

    assert len(points) == 3
    assert points[0] == screen._key(40.0, -105.0)
    assert points[-1] == screen._key(40.2, -105.2)


def test_a_span_shorter_than_the_vertex_spacing_straddles_it() -> None:
    """A 0.2 mile span between two vertices 5 miles apart still gets read."""
    polyline = [(40.0, -105.0, 0.0), (40.5, -105.5, 5.0)]

    points = screen._span_points(polyline, 2.0, 2.2)

    assert points == [screen._key(40.0, -105.0), screen._key(40.5, -105.5)]


def test_samples_are_placed_by_location_id_not_by_position(monkeypatch) -> None:
    """3DEP answers out of order and omits points it cannot read.

    Trusting the response order would hand one point's elevation to another,
    which reads as a plausible grade rather than as an error.
    """
    monkeypatch.setattr(
        screen,
        "_post",
        lambda body: {
            "samples": [
                {"locationId": "2", "value": "300.0"},
                {"locationId": "0", "value": "100.0"},
            ]
        },
    )

    values = screen._get_samples([(40.0, -105.0), (41.0, -106.0), (42.0, -107.0)])

    assert values == [100.0, None, 300.0]


def test_a_failed_batch_keeps_what_was_already_read(tmp_path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(screen, "CACHE_PATH", tmp_path / "samples.json")
    monkeypatch.setattr(screen, "BATCH", 2)
    calls: list[int] = []

    def _sampler(points):
        calls.append(len(points))
        if len(calls) == 2:
            raise OSError("no route to host")
        return [100.0] * len(points)

    cache: dict[str, float] = {}
    screen._fill_cache(cache, ["0.0,0.0", "1.0,1.0", "2.0,2.0", "3.0,3.0"], sampler=_sampler)

    assert set(cache) == {"0.0,0.0", "1.0,1.0"}
    assert "batch failed" in capsys.readouterr().err
    # The first batch was written before the second was attempted.
    saved = json.loads((tmp_path / "samples.json").read_text(encoding="utf-8"))
    assert set(saved) == {"0.0,0.0", "1.0,1.0"}


def test_a_non_json_body_is_an_error_not_an_elevation(monkeypatch) -> None:
    """3DEP answers an out-of-coverage request with HTTP 200 and `Call failed.`"""

    class _Response:
        def read(self):
            return b"Call failed."

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(screen.urllib.request, "urlopen", lambda *a, **k: _Response())

    try:
        screen._post(b"")
    except RuntimeError as exc:
        assert "non-JSON" in str(exc)
    else:  # pragma: no cover - the point of the test
        raise AssertionError("a plain-text body must not parse as a reading")


def _writable_row(profile_pct: float, dep_pct: float, highway: str, source: str = "ORS.") -> dict:
    row = _row(profile_pct, 6.0, highway=highway)
    row["dep_pct"] = dep_pct
    row["segment"] = {"avg_grade_pct": profile_pct, "source": source}
    return row


def test_write_replaces_the_profile_slope_and_keeps_it_in_the_source() -> None:
    row = _writable_row(6.42, 6.01, "US-160")

    assert screen.write_measurements([row]) == 1
    assert row["segment"]["avg_grade_pct"] == 6.01
    # The profile's own number stays readable, so the swap can be undone by
    # reading rather than by guessing.
    assert "+6.42" in row["segment"]["source"]
    assert row["segment"]["source"].startswith("ORS.")


def test_write_refuses_a_reading_the_road_class_cannot_hold() -> None:
    """The bridge blind spot must never be baked in.

    3DEP reading -13.43 on an interstate is the ground under a viaduct. Left
    alone, the load screen clamps it; written, it would be permanent.
    """
    row = _writable_row(-13.02, -13.43, "I-79")

    assert screen.write_measurements([row]) == 0
    assert row["segment"]["avg_grade_pct"] == -13.02
    assert screen.MEASURED_MARKER not in row["segment"]["source"]


def test_write_is_idempotent() -> None:
    """A second run must not re-read its own reading as if it were the profile."""
    row = _writable_row(6.42, 6.01, "US-160")
    screen.write_measurements([row])
    source_after_first = row["segment"]["source"]

    assert screen.write_measurements([row]) == 0
    assert row["segment"]["source"] == source_after_first
    assert source_after_first.count(screen.MEASURED_MARKER) == 1
