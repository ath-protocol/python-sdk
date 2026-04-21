"""Shared test fixtures."""

from __future__ import annotations

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


@pytest.fixture()
def ec_private_pem() -> str:
    """Generate a fresh EC P-256 private key in PEM format."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


GATEWAY = "https://gw.test"
AGENT_ID = "https://agent.test/.well-known/agent.json"
