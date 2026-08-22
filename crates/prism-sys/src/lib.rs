//! Raw FFI types and runtime loader for the Prism screen-reader / TTS library.
//!
//! Prism ships as a C library (`prism.dll` / `libprism.so` / `libprism.dylib`)
//! and has no crate on crates.io, so the C ABI is declared by hand here and the
//! platform binary is vendored under `vendor/<os>-<arch>/`.
//!
//! The declarations follow the cffi `cdef` that ships in the `prismatoid`
//! Python package, which is what Freight Fate's Python speech layer was
//! written against; the vendored binaries are prismatoid 0.17.3.
//!
//! The library is opened at run time rather than linked, so a machine without
//! Prism still starts the application — it just loses speech output. See
//! [`Api::get`].

#![allow(non_camel_case_types)]
#![allow(non_upper_case_globals)]

use std::os::raw::{c_char, c_int, c_void};

mod loader;

pub use loader::{library_file_name, vendor_dir, Api, PATH_ENV_VARS, REQUIRED_SYMBOLS};

/// Opaque Prism library context.
#[repr(C)]
pub struct PrismContext {
    _private: [u8; 0],
}

/// Opaque handle to a single speech backend (SAPI, NVDA, JAWS, ...).
#[repr(C)]
pub struct PrismBackend {
    _private: [u8; 0],
}

/// Opaque registry of backends, optionally supplied to [`PrismConfig`].
#[repr(C)]
pub struct PrismRegistry {
    _private: [u8; 0],
}

/// Stable identifier for a registered backend.
pub type PrismBackendId = u64;

/// Configuration handed to `prism_init`.
///
/// Forty-eight bytes with eight fields, identical on every platform. That is
/// not obvious from outside and getting it wrong is quiet: the library fills
/// the whole struct on the way out of `prism_config_init` and reads the whole
/// struct on the way into `prism_init`, so a short definition corrupts the
/// stack around it rather than failing. Windows tolerated a sixteen-byte
/// version of this for a while; Linux segfaulted on the first call.
///
/// The layout is pinned by the tests below, taken from the shipped library
/// rather than from a header. `version` is how Prism announces a change.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct PrismConfig {
    pub version: u8,
    pub registry: *mut PrismRegistry,
    /// Called when a backend appears or disappears.
    pub availability_callback: Option<
        unsafe extern "C" fn(userdata: *mut c_void, id: u64, name: *mut c_char, available: bool),
    >,
    pub availability_userdata: *mut c_void,
    pub availability_poll_interval_ms: u32,
    pub availability_debounce_samples: u32,
    pub availability_backoff_max_ms: u32,
    pub availability_auto_power_manage: bool,
}

/// Error codes returned by the `prism_backend_*` entry points.
pub type PrismError = c_int;

pub const PRISM_OK: PrismError = 0;
pub const PRISM_ERROR_NOT_INITIALIZED: PrismError = 1;
pub const PRISM_ERROR_INVALID_PARAM: PrismError = 2;
pub const PRISM_ERROR_NOT_IMPLEMENTED: PrismError = 3;
pub const PRISM_ERROR_NO_VOICES: PrismError = 4;
pub const PRISM_ERROR_VOICE_NOT_FOUND: PrismError = 5;
pub const PRISM_ERROR_SPEAK_FAILURE: PrismError = 6;
pub const PRISM_ERROR_MEMORY_FAILURE: PrismError = 7;
pub const PRISM_ERROR_RANGE_OUT_OF_BOUNDS: PrismError = 8;
pub const PRISM_ERROR_INTERNAL: PrismError = 9;
pub const PRISM_ERROR_NOT_SPEAKING: PrismError = 10;
pub const PRISM_ERROR_NOT_PAUSED: PrismError = 11;
pub const PRISM_ERROR_ALREADY_PAUSED: PrismError = 12;
pub const PRISM_ERROR_INVALID_UTF8: PrismError = 13;
pub const PRISM_ERROR_INVALID_OPERATION: PrismError = 14;
pub const PRISM_ERROR_ALREADY_INITIALIZED: PrismError = 15;
pub const PRISM_ERROR_BACKEND_NOT_AVAILABLE: PrismError = 16;
pub const PRISM_ERROR_UNKNOWN: PrismError = 17;
pub const PRISM_ERROR_INVALID_AUDIO_FORMAT: PrismError = 18;
pub const PRISM_ERROR_INTERNAL_BACKEND_LIMIT_EXCEEDED: PrismError = 19;
pub const PRISM_ERROR_BACKEND_ENTERED_UNDEFINED_STATE: PrismError = 20;
pub const PRISM_ERROR_COUNT: PrismError = 21;

/// Well-known backend identifiers, matching Prism's own registry hashes.
pub mod backend_id {
    use super::PrismBackendId;

    pub const INVALID: PrismBackendId = 0;
    pub const SAPI: PrismBackendId = 0x1D6D_F724_22CE_EE66;
    pub const AV_SPEECH: PrismBackendId = 0x28E3_4295_7780_5C24;
    pub const VOICE_OVER: PrismBackendId = 0xCB48_9796_1A75_4BCB;
    pub const SPEECH_DISPATCHER: PrismBackendId = 0xE3D6_F895_D949_EBFE;
    pub const NVDA: PrismBackendId = 0x89CC_19C5_C4AC_1A56;
    pub const JAWS: PrismBackendId = 0xAC3D_60E9_BD84_B53E;
    pub const ONE_CORE: PrismBackendId = 0x6797_D32F_0D99_4CB4;
    pub const ORCA: PrismBackendId = 0x10AA_1FC0_5A17_F96C;
    pub const ANDROID_SCREEN_READER: PrismBackendId = 0xD199_C175_AEEC_494B;
    pub const ANDROID_TTS: PrismBackendId = 0xBC17_5831_BFE4_E5CC;
    pub const WEB_SPEECH: PrismBackendId = 0x3572_538D_44D4_4A8F;
    pub const UIA: PrismBackendId = 0x6238_F019_DB67_8F8E;
    pub const ZDSR: PrismBackendId = 0x3D93_C56C_9E7F_2A2E;
    pub const ZOOM_TEXT: PrismBackendId = 0xAE43_9D62_DC7B_1479;
    pub const BOY_PC_READER: PrismBackendId = 0x285A_BA1C_16F3_300F;
    pub const PC_TALKER: PrismBackendId = 0x344B_9519_62E3_B835;
    pub const SENSE_READER: PrismBackendId = 0xED47_6089_0B55_C2F2;
    pub const SYSTEM_ACCESS: PrismBackendId = 0x8380_F2A3_7B2C_3EB6;
    pub const WINDOW_EYES: PrismBackendId = 0x9120_D899_0878_5C13;
    pub const SPIEL: PrismBackendId = 0x478B_44F1_4AD3_D89C;
}

/// Backend feature bits, as returned by `prism_backend_get_features`.
///
/// Bit positions follow prismatoid's `BackendFeatures` dataclass exactly; bit
/// 1 is unassigned upstream. `IS_SUPPORTED_AT_RUNTIME` is the live check --
/// whether the screen reader or engine is actually reachable right now --
/// and the rest say which entry points the backend implements at all.
pub mod features {
    pub const IS_SUPPORTED_AT_RUNTIME: u64 = 1 << 0;
    pub const SUPPORTS_SPEAK: u64 = 1 << 2;
    pub const SUPPORTS_SPEAK_TO_MEMORY: u64 = 1 << 3;
    pub const SUPPORTS_BRAILLE: u64 = 1 << 4;
    pub const SUPPORTS_OUTPUT: u64 = 1 << 5;
    pub const SUPPORTS_IS_SPEAKING: u64 = 1 << 6;
    pub const SUPPORTS_STOP: u64 = 1 << 7;
    pub const SUPPORTS_PAUSE: u64 = 1 << 8;
    pub const SUPPORTS_RESUME: u64 = 1 << 9;
    pub const SUPPORTS_SET_VOLUME: u64 = 1 << 10;
    pub const SUPPORTS_GET_VOLUME: u64 = 1 << 11;
    pub const SUPPORTS_SET_RATE: u64 = 1 << 12;
    pub const SUPPORTS_GET_RATE: u64 = 1 << 13;
    pub const SUPPORTS_SET_PITCH: u64 = 1 << 14;
    pub const SUPPORTS_GET_PITCH: u64 = 1 << 15;
    pub const SUPPORTS_REFRESH_VOICES: u64 = 1 << 16;
    pub const SUPPORTS_COUNT_VOICES: u64 = 1 << 17;
    pub const SUPPORTS_GET_VOICE_NAME: u64 = 1 << 18;
    pub const SUPPORTS_GET_VOICE_LANGUAGE: u64 = 1 << 19;
    pub const SUPPORTS_GET_VOICE: u64 = 1 << 20;
    pub const SUPPORTS_SET_VOICE: u64 = 1 << 21;
    pub const SUPPORTS_GET_CHANNELS: u64 = 1 << 22;
    pub const SUPPORTS_GET_SAMPLE_RATE: u64 = 1 << 23;
    pub const SUPPORTS_GET_BIT_DEPTH: u64 = 1 << 24;
    pub const PERFORMS_SILENCE_TRIMMING_ON_SPEAK: u64 = 1 << 25;
    pub const PERFORMS_SILENCE_TRIMMING_ON_SPEAK_TO_MEMORY: u64 = 1 << 26;
    pub const SUPPORTS_SPEAK_SSML: u64 = 1 << 27;
    pub const SUPPORTS_SPEAK_TO_MEMORY_SSML: u64 = 1 << 28;
}

/// Callback invoked with rendered PCM when speaking to memory.
pub type PrismAudioCallback = unsafe extern "C" fn(
    userdata: *mut c_void,
    samples: *const f32,
    sample_count: usize,
    channels: usize,
    sample_rate: usize,
);

// --- Function pointer types, one per symbol the loader resolves. ---

pub type FnConfigInit = unsafe extern "C" fn() -> PrismConfig;
pub type FnInit = unsafe extern "C" fn(*mut PrismConfig) -> *mut PrismContext;
pub type FnShutdown = unsafe extern "C" fn(*mut PrismContext);
pub type FnRegistryCount = unsafe extern "C" fn(*mut PrismContext) -> usize;
pub type FnRegistryIdAt = unsafe extern "C" fn(*mut PrismContext, usize) -> PrismBackendId;
pub type FnRegistryId = unsafe extern "C" fn(*mut PrismContext, *const c_char) -> PrismBackendId;
pub type FnRegistryName = unsafe extern "C" fn(*mut PrismContext, PrismBackendId) -> *const c_char;
pub type FnRegistryPriority = unsafe extern "C" fn(*mut PrismContext, PrismBackendId) -> c_int;
pub type FnRegistryExists = unsafe extern "C" fn(*mut PrismContext, PrismBackendId) -> bool;
pub type FnRegistryAcquire =
    unsafe extern "C" fn(*mut PrismContext, PrismBackendId) -> *mut PrismBackend;
pub type FnRegistryAcquireBest = unsafe extern "C" fn(*mut PrismContext) -> *mut PrismBackend;
pub type FnBackendFree = unsafe extern "C" fn(*mut PrismBackend);
pub type FnBackendFeatures = unsafe extern "C" fn(*mut PrismBackend) -> u64;
pub type FnBackendName = unsafe extern "C" fn(*mut PrismBackend) -> *const c_char;
pub type FnBackendInitialize = unsafe extern "C" fn(*mut PrismBackend) -> PrismError;
pub type FnBackendSpeak =
    unsafe extern "C" fn(*mut PrismBackend, *const c_char, bool) -> PrismError;
pub type FnBackendSpeakToMemory = unsafe extern "C" fn(
    *mut PrismBackend,
    *const c_char,
    Option<PrismAudioCallback>,
    *mut c_void,
) -> PrismError;
pub type FnBackendBraille = unsafe extern "C" fn(*mut PrismBackend, *const c_char) -> PrismError;
pub type FnBackendVoid = unsafe extern "C" fn(*mut PrismBackend) -> PrismError;
pub type FnBackendSetF32 = unsafe extern "C" fn(*mut PrismBackend, f32) -> PrismError;
pub type FnBackendGetF32 = unsafe extern "C" fn(*mut PrismBackend, *mut f32) -> PrismError;
pub type FnBackendGetBool = unsafe extern "C" fn(*mut PrismBackend, *mut bool) -> PrismError;
pub type FnBackendSetUsize = unsafe extern "C" fn(*mut PrismBackend, usize) -> PrismError;
pub type FnBackendGetUsize = unsafe extern "C" fn(*mut PrismBackend, *mut usize) -> PrismError;
/// `(backend, voice index, out name)`: the string is owned by the backend.
pub type FnBackendGetIndexedStr =
    unsafe extern "C" fn(*mut PrismBackend, usize, *mut *const c_char) -> PrismError;
pub type FnErrorString = unsafe extern "C" fn(PrismError) -> *const c_char;

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::size_of;

    #[test]
    fn config_layout_matches_c_header() {
        // Taken from the library itself rather than from a header we do not
        // ship: cffi reports these offsets for PrismConfig on both Linux and
        // Windows, identically. The previous version of this test asserted a
        // one-byte struct and passed, which is how a definition forty-seven
        // bytes short went unnoticed.
        assert_eq!(size_of::<PrismConfig>(), 48, "PrismConfig is 48 bytes");
        assert_eq!(align_of::<PrismConfig>(), 8);

        assert_eq!(core::mem::offset_of!(PrismConfig, version), 0);
        assert_eq!(core::mem::offset_of!(PrismConfig, registry), 8);
        assert_eq!(
            core::mem::offset_of!(PrismConfig, availability_callback),
            16
        );
        assert_eq!(
            core::mem::offset_of!(PrismConfig, availability_userdata),
            24
        );
        assert_eq!(
            core::mem::offset_of!(PrismConfig, availability_poll_interval_ms),
            32
        );
        assert_eq!(
            core::mem::offset_of!(PrismConfig, availability_debounce_samples),
            36
        );
        assert_eq!(
            core::mem::offset_of!(PrismConfig, availability_backoff_max_ms),
            40
        );
        assert_eq!(
            core::mem::offset_of!(PrismConfig, availability_auto_power_manage),
            44
        );
    }

    #[test]
    fn error_codes_are_contiguous_from_ok() {
        assert_eq!(PRISM_OK, 0);
        assert_eq!(PRISM_ERROR_NOT_INITIALIZED, 1);
        assert_eq!(PRISM_ERROR_INVALID_AUDIO_FORMAT, 18);
        assert_eq!(PRISM_ERROR_BACKEND_ENTERED_UNDEFINED_STATE, 20);
        assert_eq!(PRISM_ERROR_COUNT, 21);
    }

    #[test]
    fn feature_bits_match_prismatoid() {
        // Positions copied from prismatoid's BackendFeatures dataclass; the
        // game's backend selection reads four of them and every settings
        // screen goes wrong if one is off by a bit.
        use features::*;
        assert_eq!(IS_SUPPORTED_AT_RUNTIME, 1);
        assert_eq!(SUPPORTS_SPEAK, 1 << 2);
        assert_eq!(SUPPORTS_OUTPUT, 1 << 5);
        assert_eq!(SUPPORTS_STOP, 1 << 7);
        assert_eq!(SUPPORTS_SET_VOLUME, 1 << 10);
        assert_eq!(SUPPORTS_SET_RATE, 1 << 12);
        assert_eq!(SUPPORTS_SET_PITCH, 1 << 14);
        assert_eq!(SUPPORTS_COUNT_VOICES, 1 << 17);
        assert_eq!(SUPPORTS_GET_VOICE_NAME, 1 << 18);
        assert_eq!(SUPPORTS_SET_VOICE, 1 << 21);
        assert_eq!(SUPPORTS_SPEAK_TO_MEMORY_SSML, 1 << 28);
        let all = [
            IS_SUPPORTED_AT_RUNTIME,
            SUPPORTS_SPEAK,
            SUPPORTS_SPEAK_TO_MEMORY,
            SUPPORTS_BRAILLE,
            SUPPORTS_OUTPUT,
            SUPPORTS_IS_SPEAKING,
            SUPPORTS_STOP,
            SUPPORTS_PAUSE,
            SUPPORTS_RESUME,
            SUPPORTS_SET_VOLUME,
            SUPPORTS_GET_VOLUME,
            SUPPORTS_SET_RATE,
            SUPPORTS_GET_RATE,
            SUPPORTS_SET_PITCH,
            SUPPORTS_GET_PITCH,
            SUPPORTS_REFRESH_VOICES,
            SUPPORTS_COUNT_VOICES,
            SUPPORTS_GET_VOICE_NAME,
            SUPPORTS_GET_VOICE_LANGUAGE,
            SUPPORTS_GET_VOICE,
            SUPPORTS_SET_VOICE,
            SUPPORTS_GET_CHANNELS,
            SUPPORTS_GET_SAMPLE_RATE,
            SUPPORTS_GET_BIT_DEPTH,
            PERFORMS_SILENCE_TRIMMING_ON_SPEAK,
            PERFORMS_SILENCE_TRIMMING_ON_SPEAK_TO_MEMORY,
            SUPPORTS_SPEAK_SSML,
            SUPPORTS_SPEAK_TO_MEMORY_SSML,
        ];
        // Every constant is one distinct bit and bit 1 stays unassigned.
        let mut seen = 0u64;
        for bit in all {
            assert_eq!(bit.count_ones(), 1);
            assert_eq!(seen & bit, 0, "duplicate feature bit {bit:#x}");
            seen |= bit;
        }
        assert_eq!(seen & 2, 0, "bit 1 is unassigned upstream");
        assert_eq!(seen.count_ones(), 28);
    }

    #[test]
    fn well_known_backend_ids_are_distinct() {
        let ids = [
            backend_id::SAPI,
            backend_id::AV_SPEECH,
            backend_id::VOICE_OVER,
            backend_id::SPEECH_DISPATCHER,
            backend_id::NVDA,
            backend_id::JAWS,
            backend_id::ONE_CORE,
            backend_id::ORCA,
            backend_id::UIA,
            backend_id::ZDSR,
            backend_id::ZOOM_TEXT,
            backend_id::BOY_PC_READER,
            backend_id::PC_TALKER,
            backend_id::SENSE_READER,
            backend_id::SYSTEM_ACCESS,
            backend_id::WINDOW_EYES,
            backend_id::SPIEL,
        ];
        for (index, first) in ids.iter().enumerate() {
            assert_ne!(*first, backend_id::INVALID);
            for second in &ids[index + 1..] {
                assert_ne!(first, second);
            }
        }
    }

    #[test]
    fn library_file_name_is_platform_specific() {
        let name = library_file_name();
        assert!(name.contains("prism"));
        if cfg!(windows) {
            assert_eq!(name, "prism.dll");
        } else if cfg!(target_os = "macos") {
            assert_eq!(name, "libprism.dylib");
        } else {
            assert_eq!(name, "libprism.so");
        }
    }
}
