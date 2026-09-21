//! The three synthesized tracks Freight Fate shipped with in 1.0 to 1.5,
//! made by the game's own generator (tools/generate_audio.py, removed in
//! e751db73) and restored byte for byte from v1.5.0. Compiled in rather than
//! packed so Synthesized music never depends on either sound pack.

use std::sync::Once;

use ff_core::assets_pack::register_generated_sound;

const CLASSICS: [(&str, &[u8]); 3] = [
    (
        "music/classic_menu_theme",
        include_bytes!("../../assets/classic_music/classic_menu_theme.ogg"),
    ),
    (
        "music/classic_open_road",
        include_bytes!("../../assets/classic_music/classic_open_road.ogg"),
    ),
    (
        "music/classic_night_haul",
        include_bytes!("../../assets/classic_music/classic_night_haul.ogg"),
    ),
];

static REGISTERED: Once = Once::new();

/// Publish the classics once per process; later calls do nothing.
pub fn register() {
    REGISTERED.call_once(|| {
        for (key, bytes) in CLASSICS {
            register_generated_sound(key, bytes.to_vec(), "ogg");
        }
    });
}
