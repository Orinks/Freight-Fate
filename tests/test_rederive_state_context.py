import copy

import rederive_state_context as rsc


def _leg():
    return {
        "from": "a_tx_us",
        "to": "b_ok_us",
        "miles": 100.0,
        "highway": "I-40",
        "corridor": {
            "route_points": [
                {"lat": 30.0, "lon": -100.0},
                {"lat": 31.0, "lon": -99.0},
            ],
            "state_crossings": [
                {
                    "from_state": "Texas",
                    "state": "Oklahoma",
                    "at_mi": 10.0,
                    "place": "old boundary",
                    "source": "old",
                }
            ],
            "state_miles": [
                {"state": "Texas", "miles": 10.0, "source": "old"},
                {"state": "Oklahoma", "miles": 90.0, "source": "old"},
            ],
        },
    }


def _data(leg):
    return {
        "cities": {
            "a_tx_us": {"state": "Texas"},
            "b_ok_us": {"state": "Oklahoma"},
        },
        "legs": [leg],
    }


def _install_geometry(monkeypatch, max_off_mi=0.0):
    monkeypatch.setattr(
        rsc.lg,
        "corridor_geometry",
        lambda _leg: [(30.0, -100.0, 0.0), (31.0, -99.0, 100.0)],
    )
    monkeypatch.setattr(
        rsc.lg,
        "archived_polyline",
        lambda *_args: ([[-100.0, 30.0], [-99.0, 31.0]], []),
    )
    monkeypatch.setattr(
        rsc.lg,
        "route_point_max_off_mi",
        lambda *_args: max_off_mi,
    )


def _context(state="Oklahoma", at_mi=13.0):
    return {
        "state_crossings": [
            {
                "from_state": "Texas",
                "state": state,
                "at_mi": at_mi,
                "place": "derived boundary",
                "source": "old helper source",
            }
        ],
        "state_miles": [
            {"state": "Texas", "miles": at_mi},
            {"state": state, "miles": 100.0 - at_mi},
        ],
    }


def test_sequence_equal_state_context_updates_only_above_minimum_shift(monkeypatch):
    leg = _leg()
    data = _data(leg)
    old_miles = copy.deepcopy(leg["corridor"]["state_miles"])
    _install_geometry(monkeypatch)
    monkeypatch.setattr(rsc, "derive_state_context", lambda *_args: _context())

    report = rsc.process_world(data, [], min_shift=1.0)

    assert len(report["changed"]) == 1
    assert report["changed"][0]["sequence_matches"] is True
    assert report["changed"][0]["old_state_miles"] == old_miles
    assert leg["corridor"]["state_crossings"][0]["at_mi"] == 13.0
    assert [item["miles"] for item in leg["corridor"]["state_miles"]] == [13.0, 87.0]
    assert all(
        item["source"] == rsc.STATE_CONTEXT_SOURCE
        for field in ("state_crossings", "state_miles")
        for item in leg["corridor"][field]
    )


def test_sequence_equal_boundary_below_minimum_shift_is_not_updated(monkeypatch):
    leg = _leg()
    before = copy.deepcopy(leg["corridor"])
    _install_geometry(monkeypatch)
    monkeypatch.setattr(rsc, "derive_state_context", lambda *_args: _context(at_mi=10.5))

    report = rsc.process_world(_data(leg), [], min_shift=1.0)

    assert leg["corridor"] == before
    assert report["changed"] == []


def test_stale_publicamundi_source_updates_below_minimum_shift(monkeypatch):
    leg = _leg()
    for item in leg["corridor"]["state_crossings"] + leg["corridor"]["state_miles"]:
        item["source"] = rsc.STALE_PUBLICAMUNDI_SOURCE
    _install_geometry(monkeypatch)
    monkeypatch.setattr(rsc, "derive_state_context", lambda *_args: _context(at_mi=10.5))

    report = rsc.process_world(_data(leg), [], min_shift=1.0)

    assert len(report["changed"]) == 1
    assert report["changed"][0]["sequence_matches"] is True
    assert leg["corridor"]["state_crossings"][0]["at_mi"] == 10.5
    assert all(
        item["source"] == rsc.STATE_CONTEXT_SOURCE
        for field in ("state_crossings", "state_miles")
        for item in leg["corridor"][field]
    )


def test_sequence_difference_is_reported_without_mutating_the_leg(monkeypatch):
    leg = _leg()
    before = copy.deepcopy(leg["corridor"])
    _install_geometry(monkeypatch)
    monkeypatch.setattr(rsc, "derive_state_context", lambda *_args: _context(state="New Mexico"))

    report = rsc.process_world(_data(leg), [], min_shift=1.0)

    assert leg["corridor"] == before
    assert report["changed"] == []
    assert report["sequence_differs"] == [
        {
            "leg": "a_tx_us:b_ok_us",
            "old": ["Texas", "Oklahoma"],
            "new": ["Texas", "New Mexico"],
            "updated": False,
        }
    ]


def test_only_overrides_a_state_sequence_difference(monkeypatch):
    leg = _leg()
    _install_geometry(monkeypatch)
    monkeypatch.setattr(rsc, "derive_state_context", lambda *_args: _context(state="New Mexico"))

    report = rsc.process_world(_data(leg), [], min_shift=1.0, only={"a_tx_us:b_ok_us"})

    assert len(report["changed"]) == 1
    assert report["changed"][0]["sequence_matches"] is False
    assert report["sequence_differs"][0]["updated"] is True
    assert leg["corridor"]["state_crossings"][0]["state"] == "New Mexico"


def test_unselected_sequence_difference_is_report_only_with_only_filter(monkeypatch):
    selected_leg = _leg()
    unselected_leg = copy.deepcopy(_leg())
    unselected_leg["to"] = "c_ok_us"
    unselected_before = copy.deepcopy(unselected_leg["corridor"])
    data = _data(selected_leg)
    data["cities"]["c_ok_us"] = {"state": "Oklahoma"}
    data["legs"].append(unselected_leg)
    _install_geometry(monkeypatch)
    monkeypatch.setattr(rsc, "derive_state_context", lambda *_args: _context(state="New Mexico"))

    report = rsc.process_world(data, [], only={"a_tx_us:b_ok_us"})

    assert selected_leg["corridor"]["state_crossings"][0]["state"] == "New Mexico"
    assert unselected_leg["corridor"] == unselected_before
    assert report["sequence_differs"] == [
        {
            "leg": "a_tx_us:b_ok_us",
            "old": ["Texas", "Oklahoma"],
            "new": ["Texas", "New Mexico"],
            "updated": True,
        },
        {
            "leg": "a_tx_us:c_ok_us",
            "old": ["Texas", "Oklahoma"],
            "new": ["Texas", "New Mexico"],
            "updated": False,
        },
    ]


def test_route_point_guard_skips_state_rederivation(monkeypatch):
    leg = _leg()
    before = copy.deepcopy(leg["corridor"])
    _install_geometry(monkeypatch, max_off_mi=5.01)

    def should_not_derive(*_args):
        raise AssertionError("state context should not be computed for a mismatched archive")

    monkeypatch.setattr(rsc, "derive_state_context", should_not_derive)

    report = rsc.process_world(_data(leg), [])

    assert leg["corridor"] == before
    assert report["guard_skipped"] == [
        "a_tx_us:b_ok_us: route_points are 5.01 mi from archive (limit 5.00)"
    ]


def test_main_loads_cached_osm_boundaries_and_does_not_save_by_default(monkeypatch, capsys):
    leg = _leg()
    data = _data(leg)
    boundaries = [{"name": "Texas", "ways": [[[0.0, 0.0], [1.0, 0.0]]]}]
    saved = []
    loaded = []
    monkeypatch.setattr(rsc, "load_world", lambda: data)

    def load_boundaries(cache_path):
        loaded.append(cache_path)
        return boundaries

    def derive(_data, _leg, coords, supplied_boundaries):
        assert coords == [[-100.0, 30.0], [-99.0, 31.0]]
        assert isinstance(supplied_boundaries, rsc.StateBoundaryIndex)
        assert "Texas" in supplied_boundaries.bboxes
        return _context()

    monkeypatch.setattr(rsc, "load_state_boundaries", load_boundaries)
    monkeypatch.setattr(rsc, "derive_state_context", derive)
    monkeypatch.setattr(rsc, "save_world", saved.append)
    _install_geometry(monkeypatch)

    assert rsc.main(["--only", "a_tx_us:b_ok_us"]) == 0

    assert loaded == [rsc.BOUNDARIES_CACHE]
    assert not saved
    assert "Dry run only" in capsys.readouterr().out


def _shared_square_boundaries():
    return [
        {
            "name": "Texas",
            "ways": [[[0.0, 0.0], [1.0, 0.0], [1.0, 1.0], [0.0, 1.0], [0.0, 0.0]]],
        },
        {
            "name": "Oklahoma",
            "ways": [[[1.0, 0.0], [2.0, 0.0], [2.0, 1.0], [1.0, 1.0], [1.0, 0.0]]],
        },
    ]


def test_shared_boundary_is_one_crossing_at_interpolated_route_mile():
    leg = _leg()
    leg["miles"] = 10.0
    data = _data(leg)
    boundaries = rsc.build_boundary_index(_shared_square_boundaries())

    result = rsc.derive_state_context(data, leg, [[0.5, 0.5], [1.5, 0.5]], boundaries)

    assert len(result["state_crossings"]) == 1
    crossing = result["state_crossings"][0]
    assert crossing["from_state"] == "Texas"
    assert crossing["state"] == "Oklahoma"
    assert crossing["at_mi"] == 5.0


def test_initial_state_uses_parity_for_a_start_inside_the_second_square():
    leg = _leg()
    data = _data(leg)
    leg["miles"] = 10.0
    boundaries = rsc.build_boundary_index(_shared_square_boundaries())

    result = rsc.derive_state_context(data, leg, [[1.5, 0.5], [1.75, 0.5]], boundaries)

    assert result["state_crossings"] == []
    assert [(item["state"], item["miles"]) for item in result["state_miles"]] == [
        ("Oklahoma", 10.0)
    ]


def test_shared_vertex_hits_are_grouped_into_one_event():
    boundaries = rsc.build_boundary_index(_shared_square_boundaries())

    events = rsc._boundary_events([[0.5, 0.5], [1.5, -0.5]], boundaries)

    assert len(events) == 1
    assert events[0]["states"] == {"Texas", "Oklahoma"}
