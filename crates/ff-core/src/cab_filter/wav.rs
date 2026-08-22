//! A minimal 16-bit PCM WAV reader/writer, byte-compatible with Python's
//! `wave` module for the one shape the game writes: a 44-byte canonical
//! RIFF/WAVE header (`fmt ` of 16 bytes, format 1) followed by the `data`
//! chunk. The reader also takes the extensible format with a PCM
//! sub-format, which is what Python 3.12's `wave` accepts.
//!
//! Shared by the cab transfer (which re-wraps its render) and the
//! synthesized cues (`ladder_earcons`, `lane_guide_tone`), whose bytes must
//! match the Python build exactly.

/// The parsed contents of a 16-bit PCM WAV.
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct WavPcm16 {
    pub sample_rate: u32,
    pub channels: u16,
    /// Interleaved frames.
    pub samples: Vec<i16>,
}

/// Why a WAV could not be taken through the transfer.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum WavError {
    /// Not a RIFF/WAVE file at all, or a truncated header.
    Unreadable,
    /// RIFF/WAVE but not 16-bit PCM.
    NotPcm16,
}

impl WavPcm16 {
    pub fn frames(&self) -> usize {
        if self.channels == 0 {
            0
        } else {
            self.samples.len() / self.channels as usize
        }
    }

    /// Parse a WAV. `Unreadable` is what Python's `wave.Error` covered;
    /// `NotPcm16` is the explicit sample-width/compression check.
    pub fn parse(data: &[u8]) -> Result<Self, WavError> {
        if data.len() < 12 || &data[0..4] != b"RIFF" || &data[8..12] != b"WAVE" {
            return Err(WavError::Unreadable);
        }
        let mut pos = 12;
        let mut fmt: Option<(u16, u16, u32, u16)> = None; // tag, channels, rate, bits
        let mut pcm: Option<&[u8]> = None;
        while pos + 8 <= data.len() {
            let id = &data[pos..pos + 4];
            let size =
                u32::from_le_bytes([data[pos + 4], data[pos + 5], data[pos + 6], data[pos + 7]])
                    as usize;
            let body_start = pos + 8;
            let body_end = body_start.saturating_add(size).min(data.len());
            let body = &data[body_start..body_end];
            if id == b"fmt " {
                if body.len() < 16 {
                    return Err(WavError::Unreadable);
                }
                let tag = u16::from_le_bytes([body[0], body[1]]);
                let channels = u16::from_le_bytes([body[2], body[3]]);
                let rate = u32::from_le_bytes([body[4], body[5], body[6], body[7]]);
                let bits = u16::from_le_bytes([body[14], body[15]]);
                let tag = if tag == 0xFFFE {
                    // WAVE_FORMAT_EXTENSIBLE: the real format is the first two
                    // bytes of the sub-format GUID.
                    if body.len() >= 26 {
                        u16::from_le_bytes([body[24], body[25]])
                    } else {
                        return Err(WavError::Unreadable);
                    }
                } else {
                    tag
                };
                fmt = Some((tag, channels, rate, bits));
            } else if id == b"data" {
                pcm = Some(body);
                if fmt.is_some() {
                    break;
                }
            }
            // Chunks are word-aligned.
            pos = body_start.saturating_add(size).saturating_add(size & 1);
        }
        let (tag, channels, rate, bits) = fmt.ok_or(WavError::Unreadable)?;
        let pcm = pcm.ok_or(WavError::Unreadable)?;
        if tag != 1 {
            return Err(WavError::Unreadable);
        }
        if bits != 16 {
            return Err(WavError::NotPcm16);
        }
        if channels == 0 {
            return Err(WavError::Unreadable);
        }
        // Whole frames only, as wave.readframes(getnframes()) returns.
        let frame_bytes = 2 * channels as usize;
        let usable = pcm.len() / frame_bytes * frame_bytes;
        let samples = pcm[..usable]
            .chunks_exact(2)
            .map(|b| i16::from_le_bytes([b[0], b[1]]))
            .collect();
        Ok(Self {
            sample_rate: rate,
            channels,
            samples,
        })
    }

    /// The canonical 44-byte-header WAV Python's `wave` writes.
    pub fn to_bytes(&self) -> Vec<u8> {
        write_wav_pcm16(self.sample_rate, self.channels, &self.samples)
    }
}

/// Serialize interleaved 16-bit samples exactly as Python's `wave` module
/// does for `setnchannels(channels)`, `setsampwidth(2)`, `setframerate(rate)`.
pub fn write_wav_pcm16(sample_rate: u32, channels: u16, samples: &[i16]) -> Vec<u8> {
    let data_len = (samples.len() * 2) as u32;
    let mut out = Vec::with_capacity(44 + samples.len() * 2);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVE");
    out.extend_from_slice(b"fmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes()); // WAVE_FORMAT_PCM
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&sample_rate.to_le_bytes());
    out.extend_from_slice(&(sample_rate * channels as u32 * 2).to_le_bytes());
    out.extend_from_slice(&(channels * 2).to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    for sample in samples {
        out.extend_from_slice(&sample.to_le_bytes());
    }
    out
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn round_trips_through_the_canonical_header() {
        let wav = WavPcm16 {
            sample_rate: 44100,
            channels: 2,
            samples: vec![0, 1, -2, 32767, -32768, 5],
        };
        let bytes = wav.to_bytes();
        assert_eq!(bytes.len(), 44 + 12);
        assert_eq!(&bytes[0..4], b"RIFF");
        assert_eq!(u32::from_le_bytes(bytes[4..8].try_into().unwrap()), 36 + 12);
        assert_eq!(u32::from_le_bytes(bytes[24..28].try_into().unwrap()), 44100);
        assert_eq!(
            u32::from_le_bytes(bytes[28..32].try_into().unwrap()),
            44100 * 4
        );
        assert_eq!(WavPcm16::parse(&bytes).unwrap(), wav);
    }

    #[test]
    fn rejects_non_wav_and_non_pcm16() {
        assert_eq!(
            WavPcm16::parse(b"OggS not a wav at all"),
            Err(WavError::Unreadable)
        );
        let mut eight_bit = write_wav_pcm16(8000, 1, &[1, 2, 3]);
        eight_bit[34] = 8; // bits per sample
        assert_eq!(WavPcm16::parse(&eight_bit), Err(WavError::NotPcm16));
    }
}
