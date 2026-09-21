//! The synthesizer's own RNG. Deliberately not `pyrandom`: a piece must never
//! change once shipped, so this is a fixed SplitMix64 with no Python mirror to
//! stay in step with.

use super::style::StyleId;

#[derive(Debug, Clone)]
pub struct Rng(u64);

impl Rng {
    pub fn new(seed: u64) -> Self {
        Self(seed)
    }

    pub fn next_u64(&mut self) -> u64 {
        self.0 = self.0.wrapping_add(0x9E37_79B9_7F4A_7C15);
        let mut z = self.0;
        z = (z ^ (z >> 30)).wrapping_mul(0xBF58_476D_1CE4_E5B9);
        z = (z ^ (z >> 27)).wrapping_mul(0x94D0_49BB_1331_11EB);
        z ^ (z >> 31)
    }

    /// Uniform in [0, 1).
    pub fn unit(&mut self) -> f64 {
        (self.next_u64() >> 11) as f64 / (1u64 << 53) as f64
    }

    /// Uniform in 0..n; 0 when n is 0.
    pub fn below(&mut self, n: usize) -> usize {
        if n == 0 {
            return 0;
        }
        (self.next_u64() % n as u64) as usize
    }

    pub fn chance(&mut self, p: f64) -> bool {
        self.unit() < p
    }
}

/// The seed one piece is composed from: which place, which music seed, which
/// track in that place's rotation.
pub fn piece_seed(style: StyleId, music_seed: i64, index: usize) -> u64 {
    let mut rng = Rng::new(crate::music::crc32(style.id().as_bytes()) as u64);
    let mixed =
        rng.next_u64() ^ (music_seed as u64).rotate_left(21) ^ (index as u64).rotate_left(42);
    Rng::new(mixed).next_u64()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn splitmix_sequence_is_pinned() {
        let mut rng = Rng::new(1);
        let got: Vec<u64> = (0..3).map(|_| rng.next_u64()).collect();
        assert_eq!(
            got,
            vec![
                0x910A_2DEC_8902_5CC1,
                0xBEEB_8DA1_658E_EC67,
                0xF893_A2EE_FB32_555E
            ]
        );
    }

    #[test]
    fn below_stays_in_range_and_zero_is_safe() {
        let mut rng = Rng::new(7);
        assert!((0..1000).all(|_| rng.below(5) < 5));
        assert_eq!(rng.below(0), 0);
    }

    #[test]
    fn piece_seed_changes_with_each_input() {
        let a = piece_seed(StyleId::DayDrive, 48213, 0);
        assert_ne!(a, piece_seed(StyleId::DayDrive, 48214, 0));
        assert_ne!(a, piece_seed(StyleId::DayDrive, 48213, 1));
        assert_ne!(a, piece_seed(StyleId::NightDrive, 48213, 0));
        assert_eq!(a, piece_seed(StyleId::DayDrive, 48213, 0));
    }
}
