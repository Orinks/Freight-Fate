//! California's lane closures, fetched only for the districts a route crosses.
//!
//! Caltrans publishes its Lane Closure System one district at a time with no
//! key, at `cwwp2.dot.ca.gov/data/d<N>/lcs/lcsStatusD<NN>.csv`; all twelve
//! answered 200 on 2026-09-24. The CSV is the size answer: District 7's JSON
//! twin was 13.6 MB and took 11 to 16 seconds to arrive that day, while the
//! CSV carries the same rows in 2.2 MB and arrived in 4.5 to 5.0 seconds,
//! inside the 8-second feed budget (`FETCH_TIMEOUT_S`). The other eleven
//! districts' CSVs ran 38 KB to 780 KB.
//!
//! A district is a set of whole counties ([`COUNTY_DISTRICTS`]), so the
//! lookup asks which counties lie within reach of the route's points, from
//! the Census county outlines in `ca_county_outlines.txt`
//! (`tools/build_ca_county_outlines.py` writes them).

use once_cell::sync::Lazy;

/// The registry key California's district feeds hang off.
pub const CALTRANS_STATE: &str = "california";

/// County to Caltrans district. Read: the `DISTRICT` field of Caltrans's own
/// `CHboundary/County_Boundaries` layer (caltrans-gis.dot.ca.gov, queried
/// 2026-09-24), which lists all 58 counties.
///
/// One addition, also read: Kern also gets District 9, which files eastern
/// Kern's closures itself. On 2026-09-24, 18 of the 274 Kern closures in the
/// twelve feeds came from District 9, on SR-58 and SR-202 around Tehachapi,
/// Keene and Boron, and District 9's page names Kern COG a local partner.
pub static COUNTY_DISTRICTS: &[(&str, &[u8])] = &[
    ("Del Norte", &[1]),
    ("Humboldt", &[1]),
    ("Lake", &[1]),
    ("Mendocino", &[1]),
    ("Lassen", &[2]),
    ("Modoc", &[2]),
    ("Plumas", &[2]),
    ("Shasta", &[2]),
    ("Siskiyou", &[2]),
    ("Tehama", &[2]),
    ("Trinity", &[2]),
    ("Butte", &[3]),
    ("Colusa", &[3]),
    ("El Dorado", &[3]),
    ("Glenn", &[3]),
    ("Nevada", &[3]),
    ("Placer", &[3]),
    ("Sacramento", &[3]),
    ("Sierra", &[3]),
    ("Sutter", &[3]),
    ("Yolo", &[3]),
    ("Yuba", &[3]),
    ("Alameda", &[4]),
    ("Contra Costa", &[4]),
    ("Marin", &[4]),
    ("Napa", &[4]),
    ("San Francisco", &[4]),
    ("San Mateo", &[4]),
    ("Santa Clara", &[4]),
    ("Solano", &[4]),
    ("Sonoma", &[4]),
    ("Monterey", &[5]),
    ("San Benito", &[5]),
    ("San Luis Obispo", &[5]),
    ("Santa Barbara", &[5]),
    ("Santa Cruz", &[5]),
    ("Fresno", &[6]),
    ("Kern", &[6, 9]),
    ("Kings", &[6]),
    ("Madera", &[6]),
    ("Tulare", &[6]),
    ("Los Angeles", &[7]),
    ("Ventura", &[7]),
    ("Riverside", &[8]),
    ("San Bernardino", &[8]),
    ("Inyo", &[9]),
    ("Mono", &[9]),
    ("Alpine", &[10]),
    ("Amador", &[10]),
    ("Calaveras", &[10]),
    ("Mariposa", &[10]),
    ("Merced", &[10]),
    ("San Joaquin", &[10]),
    ("Stanislaus", &[10]),
    ("Tuolumne", &[10]),
    ("Imperial", &[11]),
    ("San Diego", &[11]),
    ("Orange", &[12]),
];

/// How far the outlines may sit from the true county line. Derived:
/// `tools/build_ca_county_outlines.py --measure` finds the farthest a
/// 1:500,000 boundary vertex lies from the 1:20,000,000 outline the game
/// carries, 3.24 mi (the Sutter-Yolo line), rounded up.
pub const OUTLINE_TOLERANCE_MI: f64 = 3.25;

const MILES_PER_DEGREE: f64 = 69.17;

struct County {
    districts: &'static [u8],
    /// Rings of (lon, lat), read with the even-odd rule.
    rings: Vec<Vec<(f64, f64)>>,
    /// (west, south, east, north)
    bounds: (f64, f64, f64, f64),
}

static COUNTIES: Lazy<Vec<County>> =
    Lazy::new(|| parse_outlines(include_str!("ca_county_outlines.txt")));

fn districts_of_county(name: &str) -> Option<&'static [u8]> {
    COUNTY_DISTRICTS
        .iter()
        .find(|(county, _)| *county == name)
        .map(|(_, districts)| *districts)
}

fn parse_outlines(text: &str) -> Vec<County> {
    let mut counties: Vec<(&str, County)> = Vec::new();
    for line in text.lines() {
        if line.starts_with('#') || line.trim().is_empty() {
            continue;
        }
        let Some((name, pairs)) = line.split_once('\t') else {
            continue;
        };
        let Some(districts) = districts_of_county(name) else {
            log::warn!("county outline {name} has no Caltrans district");
            continue;
        };
        let ring: Vec<(f64, f64)> = pairs
            .split_whitespace()
            .filter_map(|pair| {
                let (lon, lat) = pair.split_once(',')?;
                Some((lon.parse().ok()?, lat.parse().ok()?))
            })
            .collect();
        let index = match counties.iter().position(|(n, _)| *n == name) {
            Some(index) => index,
            None => {
                counties.push((
                    name,
                    County {
                        districts,
                        rings: Vec::new(),
                        bounds: (f64::MAX, f64::MAX, f64::MIN, f64::MIN),
                    },
                ));
                counties.len() - 1
            }
        };
        let county = &mut counties[index].1;
        for &(lon, lat) in &ring {
            let (w, s, e, n) = county.bounds;
            county.bounds = (w.min(lon), s.min(lat), e.max(lon), n.max(lat));
        }
        county.rings.push(ring);
    }
    counties.into_iter().map(|(_, county)| county).collect()
}

impl County {
    /// Whether (lat, lon) lies inside the county or within `reach_mi` of it.
    fn within(&self, lat: f64, lon: f64, reach_mi: f64) -> bool {
        let dlat = reach_mi / MILES_PER_DEGREE;
        let dlon = reach_mi / (MILES_PER_DEGREE * lat.to_radians().cos().max(0.1));
        let (w, s, e, n) = self.bounds;
        if lon < w - dlon || lon > e + dlon || lat < s - dlat || lat > n + dlat {
            return false;
        }
        self.contains(lat, lon) || self.edge_miles(lat, lon) <= reach_mi
    }

    fn contains(&self, lat: f64, lon: f64) -> bool {
        let mut inside = false;
        for ring in &self.rings {
            for (a, b) in ring.iter().zip(ring.iter().cycle().skip(1)) {
                if (a.1 > lat) != (b.1 > lat) && lon < a.0 + (lat - a.1) * (b.0 - a.0) / (b.1 - a.1)
                {
                    inside = !inside;
                }
            }
        }
        inside
    }

    /// Distance to the nearest outline edge, flat-earth about the point
    /// (derived; well inside the tolerance at a few miles' reach).
    fn edge_miles(&self, lat: f64, lon: f64) -> f64 {
        let kx = lat.to_radians().cos() * MILES_PER_DEGREE;
        let local = |(x, y): (f64, f64)| ((x - lon) * kx, (y - lat) * MILES_PER_DEGREE);
        let mut best = f64::MAX;
        for ring in &self.rings {
            for pair in ring.windows(2) {
                let (qx, qy) = local(pair[0]);
                let (rx, ry) = local(pair[1]);
                let (dx, dy) = (rx - qx, ry - qy);
                let length = dx * dx + dy * dy;
                let t = if length == 0.0 {
                    0.0
                } else {
                    (-(qx * dx + qy * dy) / length).clamp(0.0, 1.0)
                };
                best = best.min((qx + t * dx).hypot(qy + t * dy));
            }
        }
        best
    }
}

/// The Caltrans districts whose counties lie within `radius_mi` of any
/// route point (`(lat, lon)`), widened by [`OUTLINE_TOLERANCE_MI`] so an
/// outline's generalisation never drops a district the route touches.
/// Sorted, no repeats.
pub fn districts_near_route(points: &[(f64, f64)], radius_mi: f64) -> Vec<u8> {
    let reach = radius_mi.max(0.0) + OUTLINE_TOLERANCE_MI;
    let mut found: Vec<u8> = Vec::new();
    for county in COUNTIES.iter() {
        if county.districts.iter().all(|d| found.contains(d)) {
            continue;
        }
        if points
            .iter()
            .any(|&(lat, lon)| county.within(lat, lon, reach))
        {
            found.extend_from_slice(county.districts);
        }
    }
    found.sort_unstable();
    found.dedup();
    found
}

/// The provider's feed key for one district (`california/d7`): its own
/// cache entry and retry cooldown.
pub fn feed_key(district: u8) -> String {
    format!("{CALTRANS_STATE}/d{district}")
}

/// The district a feed key names, if it names one.
pub fn district_of_feed_key(key: &str) -> Option<u8> {
    key.strip_prefix(CALTRANS_STATE)?
        .strip_prefix("/d")?
        .parse()
        .ok()
        .filter(|d| (1..=12).contains(d))
}

/// A district's lane-closure CSV under the registry's base URL.
pub fn lcs_csv_url(base_url: &str, district: u8) -> String {
    format!("{base_url}/d{district}/lcs/lcsStatusD{district:02}.csv")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn every_county_has_one_outline_and_a_district() {
        assert_eq!(COUNTY_DISTRICTS.len(), 58);
        assert_eq!(COUNTIES.len(), 58);
        for district in 1..=12u8 {
            assert!(
                COUNTY_DISTRICTS.iter().any(|(_, d)| d.contains(&district)),
                "district {district} has no county"
            );
        }
    }

    #[test]
    fn a_point_lands_in_its_own_county() {
        let county_at = |lat: f64, lon: f64| -> Vec<&'static [u8]> {
            COUNTIES
                .iter()
                .filter(|c| c.contains(lat, lon))
                .map(|c| c.districts)
                .collect()
        };
        // Downtown Los Angeles, Fresno, Sacramento, San Diego.
        assert_eq!(county_at(34.0522, -118.2437), vec![&[7u8][..]]);
        assert_eq!(county_at(36.7378, -119.7871), vec![&[6u8][..]]);
        assert_eq!(county_at(38.5816, -121.4944), vec![&[3u8][..]]);
        assert_eq!(county_at(32.7157, -117.1611), vec![&[11u8][..]]);
    }

    #[test]
    fn a_route_in_los_angeles_fetches_district_7_only() {
        // I-5 and US-101 through central Los Angeles, Glendale to downtown
        // to Hollywood: 17 miles or more from any other district's county.
        let points = [
            (34.1425, -118.2551),
            (34.0522, -118.2437),
            (34.0928, -118.3287),
        ];
        assert_eq!(districts_near_route(&points, 3.0), vec![7]);
    }

    #[test]
    fn a_route_over_the_grapevine_fetches_every_district_it_touches() {
        // Downtown LA to Bakersfield on I-5: Los Angeles County, then Kern,
        // whose closures District 6 and District 9 both file.
        let points = [(34.0522, -118.2437), (34.80, -118.87), (35.3733, -119.0187)];
        assert_eq!(districts_near_route(&points, 3.0), vec![6, 7, 9]);
        assert!(districts_near_route(&[], 3.0).is_empty());
    }

    /// Answers every Caltrans URL with the parser fixture, recording each.
    struct Recorder(std::sync::Mutex<Vec<String>>);

    impl crate::sim::real_traffic::HttpTransport for Recorder {
        fn get(
            &self,
            url: &str,
            _: &[(&str, &str)],
            _: f64,
        ) -> Result<Vec<u8>, crate::sim::real_traffic::TransportError> {
            self.0.lock().unwrap().push(url.to_string());
            Ok(include_bytes!("../real_traffic_parsers/fixtures/lcs_sample.csv").to_vec())
        }

        fn post(
            &self,
            url: &str,
            _: &[u8],
            _: &[(&str, &str)],
            _: f64,
        ) -> Result<Vec<u8>, crate::sim::real_traffic::TransportError> {
            Err(crate::sim::real_traffic::TransportError::new(url))
        }
    }

    #[test]
    fn the_provider_fetches_only_the_route_s_districts() {
        use crate::sim::real_traffic::RealTrafficProvider;
        use std::sync::Arc;

        let transport = Arc::new(Recorder(Default::default()));
        let provider = RealTrafficProvider::new(transport.clone())
            .with_threaded(false)
            .with_clock(Arc::new(|| 1_790_272_983.0));
        // I-5 north out of Los Angeles: downtown, Pacoima, Castaic.
        let la = [
            (34.0522, -118.2437),
            (34.2626, -118.4409),
            (34.4600, -118.6100),
        ];
        // The first ask starts the fetch and answers from the (empty) cache,
        // as every state does; the second is served from what arrived.
        provider.get_construction_near_route("California", &la, Some("I-5"), 3.0);
        let events = provider.get_construction_near_route("California", &la, Some("I-5"), 3.0);
        assert_eq!(
            *transport.0.lock().unwrap(),
            vec!["https://cwwp2.dot.ca.gov/data/d7/lcs/lcsStatusD07.csv"]
        );
        // The Castaic lane closure on I-5; the fixture's other rows are
        // other roads, far off, or not in effect.
        let ids: Vec<&str> = events.iter().map(|e| e.id.as_str()).collect();
        assert_eq!(ids, vec!["C5DA-0077-2026-09-24-06:01:00"]);

        // On over the Grapevine: District 7 is cached, so only 6 and 9 go
        // out. The whole state never fetches, incidents or construction.
        let grapevine = [(34.46, -118.61), (34.80, -118.87), (35.3733, -119.0187)];
        provider.get_construction_near_route("california", &grapevine, Some("I-5"), 3.0);
        provider.request("california");
        provider.fetch_construction("california");
        let calls = transport.0.lock().unwrap().clone();
        assert_eq!(calls.len(), 3, "{calls:?}");
        assert!(calls[1].ends_with("/d6/lcs/lcsStatusD06.csv"), "{calls:?}");
        assert!(calls[2].ends_with("/d9/lcs/lcsStatusD09.csv"), "{calls:?}");
    }

    #[test]
    fn feed_keys_round_trip() {
        assert_eq!(feed_key(7), "california/d7");
        assert_eq!(district_of_feed_key("california/d7"), Some(7));
        assert_eq!(district_of_feed_key("california/d12"), Some(12));
        assert_eq!(district_of_feed_key("california"), None);
        assert_eq!(district_of_feed_key("california/d13"), None);
        assert_eq!(district_of_feed_key("oregon/d7"), None);
        assert_eq!(
            lcs_csv_url("https://cwwp2.dot.ca.gov/data", 7),
            "https://cwwp2.dot.ca.gov/data/d7/lcs/lcsStatusD07.csv"
        );
    }
}
