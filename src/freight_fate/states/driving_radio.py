# ruff: noqa: F403,F405
"""Non-blocking runtime discovery and tuning for the in-cab radio."""

from __future__ import annotations

from .driving_core import *


class DrivingRadioDiscoveryMixin:
    def _radio_discovery_allowed(self) -> bool:
        settings = self.ctx.settings
        supports_streams = getattr(self.ctx.audio, "supports_radio_streams", lambda: True)
        return bool(
            settings.online_services and not settings.radio_streamer_safe and supports_streams()
        )

    def _truck_radio_location(self) -> ApproximateLocation:
        position = truck_position(self.route, self.trip.position_mi, self.ctx.world)
        target = self.trip.current_target_city
        state = self.trip.current_state or target.state
        candidates = [city for city in self.ctx.world.cities.values() if city.state == state]
        if position is None:
            position = (target.lat, target.lon)
        if candidates:
            market = min(
                candidates,
                key=lambda city: (city.lat - position[0]) ** 2 + (city.lon - position[1]) ** 2,
            )
        else:
            market = target
        state_code = next(
            (city.state_code for city in candidates if city.state == state and city.state_code),
            target.state_code,
        )
        return ApproximateLocation(
            position[0],
            position[1],
            market.name,
            state,
            state_code,
            source=LOCATION_MODE_TRUCK,
        )

    def _radio_market_key(self) -> str:
        mode = self.ctx.settings.radio_discovery_location
        if mode == LOCATION_MODE_REAL and (
            self._radio_discovery_effective_source != LOCATION_MODE_TRUCK
        ):
            return "player-location"
        location = self._truck_radio_location()
        if mode == LOCATION_MODE_REAL:
            return f"player-location-fallback:{location.state_code}"
        return location.state_code

    def _maybe_refresh_radio_discovery(self) -> None:
        if not self._radio_discovery_allowed():
            self._cancel_blocked_radio_tune()
            if self._radio_discovery_key:
                self._radio_discovery.cancel()
                self._radio_discovery_key = ""
                self.radio.replace_directory_stations(())
            return
        key = self._radio_market_key()
        if key == self._radio_discovery_key:
            return
        self._radio_discovery_key = key
        self._request_radio_discovery(explicit=False, force=False)

    def _request_radio_discovery(self, *, explicit: bool, force: bool) -> str:
        if not self._radio_discovery_allowed():
            if explicit:
                settings = self.ctx.settings
                if not settings.online_services:
                    message = "Online services are off. Built-in stations remain available."
                elif settings.radio_streamer_safe:
                    message = (
                        "Real public streams are hidden by streamer-safe mode. "
                        "Built-in stations remain available."
                    )
                else:
                    message = (
                        "The active audio system cannot play public streams. "
                        "Built-in stations remain available."
                    )
                self.ctx.say(message)
                self._radio_discovery_status = message
                self._radio_discovery_details = ()
            return "blocked"
        mode = self.ctx.settings.radio_discovery_location
        truck = self._truck_radio_location()
        market_key = self._radio_market_key()
        result = self._radio_discovery.request(
            mode=mode,
            truck_location=truck,
            market_key=market_key,
            explicit=explicit,
            force=force,
        )
        if result == "already":
            if explicit:
                self.ctx.say("A public radio search is already in progress.")
            return result
        mode_text = (
            "your approximate location"
            if mode == LOCATION_MODE_REAL
            else f"the simulated truck near {truck.city}, {truck.state}"
        )
        self._radio_discovery_status = "Checking public radio."
        self._radio_discovery_details = (f"Search location: {mode_text}.",)
        if explicit:
            self.ctx.say(f"{self._radio_discovery_status} {self._radio_discovery_details[0]}")
        return result

    def _update_radio_discovery(self) -> None:
        self._maybe_refresh_radio_discovery()
        result = self._radio_discovery.poll()
        if result is not None:
            self._apply_radio_discovery_result(result)
        self._poll_radio_tune()

    def _apply_radio_discovery_result(self, result: DiscoveryResult) -> None:
        self._radio_discovery_effective_source = result.location.source
        if (
            self.ctx.settings.radio_discovery_location == LOCATION_MODE_REAL
            and result.location.source == LOCATION_MODE_TRUCK
        ):
            self._radio_discovery_key = (
                f"player-location-fallback:{self._truck_radio_location().state_code}"
            )
        elif self.ctx.settings.radio_discovery_location == LOCATION_MODE_REAL:
            self._radio_discovery_key = "player-location"
        else:
            self._radio_discovery_key = self._truck_radio_location().state_code
        self.radio.replace_directory_stations(
            result.stations,
            preserve_station_ids=(self._radio_pending_station_id,),
        )
        self._radio_discovery_location_label = result.location.label
        status, details = self._radio_discovery_lines(result)
        preferred = self.radio.station_by_id(self.radio.preferred_station_id)
        if (
            preferred is not None
            and preferred.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
            and preferred.id != self.radio.station_id
        ):
            details += (f"Saved station {preferred.display_name} is back on the dial.",)
        self._radio_discovery_status = status
        self._radio_discovery_details = details
        restore_candidate = bool(
            preferred is not None
            and preferred.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
            and preferred.id != self.radio.station_id
        )
        if restore_candidate and self._radio_pending_station_id:
            # The player's newer bracket choice wins for this drive. Keep the
            # older saved ID persisted only if that explicit tune fails.
            self._radio_saved_station_restore_attempted = True
        should_restore = (
            not self._radio_saved_station_restore_attempted
            and not self._radio_pending_station_id
            and restore_candidate
        )
        if should_restore:
            self._radio_saved_station_restore_attempted = True
            if self.radio.enabled:
                self._begin_radio_stream_tune(
                    preferred,
                    prefix=f"Restoring saved station. Tuning to {preferred.display_name}.",
                    interrupt=False,
                )
            else:
                self.radio.station_id = preferred.id

    @staticmethod
    def _radio_discovery_lines(result: DiscoveryResult) -> tuple[str, tuple[str, ...]]:
        state = result.location.state
        nearby = sum(not station.internet_only for station in result.stations)
        internet_only = sum(station.internet_only for station in result.stations)
        counts = []
        if nearby:
            counts.append(f"{nearby} nearby")
        if internet_only:
            counts.append(f"{internet_only} internet-only")
        summary = " and ".join(counts) or "none"
        status = f"Public radio for {state}: {summary}."
        details: tuple[str, ...] = ()
        if result.outcome == "updated":
            details = ("Live station directory updated.",)
        elif result.outcome == "cached":
            details = ("Using saved public radio results.",)
        elif result.outcome == "stale":
            details = (
                "Using saved public radio results.",
                "The live station directory could not be reached.",
            )
        elif result.outcome == "empty":
            details = (
                "No matching public stations were found.",
                "Built-in stations remain available.",
            )
        else:
            status = "Public radio could not be loaded."
            details = ("Built-in stations remain available.",)
        if result.used_truck_fallback:
            details += ("Approximate location unavailable; following the simulated truck.",)
        return status, details

    def _begin_radio_stream_tune(
        self,
        station: RadioStation,
        *,
        prefix: str = "",
        interrupt: bool = True,
    ) -> None:
        self._radio_tune_generation += 1
        generation = self._radio_tune_generation
        self._radio_pending_station_id = station.id
        message = prefix or f"Tuning to {station.display_name}."
        self.ctx.say(message, interrupt=interrupt)
        self._apply_radio_volume()

        def worker() -> None:
            prepared = None
            url = ""
            try:
                probe = probe_stream_url(station.stream_url, user_agent=USER_AGENT)
                url = probe.url
                prepared = self.ctx.audio.prepare_radio_stream(url)
                error = ""
            except (OSError, TypeError, ValueError, ConnectionError) as exc:
                error = str(exc)
            except RuntimeError as exc:
                error = str(exc)
            if generation != self._radio_tune_generation:
                if prepared is not None:
                    self.ctx.audio.discard_radio_stream(prepared)
                return
            self._radio_tune_results.put((generation, station.id, url, prepared, error))

        threading.Thread(
            target=worker,
            name=f"radio-tune-{generation}",
            daemon=True,
        ).start()

    def _poll_radio_tune(self) -> None:
        latest = None
        while True:
            try:
                candidate = self._radio_tune_results.get_nowait()
            except queue.Empty:
                break
            if candidate[0] == self._radio_tune_generation:
                if latest is not None and latest[3] is not None:
                    self.ctx.audio.discard_radio_stream(latest[3])
                latest = candidate
            elif candidate[3] is not None:
                self.ctx.audio.discard_radio_stream(candidate[3])
        if latest is None:
            return
        generation, station_id, url, prepared, error = latest
        if generation != self._radio_tune_generation:
            if prepared is not None:
                self.ctx.audio.discard_radio_stream(prepared)
            return
        station = self.radio.station_by_id(station_id)
        if (
            station is None
            or self._radio_pending_station_id != station_id
            or not self.radio.enabled
            or not self._radio_discovery_allowed()
        ):
            if prepared is not None:
                self.ctx.audio.discard_radio_stream(prepared)
            if self._radio_pending_station_id == station_id:
                self._radio_pending_station_id = ""
                if self.radio.enabled:
                    current = self.radio.current_station()
                    self.ctx.say(
                        f"Public station tuning ended. {current.display_name} remains playing.",
                        interrupt=False,
                    )
            return
        if not error and prepared is not None:
            try:
                self.ctx.audio.play_prepared_radio_stream(prepared, url, fade_ms=900)
            except RuntimeError as exc:
                error = str(exc)
            else:
                self.radio.station_id = station.id
                self.radio.preferred_station_id = station.id
                self._radio_pending_station_id = ""
                self.radio.write_settings(self.ctx.settings)
                self.ctx.settings.save()
                self._radio_discovery.record_click(station_id.removeprefix("radio-browser:"))
                self.ctx.say(f"Playing {station.display_name}.", interrupt=False)
                return
        elif prepared is not None:
            self.ctx.audio.discard_radio_stream(prepared)
        self._radio_pending_station_id = ""
        self.radio.station_id = SAFE_ROUTE_PLAYLIST
        fallback = self.radio.play(self._radio_backend)
        self.radio.write_settings(self.ctx.settings)
        self.ctx.settings.save()
        self.ctx.say(
            f"{station.display_name} is unavailable. "
            f"Playing {fallback.station.display_name} instead.",
            interrupt=False,
        )

    def _cancel_radio_tune(self) -> None:
        self._radio_tune_generation += 1
        self._radio_pending_station_id = ""

    def _cancel_blocked_radio_tune(self, *, announce: bool = True) -> bool:
        if self._radio_discovery_allowed() or not self._radio_pending_station_id:
            return False
        self._cancel_radio_tune()
        if announce and self.radio.enabled:
            current = self.radio.current_station()
            self.ctx.say(
                f"Public station tuning canceled. {current.display_name} remains playing.",
                interrupt=False,
            )
        return True

    def _radio_stream_availability_text(self) -> str:
        supports_streams = getattr(self.ctx.audio, "supports_radio_streams", lambda: True)
        return public_stream_availability(
            self.ctx.settings,
            backend_supported=supports_streams(),
        )

    def _radio_discovery_status_text(self) -> str:
        return " ".join(self._radio_discovery_status_lines())

    def _radio_discovery_status_lines(self) -> tuple[str, ...]:
        if not self._radio_discovery_allowed():
            return (self._radio_stream_availability_text(),)
        return (self._radio_discovery_status, *self._radio_discovery_details)

    def _radio_status_text(self, *, include_availability: bool = True) -> str:
        text = self.radio.status_text()
        pending = self.radio.station_by_id(self._radio_pending_station_id)
        if pending is not None:
            current = self.radio.current_station()
            text += (
                f" Tuning to {pending.display_name}. "
                f"{current.display_name} remains on until the stream is ready."
            )
        preferred = self.radio.station_by_id(self.radio.preferred_station_id)
        if (
            pending is None
            and preferred is not None
            and preferred.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
            and preferred.id != self.radio.station_id
        ):
            text += (
                f" Saved station {preferred.display_name} is available on the dial. "
                "Use the bracket keys to tune it."
            )
        if include_availability:
            text += f" {self._radio_stream_availability_text()}"
        return text

    def _sync_radio_settings(self) -> None:
        station_before = self.radio.station_id
        selected_before = self.radio.station_by_id(station_before)
        pending_before = self.radio.station_by_id(self._radio_pending_station_id)
        self.radio.apply_settings(self.ctx.settings)
        self.radio.update_position(
            truck_position(self.route, self.trip.position_mi, self.ctx.world)
        )
        self.radio.current_station()
        selected_became_unavailable = bool(
            selected_before is not None
            and (
                (selected_before.real_stream and not self._radio_discovery_allowed())
                or (
                    selected_before.source_type == PERSONAL_PLAYLIST_SOURCE_TYPE
                    and self.radio.streamer_safe
                )
            )
        )
        pending_was_canceled = self._cancel_blocked_radio_tune(
            announce=not selected_became_unavailable,
        )
        if selected_became_unavailable:
            if (
                selected_before.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
                or pending_before is not None
                and pending_before.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES
            ):
                self._radio_saved_station_restore_attempted = True
            self.radio.station_id = self.radio.fallback_station().id
        if self.radio.station_id != station_before:
            self.radio.write_settings(self.ctx.settings)
            self.ctx.settings.save()
            if selected_became_unavailable and self.radio.enabled:
                self._cancel_radio_tune()
                cancellation = " Public station tuning canceled." if pending_was_canceled else ""
                action = self.radio.play(self._radio_backend)
                if self.ctx.settings.radio_streamer_safe:
                    reason = "Streamer-safe mode on."
                elif not self.ctx.settings.online_services:
                    reason = "Online services off."
                else:
                    reason = "Public audio unavailable with this audio system."
                self.ctx.say(
                    f"{reason}{cancellation} Playing {action.station.display_name} instead.",
                    interrupt=False,
                )

    def _apply_radio_volume(self) -> None:
        factor = getattr(self, "_radio_signal_factor", 1.0)
        self.ctx.audio.set_volumes(music=self.ctx.settings.radio_volume * factor)

    def _play_radio_current(self) -> None:
        self._sync_radio_settings()
        if self.radio.enabled:
            self._apply_radio_volume()
            station = self.radio.current_station()
            if station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES:
                self.radio.station_id = self.radio.fallback_station().id
                self._begin_radio_stream_tune(station)
            else:
                self.radio.play(self._radio_backend)
        else:
            self.ctx.audio.stop_music(600)

    def _finish_radio_action(self, action) -> None:
        self.radio.write_settings(self.ctx.settings)
        self.ctx.settings.save()
        self.ctx.say(action.message)

    def _toggle_radio(self) -> None:
        self._sync_radio_settings()
        station = self.radio.current_station()
        if not self.radio.enabled and station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES:
            self.radio.toggle(None)
            self.radio.station_id = self.radio.fallback_station().id
            self._begin_radio_stream_tune(
                station,
                prefix=f"Radio on. Tuning to {station.display_name}.",
            )
            return
        self._cancel_radio_tune()
        action = self.radio.toggle(self._radio_backend)
        self._finish_radio_action(action)

    def _tune_radio(self, direction: int) -> None:
        self._sync_radio_settings()
        from_station_id = self._radio_pending_station_id or self.radio.station_id
        reception = self.radio.next_reception(
            direction,
            from_station_id=from_station_id,
        )
        self._cancel_radio_tune()
        station = reception.station
        if station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES and self.radio.enabled:
            self._begin_radio_stream_tune(
                station,
                prefix=f"Tuning to {station.display_name}.",
            )
            return
        action = self.radio.select_station(station.id, None)
        if action.enabled:
            action = self.radio.play(
                self._radio_backend,
                prefix=f"Tuned to {station.display_name}.",
            )
        self._finish_radio_action(action)

    def _jump_radio_category(self, direction: int) -> None:
        self._sync_radio_settings()
        from_station_id = self._radio_pending_station_id or self.radio.station_id
        reception, category = self.radio.next_category_reception(
            direction,
            from_station_id=from_station_id,
        )
        self._cancel_radio_tune()
        station = reception.station
        if station.source_type in PUBLIC_DIRECTORY_SOURCE_TYPES and self.radio.enabled:
            self._begin_radio_stream_tune(
                station,
                prefix=f"{category}. Tuning to {station.display_name}.",
            )
            return
        action = self.radio.select_station(station.id, None)
        if action.enabled:
            action = self.radio.play(
                self._radio_backend,
                prefix=f"{category}. Tuned to {station.display_name}.",
            )
        self._finish_radio_action(action)

    def _speak_radio_status(self) -> None:
        self._sync_radio_settings()
        self.ctx.say(self._radio_status_text())
