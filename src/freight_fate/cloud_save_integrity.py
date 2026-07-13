"""Verify orinks.net-signed private cloud revisions before restore."""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Mapping

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


def canonical_profile(payload: dict) -> bytes:
    try:
        return json.dumps(
            payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
        ).encode("utf-8")
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
        return Profile.from_dict(payload)
    except Exception as exc:
        raise CloudSaveIntegrityError("invalid_profile", "The backup cannot be loaded.") from exc
