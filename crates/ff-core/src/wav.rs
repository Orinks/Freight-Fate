//! A 16-bit PCM WAV container around interleaved samples -- what the
//! runtime-generated sounds (siren, earcons, synthesized music) publish.

pub fn pcm16_wav(samples: &[i16], channels: u16, rate: u32) -> Vec<u8> {
    let mut out = pcm16_header(samples.len(), channels, rate);
    for s in samples {
        out.extend_from_slice(&s.to_le_bytes());
    }
    out
}

/// The 44-byte header for `sample_count` interleaved samples, in a buffer
/// with room for them, so a caller can append samples as it makes them.
pub fn pcm16_header(sample_count: usize, channels: u16, rate: u32) -> Vec<u8> {
    let data_len = (sample_count * 2) as u32;
    let mut out = Vec::with_capacity(44 + data_len as usize);
    out.extend_from_slice(b"RIFF");
    out.extend_from_slice(&(36 + data_len).to_le_bytes());
    out.extend_from_slice(b"WAVEfmt ");
    out.extend_from_slice(&16u32.to_le_bytes());
    out.extend_from_slice(&1u16.to_le_bytes());
    out.extend_from_slice(&channels.to_le_bytes());
    out.extend_from_slice(&rate.to_le_bytes());
    out.extend_from_slice(&(rate * channels as u32 * 2).to_le_bytes());
    out.extend_from_slice(&(channels * 2).to_le_bytes());
    out.extend_from_slice(&16u16.to_le_bytes());
    out.extend_from_slice(b"data");
    out.extend_from_slice(&data_len.to_le_bytes());
    out
}

#[cfg(test)]
mod tests {
    #[test]
    fn header_describes_the_samples() {
        let wav = super::pcm16_wav(&[0, 1, 2, 3], 2, 22_050);
        assert_eq!(&wav[0..4], b"RIFF");
        assert_eq!(u32::from_le_bytes(wav[40..44].try_into().unwrap()), 8);
        assert_eq!(wav.len(), 52);
    }
}
