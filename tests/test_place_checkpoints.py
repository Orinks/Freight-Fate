from pathlib import Path

import place_checkpoints as pc


def test_candidate_source_is_preserved():
    candidate = pc._parse_candidate(
        "Dakota|43.913886|-91.359848|Minnesota|village|US-61|OSM place-cache node 151345351"
    )

    assert candidate["source"] == "OSM place-cache node 151345351"


def test_existing_checkpoint_can_be_replaced():
    existing = [
        {"name": "Green Spring", "at_mi": 14.8},
        {"name": "Cumberland", "at_mi": 1.0},
    ]
    accepted = [{"name": "Oldtown", "at_mi": 14.8}]

    merged = pc.merge_checkpoints(existing, accepted, ["Green Spring"])

    assert merged == [
        {"name": "Cumberland", "at_mi": 1.0},
        {"name": "Oldtown", "at_mi": 14.8},
    ]


def test_archived_route_geometry_is_used_without_an_ors_key(monkeypatch):
    monkeypatch.setattr(
        pc.lg,
        "archived_polyline",
        lambda _leg_id, _state: ([[0.0, 0.0], [1.0, 0.0]], []),
    )
    data = {"legs": []}
    leg = {"from": "a_tx_us", "to": "b_tx_us", "miles": 69.0}

    route, source = pc._route_geometry(data, leg, True, Path("."), 0.0, None)

    assert route["coordinates"] == [[0.0, 0.0], [1.0, 0.0]]
    assert source == "archived dense route geometry"
