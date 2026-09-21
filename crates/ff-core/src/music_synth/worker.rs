//! Renders synthesized pieces off the game loop.
//!
//! One thread, a bounded queue of two requests. A full queue drops the new
//! request -- the caller plays the classic and asks again next track -- so
//! the loop never waits here. A rendered piece is published as a generated
//! sound under `music/<key>`; at most KEEP_RENDERED stay registered.

use super::{compose, render, SynthKey, SAMPLE_RATE};
use crate::assets_pack::{generated_sound, register_generated_sound, unregister_generated_sound};
use std::collections::VecDeque;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::mpsc::{sync_channel, Receiver, SyncSender, TrySendError};
use std::sync::Arc;
use std::thread::JoinHandle;
use std::time::{Duration, Instant};

const QUEUE: usize = 2;
const KEEP_RENDERED: usize = 3;

pub struct SynthWorker {
    tx: Option<SyncSender<SynthKey>>,
    cancel: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl SynthWorker {
    pub fn start() -> SynthWorker {
        let (tx, rx) = sync_channel::<SynthKey>(QUEUE);
        let cancel = Arc::new(AtomicBool::new(false));
        let flag = Arc::clone(&cancel);
        let handle = std::thread::Builder::new()
            .name("synth-music".into())
            .spawn(move || run(rx, flag))
            .map_err(|err| log::warn!("Synthesized music worker did not start ({err})"))
            .ok();
        SynthWorker {
            tx: handle.as_ref().map(|_| tx),
            cancel,
            handle,
        }
    }

    /// Queue a render. False when `key` is not a synth key, is already
    /// published, the worker is shut down, or the queue is full.
    pub fn request(&self, key: &str) -> bool {
        let (Some(tx), Some(parsed)) = (&self.tx, SynthKey::parse(key)) else {
            return false;
        };
        if Self::is_ready(key) {
            return true;
        }
        match tx.try_send(parsed) {
            Ok(()) => true,
            Err(TrySendError::Full(_)) => false,
            Err(TrySendError::Disconnected(_)) => false,
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
            let _ = handle.join();
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

fn run(rx: Receiver<SynthKey>, cancel: Arc<AtomicBool>) {
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
        let pcm = render(&score);
        if cancel.load(Ordering::SeqCst) {
            break;
        }
        register_generated_sound(&name, crate::wav::pcm16_wav(&pcm, 2, SAMPLE_RATE), "wav");
        published.push_back(name);
        while published.len() > KEEP_RENDERED {
            if let Some(old) = published.pop_front() {
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
