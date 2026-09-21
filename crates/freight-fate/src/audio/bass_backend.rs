use super::*;

impl AudioBackend for BassBackend {
    fn name(&self) -> &'static str {
        "bass"
    }

    fn enabled(&self) -> bool {
        self.enabled
    }

    fn buses(&self) -> &Buses {
        &self.buses
    }

    fn buses_mut(&mut self) -> &mut Buses {
        &mut self.buses
    }

    fn as_any(&self) -> &dyn Any {
        self
    }

    fn as_any_mut(&mut self) -> &mut dyn Any {
        self
    }

    fn play_if_idle(&mut self, key: &str, volume: f64, pan: f64) {
        BassBackend::play_if_idle(self, key, volume, pan);
    }

    fn update_cue(&mut self, key: &str, volume: f64, pan: f64) {
        if let Some(stream) = self.exclusive_cues.get(key) {
            let level =
                (volume * self.buses.category_volume(one_shot_category(key)) * self.buses.master)
                    .clamp(0.0, 1.0);
            let result = set_volume(stream.handle(), level).and_then(|()| {
                safe::channel_set_attribute(
                    stream.handle(),
                    BASS_ATTRIB_PAN,
                    pan.clamp(-1.0, 1.0) as f32,
                )
            });
            if let Err(err) = result {
                log::debug!("Could not update cue {key} ({err})");
            }
        }
    }

    fn stop_cue(&mut self, key: &str) {
        self.exclusive_cues.remove(key);
    }

    fn play(&mut self, key: &str, volume: f64, pan: f64) {
        BassBackend::play(self, key, volume, pan);
    }

    fn start_loop(&mut self, channel: u32, key: &str, volume: f64, fade_ms: u32) {
        BassBackend::start_loop(self, channel, key, volume, fade_ms);
    }

    fn set_loop_volume(&mut self, channel: u32, volume: f64) {
        BassBackend::set_loop_volume(self, channel, volume);
    }

    fn set_loop_pan(&mut self, channel: u32, pan: f64) {
        BassBackend::set_loop_pan(self, channel, pan);
    }

    fn set_loop_rate(&mut self, channel: u32, rate: f64) {
        BassBackend::set_loop_rate(self, channel, rate);
    }

    fn stop_loop(&mut self, channel: u32, fade_ms: u32) {
        BassBackend::stop_loop(self, channel, fade_ms);
    }

    fn loop_entry(&self, channel: u32) -> Option<(String, f64)> {
        self.loops
            .get(&channel)
            .map(|entry| (entry.key.clone(), entry.gain))
    }

    fn start_sustain_loop(&mut self, channel: u32, key: &str, spec: SustainLoopSpec, volume: f64) {
        BassBackend::start_sustain_loop(self, channel, key, spec, volume);
    }

    fn release_sustain_loop(&mut self, channel: u32, fade_ms: u32) {
        BassBackend::release_sustain_loop(self, channel, fade_ms);
    }

    fn engine_start(&mut self, play_start_sound: bool) {
        BassBackend::engine_start(self, play_start_sound);
    }

    fn engine_stop(&mut self, shutdown_sound: bool) {
        BassBackend::engine_stop(self, shutdown_sound);
    }

    fn set_engine_pan(&mut self, pan: f64) {
        BassBackend::set_engine_pan(self, pan);
    }

    fn set_engine_rpm(&mut self, rpm: f64, throttle: f64) {
        BassBackend::set_engine_rpm(self, rpm, throttle);
    }

    fn set_engine_duck(&mut self, duck: f64) {
        BassBackend::set_engine_duck(self, duck);
    }

    fn set_road_noise(&mut self, speed_mps: f64) {
        BassBackend::set_road_noise(self, speed_mps);
    }

    fn update(&mut self, dt: f64) {
        BassBackend::update(self, dt);
    }

    fn reverse_start(&mut self) {
        BassBackend::reverse_start(self);
    }

    fn reverse_stop(&mut self) {
        BassBackend::reverse_stop(self);
    }

    fn engine_running(&self) -> bool {
        self.engine_running
    }

    fn engine_starting(&self) -> bool {
        self.engine_starting.get()
    }

    fn engine_voice_classic(&self) -> Option<bool> {
        Some(self.engine_voice_classic)
    }

    fn set_engine_voice_classic(&mut self, classic: bool) {
        self.engine_voice_classic = classic;
    }

    fn engine_last_rpm_throttle(&self) -> (f64, f64) {
        (self.engine_last_rpm, self.engine_last_throttle)
    }

    fn play_music(&mut self, track: &str, fade_ms: u32) {
        BassBackend::play_music(self, track, fade_ms);
    }

    fn play_music_at(&mut self, track: &str, fade_ms: u32, start_s: f64) {
        BassBackend::play_music_at(self, track, fade_ms, start_s);
    }

    fn play_radio_stream(&mut self, url: &str, fade_ms: u32) -> Result<(), AudioError> {
        BassBackend::play_radio_stream(self, url, fade_ms)
    }

    fn radio_now_playing(&self) -> Option<String> {
        BassBackend::radio_now_playing(self)
    }

    fn play_music_file(&mut self, path: &str, fade_ms: u32) -> Result<(), AudioError> {
        BassBackend::play_music_file(self, path, fade_ms)
    }

    fn music_playing(&self) -> bool {
        BassBackend::music_playing(self)
    }

    fn stop_music(&mut self, fade_ms: u32) {
        BassBackend::stop_music(self, fade_ms);
    }

    fn set_volumes(&mut self, volumes: &VolumeUpdate) {
        BassBackend::set_volumes(self, volumes);
    }

    fn shutdown(&mut self) {
        BassBackend::shutdown(self);
    }
}
