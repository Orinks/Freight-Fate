"""Tests for tools/build_channel3000.py: Channel 3000's own pack and manifest."""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import assets_pack
import build_channel3000
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _clip(key, kind, dayparts, *, opener=False, title="Channel 3000", duration_s=10.0):
    return {
        "key": key,
        "kind": kind,
        "dayparts": dayparts,
        "opener": opener,
        "title": title,
        "duration_s": duration_s,
    }


def _manifest() -> dict:
    """The smallest station that runs: per daypart a programme, an ident, an opener."""
    clips = [_clip("ad_c3k_fixture", "ad", list(build_channel3000.DAYPARTS), duration_s=30.0)]
    for part in build_channel3000.DAYPARTS:
        clips += [
            _clip(f"{part}_show_01", "programme", [part], title=f"The {part} show", duration_s=600),
            _clip(f"id_{part}", "ident", [part], duration_s=6.0),
            _clip(f"host_{part}", "continuity", [part], opener=True, duration_s=12.0),
        ]
    return {
        "schema": 1,
        "notes": "fixture",
        "frequency_mhz": 87.7,
        "dayparts": {"day": [5, 19], "prime": [19, 22], "late": [22, 2], "overnight": [2, 5]},
        "clips": clips,
    }


def _write_source(tmp_path: Path, manifest: dict | None = None) -> Path:
    manifest = manifest or _manifest()
    source = tmp_path / "c3k-clips"
    (source / "clips").mkdir(parents=True)
    for clip in manifest["clips"]:
        (source / "clips" / f"{clip['key']}.opus").write_bytes(f"opus {clip['key']}".encode())
    (source / "clips.json").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return source


def _errors(source: Path) -> list[str]:
    return build_channel3000.validate(
        build_channel3000.load_manifest(source / "clips.json"), source / "clips"
    )


def test_a_whole_station_validates(tmp_path):
    assert _errors(_write_source(tmp_path)) == []


def test_build_packs_every_clip_under_c3k_and_copies_the_manifest(tmp_path):
    source = _write_source(tmp_path)
    pack_path, manifest_path = build_channel3000.build(
        source, tmp_path / "channel3000.pak", tmp_path / "channel3000.json"
    )
    pack = assets_pack.SoundPack(pack_path)
    keys = [clip["key"] for clip in _manifest()["clips"]]
    assert sorted(pack.names()) == sorted(f"c3k/{key}.opus" for key in keys)
    assert pack.read("c3k/day_show_01.opus") == b"opus day_show_01"
    assert manifest_path.read_bytes() == (source / "clips.json").read_bytes()


def test_entries_are_stored_not_deflated(tmp_path):
    out = build_channel3000.write_channel3000_pack(
        _write_source(tmp_path) / "clips", tmp_path / "channel3000.pak"
    )
    raw = out.read_bytes()
    assert raw.startswith(assets_pack.PACK_MAGIC)
    payload = assets_pack._mask(raw[len(assets_pack.PACK_MAGIC) :])
    with zipfile.ZipFile(io.BytesIO(payload)) as z:
        assert {info.compress_type for info in z.infolist()} == {zipfile.ZIP_STORED}


def test_pack_is_byte_for_byte_deterministic(tmp_path):
    clips = _write_source(tmp_path) / "clips"
    first = build_channel3000.write_channel3000_pack(clips, tmp_path / "a.pak")
    second = build_channel3000.write_channel3000_pack(clips, tmp_path / "b.pak")
    assert first.read_bytes() == second.read_bytes()


def test_a_manifest_key_with_no_clip_is_refused(tmp_path):
    source = _write_source(tmp_path)
    (source / "clips" / "day_show_01.opus").unlink()
    assert any("day_show_01 is in the manifest" in e for e in _errors(source))


def test_a_clip_with_no_manifest_row_is_refused(tmp_path):
    source = _write_source(tmp_path)
    (source / "clips" / "night_starhauler_01.opus").write_bytes(b"opus")
    assert any("night_starhauler_01.opus is in the clips folder" in e for e in _errors(source))


def test_a_stray_file_in_the_clips_folder_is_refused(tmp_path):
    source = _write_source(tmp_path)
    (source / "clips" / "notes.txt").write_text("not a clip")
    assert any("notes.txt" in e for e in _errors(source))


def test_build_refuses_a_mismatch_and_writes_nothing(tmp_path):
    source = _write_source(tmp_path)
    (source / "clips" / "id_day.opus").unlink()
    with pytest.raises(ValueError, match="id_day"):
        build_channel3000.build(source, tmp_path / "out.pak", tmp_path / "out.json")
    assert not (tmp_path / "out.pak").exists()
    assert not (tmp_path / "out.json").exists()


def test_more_programmes_are_simply_more_clips(tmp_path):
    # Counts are never pinned: two more prime shows may land on the branch.
    manifest = _manifest()
    manifest["clips"] += [
        _clip("night_starhauler_01", "programme", ["prime"], title="Starhauler"),
        _clip("night_starhauler_02", "programme", ["prime"], title="Starhauler"),
    ]
    assert _errors(_write_source(tmp_path, manifest)) == []


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda m: m["clips"][1].update(duration_s=0), "must be above zero"),
        (lambda m: m["clips"][1].update(duration_s=-3.5), "must be above zero"),
        (lambda m: m["clips"][1].update(kind="documentary"), "unknown kind"),
        (lambda m: m["clips"][1].update(dayparts=["brunch"]), "unknown dayparts"),
        (lambda m: m["clips"][1].update(dayparts=[]), "has no dayparts"),
        (lambda m: m["clips"][1].update(title=""), "has no title"),
        (lambda m: m["clips"].pop(1), "daypart day has no programmes"),
        (lambda m: m["clips"].pop(2), "daypart day has no idents"),
        (lambda m: m["clips"][3].update(opener=False), "daypart day has 0 openers"),
        (
            lambda m: m["clips"].append(_clip("host_day_02", "continuity", ["day"], opener=True)),
            "daypart day has 2 openers",
        ),
        (lambda m: m["clips"][2].update(opener=True), "is an opener but not a continuity line"),
        (lambda m: m.update(schema=2), "schema"),
        (lambda m: m["dayparts"].pop("late"), "dayparts must be exactly"),
    ],
)
def test_bad_manifests_are_refused(tmp_path, change, expected):
    manifest = _manifest()
    change(manifest)
    source = _write_source(tmp_path, manifest)
    # A popped row's clip is still on disk; only the named error matters here.
    assert any(expected in e for e in _errors(source)), _errors(source)


def test_committed_manifest_is_a_station_that_runs():
    # The committed copy alone: the clips themselves live on their own branch.
    manifest = build_channel3000.load_manifest(ROOT / "data" / "channel3000.json")
    errors = [
        e
        for e in build_channel3000.validate(manifest, ROOT / "no-clips-here")
        if "no clips folder" not in e
    ]
    assert errors == []
    assert manifest["frequency_mhz"] == 87.7


def test_the_pack_is_gitignored():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert "assets/channel3000.pak" in ignored


def test_main_check_writes_nothing(tmp_path, capsys):
    source = _write_source(tmp_path)
    out = tmp_path / "never.pak"
    assert build_channel3000.main([str(source), "--check", "--out", str(out)]) == 0
    assert not out.exists()
    assert "Clips and manifest agree." in capsys.readouterr().out
