import json

import extract_osm_state_boundaries as extract


def _payload():
    return {
        "source_timestamp": "2026-09-29T20:22:51Z",
        "states": [
            {
                "name": "Alaska",
                "iso": "US-AK",
                "relation_id": 1,
                "ways": [[[0.0, 0.0], [1.0, 1.0]]],
            }
        ],
    }


def test_incomplete_state_is_fatal_without_an_explicit_allowance(tmp_path, monkeypatch, capsys):
    pbf = tmp_path / "us-latest.osm.pbf"
    output = tmp_path / "boundaries.json"
    pbf.touch()
    monkeypatch.setattr(
        extract,
        "extract_boundaries",
        lambda _path: (_payload(), ["US-AK: two odd-degree endpoints"]),
    )

    assert extract.main(["--pbf", str(pbf), "--out", str(output)]) == 1

    assert not output.exists()
    assert "ERROR: US-AK: two odd-degree endpoints" in capsys.readouterr().err


def test_only_explicitly_allowed_incomplete_states_are_cached(tmp_path, monkeypatch, capsys):
    pbf = tmp_path / "us-latest.osm.pbf"
    output = tmp_path / "boundaries.json"
    pbf.touch()
    monkeypatch.setattr(
        extract,
        "extract_boundaries",
        lambda _path: (
            _payload(),
            ["US-AK: missing member way", "US-CA: odd-degree endpoints"],
        ),
    )

    result = extract.main(
        [
            "--pbf",
            str(pbf),
            "--out",
            str(output),
            "--allow-incomplete-state",
            "US-AK",
        ]
    )

    assert result == 1
    assert not output.exists()
    errors = capsys.readouterr().err
    assert "WARNING: US-AK: missing member way" in errors
    assert "ERROR: US-CA: odd-degree endpoints" in errors


def test_reviewed_incomplete_state_can_be_explicitly_cached(tmp_path, monkeypatch, capsys):
    pbf = tmp_path / "us-latest.osm.pbf"
    output = tmp_path / "boundaries.json"
    payload = _payload()
    pbf.touch()
    monkeypatch.setattr(
        extract,
        "extract_boundaries",
        lambda _path: (payload, ["US-AK: missing member way"]),
    )

    result = extract.main(
        [
            "--pbf",
            str(pbf),
            "--out",
            str(output),
            "--allow-incomplete-state",
            "US-AK",
        ]
    )

    assert result == 0
    assert json.loads(output.read_text(encoding="utf-8")) == payload
    assert "Proceeding with the explicitly allowed incomplete state boundary" in (
        capsys.readouterr().err
    )
