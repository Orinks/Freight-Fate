//! Renders synthesized pieces off the game loop.
//!
//! One thread, a bounded queue of two requests. A full queue drops the new
//! request -- the caller plays the classic and asks again next track -- so
//! the loop never waits here. A rendered piece is published as a generated
//! sound under `music/<key>`; KEEP_RENDERED stay registered, and a piece
//! among the last RECENT_REQUESTS requests is never evicted, so what a
//! rotation just resolved as playing or next is still there to play.

use super::render::render_wav;
use super::{compose, SynthKey};
use crate::assets_pack::{generated_sound, register_generated_sound, unregister_generated_sound};
use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{sync_channel, Receiver, SyncSender, TrySendError};
use std::sync::{Arc, Mutex};
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

const QUEUE: usize = 2;
const KEEP_RENDERED: usize = 4;
/// A rotation requests its current piece and the next one, and the menu and
/// the Roadhouse can both be rotating: four requests cover both.
const RECENT_REQUESTS: usize = 4;

type Recent = Arc<Mutex<VecDeque<String>>>;

pub struct SynthWorker {
    tx: Option<SyncSender<SynthKey>>,
    cancel: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
    /// Generated-sound names (`music/<key>`) of the latest requests.
    recent: Recent,
    stopped_logged: AtomicBool,
}

impl SynthWorker {
    pub fn start() -> SynthWorker {
        let (tx, rx) = sync_channel::<SynthKey>(QUEUE);
        let cancel = Arc::new(AtomicBool::new(false));
        let flag = Arc::clone(&cancel);
        let recent: Recent = Arc::default();
        let in_use = Arc::clone(&recent);
        let handle = std::thread::Builder::new()
            .name("synth-music".into())
            .spawn(move || run(rx, flag, in_use))
            .map_err(|err| log::warn!("Synthesized music worker did not start ({err})"))
            .ok();
        SynthWorker {
            tx: handle.as_ref().map(|_| tx),
            cancel,
            handle,
            recent,
            stopped_logged: AtomicBool::new(false),
        }
    }

    /// Queue a render, and mark `key` in use so it is not evicted. True when
    /// it is queued or already published. False when `key` is not a synth
    /// key, the worker is shut down or has stopped, or the queue is full.
    pub fn request(&self, key: &str) -> bool {
        let (Some(tx), Some(parsed)) = (&self.tx, SynthKey::parse(key)) else {
            return false;
        };
        note_request(&self.recent, format!("music/{key}"));
        if Self::is_ready(key) {
            return true;
        }
        match tx.try_send(parsed) {
            Ok(()) => true,
            Err(TrySendError::Full(_)) => false,
            Err(TrySendError::Disconnected(_)) => {
                if !self.stopped_logged.swap(true, Ordering::Relaxed) {
                    log::warn!("Synthesized music worker has stopped; the classics play instead");
                }
                false
            }
        }
    }

    pub fn is_ready(key: &str) -> bool {
        generated_sound(&format!("music/{key}")).is_some()
    }

    /// Signal, stop accepting work, then wait at most `bound`.
    pub fn shutdown(&mut self, bound: Duration) {
        self.cancel.store(true, Ordering::SeqCst);
        self.tx = None; // disconnects the channel; the thread's recv ends
        let Some(handle) = self.handle.take() else {
            return;
        };
        log::info!("shutdown: synthesized music worker signalled");
        let started = Instant::now();
        while !handle.is_finished() && started.elapsed() < bound {
            std::thread::sleep(Duration::from_millis(10));
        }
        if handle.is_finished() {
            if handle.join().is_err() {
                log::warn!("shutdown: synthesized music worker had panicked");
            }
            log::info!(
                "shutdown: synthesized music worker joined in {} ms",
                started.elapsed().as_millis()
            );
        } else {
            log::warn!(
                "shutdown: synthesized music worker still rendering after {} ms; leaving it",
                bound.as_millis()
            );
        }
    }
}

impl Drop for SynthWorker {
    fn drop(&mut self) {
        // Signal only: never join in Drop.
        self.cancel.store(true, Ordering::SeqCst);
        self.tx = None;
    }
}

fn note_request(recent: &Recent, name: String) {
    let mut recent = recent.lock().unwrap_or_else(|e| e.into_inner());
    recent.retain(|k| *k != name);
    recent.push_back(name);
    while recent.len() > RECENT_REQUESTS {
        recent.pop_front();
    }
}

/// The oldest published piece that no recent request is using.
fn evictable(published: &VecDeque<String>, recent: &VecDeque<String>) -> Option<usize> {
    published.iter().position(|k| !recent.contains(k))
}

fn run(rx: Receiver<SynthKey>, cancel: Arc<AtomicBool>, recent: Recent) {
    let mut published: VecDeque<String> = VecDeque::new();
    while let Ok(key) = rx.recv() {
        if cancel.load(Ordering::SeqCst) {
            break;
        }
        let name = format!("music/{}", key.key());
        if generated_sound(&name).is_some() {
            continue;
        }
        let score = compose(key.style, key.seed());
        let Some(wav) = render_wav(&score, &cancel) else {
            break; // cancelled mid-render: publish nothing
        };
        if cancel.load(Ordering::SeqCst) {
            break;
        }
        register_generated_sound(&name, wav, "wav");
        published.push_back(name);
        while published.len() > KEEP_RENDERED {
            let in_use = recent.lock().unwrap_or_else(|e| e.into_inner()).clone();
            let Some(i) = evictable(&published, &in_use) else {
                break; // every piece is in use: keep them all for now
            };
            if let Some(old) = published.remove(i) {
                unregister_generated_sound(&old);
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::music_synth::{StyleId, SynthKey};
    use std::time::{Duration, Instant};

    fn wait_ready(key: &str) -> bool {
        let t = Instant::now();
        while t.elapsed() < Duration::from_secs(60) {
            if SynthWorker::is_ready(key) {
                return true;
            }
            std::thread::sleep(Duration::from_millis(20));
        }
        false
    }

    #[test]
    fn a_requested_piece_is_published_as_a_wav() {
        let mut worker = SynthWorker::start();
        let key = SynthKey {
            style: StyleId::NightMenu,
            music_seed: 777,
            index: 0,
        }
        .key();
        assert!(worker.request(&key));
        assert!(wait_ready(&key));
        let (bytes, ext) =
            crate::assets_pack::generated_sound(&format!("music/{key}")).expect("published");
        assert_eq!(ext, "wav");
        assert_eq!(&bytes[..4], b"RIFF");
        worker.shutdown(Duration::from_secs(5));
    }

    #[test]
    fn a_piece_resolved_as_playing_or_next_is_never_evicted() {
        let names = |v: &[&str]| v.iter().map(|s| s.to_string()).collect::<VecDeque<_>>();
        let recent: Recent = Arc::default();
        // The menu resolves a and asks for b; the Roadhouse resolves c, asks d.
        for k in ["music/a", "music/b", "music/c", "music/d"] {
            note_request(&recent, k.to_string());
        }
        let in_use = recent.lock().unwrap().clone();
        // e was just published over the cap: the oldest piece not in use goes.
        let published = names(&["music/old", "music/a", "music/b", "music/c", "music/d"]);
        assert_eq!(evictable(&published, &in_use), Some(0));
        // With every published piece in use, nothing is evicted.
        let published = names(&["music/a", "music/b", "music/c", "music/d"]);
        assert_eq!(evictable(&published, &in_use), None);
        // A repeat request refreshes a key instead of pushing a live one out.
        note_request(&recent, "music/a".into());
        note_request(&recent, "music/e".into());
        let in_use = recent.lock().unwrap().clone();
        assert_eq!(in_use, names(&["music/c", "music/d", "music/a", "music/e"]));
    }

    #[test]
    fn a_ready_piece_is_marked_in_use_when_requested() {
        let worker = SynthWorker::start();
        let key = SynthKey {
            style: StyleId::DayDrive,
            music_seed: 4242,
            index: 1,
        }
        .key();
        let name = format!("music/{key}");
        register_generated_sound(&name, b"RIFF".to_vec(), "wav");
        assert!(worker.request(&key), "already published is true");
        assert!(worker.recent.lock().unwrap().contains(&name));
        unregister_generated_sound(&name);
    }

    #[test]
    fn non_synth_keys_are_refused_and_shutdown_is_idempotent() {
        let mut worker = SynthWorker::start();
        assert!(!worker.request("open_road"));
        worker.shutdown(Duration::from_secs(5));
        worker.shutdown(Duration::from_secs(5));
        assert!(!worker.request(
            &SynthKey {
                style: StyleId::DayDrive,
                music_seed: 1,
                index: 0,
            }
            .key()
        ));
    }
}
