import reroute_enrich as re


def test_pending_legs_uses_missing_grade_profile_not_empty_interchanges():
    enriched_without_interchanges = {
        "from": "a_tx_us",
        "to": "b_tx_us",
        "rerouted": True,
        "corridor": {
            "interchanges": [],
            "grade_segments": [{"start_mi": 0.0, "end_mi": 1.0}],
        },
    }
    pending_without_grade_profile = {
        "from": "c_tx_us",
        "to": "d_tx_us",
        "rerouted": True,
        "corridor": {"interchanges": []},
    }
    untouched_leg = {
        "from": "e_tx_us",
        "to": "f_tx_us",
        "corridor": {},
    }

    assert re.pending_legs(
        {
            "legs": [
                enriched_without_interchanges,
                pending_without_grade_profile,
                untouched_leg,
            ]
        }
    ) == [pending_without_grade_profile]


def test_interchanges_are_only_expected_for_eligible_local_routes():
    assert "interchanges" not in re.expected_layers_for_leg(
        {"highway": "US-10", "corridor": {"interchanges": []}}, True
    )
    assert "interchanges" in re.expected_layers_for_leg(
        {"highway": "I-5", "corridor": {"interchanges": []}}, True
    )
    assert "interchanges" not in re.expected_layers_for_leg(
        {"highway": "I-5", "corridor": {"interchanges": []}}, False
    )
