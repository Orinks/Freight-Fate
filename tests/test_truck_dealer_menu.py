"""The terminal menu opens the truck dealer directly.

The "Drive to city services" driving machinery is gone; the terminal's
menu item is a direct hop into ``TruckShopState``, and its spoken entry
names the source-backed dealer when one exists.
"""

from speech_capture import speech_stub


def _profile(name="Dale", **kwargs):
    from freight_fate.models.profile import Profile

    p = Profile(name=name, current_city="Buffalo")
    for key, value in kwargs.items():
        setattr(p, key, value)
    return p


def _quiet(app, monkeypatch):
    spoken = []
    monkeypatch.setattr(app.ctx, "say", speech_stub(spoken))
    monkeypatch.setattr(app.ctx, "say_event", speech_stub(spoken))
    monkeypatch.setattr(app.ctx.audio, "play", lambda *a, **k: None)
    return spoken


def test_the_terminal_menu_offers_truck_dealer_directly(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState

    app = App()
    try:
        app.ctx.profile = _profile()
        _quiet(app, monkeypatch)
        menu = CityMenuState(app.ctx)
        items = menu.build_items()

        assert any(item.text == "Truck dealer" for item in items)
        assert not any(item.text == "Drive to city services" for item in items)
    finally:
        app.shutdown()


def test_the_truck_dealer_item_pushes_truck_shop_state(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city import CityMenuState
    from freight_fate.states.city_business import TruckShopState

    app = App()
    try:
        app.ctx.profile = _profile()
        _quiet(app, monkeypatch)
        menu = CityMenuState(app.ctx)
        item = next(i for i in menu.build_items() if i.text == "Truck dealer")
        item.action()

        assert isinstance(app.state, TruckShopState)
    finally:
        app.shutdown()


def test_truck_shop_entry_names_the_source_backed_dealer(monkeypatch):
    """Opened from the terminal's "Truck dealer" row (at_dealer=True), the
    entry names the source-backed dealer the player is actually standing in."""
    from freight_fate.app import App
    from freight_fate.states.city_business import TruckShopState

    app = App()
    try:
        app.ctx.profile = _profile(current_city="Indianapolis")
        spoken = _quiet(app, monkeypatch)
        dealer = app.ctx.world.city_service("Indianapolis", "truck_dealer")
        assert not dealer.fallback

        app.push_state(TruckShopState(app.ctx, at_dealer=True))

        assert any(dealer.name in line for line in spoken)
        assert any(line.startswith(f"Inside {dealer.name}. Trucks.") for line in spoken)
    finally:
        app.shutdown()


def test_truck_shop_entry_stays_plain_for_a_fallback_city(monkeypatch):
    from freight_fate.app import App
    from freight_fate.states.city_business import TruckShopState

    app = App()
    try:
        app.ctx.profile = _profile(current_city="Erie")
        spoken = _quiet(app, monkeypatch)
        dealer = app.ctx.world.city_service("Erie", "truck_dealer")
        assert dealer.fallback

        app.push_state(TruckShopState(app.ctx, at_dealer=True))

        assert any(line.startswith("Trucks. You have") for line in spoken)
        assert not any("Inside" in line for line in spoken)
    finally:
        app.shutdown()


def test_truck_shop_entry_stays_plain_from_the_garage(monkeypatch):
    """Opened from the terminal garage's "Trucks" row (no at_dealer flag),
    the entry never names the dealer -- even in a city with a real
    source-backed one -- because the player is standing in the garage, not
    the dealership, and naming it would contradict where they actually are."""
    from freight_fate.app import App
    from freight_fate.states.city_business import TruckShopState
    from freight_fate.states.city_garage import GarageState

    app = App()
    try:
        app.ctx.profile = _profile(current_city="Indianapolis")
        spoken = _quiet(app, monkeypatch)
        dealer = app.ctx.world.city_service("Indianapolis", "truck_dealer")
        assert not dealer.fallback

        garage = GarageState(app.ctx)
        app.push_state(garage)
        item = next(i for i in garage.build_items() if i.text == "Trucks")
        item.action()

        assert isinstance(app.state, TruckShopState)
        assert app.state.at_dealer is False
        assert not any("Inside" in line for line in spoken)
        assert not any(dealer.name in line for line in spoken)
    finally:
        app.shutdown()
