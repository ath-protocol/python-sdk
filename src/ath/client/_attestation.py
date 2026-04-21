"""JWT agent attestation helper (ES256) using joserfc (RFC 7515/7519)."""

from __future__ import annotations

import time
from typing import Any

from joserfc import jwt
from joserfc.jwk import ECKey


def sign_attestation(
    *,
    agent_id: str,
    private_key: str | bytes,
    key_id: str,
    audience: str,
) -> str:
    """Build and sign an agent attestation JWT per spec §3.3.

    Uses ES256 (ECDSA with P-256 and SHA-256) as required by the ATH spec.
    The private_key must be a PEM-encoded EC private key (P-256/secp256r1).
    """
    now = int(time.time())
    header: dict[str, Any] = {"alg": "ES256", "kid": key_id}
    claims: dict[str, Any] = {
        "capabilities": [],
        "iss": agent_id,
        "sub": agent_id,
        "aud": audience,
        "iat": now,
        "exp": now + 3600,
    }
    key = ECKey.import_key(private_key)
    return jwt.encode(header, claims, key)
