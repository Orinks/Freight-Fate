"""Portable save layout: game-directory storage and legacy migration."""

import sys

from freight_fate.models import profile as profile_mod


def _reset(monkeypatch, tmp_path, game_dir=None, legacy_dir=None):
    """Point both roots at controlled temp locations."""
    monkeypatch.delenv("FREIGHT_FATE_DATA_DIR", raising=False)
    monkeypatch.setattr(profile_mod, "_legacy_checked", False)
    # These cover the portable Windows/Linux layout (saves beside the game).
    # Pin a non-darwin platform so the macOS Application Support branch in
    # _save_root() does not divert them when the test host is a Mac.
    monkeypatch.setattr(sys, "platform", "linux")
    game = game_dir or tmp_path / "game"
    game.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(profile_mod, "game_root", lambda: game)
    legacy = legacy_dir or tmp_path / "appdata"
    monkeypatch.setattr(profile_mod, "_legacy_data_dir", lambda: legacy / "FreightFate")
    return game, legacy / "FreightFate"


def test_env_override_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("FREIGHT_FATE_DATA_DIR", str(tmp_path / "custom"))
    assert profile_mod.data_dir() == tmp_path / "custom"


def test_data_dir_is_saves_inside_game_root(monkeypatch, tmp_path):
    game, _ = _reset(monkeypatch, tmp_path)
    assert profile_mod.data_dir() == game / "saves"


def test_game_root_when_frozen(monkeypatch, tmp_path):
    # a real temp path, so .resolve() behaves the same on Windows and Linux
    exe = tmp_path / "Games" / "FreightFate" / "FreightFate.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert profile_mod.game_root() == exe.resolve().parent


def test_game_root_when_nuitka_compiled(monkeypatch, tmp_path):
    # Nuitka builds do not set sys.frozen; is_frozen() detects them via the
    # __compiled__ global instead. game_root must still resolve to the
    # executable's directory, not the source-checkout fallback.
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr("freight_fate.updater.__compiled__", object(), raising=False)
    exe = tmp_path / "Games" / "FreightFate" / "FreightFate.exe"
    monkeypatch.setattr(sys, "executable", str(exe))
    assert profile_mod.game_root() == exe.resolve().parent


def test_game_root_for_macos_app_is_bundle_parent(monkeypatch, tmp_path):
    exe = (
        tmp_path / "Games" / "FreightFate.app" / "Contents" / "MacOS" / "FreightFate"
    )
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert profile_mod.game_root() == (tmp_path / "Games").resolve()


def test_game_root_from_source_is_project_root():
    root = profile_mod.game_root()
    assert (root / "src" / "freight_fate").is_dir()


def test_legacy_saves_migrate_once(monkeypatch, tmp_path):
    game, legacy = _reset(monkeypatch, tmp_path)
    old_profile = legacy / "profiles" / "Driver.json"
    old_profile.parent.mkdir(parents=True)
    old_profile.write_text("{}", encoding="utf-8")
    (legacy / "settings.json").write_text("{}", encoding="utf-8")

    target = profile_mod.data_dir()
    assert (target / "profiles" / "Driver.json").is_file()
    assert (target / "settings.json").is_file()
    assert old_profile.is_file()  # originals are left in place


def test_migration_never_overwrites_portable_saves(monkeypatch, tmp_path):
    game, legacy = _reset(monkeypatch, tmp_path)
    (legacy / "profiles").mkdir(parents=True)
    (legacy / "profiles" / "Old.json").write_text("{}", encoding="utf-8")
    existing = game / "saves" / "profiles"
    existing.mkdir(parents=True)
    (existing / "Current.json").write_text("{}", encoding="utf-8")

    target = profile_mod.data_dir()
    assert (target / "profiles" / "Current.json").is_file()
    assert not (target / "profiles" / "Old.json").exists()


def test_nested_install_moves_parent_portable_saves(monkeypatch, tmp_path):
    game = tmp_path / "freightfate" / "FreightFate"
    game.mkdir(parents=True)
    old_profile = tmp_path / "freightfate" / "saves" / "profiles" / "Driver.json"
    old_profile.parent.mkdir(parents=True)
    old_profile.write_text("{}", encoding="utf-8")
    _reset(monkeypatch, tmp_path, game_dir=game)

    target = profile_mod.data_dir()
    assert target == game / "saves"
    assert (target / "profiles" / "Driver.json").is_file()
    assert not (tmp_path / "freightfate" / "saves").exists()


def test_parent_install_moves_nested_portable_saves(monkeypatch, tmp_path):
    game = tmp_path / "freightfate"
    game.mkdir(parents=True)
    old_profile = game / "FreightFate" / "saves" / "profiles" / "Driver.json"
    old_profile.parent.mkdir(parents=True)
    old_profile.write_text("{}", encoding="utf-8")
    _reset(monkeypatch, tmp_path, game_dir=game)

    target = profile_mod.data_dir()
    assert target == game / "saves"
    assert (target / "profiles" / "Driver.json").is_file()
    assert not (game / "FreightFate" / "saves").exists()


def test_existing_active_saves_merge_parent_duplicate(monkeypatch, tmp_path):
    game = tmp_path / "freightfate" / "FreightFate"
    game.mkdir(parents=True)
    active_profile = game / "saves" / "profiles" / "Current.json"
    active_profile.parent.mkdir(parents=True)
    active_profile.write_text("{}", encoding="utf-8")
    duplicate_profile = tmp_path / "freightfate" / "saves" / "profiles" / "Old.json"
    duplicate_profile.parent.mkdir(parents=True)
    duplicate_profile.write_text("{}", encoding="utf-8")
    _reset(monkeypatch, tmp_path, game_dir=game)

    target = profile_mod.data_dir()
    assert (target / "profiles" / "Current.json").is_file()
    assert (target / "profiles" / "Old.json").is_file()
    assert not (tmp_path / "freightfate" / "saves").exists()


def test_macos_uses_application_support(monkeypatch, tmp_path):
    """macOS saves land in Application Support, never beside the app bundle."""
    monkeypatch.delenv("FREIGHT_FATE_DATA_DIR", raising=False)
    monkeypatch.setattr(profile_mod, "_legacy_checked", False)
    monkeypatch.setattr(sys, "platform", "darwin")
    app_support = tmp_path / "Application Support" / "FreightFate"
    monkeypatch.setattr(profile_mod, "_macos_data_dir", lambda: app_support)
    # The app bundle sits in an admin-owned /Applications-style folder.
    applications = tmp_path / "Applications"
    applications.mkdir()
    monkeypatch.setattr(profile_mod, "game_root", lambda: applications)

    assert profile_mod.data_dir() == app_support


def test_macos_app_moves_bundle_internal_saves(monkeypatch, tmp_path):
    """Saves an earlier build dropped beside/inside the bundle migrate into
    Application Support rather than staying in /Applications."""
    exe = (
        tmp_path / "Games" / "FreightFate.app" / "Contents" / "MacOS" / "FreightFate"
    )
    old_profile = exe.parent / "saves" / "profiles" / "Driver.json"
    old_profile.parent.mkdir(parents=True)
    old_profile.write_text("{}", encoding="utf-8")
    app_support = tmp_path / "Application Support" / "FreightFate"
    monkeypatch.delenv("FREIGHT_FATE_DATA_DIR", raising=False)
    monkeypatch.setattr(profile_mod, "_legacy_checked", False)
    monkeypatch.setattr(profile_mod, "_macos_data_dir", lambda: app_support)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "darwin")

    target = profile_mod.data_dir()
    assert target == app_support
    assert (target / "profiles" / "Driver.json").is_file()
    assert not (exe.parent / "saves").exists()


def test_macos_moves_saves_beside_app_bundle(monkeypatch, tmp_path):
    """The reported bug: saves dropped in /Applications next to the .app are
    relocated into Application Support."""
    applications = tmp_path / "Applications"
    beside = applications / "saves" / "profiles" / "Driver.json"
    beside.parent.mkdir(parents=True)
    beside.write_text("{}", encoding="utf-8")
    app_support = tmp_path / "Application Support" / "FreightFate"
    monkeypatch.delenv("FREIGHT_FATE_DATA_DIR", raising=False)
    monkeypatch.setattr(profile_mod, "_legacy_checked", False)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(profile_mod, "_macos_data_dir", lambda: app_support)
    monkeypatch.setattr(profile_mod, "game_root", lambda: applications)

    target = profile_mod.data_dir()
    assert target == app_support
    assert (target / "profiles" / "Driver.json").is_file()
    assert not (applications / "saves").exists()
