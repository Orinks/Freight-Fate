"""Radio, weather, and terrain-law abuse.

Chains left on bare pavement, a full jake on glare ice, rolling a Level 2
chain law bare, and spinning the radio dial across a 1,200-mile teleport.
"""

from __future__ import annotations

import re

from playtest_break import Outcome, Rig, _fresh_data_dir, _outcome, scenario


@scenario(
    "chains_on_dry_interstate_at_70",
    "Leave the chains on and run 70 on bare pavement: wear math, snap event, spoken truth.",
)
def _chains_dry():
    rig = Rig()
    findings: list[str] = []
    try:
        d = rig.d
        t = d.truck
        d.trip.position_mi = 12.0
        d.trip.curves = []
        t.chains_on = True
        rig.prepare(speed_mph=70.0)
        start_mi = d.trip.position_mi
        rig.held.add(rig.pygame.K_UP)
        rig.step(9000, until=lambda: not t.chains_on)
        snap_mi = d.trip.position_mi - start_mi
        if t.chains_on:
            findings.append("chains survived miles of bare pavement at 70")
        else:
            if rig.said("chain let go") == 0:
                findings.append("chain snap happened silently")
            if rig.said("chains are hammering") == 0:
                findings.append("no overspeed-chain warning before the snap")
            # 0.2 %/mi x40 bare x6 overspeed = 48 %/mi -> ~2.1 miles to scrap.
            if not (0.8 <= snap_mi <= 4.5):
                findings.append(f"chains lasted {snap_mi:.1f} mi; wear model predicts ~2.1")
        return _outcome(
            "chains_on_dry_interstate_at_70",
            rig,
            findings,
            f"snapped after {snap_mi:.1f} mi with both warnings spoken",
        )
    finally:
        rig.close()


@scenario(
    "glare_ice_full_jake",
    "Stage-3 jake in a low gear on glare ice: the drive axle must slide, and say so.",
)
def _ice_jake():
    rig = Rig(automatic=False)
    findings: list[str] = []
    try:
        d = rig.d
        t = d.truck
        d.trip.position_mi = 12.0
        d.trip.curves = []
        d.weather.current = rig.WeatherKind.ICE
        rig.prepare(speed_mph=30.0, gear=4)
        t.engine_brake = True
        t.throttle = 0.0
        rig.step(90)
        if not t.jake_slipping:
            findings.append(
                f"full jake in gear 4 at 30 mph on ice (grip {t.effective_grip:.2f}) never "
                "broke the drive axle loose"
            )
        if rig.said("drive wheels are sliding") == 0:
            findings.append("jake slip has no spoken warning on ice")
        demand = t._jake_force_demand()
        delivered = t.jake_brake_force()
        if demand > 0 and delivered > t._jake_traction_cap() + 1e-6:
            findings.append("jake force exceeded the drive-axle traction cap")
        dry_decel = None
        ice_decel = t.full_service_decel_mps2()
        d.weather.current = rig.WeatherKind.CLEAR
        rig.step(2)
        dry_decel = t.full_service_decel_mps2()
        if dry_decel <= ice_decel * 2.0:
            findings.append(
                f"full-brake decel on ice ({ice_decel:.2f}) is not meaningfully worse than "
                f"dry ({dry_decel:.2f})"
            )
        return _outcome(
            "glare_ice_full_jake",
            rig,
            findings,
            f"axle slid, warning spoken, ice stop {ice_decel:.2f} vs dry {dry_decel:.2f} m/s2",
        )
    finally:
        rig.close()


@scenario(
    "chain_law_citation_balance",
    "Roll through a Level 2 chain law bare; citation, spoken balance, and tire claims checked.",
)
def _chain_law():
    import random as random_mod

    from freight_fate.sim.vehicle import TIRE_WINTER
    from freight_fate.states.driving_core import CHAIN_LAW_CHECKPOINT_CHANCE, CHAIN_LAW_FINE

    # Pick a trip seed whose deterministic checkpoint roll is a hit.
    seed = next(
        s
        for s in range(1000, 1200)
        if random_mod.Random(f"{s}:chain-law:0:2").random() < CHAIN_LAW_CHECKPOINT_CHANCE
    )
    rig = Rig(seed=seed)
    findings: list[str] = []
    try:
        d = rig.d
        t = d.truck
        p = rig.ctx.profile
        d.trip.chain_law_areas = [(10.0, 14.0)]
        d.weather.current = rig.WeatherKind.ICE  # surface ice -> Level 2, chains required
        rig.prepare(speed_mph=30.0)
        rig.step(3)  # let the trip push weather surface onto the truck
        d.trip.position_mi = 12.5  # past the area midpoint: checkpoint territory
        money_before = p.money
        d._update_chain_law()
        if rig.said("without chains") == 0:
            findings.append("no spoken warning for entering a Level 2 chain law bare")
        d._update_chain_law()
        cited = rig.lines_with("chain-law citation")
        if not cited:
            findings.append("seeded checkpoint roll was a hit but no citation was written")
        else:
            delta = money_before - p.money
            if abs(delta - CHAIN_LAW_FINE) > 0.01:
                findings.append(f"citation took {delta:,.0f}, the fine is {CHAIN_LAW_FINE:,.0f}")
            m = re.search(r"You have (-?[\d,]+) dollars", cited[0])
            if m and abs(float(m.group(1).replace(",", "")) - round(p.money)) > 0.5:
                findings.append(
                    f"citation spoke a balance of {m.group(1)} but the ledger holds {p.money:,.0f}"
                )
        # Winter tires satisfy Level 1 but never Level 2 -- and the warning
        # must name chains, not tires, when only chains will do.
        d.weather.current = rig.WeatherKind.SNOW
        rig.step(3)
        t.tire_type = TIRE_WINTER
        d.trip.position_mi = 10.5
        before = len(rig.transcript)
        d._update_chain_law()
        if len(rig.transcript) != before:
            findings.append("winter tires drew a chain-law warning at Level 1 (compliant)")
        d.weather.current = rig.WeatherKind.ICE
        rig.step(3)
        d._update_chain_law()
        level2 = [ln for ln in rig.transcript[before:] if "chain law without" in ln]
        if level2 and "chains" not in level2[-1].split("without", 1)[1]:
            findings.append("Level 2 warning did not name chains as the requirement")
        return _outcome(
            "chain_law_citation_balance",
            rig,
            findings,
            f"citation billed {CHAIN_LAW_FINE:,.0f}, spoken balance matched, tier claims held",
        )
    finally:
        rig.close()


@scenario(
    "radio_dial_abuse_offline",
    "Spin the dial, favorite it, tune through a dead handover, then teleport 1,200 miles.",
)
def _radio_dial():
    _fresh_data_dir()
    from freight_fate.radio import RadioState
    from freight_fate.settings import Settings

    findings: list[str] = []
    played: list[str] = []
    stopped: list[bool] = []
    volumes: list[float] = []

    class StubBackend:
        def play_station(self, station, volume) -> None:
            played.append(station.id)
            volumes.append(volume)

        def stop_radio(self) -> None:
            stopped.append(True)

    settings = Settings()
    settings.radio_enabled = True
    radio = RadioState.from_settings(settings, None)
    backend = StubBackend()
    radio.update_position((42.886, -78.878), 600.0)  # Buffalo
    messages: list[str] = []
    action = radio.toggle(backend)
    messages.append(action.message)
    for _ in range(18):
        action = radio.tune(1, backend)
        messages.append(action.message)
        reception = radio.current_reception()
        if not (0.0 <= reception.signal <= 1.0):
            findings.append(f"reception signal out of bounds: {reception.signal}")
    messages.append(radio.toggle_favorite())

    # Volume 0 must read as "silent," never claim to be "off" -- muting and
    # zero-volume are different states and a screen reader user relies on
    # the status line to tell them apart.
    if hasattr(radio, "set_volume"):
        radio.set_volume(0.0)
        zero_vol_text = radio.status_text()
        if "off" in zero_vol_text.lower() and "volume" not in zero_vol_text.lower():
            findings.append(
                f"volume 0 status reads {zero_vol_text!r} -- indistinguishable from radio off"
            )
        radio.set_volume(0.5)

    radio.update_position((25.77, -80.19), 10.0)  # Miami, 1,200 miles from the dial
    reception = radio.current_reception()
    if not (0.0 <= reception.signal <= 1.0):
        findings.append(f"post-teleport signal out of bounds: {reception.signal}")
    messages.append(radio.status_text())
    for message in messages:
        if not message or not message.strip():
            findings.append("a radio action produced an empty spoken message")
            break
    for message in messages:
        if "http" in message.lower() or "://" in message:
            findings.append(f"radio speech leaked a stream URL: {message[:80]}")
            break
    verdict = "ODD" if findings else "CLEAN"
    note = (
        findings[0]
        if findings
        else (f"{len(messages)} spoken radio actions, signals bounded, no URLs leaked")
    )
    return Outcome("radio_dial_abuse_offline", verdict, note, findings, messages)
