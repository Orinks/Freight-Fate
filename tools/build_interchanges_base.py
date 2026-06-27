# ruff: noqa: F401,I001
import argparse
import hashlib
import json
import math
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
WORLD_PATH = ROOT / "src" / "freight_fate" / "data" / "world.json"
CACHE_DIR = ROOT / ".route-cache" / "interchanges"
OVERPASS_MIRRORS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)
OSRM_ROUTE_URL = "https://router.project-osrm.org/route/v1/driving/{coords}"
USER_AGENT = "FreightFate interchange curation (https://github.com/Orinks/Freight-Fate)"
ACCESSED_DATE = "2026-06-23"
EARTH_RADIUS_MI = 3958.7613

SAMPLE_SPACING_MI = 10.0   # how often to drop an Overpass probe along the leg
PROBE_RADIUS_M = 9_000     # search radius per probe
RAMP_NEAR_M = 350.0        # a ramp this close to a junction belongs to it
LOCAL_CORRIDOR_M = 200.0   # local PBF features must snap this close to a leg
LOCAL_PBF_PREFILTER_PAD_M = PROBE_RADIUS_M
MIN_EXIT_SPACING_MI = 2.0  # collapse exits closer than this (keep the richer)
MAX_DESTINATIONS = 3       # cap control cities per exit for speech brevity
LOCAL_INDEX_CACHE_VERSION = 1
LOCAL_INDEX_PROGRESS_INTERVAL_SEC = 60.0

__all__ = [name for name in globals() if not name.startswith("__")]
