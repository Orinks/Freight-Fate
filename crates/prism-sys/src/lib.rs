//! Raw FFI types and runtime loader for the Prism screen-reader / TTS library.
//!
//! Prism ships as a C library (`prism.dll` / `libprism.so` / `libprism.dylib`)
//! and has no crate on crates.io, so the C ABI is declared by hand here and the
//! platform binary is vendored under `vendor/bin/`.
//!
//! The library is opened at run time rather than linked, so a machine without
//! Prism still starts the application — it just loses speech output. See
//! [`Api::get`].

#![allow(non_camel_case_types)]
#![allow(non_upper_case_globals)]

use std::os::raw::{c_char, c_int, c_void};

mod loader;

pub use loader::{library_file_name, Api};

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
pub const PRISM_ERROR_COUNT: PrismError = 19;

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
}

/// Backend feature bits, as returned by `prism_backend_get_features`.
pub mod features {
    pub const IS_SUPPORTED_AT_RUNTIME: u64 = 1 << 0;
    pub const SUPPORTS_SPEAK: u64 = 1 << 2;
    pub const SUPPORTS_SPEAK_TO_MEMORY: u64 = 1 << 3;
    pub const SUPPORTS_BRAILLE: u64 = 1 << 4;
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
pub type FnBackendBraille = unsafe extern "C" fn(*mut PrismBackend, *const c_char) -> PrismError;
pub type FnBackendVoid = unsafe extern "C" fn(*mut PrismBackend) -> PrismError;
pub type FnBackendSetF32 = unsafe extern "C" fn(*mut PrismBackend, f32) -> PrismError;
pub type FnBackendGetF32 = unsafe extern "C" fn(*mut PrismBackend, *mut f32) -> PrismError;
pub type FnBackendGetBool = unsafe extern "C" fn(*mut PrismBackend, *mut bool) -> PrismError;
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
        assert_eq!(PRISM_ERROR_COUNT, 19);
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
