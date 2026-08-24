//! Raw FFI types and runtime loader for the BASS audio library (Un4seen).
//!
//! BASS ships as a closed C library (`bass.dll` / `libbass.so` /
//! `libbass.dylib`) plus add-on plugins, so the C ABI is declared by hand here
//! and the platform binaries are vendored under `vendor/<os>-<arch>/`.
//!
//! The library is opened at run time rather than linked, so a machine without
//! BASS still starts the game -- it just loses audio, exactly as the Python
//! build falls back to its null backend. See [`Api::get`] and [`api`].
//!
//! Only the entry points Freight Fate calls are declared: the surface is the
//! one the Python `_BassBackend` and `SustainLoop` use (memory streams, URL
//! streams, attribute slides, mixtime position syncs, ICY tags, plugins).
//! Adding a call site means adding a function-pointer type here, a field in
//! [`loader::Api`] and a matching `load` line.
//!
//! Calling convention: BASS exports are `WINAPI` (stdcall) on 32-bit Windows
//! and plain C everywhere else; `extern "system"` is exactly that rule.

#![allow(non_camel_case_types)]
#![allow(non_upper_case_globals)]
#![allow(clippy::missing_safety_doc)]

use std::os::raw::{c_char, c_int, c_void};

mod loader;
pub mod safe;

pub use loader::{library_file_name, Api, LoadError, LIBRARY_PATH_ENV};

// --- Primitive aliases, matching bass.h -------------------------------------

/// `DWORD` -- 32-bit unsigned on every BASS platform.
pub type DWORD = u32;
/// `QWORD` -- 64-bit unsigned.
pub type QWORD = u64;
/// `BOOL` -- C int, non-zero is true.
pub type BOOL = c_int;
/// Sample stream handle.
pub type HSTREAM = DWORD;
/// Playing sample's channel handle (also what every `BASS_Channel*` takes).
pub type HCHANNEL = DWORD;
/// Synchroniser handle.
pub type HSYNC = DWORD;
/// Plugin handle.
pub type HPLUGIN = DWORD;
/// Sample handle.
pub type HSAMPLE = DWORD;
/// MOD music handle.
pub type HMUSIC = DWORD;

/// The "no sound" device passed to `BASS_Init`: channels play and decode in
/// real time, syncs fire, nothing is audible. Headless runs and tests use it.
pub const BASS_NO_SOUND_DEVICE: c_int = 0;
/// The default device for `BASS_Init`.
pub const BASS_DEFAULT_DEVICE: c_int = -1;

/// `BASS_GetVersion` for the 2.4 line returns `0x0204xxxx`.
pub const BASSVERSION: DWORD = 0x204;

// --- Error codes (BASS_ErrorGetCode) ----------------------------------------

pub const BASS_OK: c_int = 0;
pub const BASS_ERROR_MEM: c_int = 1;
pub const BASS_ERROR_FILEOPEN: c_int = 2;
pub const BASS_ERROR_DRIVER: c_int = 3;
pub const BASS_ERROR_BUFLOST: c_int = 4;
pub const BASS_ERROR_HANDLE: c_int = 5;
pub const BASS_ERROR_FORMAT: c_int = 6;
pub const BASS_ERROR_POSITION: c_int = 7;
pub const BASS_ERROR_INIT: c_int = 8;
pub const BASS_ERROR_START: c_int = 9;
pub const BASS_ERROR_SSL: c_int = 10;
pub const BASS_ERROR_REINIT: c_int = 11;
pub const BASS_ERROR_ALREADY: c_int = 14;
pub const BASS_ERROR_NOTAUDIO: c_int = 17;
pub const BASS_ERROR_NOCHAN: c_int = 18;
pub const BASS_ERROR_ILLTYPE: c_int = 19;
pub const BASS_ERROR_ILLPARAM: c_int = 20;
pub const BASS_ERROR_NO3D: c_int = 21;
pub const BASS_ERROR_NOEAX: c_int = 22;
pub const BASS_ERROR_DEVICE: c_int = 23;
pub const BASS_ERROR_NOPLAY: c_int = 24;
pub const BASS_ERROR_FREQ: c_int = 25;
pub const BASS_ERROR_NOTFILE: c_int = 27;
pub const BASS_ERROR_NOHW: c_int = 29;
pub const BASS_ERROR_EMPTY: c_int = 31;
pub const BASS_ERROR_NONET: c_int = 32;
pub const BASS_ERROR_CREATE: c_int = 33;
pub const BASS_ERROR_NOFX: c_int = 34;
pub const BASS_ERROR_NOTAVAIL: c_int = 37;
pub const BASS_ERROR_DECODE: c_int = 38;
pub const BASS_ERROR_DX: c_int = 39;
pub const BASS_ERROR_TIMEOUT: c_int = 40;
pub const BASS_ERROR_FILEFORM: c_int = 41;
pub const BASS_ERROR_SPEAKER: c_int = 42;
pub const BASS_ERROR_VERSION: c_int = 43;
pub const BASS_ERROR_CODEC: c_int = 44;
pub const BASS_ERROR_ENDED: c_int = 45;
pub const BASS_ERROR_BUSY: c_int = 46;
pub const BASS_ERROR_UNSTREAMABLE: c_int = 47;
pub const BASS_ERROR_PROTOCOL: c_int = 48;
pub const BASS_ERROR_DENIED: c_int = 49;
pub const BASS_ERROR_UNKNOWN: c_int = -1;

/// Human-readable name for a BASS error code, `None` for an unknown one.
pub const fn error_name(code: c_int) -> Option<&'static str> {
    Some(match code {
        BASS_OK => "BASS_OK",
        BASS_ERROR_MEM => "BASS_ERROR_MEM",
        BASS_ERROR_FILEOPEN => "BASS_ERROR_FILEOPEN",
        BASS_ERROR_DRIVER => "BASS_ERROR_DRIVER",
        BASS_ERROR_BUFLOST => "BASS_ERROR_BUFLOST",
        BASS_ERROR_HANDLE => "BASS_ERROR_HANDLE",
        BASS_ERROR_FORMAT => "BASS_ERROR_FORMAT",
        BASS_ERROR_POSITION => "BASS_ERROR_POSITION",
        BASS_ERROR_INIT => "BASS_ERROR_INIT",
        BASS_ERROR_START => "BASS_ERROR_START",
        BASS_ERROR_SSL => "BASS_ERROR_SSL",
        BASS_ERROR_REINIT => "BASS_ERROR_REINIT",
        BASS_ERROR_ALREADY => "BASS_ERROR_ALREADY",
        BASS_ERROR_NOTAUDIO => "BASS_ERROR_NOTAUDIO",
        BASS_ERROR_NOCHAN => "BASS_ERROR_NOCHAN",
        BASS_ERROR_ILLTYPE => "BASS_ERROR_ILLTYPE",
        BASS_ERROR_ILLPARAM => "BASS_ERROR_ILLPARAM",
        BASS_ERROR_NO3D => "BASS_ERROR_NO3D",
        BASS_ERROR_NOEAX => "BASS_ERROR_NOEAX",
        BASS_ERROR_DEVICE => "BASS_ERROR_DEVICE",
        BASS_ERROR_NOPLAY => "BASS_ERROR_NOPLAY",
        BASS_ERROR_FREQ => "BASS_ERROR_FREQ",
        BASS_ERROR_NOTFILE => "BASS_ERROR_NOTFILE",
        BASS_ERROR_NOHW => "BASS_ERROR_NOHW",
        BASS_ERROR_EMPTY => "BASS_ERROR_EMPTY",
        BASS_ERROR_NONET => "BASS_ERROR_NONET",
        BASS_ERROR_CREATE => "BASS_ERROR_CREATE",
        BASS_ERROR_NOFX => "BASS_ERROR_NOFX",
        BASS_ERROR_NOTAVAIL => "BASS_ERROR_NOTAVAIL",
        BASS_ERROR_DECODE => "BASS_ERROR_DECODE",
        BASS_ERROR_DX => "BASS_ERROR_DX",
        BASS_ERROR_TIMEOUT => "BASS_ERROR_TIMEOUT",
        BASS_ERROR_FILEFORM => "BASS_ERROR_FILEFORM",
        BASS_ERROR_SPEAKER => "BASS_ERROR_SPEAKER",
        BASS_ERROR_VERSION => "BASS_ERROR_VERSION",
        BASS_ERROR_CODEC => "BASS_ERROR_CODEC",
        BASS_ERROR_ENDED => "BASS_ERROR_ENDED",
        BASS_ERROR_BUSY => "BASS_ERROR_BUSY",
        BASS_ERROR_UNSTREAMABLE => "BASS_ERROR_UNSTREAMABLE",
        BASS_ERROR_PROTOCOL => "BASS_ERROR_PROTOCOL",
        BASS_ERROR_DENIED => "BASS_ERROR_DENIED",
        BASS_ERROR_UNKNOWN => "BASS_ERROR_UNKNOWN",
        _ => return None,
    })
}

// --- BASS_SetConfig options --------------------------------------------------

pub const BASS_CONFIG_BUFFER: DWORD = 0;
pub const BASS_CONFIG_UPDATEPERIOD: DWORD = 1;
pub const BASS_CONFIG_GVOL_SAMPLE: DWORD = 4;
pub const BASS_CONFIG_GVOL_STREAM: DWORD = 5;
pub const BASS_CONFIG_GVOL_MUSIC: DWORD = 6;
pub const BASS_CONFIG_FLOATDSP: DWORD = 9;
pub const BASS_CONFIG_NET_TIMEOUT: DWORD = 11;
pub const BASS_CONFIG_NET_BUFFER: DWORD = 12;
pub const BASS_CONFIG_NET_PREBUF: DWORD = 15;
/// Pointer option (`BASS_SetConfigPtr`): the HTTP user-agent string.
pub const BASS_CONFIG_NET_AGENT: DWORD = 16;
/// Pointer option (`BASS_SetConfigPtr`): the HTTP proxy.
pub const BASS_CONFIG_NET_PROXY: DWORD = 17;
pub const BASS_CONFIG_NET_PASSIVE: DWORD = 18;
pub const BASS_CONFIG_NET_PLAYLIST: DWORD = 21;
pub const BASS_CONFIG_UPDATETHREADS: DWORD = 24;
pub const BASS_CONFIG_DEV_BUFFER: DWORD = 27;
pub const BASS_CONFIG_DEV_DEFAULT: DWORD = 36;
pub const BASS_CONFIG_NET_READTIMEOUT: DWORD = 37;
pub const BASS_CONFIG_UNICODE: DWORD = 42;
pub const BASS_CONFIG_SRC: DWORD = 43;
pub const BASS_CONFIG_SRC_SAMPLE: DWORD = 44;
pub const BASS_CONFIG_NET_PLAYLIST_DEPTH: DWORD = 59;
pub const BASS_CONFIG_NET_PREBUF_WAIT: DWORD = 60;

// --- BASS_Init flags ----------------------------------------------------------

pub const BASS_DEVICE_8BITS: DWORD = 1;
pub const BASS_DEVICE_MONO: DWORD = 2;
pub const BASS_DEVICE_3D: DWORD = 4;
pub const BASS_DEVICE_16BITS: DWORD = 8;
pub const BASS_DEVICE_REINIT: DWORD = 128;
pub const BASS_DEVICE_LATENCY: DWORD = 0x100;
pub const BASS_DEVICE_CPSPEAKERS: DWORD = 0x400;
pub const BASS_DEVICE_SPEAKERS: DWORD = 0x800;
pub const BASS_DEVICE_NOSPEAKER: DWORD = 0x1000;
pub const BASS_DEVICE_DMIX: DWORD = 0x2000;
pub const BASS_DEVICE_FREQ: DWORD = 0x4000;
pub const BASS_DEVICE_STEREO: DWORD = 0x8000;
pub const BASS_DEVICE_HOG: DWORD = 0x10000;
pub const BASS_DEVICE_AUDIOTRACK: DWORD = 0x20000;
pub const BASS_DEVICE_DSOUND: DWORD = 0x40000;
pub const BASS_DEVICE_SOFTWARE: DWORD = 0x80000;

// --- BASS_DEVICEINFO flags ----------------------------------------------------

pub const BASS_DEVICE_ENABLED: DWORD = 1;
pub const BASS_DEVICE_DEFAULT: DWORD = 2;
pub const BASS_DEVICE_INIT: DWORD = 4;
pub const BASS_DEVICE_LOOPBACK: DWORD = 8;
pub const BASS_DEVICE_DEFAULTCOM: DWORD = 128;
pub const BASS_DEVICE_TYPE_MASK: DWORD = 0xff00_0000;

// --- Sample / stream flags ----------------------------------------------------

pub const BASS_SAMPLE_8BITS: DWORD = 1;
pub const BASS_SAMPLE_MONO: DWORD = 2;
pub const BASS_SAMPLE_LOOP: DWORD = 4;
pub const BASS_SAMPLE_3D: DWORD = 8;
pub const BASS_SAMPLE_SOFTWARE: DWORD = 16;
pub const BASS_SAMPLE_FLOAT: DWORD = 256;
pub const BASS_STREAM_PRESCAN: DWORD = 0x20000;
/// Free the stream automatically when it stops or ends. Every one-shot in the
/// game is created with this; the "fade to -1 volume" idiom relies on it.
pub const BASS_STREAM_AUTOFREE: DWORD = 0x40000;
pub const BASS_STREAM_RESTRATE: DWORD = 0x80000;
/// Download and play an internet stream in small blocks (radio).
pub const BASS_STREAM_BLOCK: DWORD = 0x100000;
pub const BASS_STREAM_DECODE: DWORD = 0x200000;
/// Give server status info (HTTP/ICY tags) to the `DOWNLOADPROC`.
pub const BASS_STREAM_STATUS: DWORD = 0x800000;
/// `file`/`url` parameters are UTF-16 (Windows) rather than ANSI.
pub const BASS_UNICODE: DWORD = 0x8000_0000;

/// Slide attribute logarithmically (`BASS_ChannelSlideAttribute` flag).
pub const BASS_SLIDE_LOG: DWORD = 0x100_0000;

// --- Channel attributes ------------------------------------------------------

pub const BASS_ATTRIB_FREQ: DWORD = 1;
pub const BASS_ATTRIB_VOL: DWORD = 2;
pub const BASS_ATTRIB_PAN: DWORD = 3;
pub const BASS_ATTRIB_EAXMIX: DWORD = 4;
pub const BASS_ATTRIB_NOBUFFER: DWORD = 5;
pub const BASS_ATTRIB_VBR: DWORD = 6;
pub const BASS_ATTRIB_CPU: DWORD = 7;
pub const BASS_ATTRIB_SRC: DWORD = 8;
pub const BASS_ATTRIB_NET_RESUME: DWORD = 9;
pub const BASS_ATTRIB_SCANINFO: DWORD = 10;
pub const BASS_ATTRIB_NORAMP: DWORD = 11;
pub const BASS_ATTRIB_BITRATE: DWORD = 12;
pub const BASS_ATTRIB_BUFFER: DWORD = 13;
pub const BASS_ATTRIB_GRANULE: DWORD = 14;
pub const BASS_ATTRIB_USER: DWORD = 15;
pub const BASS_ATTRIB_TAIL: DWORD = 16;
pub const BASS_ATTRIB_PUSH_LIMIT: DWORD = 17;

// --- BASS_ChannelIsActive results ---------------------------------------------

pub const BASS_ACTIVE_STOPPED: DWORD = 0;
pub const BASS_ACTIVE_PLAYING: DWORD = 1;
pub const BASS_ACTIVE_STALLED: DWORD = 2;
pub const BASS_ACTIVE_PAUSED: DWORD = 3;
pub const BASS_ACTIVE_PAUSED_DEVICE: DWORD = 4;

// --- Sync types and flags -------------------------------------------------------

pub const BASS_SYNC_POS: DWORD = 0;
pub const BASS_SYNC_END: DWORD = 2;
pub const BASS_SYNC_META: DWORD = 4;
pub const BASS_SYNC_SLIDE: DWORD = 5;
pub const BASS_SYNC_STALL: DWORD = 6;
pub const BASS_SYNC_DOWNLOAD: DWORD = 7;
pub const BASS_SYNC_FREE: DWORD = 8;
pub const BASS_SYNC_SETPOS: DWORD = 11;
pub const BASS_SYNC_OGG_CHANGE: DWORD = 12;
pub const BASS_SYNC_DEV_FAIL: DWORD = 14;
pub const BASS_SYNC_DEV_FORMAT: DWORD = 15;
/// Flag: call the sync on a dedicated BASS thread rather than the mixer.
pub const BASS_SYNC_THREAD: DWORD = 0x2000_0000;
/// Flag: call the sync on the mixer thread at mix time rather than when the
/// position is heard. This is what lets a loop seek land exactly on the
/// boundary with no audible gap.
pub const BASS_SYNC_MIXTIME: DWORD = 0x4000_0000;
pub const BASS_SYNC_ONETIME: DWORD = 0x8000_0000;

// --- Position modes ---------------------------------------------------------------

pub const BASS_POS_BYTE: DWORD = 0;
pub const BASS_POS_MUSIC_ORDER: DWORD = 1;
pub const BASS_POS_OGG: DWORD = 3;
pub const BASS_POS_END: DWORD = 0x10;
pub const BASS_POS_LOOP: DWORD = 0x11;
pub const BASS_POS_FLUSH: DWORD = 0x100_0000;
pub const BASS_POS_RESET: DWORD = 0x200_0000;
pub const BASS_POS_RELATIVE: DWORD = 0x400_0000;
pub const BASS_POS_INEXACT: DWORD = 0x800_0000;
pub const BASS_POS_DECODE: DWORD = 0x1000_0000;
pub const BASS_POS_DECODETO: DWORD = 0x2000_0000;
pub const BASS_POS_SCAN: DWORD = 0x4000_0000;

// --- Tag types (BASS_ChannelGetTags) ------------------------------------------

/// ID3v1 tags: `TAG_ID3` structure.
pub const BASS_TAG_ID3: DWORD = 0;
/// ID3v2 tags: variable-length block.
pub const BASS_TAG_ID3V2: DWORD = 1;
/// OGG comments: series of null-terminated UTF-8 strings.
pub const BASS_TAG_OGG: DWORD = 2;
/// HTTP headers: series of null-terminated ANSI strings.
pub const BASS_TAG_HTTP: DWORD = 3;
/// ICY headers: series of null-terminated ANSI strings.
pub const BASS_TAG_ICY: DWORD = 4;
/// ICY metadata (the `StreamTitle='...'` block): one ANSI string.
pub const BASS_TAG_META: DWORD = 5;
pub const BASS_TAG_APE: DWORD = 6;
pub const BASS_TAG_MP4: DWORD = 7;
pub const BASS_TAG_WMA: DWORD = 8;
pub const BASS_TAG_VENDOR: DWORD = 9;
pub const BASS_TAG_LYRICS3: DWORD = 10;
pub const BASS_TAG_WAVEFORMAT: DWORD = 14;
pub const BASS_TAG_RIFF_INFO: DWORD = 0x100;

// --- Channel types (BASS_CHANNELINFO.ctype) -----------------------------------

pub const BASS_CTYPE_SAMPLE: DWORD = 1;
pub const BASS_CTYPE_RECORD: DWORD = 2;
pub const BASS_CTYPE_STREAM: DWORD = 0x10000;
pub const BASS_CTYPE_STREAM_VORBIS: DWORD = 0x10002;
pub const BASS_CTYPE_STREAM_OGG: DWORD = 0x10002;
pub const BASS_CTYPE_STREAM_MP1: DWORD = 0x10003;
pub const BASS_CTYPE_STREAM_MP2: DWORD = 0x10004;
pub const BASS_CTYPE_STREAM_MP3: DWORD = 0x10005;
pub const BASS_CTYPE_STREAM_AIFF: DWORD = 0x10006;
pub const BASS_CTYPE_STREAM_CA: DWORD = 0x10007;
pub const BASS_CTYPE_STREAM_MF: DWORD = 0x10008;
pub const BASS_CTYPE_STREAM_AM: DWORD = 0x10009;
pub const BASS_CTYPE_STREAM_SAMPLE: DWORD = 0x1000a;
pub const BASS_CTYPE_STREAM_DUMMY: DWORD = 0x18000;
pub const BASS_CTYPE_STREAM_DEVICE: DWORD = 0x18001;
/// WAVE is a flag on the channel type: `BASS_CTYPE_STREAM_WAV | codec`.
pub const BASS_CTYPE_STREAM_WAV: DWORD = 0x40000;
pub const BASS_CTYPE_STREAM_WAV_PCM: DWORD = 0x50001;
pub const BASS_CTYPE_STREAM_WAV_FLOAT: DWORD = 0x50003;
pub const BASS_CTYPE_STREAM_OPUS: DWORD = 0x11200;
pub const BASS_CTYPE_STREAM_FLAC: DWORD = 0x10900;
pub const BASS_CTYPE_STREAM_FLAC_OGG: DWORD = 0x10901;
pub const BASS_CTYPE_STREAM_AAC: DWORD = 0x10b00;
pub const BASS_CTYPE_STREAM_MP4: DWORD = 0x10b01;
pub const BASS_CTYPE_STREAM_HLS: DWORD = 0x10f00;

// --- Structs, exact C layout ---------------------------------------------------

/// Device information from `BASS_GetDeviceInfo`.
///
/// ```c
/// typedef struct {
///     const char *name;   // description
///     const char *driver; // driver
///     DWORD flags;
/// } BASS_DEVICEINFO;
/// ```
///
/// On 64-bit targets that is 24 bytes (two pointers, a DWORD and four bytes of
/// tail padding); the layout test below pins it. The strings are UTF-8 when
/// `BASS_CONFIG_UNICODE` is set, ANSI otherwise; they point into BASS's own
/// storage and are only valid until the next call.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct BASS_DEVICEINFO {
    pub name: *const c_char,
    pub driver: *const c_char,
    pub flags: DWORD,
}

/// Channel information from `BASS_ChannelGetInfo`.
///
/// ```c
/// typedef struct {
///     DWORD freq;      // default playback rate
///     DWORD chans;     // channels
///     DWORD flags;     // BASS_SAMPLE/STREAM/MUSIC/SPEAKER flags
///     DWORD ctype;     // type of channel
///     DWORD origres;   // original resolution
///     HPLUGIN plugin;  // plugin
///     HSAMPLE sample;  // sample
///     const char *filename; // filename
/// } BASS_CHANNELINFO;
/// ```
///
/// Seven DWORDs, four bytes of padding, then a pointer: 40 bytes on 64-bit,
/// 32 on 32-bit. Pinned by the layout test below.
#[repr(C)]
#[derive(Debug, Clone, Copy)]
pub struct BASS_CHANNELINFO {
    pub freq: DWORD,
    pub chans: DWORD,
    pub flags: DWORD,
    pub ctype: DWORD,
    pub origres: DWORD,
    pub plugin: HPLUGIN,
    pub sample: HSAMPLE,
    pub filename: *const c_char,
}

// --- Callback types -----------------------------------------------------------------

/// `void CALLBACK SYNCPROC(HSYNC handle, DWORD channel, DWORD data, void *user)`.
///
/// Called by BASS on one of its own threads -- for `BASS_SYNC_MIXTIME` syncs
/// that is the mixer/update thread, while it holds the channel's lock. The
/// callback must be quick and must not block on anything the mixer thread
/// may itself be waiting for. `BASS_ChannelSetPosition` on the same channel
/// is explicitly allowed (it is what the sustain-loop sync does).
pub type SYNCPROC =
    unsafe extern "system" fn(handle: HSYNC, channel: DWORD, data: DWORD, user: *mut c_void);

/// `void CALLBACK DOWNLOADPROC(const void *buffer, DWORD length, void *user)`.
///
/// The game passes NULL for this; the type exists so the `BASS_StreamCreateURL`
/// signature is exact.
pub type DOWNLOADPROC =
    unsafe extern "system" fn(buffer: *const c_void, length: DWORD, user: *mut c_void);

// --- Function pointer types, one per symbol the loader resolves -------------------

pub type FnInit = unsafe extern "system" fn(
    device: c_int,
    freq: DWORD,
    flags: DWORD,
    win: *mut c_void,
    clsid: *const c_void,
) -> BOOL;
pub type FnFree = unsafe extern "system" fn() -> BOOL;
pub type FnSetConfig = unsafe extern "system" fn(option: DWORD, value: DWORD) -> BOOL;
pub type FnSetConfigPtr = unsafe extern "system" fn(option: DWORD, value: *const c_void) -> BOOL;
pub type FnGetConfig = unsafe extern "system" fn(option: DWORD) -> DWORD;
pub type FnErrorGetCode = unsafe extern "system" fn() -> c_int;
pub type FnGetVersion = unsafe extern "system" fn() -> DWORD;
pub type FnGetDevice = unsafe extern "system" fn() -> DWORD;
pub type FnGetDeviceInfo =
    unsafe extern "system" fn(device: DWORD, info: *mut BASS_DEVICEINFO) -> BOOL;
pub type FnUpdate = unsafe extern "system" fn(length: DWORD) -> BOOL;

pub type FnPluginLoad = unsafe extern "system" fn(file: *const c_void, flags: DWORD) -> HPLUGIN;
pub type FnPluginFree = unsafe extern "system" fn(handle: HPLUGIN) -> BOOL;

pub type FnStreamCreateFile = unsafe extern "system" fn(
    mem: BOOL,
    file: *const c_void,
    offset: QWORD,
    length: QWORD,
    flags: DWORD,
) -> HSTREAM;
pub type FnStreamCreateURL = unsafe extern "system" fn(
    url: *const c_void,
    offset: DWORD,
    flags: DWORD,
    proc_: Option<DOWNLOADPROC>,
    user: *mut c_void,
) -> HSTREAM;
pub type FnStreamFree = unsafe extern "system" fn(handle: HSTREAM) -> BOOL;

pub type FnChannelPlay = unsafe extern "system" fn(handle: DWORD, restart: BOOL) -> BOOL;
pub type FnChannelPause = unsafe extern "system" fn(handle: DWORD) -> BOOL;
pub type FnChannelStop = unsafe extern "system" fn(handle: DWORD) -> BOOL;
pub type FnChannelIsActive = unsafe extern "system" fn(handle: DWORD) -> DWORD;
pub type FnChannelUpdate = unsafe extern "system" fn(handle: DWORD, length: DWORD) -> BOOL;
pub type FnChannelSetAttribute =
    unsafe extern "system" fn(handle: DWORD, attrib: DWORD, value: f32) -> BOOL;
pub type FnChannelGetAttribute =
    unsafe extern "system" fn(handle: DWORD, attrib: DWORD, value: *mut f32) -> BOOL;
pub type FnChannelSlideAttribute =
    unsafe extern "system" fn(handle: DWORD, attrib: DWORD, value: f32, time: DWORD) -> BOOL;
pub type FnChannelIsSliding = unsafe extern "system" fn(handle: DWORD, attrib: DWORD) -> BOOL;
pub type FnChannelGetLength = unsafe extern "system" fn(handle: DWORD, mode: DWORD) -> QWORD;
pub type FnChannelGetPosition = unsafe extern "system" fn(handle: DWORD, mode: DWORD) -> QWORD;
pub type FnChannelSetPosition =
    unsafe extern "system" fn(handle: DWORD, pos: QWORD, mode: DWORD) -> BOOL;
pub type FnChannelBytes2Seconds = unsafe extern "system" fn(handle: DWORD, pos: QWORD) -> f64;
pub type FnChannelSeconds2Bytes = unsafe extern "system" fn(handle: DWORD, pos: f64) -> QWORD;
pub type FnChannelSetSync = unsafe extern "system" fn(
    handle: DWORD,
    type_: DWORD,
    param: QWORD,
    proc_: Option<SYNCPROC>,
    user: *mut c_void,
) -> HSYNC;
pub type FnChannelRemoveSync = unsafe extern "system" fn(handle: DWORD, sync: HSYNC) -> BOOL;
pub type FnChannelGetTags = unsafe extern "system" fn(handle: DWORD, tags: DWORD) -> *const c_char;
pub type FnChannelFlags =
    unsafe extern "system" fn(handle: DWORD, flags: DWORD, mask: DWORD) -> DWORD;
pub type FnChannelGetInfo =
    unsafe extern "system" fn(handle: DWORD, info: *mut BASS_CHANNELINFO) -> BOOL;
pub type FnChannelGetDevice = unsafe extern "system" fn(handle: DWORD) -> DWORD;

/// Is the BASS library loadable on this machine?
///
/// Cheap after the first call: the loader caches its result, success or
/// failure, for the life of the process.
pub fn native_available() -> bool {
    Api::get().is_ok()
}

/// The resolved BASS entry points, or why they could not be resolved.
///
/// Same cached result as [`Api::get`]; this is the spelling the safe layer and
/// the game use.
pub fn api() -> Result<&'static Api, LoadError> {
    Api::get()
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::mem::{align_of, offset_of, size_of};

    #[test]
    fn channelinfo_layout_matches_bass_h() {
        let ptr = size_of::<*const c_char>();
        // Seven DWORDs (28 bytes) then the pointer, aligned to pointer size.
        let expected = if ptr == 8 { 40 } else { 32 };
        assert_eq!(size_of::<BASS_CHANNELINFO>(), expected);
        assert_eq!(align_of::<BASS_CHANNELINFO>(), ptr);
        assert_eq!(offset_of!(BASS_CHANNELINFO, freq), 0);
        assert_eq!(offset_of!(BASS_CHANNELINFO, chans), 4);
        assert_eq!(offset_of!(BASS_CHANNELINFO, flags), 8);
        assert_eq!(offset_of!(BASS_CHANNELINFO, ctype), 12);
        assert_eq!(offset_of!(BASS_CHANNELINFO, origres), 16);
        assert_eq!(offset_of!(BASS_CHANNELINFO, plugin), 20);
        assert_eq!(offset_of!(BASS_CHANNELINFO, sample), 24);
        assert_eq!(
            offset_of!(BASS_CHANNELINFO, filename),
            if ptr == 8 { 32 } else { 28 }
        );
    }

    #[test]
    fn deviceinfo_layout_matches_bass_h() {
        let ptr = size_of::<*const c_char>();
        let expected = if ptr == 8 { 24 } else { 12 };
        assert_eq!(size_of::<BASS_DEVICEINFO>(), expected);
        assert_eq!(offset_of!(BASS_DEVICEINFO, name), 0);
        assert_eq!(offset_of!(BASS_DEVICEINFO, driver), ptr);
        assert_eq!(offset_of!(BASS_DEVICEINFO, flags), 2 * ptr);
    }

    #[test]
    fn error_names_cover_every_declared_code() {
        for code in [
            BASS_OK,
            BASS_ERROR_MEM,
            BASS_ERROR_HANDLE,
            BASS_ERROR_INIT,
            BASS_ERROR_ALREADY,
            BASS_ERROR_NOTAVAIL,
            BASS_ERROR_TIMEOUT,
            BASS_ERROR_DENIED,
            BASS_ERROR_UNKNOWN,
        ] {
            assert!(error_name(code).is_some(), "code {code} has no name");
        }
        assert_eq!(error_name(12345), None);
        assert_eq!(error_name(BASS_ERROR_HANDLE), Some("BASS_ERROR_HANDLE"));
    }

    #[test]
    fn flag_values_match_pybass() {
        // Spot checks against the values the Python game has been passing.
        assert_eq!(BASS_STREAM_AUTOFREE, 0x40000);
        assert_eq!(BASS_SAMPLE_LOOP, 4);
        assert_eq!(BASS_UNICODE, 0x8000_0000);
        assert_eq!(BASS_SYNC_POS | BASS_SYNC_MIXTIME, 0x4000_0000);
        assert_eq!(BASS_CONFIG_NET_READTIMEOUT, 37);
        assert_eq!(BASS_TAG_META, 5);
        assert_eq!(BASS_ATTRIB_PAN, 3);
    }
}
