import copy

import place_billboard_bans as pbb


def test_merge_runs_with_same_name_when_gap_is_under_one_mile():
    spans = [
        {"from_mi": 10.0, "to_mi": 11.2, "name": "Byway", "way_ids": ["1"]},
        {"from_mi": 11.9, "to_mi": 13.0, "name": "Byway", "way_ids": ["2"]},
        {"from_mi": 13.5, "to_mi": 14.0, "name": "Other", "way_ids": ["3"]},
    ]

    merged = pbb.merge_and_filter_spans(spans)

    assert merged == [
        {
            "from_mi": 10.0,
            "to_mi": 13.0,
            "name": "Byway",
            "way_ids": ["1", "2"],
            "source": "",
        }
    ]


def test_drop_runs_shorter_than_one_mile():
    spans = [
        {"from_mi": 1.0, "to_mi": 1.99, "name": "Short", "way_ids": ["1"]},
        {"from_mi": 4.0, "to_mi": 5.0, "name": "Long", "way_ids": ["2"]},
    ]

    assert [span["name"] for span in pbb.merge_and_filter_spans(spans)] == ["Long"]


def test_crossing_only_byway_produces_no_span():
    samples = [(39.0, -105.0 + index * 0.05 / 69.0, index * 0.05) for index in range(41)]
    crossing_mile = 1.0
    crossing = {
        "geometry": {
            "type": "LineString",
            "coordinates": [
                [-105.0 + crossing_mile / 69.0, 38.99],
                [-105.0 + crossing_mile / 69.0, 39.01],
            ],
        },
        "properties": {"name": "Crossing", "label": "99"},
    }
    matches = {"leg": [[] for _ in samples]}
    matches["leg"][20] = [{"way_id": "1", "ref": "US 99", "distance_m": 0.0}]

    assert (
        pbb.derive_colorado_spans([crossing], {"leg": samples}, matches, "2026-09-29")["leg"] == []
    )


def test_farther_matching_osm_ref_survives_nearer_unrelated_road():
    samples = [(39.0, -105.0 + mile / 69.0, mile) for mile in range(0, 22)]
    features = [
        {
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-105.0, 39.00001 + offset * 0.00001],
                    [-104.68, 39.00001 + offset * 0.00001],
                ],
            },
            "properties": {"name": f"Unrelated {offset}", "route": str(offset + 1)},
        }
        for offset in range(40)
    ]
    features.append(
        {
            "geometry": {
                "type": "LineString",
                "coordinates": [[-105.0, 39.001], [-104.68, 39.001]],
            },
            "properties": {"name": "Target Byway", "route": "99"},
        }
    )
    matches = {
        "leg": [
            [
                {"way_id": "near", "ref": "I 25", "distance_m": 1.0},
                {"way_id": "7", "ref": "US 99", "distance_m": 20.0},
            ]
            for _ in samples
        ]
    }

    spans = pbb.derive_colorado_spans(
        features,
        {"leg": samples},
        matches,
        "2026-09-29",
    )["leg"]

    assert len(spans) == 1
    assert spans[0]["name"] == "Target Byway"
    assert spans[0]["to_mi"] - spans[0]["from_mi"] >= 1.0
    assert "OSM route refs: US 99" in spans[0]["source"]
    assert "OpenStreetMap US PBF 2026-09-29" in spans[0]["source"]
    assert "OSM way IDs: 7" in spans[0]["source"]


def test_colorado_match_requires_the_full_osm_route_ref():
    samples = [(39.0, -105.0 + mile / 69.0, float(mile)) for mile in range(22)]
    feature = {
        "geometry": {
            "type": "LineString",
            "coordinates": [[-105.0, 39.00001], [-104.68, 39.00001]],
        },
        "properties": {"name": "State Highway Byway", "route": "025A", "label": "25"},
    }

    interstate_match = {
        "leg": [[{"way_id": "1", "ref": "I 25", "distance_m": 1.0}] for _ in samples]
    }
    assert (
        pbb.derive_colorado_spans([feature], {"leg": samples}, interstate_match, "2026-09-29")[
            "leg"
        ]
        == []
    )

    state_route_match = {
        "leg": [[{"way_id": "2", "ref": "CO 25", "distance_m": 1.0}] for _ in samples]
    }
    spans = pbb.derive_colorado_spans([feature], {"leg": samples}, state_route_match, "2026-09-29")[
        "leg"
    ]
    assert len(spans) == 1
    assert spans[0]["route_refs"] == ["CO 25"]


def test_cdot_segments_are_densified_for_distance_queries():
    feature = {
        "geometry": {
            "type": "MultiLineString",
            "coordinates": [[[-105.0, 39.0], [-104.999, 39.0]]],
        },
        "properties": {"name": "Byway", "route": "001A", "label": "1"},
    }

    segments, _ = pbb._cdot_segments([feature])

    assert len(segments) > 1
    assert pbb.expected_route_numbers(feature["properties"]) == {"1"}
    assert pbb.expected_route_refs(feature["properties"]) == {"CO 1", "US 1"}


def test_world_update_is_idempotent():
    data = {
        "legs": [
            {
                "from": "a_co_us",
                "to": "b_co_us",
                "corridor": {"billboard_bans": []},
            }
        ]
    }
    generated = {
        "a_co_us:b_co_us": [
            {
                "from_mi": 1.0,
                "to_mi": 3.0,
                "name": "Byway",
                "source": "CDOT dataset 6aqe-63uq; OSM PBF 2026-09-29; way IDs: 1.",
            }
        ]
    }

    assert pbb.update_world(data, generated) == 1
    snapshot = copy.deepcopy(data)
    assert pbb.update_world(data, generated) == 0
    assert data == snapshot
