import snap_stops_to_interchanges as snap


def test_selected_legs_limits_stop_refresh_to_requested_routes():
    legs = [
        {"from": "a_pa_us", "to": "b_nj_us"},
        {"from": "c_ny_us", "to": "d_ct_us"},
    ]

    assert snap._selected_legs(legs, "c_ny_us->d_ct_us") == [legs[1]]
    assert snap._selected_legs(legs, None) is legs


def test_explicit_osm_extracts_override_missing_state_cache(tmp_path):
    pbf = tmp_path / "corridor.osm.pbf"
    pbf.touch()

    assert snap._input_pbf_paths({"Pennsylvania"}, tmp_path / "missing", [pbf]) == [pbf]
