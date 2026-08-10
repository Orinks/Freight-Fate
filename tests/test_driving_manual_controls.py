import pygame
import pytest
from driving_feature_helpers import open_limits, quiet_trip, start_drive


def test_shift_modified_manual_downshift_uses_clutch_before_next_update(monkeypatch):
    from freight_fate.app import App

    class Keys:
        pressed = {pygame.K_LSHIFT}

        def __getitem__(self, key):
            return key in self.pressed

    monkeypatch.setattr(pygame.key, "get_pressed", lambda: Keys())

    app = App()
    try:
        driving = start_drive(app)
        quiet_trip(driving)
        open_limits(driving)
        app.ctx.settings.automatic_transmission = False
        truck = driving.truck
        truck.start_engine()
        truck.set_air_ready(parking_brake=False)
        truck.transmission.automatic = False
        truck.transmission.gear = 2
        truck.transmission.clutch = 0.0  # stale until the update loop samples held keys
        truck.velocity_mps = 60.0 / 2.23694
        truck.rpm = truck.specs.idle_rpm

        driving.handle_event(
            pygame.event.Event(
                pygame.KEYDOWN,
                key=pygame.K_q,
                unicode="q",
                mod=pygame.KMOD_SHIFT,
            )
        )

        assert truck.transmission.gear == 1
        assert truck.transmission.clutch == 1.0
        assert truck.coupled_rpm() > truck.specs.max_rpm * 1.05
        assert not truck.over_revving

        for _ in range(5 * 60):
            driving.update(1 / 60)

        assert truck.rpm < truck.specs.max_rpm * 0.6
        assert truck.damage_pct == pytest.approx(0.0)
    finally:
        app.shutdown()
