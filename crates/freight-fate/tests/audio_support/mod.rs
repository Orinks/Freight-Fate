//! Shared rigging for the audio integration tests.
//!
//! BASS has one device per process and `cargo test` runs tests on parallel
//! threads, so every test that builds an `AudioEngine` takes `AUDIO_LOCK`
//! and sets `SDL_AUDIODRIVER=dummy` (the Python conftest did the latter for
//! the whole suite) so BASS opens its no-sound device. Tests that need the
//! BASS backend skip themselves -- an early return with a note -- when the
//! library is not loadable on this machine.

#![allow(dead_code)]

use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::sync::atomic::{AtomicBool, AtomicUsize, Ordering};
use std::sync::{Arc, Mutex, MutexGuard, Once};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

use freight_fate::audio::{Audio, AudioEngine};

static AUDIO_LOCK: Mutex<()> = Mutex::new(());
static HEADLESS: Once = Once::new();

/// Serialise engine construction and route BASS to the no-sound device.
pub fn audio_lock() -> MutexGuard<'static, ()> {
    HEADLESS.call_once(|| std::env::set_var("SDL_AUDIODRIVER", "dummy"));
    AUDIO_LOCK.lock().unwrap_or_else(|e| e.into_inner())
}

/// An engine plus the lock that keeps it alone on the device. Shutdown runs
/// on drop too, so a failing test cannot leave the device initialised for
/// the next one.
pub struct Rig {
    pub engine: AudioEngine,
    _guard: MutexGuard<'static, ()>,
}

impl Drop for Rig {
    fn drop(&mut self) {
        self.engine.shutdown();
    }
}

/// The facade on whatever backend the environment gives (BASS when loadable,
/// the null backend otherwise).
pub fn rig() -> Rig {
    let guard = audio_lock();
    let engine = AudioEngine::new();
    Rig {
        engine,
        _guard: guard,
    }
}

/// The facade on the BASS backend, or `None` (with a note) when BASS cannot
/// load here -- the Python `pytest.skip("BASS backend unavailable")`.
pub fn bass_rig() -> Option<Rig> {
    let rig = rig();
    if rig.engine.backend_name() != "bass" {
        eprintln!("BASS backend unavailable on this machine; skipping");
        return None;
    }
    Some(rig)
}

/// Poll `cond` every 10 ms for up to `timeout`.
pub fn wait_for(timeout: Duration, mut cond: impl FnMut() -> bool) -> bool {
    let start = Instant::now();
    while start.elapsed() < timeout {
        if cond() {
            return true;
        }
        std::thread::sleep(Duration::from_millis(10));
    }
    cond()
}

/// A 16-bit PCM WAV of `seconds` of a 440 Hz sine at 44.1 kHz, `channels`
/// wide.
pub fn sine_wav(seconds: f64, channels: u16) -> Vec<u8> {
    let rate: u32 = 44100;
    let frames = (seconds * rate as f64).round() as u32;
    let block = channels as u32 * 2;
    let data_len = frames * block;
    let mut out = Vec::with_capacity(44 + data_len as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&rate.to_le_bytes());
    out.extend_from_slice(&(rate * block).to_le_bytes());
    out.extend_from_slice(&(block as u16).to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for i in 0..frames {
        let t = i as f64 / rate as f64;
        let s = ((t * 440.0 * std::f64::consts::TAU).sin() * 0.5 * i16::MAX as f64) as i16;
        for _ in 0..channels {
            out.extend_from_slice(&s.to_le_bytes());
        }
    }
    out
}

/// A tiny Shoutcast-style server on localhost: every connection gets the
/// same body, with ICY metadata interleaved every `metaint` bytes when a
/// title is given. Stands in for the station the Python tests faked.
pub struct IcyServer {
    pub url: String,
    pub connections: Arc<AtomicUsize>,
    stop: Arc<AtomicBool>,
    thread: Option<JoinHandle<()>>,
}

const METAINT: usize = 8192;

fn icy_body(audio: &[u8], title: Option<&str>) -> Vec<u8> {
    let Some(title) = title else {
        return audio.to_vec();
    };
    let mut block = format!("StreamTitle='{title}';StreamUrl='';").into_bytes();
    let pad = (16 - block.len() % 16) % 16;
    block.resize(block.len() + pad, 0);
    let len_byte = (block.len() / 16) as u8;
    let mut out = Vec::with_capacity(audio.len() + audio.len() / METAINT * (block.len() + 1));
    for chunk in audio.chunks(METAINT) {
        out.extend_from_slice(chunk);
        if chunk.len() == METAINT {
            out.push(len_byte);
            out.extend_from_slice(&block);
        }
    }
    out
}

fn serve_one(mut socket: TcpStream, headers: &str, body: &[u8]) {
    let _ = socket.set_read_timeout(Some(Duration::from_secs(2)));
    let mut request = Vec::new();
    let mut buf = [0u8; 1024];
    while !request.windows(4).any(|w| w == b"\r\n\r\n") {
        match socket.read(&mut buf) {
            Ok(0) | Err(_) => break,
            Ok(n) => request.extend_from_slice(&buf[..n]),
        }
    }
    let _ = socket.write_all(headers.as_bytes());
    let _ = socket.write_all(body);
    let _ = socket.flush();
    // Keep the connection open a moment so a reader that wants more sees a
    // clean end, not a reset mid-buffer.
    std::thread::sleep(Duration::from_millis(200));
    let _ = socket.shutdown(std::net::Shutdown::Both);
}

impl IcyServer {
    pub fn start(audio: Vec<u8>, title: Option<&str>) -> IcyServer {
        let listener = TcpListener::bind("127.0.0.1:0").expect("bind localhost");
        listener
            .set_nonblocking(true)
            .expect("nonblocking listener");
        let port = listener.local_addr().unwrap().port();
        let body = icy_body(&audio, title);
        let mut headers = String::from(
            "ICY 200 OK\r\nicy-name: Freight Fate test station\r\nContent-Type: audio/wav\r\n",
        );
        if title.is_some() {
            headers.push_str(&format!("icy-metaint: {METAINT}\r\n"));
        }
        headers.push_str("\r\n");
        let connections = Arc::new(AtomicUsize::new(0));
        let stop = Arc::new(AtomicBool::new(false));
        let thread = {
            let connections = Arc::clone(&connections);
            let stop = Arc::clone(&stop);
            std::thread::spawn(move || {
                let mut workers: Vec<JoinHandle<()>> = Vec::new();
                while !stop.load(Ordering::SeqCst) {
                    match listener.accept() {
                        Ok((socket, _)) => {
                            connections.fetch_add(1, Ordering::SeqCst);
                            let _ = socket.set_nonblocking(false);
                            let headers = headers.clone();
                            let body = body.clone();
                            workers.push(std::thread::spawn(move || {
                                serve_one(socket, &headers, &body)
                            }));
                        }
                        Err(_) => std::thread::sleep(Duration::from_millis(10)),
                    }
                }
                for worker in workers {
                    let _ = worker.join();
                }
            })
        };
        IcyServer {
            url: format!("http://127.0.0.1:{port}/live"),
            connections,
            stop,
            thread: Some(thread),
        }
    }

    pub fn connections(&self) -> usize {
        self.connections.load(Ordering::SeqCst)
    }
}

impl Drop for IcyServer {
    fn drop(&mut self) {
        self.stop.store(true, Ordering::SeqCst);
        if let Some(thread) = self.thread.take() {
            let _ = thread.join();
        }
    }
}
