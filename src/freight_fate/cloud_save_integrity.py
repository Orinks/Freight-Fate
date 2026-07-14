"""Verify orinks.net-signed private cloud revisions before restore."""

from __future__ import annotations

import base64
import binascii
import json
import math
from collections.abc import Mapping
from decimal import Decimal

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from .models.profile import Profile

PUBLIC_KEYS = {
    "2026-07": base64.b64decode("RJ1PR6fVDk98eb3uMysfmvzfURO/wPkLX5O52OapNoY="),
}
SUPPORTED_VALIDATOR_VERSION = 1


class CloudSaveIntegrityError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _js_number(value: float) -> str:
    """Serialize a float exactly as JavaScript's JSON.stringify does.

    The server signs the canonical form it built with JSON.stringify, where
    numbers carry no int/float distinction: 6.0 prints as "6", tiny values
    stay decimal down to 1e-6, exponents are never zero-padded, and -0
    prints as "0". Python's repr disagrees on all four, so leaning on
    json.dumps here made every server signature unverifiable (the ".0" on
    whole floats alone broke every real profile).
    """
    if math.isnan(value) or math.isinf(value):
        raise ValueError("NaN and infinity cannot appear in a profile")
    if value == 0.0:
        return "0"
    sign = "-" if value < 0 else ""
    # repr() already yields the shortest round-trip digits, the same digits
    # ECMAScript's Number::toString picks; only the layout rules differ.
    digits, exponent = Decimal(repr(abs(value))).normalize().as_tuple()[1:]
    mantissa = "".join(map(str, digits))
    k = len(mantissa)
    n = exponent + k  # value == 0.mantissa * 10**n
    if k <= n <= 21:
        body = mantissa + "0" * (n - k)
    elif 0 < n <= 21:
        body = f"{mantissa[:n]}.{mantissa[n:]}"
    elif -6 < n <= 0:
        body = f"0.{'0' * -n}{mantissa}"
    else:
        tail = f".{mantissa[1:]}" if k > 1 else ""
        body = f"{mantissa[0]}{tail}e{'+' if n > 0 else '-'}{abs(n - 1)}"
    return sign + body


def _canonical_value(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        # json.dumps escaping of a lone string matches JSON.stringify plus
        # the server's non-ASCII escape pass byte for byte.
        return json.dumps(value, ensure_ascii=True)
    if isinstance(value, int):
        # The server parsed every number into a double; an int the double
        # cannot hold exactly would canonicalize differently there, so honest
        # profiles must stay inside the safe-integer range.
        if abs(value) > 2**53:
            raise ValueError("integer outside the JSON-safe range")
        return str(value)
    if isinstance(value, float):
        return _js_number(value)
    if isinstance(value, dict):
        parts = (
            f"{json.dumps(key, ensure_ascii=True)}:{_canonical_value(item)}"
            for key, item in sorted(value.items())
        )
        return "{" + ",".join(parts) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_canonical_value(item) for item in value) + "]"
    raise TypeError(f"unsupported profile value: {type(value).__name__}")


def canonical_profile(payload: dict) -> bytes:
    """The byte form both sides sign: key-sorted, ASCII-escaped JSON with
    numbers laid out by JavaScript's rules (see _js_number) — the server
    builds its copy with JSON.stringify, and the signature only verifies
    when the two agree on every byte."""
    try:
        return _canonical_value(payload).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CloudSaveIntegrityError("invalid_profile", "Unsupported profile data.") from exc


def verify_cloud_revision(
    payload: dict,
    metadata: Mapping[str, object],
    *,
    public_keys: Mapping[str, bytes] | None = None,
) -> Profile:
    """Return a loadable profile only when metadata and signature are valid."""
    key_id = metadata.get("keyId")
    validator_version = metadata.get("validatorVersion")
    signature_text = metadata.get("sig")
    signed_at = metadata.get("signedAt")
    if not all((key_id, validator_version, signature_text, signed_at)):
        raise CloudSaveIntegrityError("unverified", "The backup is not server-verified.")
    keys = PUBLIC_KEYS if public_keys is None else public_keys
    if not isinstance(key_id, str) or key_id not in keys:
        raise CloudSaveIntegrityError("update_required", "The backup uses a newer signing key.")
    if not isinstance(validator_version, int) or validator_version < 1:
        raise CloudSaveIntegrityError("unverified", "The validator version is invalid.")
    if validator_version > SUPPORTED_VALIDATOR_VERSION:
        raise CloudSaveIntegrityError("update_required", "The backup needs a newer game version.")
    if not isinstance(signature_text, str) or not isinstance(signed_at, str) or not signed_at:
        raise CloudSaveIntegrityError("unverified", "The backup signature metadata is incomplete.")
    try:
        signature = base64.b64decode(signature_text, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise CloudSaveIntegrityError(
            "integrity_failed", "The backup signature is unreadable."
        ) from exc
    if len(signature) != 64:
        raise CloudSaveIntegrityError("integrity_failed", "The backup signature is unreadable.")
    try:
        Ed25519PublicKey.from_public_bytes(keys[key_id]).verify(
            signature, canonical_profile(payload)
        )
    except InvalidSignature as exc:
        raise CloudSaveIntegrityError(
            "integrity_failed", "The backup signature is invalid."
        ) from exc
    try:
        profile = Profile.from_dict(payload)
    except Exception as exc:
        raise CloudSaveIntegrityError("invalid_profile", "The backup cannot be loaded.") from exc
    # Defense in depth behind the signature: a payload blessed by an older
    # validator (or a compromised one) still has to satisfy the invariants
    # every honest save obeys -- see profile_invariants and its doc.
    from .profile_invariants import check_profile_invariants, spoken_rejection

    violations = check_profile_invariants(profile)
    if violations:
        raise CloudSaveIntegrityError("invalid_profile", spoken_rejection(violations))
    return profile
