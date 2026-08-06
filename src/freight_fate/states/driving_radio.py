# ruff: noqa: F403,F405
"""The in-cab radio while driving: tuning, reception, and what it says.

The tuner itself lives in ``sim.radio`` and knows nothing about audio; this
mixin is the wiring between it, the position on the route, and the stream the
audio engine plays. It is deliberately quiet: the radio only speaks when the
driver presses a key or when reception actually changes, because a voice
talking over a station is the one thing a screen reader user cannot filter out.
"""

from __future__ import annotations

from ..sim.radio import RadioTuner, band_text, station_text
from .driving_core import *

# How often the truck's map position is pushed into the tuner. Reception
# changes over miles, so once a second is far more often than it can matter,
# and it keeps the catalog scan off the frame budget.
RADIO_POSITION_INTERVAL_S = 1.0

# Signal below this is inaudible anyway; the stream is dropped rather than
# played into silence, which also frees the connection on a long dead stretch.
RADIO_MIN_AUDIBLE_SIGNAL = 0.02


class DrivingRadioMixin:
    # -- access ---------------------------------------------------------------

    @property
    def radio(self) -> RadioTuner:
        """The tuner, built on first use.

        Lazy because the catalog is a megabyte of stations and most runs never
        switch the radio on: a player who never presses the radio key never
        pays for it.
        """
        tuner = getattr(self, "_radio", None)
        if tuner is None:
            position = self.trip.position_latlon() or (0.0, 0.0)
            tuner = RadioTuner(lat=position[0], lon=position[1])
            self._radio = tuner
            self._radio_position_timer = 0.0
        return tuner

    def _radio_available(self) -> bool:
        """Whether the radio can play at all, saying why once when it cannot."""
        if not self.ctx.settings.radio_enabled:
            self.ctx.say(
                "The radio is switched off in Settings, Audio. Turn on "
                "Radio stations to listen while you drive."
            )
            return False
        if not self.ctx.audio.radio_supported:
            self.ctx.say(
                "The radio needs the BASS sound system, which is not running. "
                "Everything else still works."
            )
            return False
        return True

    # -- controls -------------------------------------------------------------

    def _toggle_radio(self) -> None:
        """Radio on or off. Off is instant, so it doubles as the mute key."""
        tuner = getattr(self, "_radio", None)
        if tuner is not None and tuner.on:
            self._stop_radio_and_restore_music()
            self.ctx.say("Radio off.")
            self._set_status("Radio off.")
            return
        if not self._radio_available():
            return
        station = self.radio.turn_on()
        if station is None:
            self.ctx.say("Radio on. Nothing is in range.")
            self._set_status("Radio on, nothing in range.")
            return
        self._announce_station(station)

    def _seek_radio(self, step: int) -> None:
        """Step along the dial. Turns the radio on if it was off."""
        if not self._radio_available():
            return
        tuner = self.radio
        if not tuner.on:
            tuner.turn_on()
        available = tuner.stations_for(tuner.band)
        if not available:
            self.ctx.say(f"Nothing on {band_text(tuner.band)}.")
            return
        if len(available) == 1:
            # Seeking a band with one station on it just re-reads that station.
            # Say so instead: a driver pressing the key again and again is
            # asking for something else, not for the same line twelve times.
            self.ctx.say(
                f"{available[0].name} is the only station on "
                f"{band_text(tuner.band)}. Press Y for another band."
            )
            self.driving_radio_tune_single(available[0])
            return
        station = tuner.seek(step)
        if station is None:
            self.ctx.say(f"Nothing on {band_text(tuner.band)}.")
            return
        self._announce_station(station)

    def driving_radio_tune_single(self, station) -> None:
        """Make sure the one station on this band is the one actually playing."""
        tuner = self.radio
        if tuner.station is not station:
            tuner.tune(station)
        self._start_radio_stream()

    def _cycle_radio_band(self) -> None:
        if not self._radio_available():
            return
        tuner = self.radio
        if not tuner.on:
            tuner.turn_on()
        tuner.next_band()
        if tuner.station is None:
            self.ctx.say(f"{band_text(tuner.band)}, nothing in range.")
            return
        self._announce_station(tuner.station)

    def _open_radio_menu(self) -> None:
        from .radio_states import RadioState

        self.ctx.push_state(RadioState(self.ctx, self))

    def _speak_radio_status(self) -> None:
        tuner = getattr(self, "_radio", None)
        if tuner is None or not tuner.on:
            self.ctx.say("Radio off.")
            return
        self.ctx.say(tuner.describe())

    def _announce_station(self, station) -> None:
        """Say what just came on, and start playing it."""
        text = station_text(station, self.radio.signal)
        self.ctx.say(text)
        self._set_status(text)
        self._start_radio_stream()

    # -- per-frame ------------------------------------------------------------

    def radio_owns_audio(self) -> bool:
        """True while the radio is what the cab is playing.

        The game's own music beds and a radio station are both music. Playing
        them together is a wall of sound a screen reader user cannot hear
        through, so whichever one the driver chose wins outright.
        """
        tuner = getattr(self, "_radio", None)
        return bool(tuner is not None and tuner.on and self.ctx.settings.radio_enabled)

    def _start_radio_stream(self) -> None:
        tuner = getattr(self, "_radio", None)
        if tuner is None or not tuner.on or tuner.station is None:
            return
        # The radio takes over from the music bed, including a menu bed left
        # rotating by a pause the drive is resuming from.
        self.ctx.clear_music_rotation()
        self.ctx.audio.stop_music(1200)
        self.ctx.audio.set_radio_gain(max(RADIO_MIN_AUDIBLE_SIGNAL, tuner.signal))
        self.ctx.audio.play_radio(tuner.station.url)

    def _stop_radio_and_restore_music(self) -> None:
        """Switch the radio off and hand the cab back to the music bed."""
        tuner = getattr(self, "_radio", None)
        if tuner is not None:
            tuner.turn_off()
        self.ctx.audio.stop_radio()
        self._play_current_music(fade_ms=2500)

    def _update_radio(self, dt: float) -> None:
        """Follow the truck down the road: reception, fades, and dropouts."""
        tuner = getattr(self, "_radio", None)
        if tuner is None or not tuner.on:
            return
        if not self.ctx.settings.radio_enabled:
            # Switched off in Settings mid-drive; stop rather than keep playing.
            self._stop_radio_and_restore_music()
            return

        self._radio_position_timer = getattr(self, "_radio_position_timer", 0.0) + dt
        if self._radio_position_timer >= RADIO_POSITION_INTERVAL_S:
            self._radio_position_timer = 0.0
            position = self.trip.position_latlon()
            if position is not None:
                change = tuner.set_position(*position)
                if change.lost is not None:
                    self._announce_lost_station(change)
                    return

        station = tuner.station
        if station is None:
            return
        signal = tuner.signal
        if signal <= RADIO_MIN_AUDIBLE_SIGNAL:
            return  # about to be handed over by set_position; do not thrash
        self.ctx.audio.set_radio_gain(signal)
        if self.ctx.audio.radio_state in ("idle", "failed"):
            # Either the drive is resuming after a pause stopped the world, or
            # the stream died. Both recover the same way: tune it again.
            if self.ctx.audio.radio_state == "failed":
                self._hand_over_from_dead_stream(station)
            else:
                self.ctx.audio.play_radio(station.url)

    def _announce_lost_station(self, change) -> None:
        lost = change.lost.call_sign or change.lost.name
        if change.fell_back_to is None:
            self.ctx.audio.stop_radio()
            self.ctx.say_event(f"{lost} lost. Nothing else is in range.")
            return
        # Name the new station in full: the driver did not choose it, so they
        # need the call sign and the dial position to decide whether to keep it.
        self.ctx.say_event(f"{lost} lost. {station_text(change.fell_back_to, self.radio.signal)}.")
        self._start_radio_stream()

    def _hand_over_from_dead_stream(self, failed) -> None:
        """A stream that will not play hands over like a signal that faded.

        Public stream URLs rot and some stations refuse third-party players,
        so this is an ordinary outcome, not an error. It takes the same route
        as losing reception: the next station on the same band, and only the
        satellite when there is nothing else. Dropping straight to satellite
        would eject the driver from the band they were listening to, and the
        satellite band holds one station, so the seek keys would then do
        nothing.
        """
        tuner = self.radio
        tuner.mark_unavailable(failed)
        replacement = tuner.hand_over_from(failed)
        name = failed.call_sign or failed.name
        if replacement is None or replacement is failed:
            self._stop_radio_and_restore_music()
            self.ctx.say_event(f"{name} is not answering, and nothing else is in range.")
            return
        self.ctx.say_event(
            f"{name} is not answering. {station_text(replacement, self.radio.signal)}."
        )
        self._start_radio_stream()
