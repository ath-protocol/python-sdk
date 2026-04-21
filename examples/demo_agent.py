#!/usr/bin/env python3
"""ATH Demo Agent — exercises the full gateway-mode protocol flow.

Usage:
    ATH_GATEWAY_URL=http://localhost:3000 python examples/demo_agent.py
"""

from __future__ import annotations

import os
import sys
from urllib.parse import parse_qs, urlparse

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from ath import ATHGatewayClient

GATEWAY_URL = os.environ.get("ATH_GATEWAY_URL", "http://localhost:3000")


def generate_ec_key() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def main() -> None:
    print("=== ATH Protocol Demo (Python) ===\n")

    pem = generate_ec_key()
    agent_id = "https://demo-agent.example.com/.well-known/agent.json"

    with ATHGatewayClient(GATEWAY_URL, agent_id, pem, key_id="demo-key-1") as client:
        print("1. Discovering gateway...")
        try:
            doc = client.discover()
        except Exception as e:
            print(f"   Failed: {e}")
            sys.exit(1)
        print(f"   Gateway: {doc.gateway_id}")
        print(f"   ATH version: {doc.ath_version}")
        providers = ", ".join(p.display_name for p in doc.supported_providers)
        print(f"   Providers: {providers}\n")

        print("2. Registering agent...")
        reg = client.register(
            developer={"name": "Demo Developer", "id": "dev-demo-001"},
            providers=[{"provider_id": "github", "scopes": ["repo", "read:user"]}],
            purpose="ATH protocol demonstration",
        )
        print(f"   Client ID: {reg.client_id}")
        print(f"   Status: {reg.agent_status.value}")
        for p in reg.approved_providers:
            print(f"   {p.provider_id}: approved={p.approved_scopes} denied={p.denied_scopes}")
        print()

        print("3. Starting authorization flow...")
        auth = client.authorize("github", ["repo", "read:user"])
        print(f"   Session: {auth.ath_session_id}")
        print(f"   User should visit: {auth.authorization_url}\n")

        print("4. Simulating user consent (demo mock mode)...")
        consent_url = urlparse(auth.authorization_url)
        params = parse_qs(consent_url.query)
        callback = params.get("callback", [""])[0]
        state = params.get("state", [""])[0]
        with httpx.Client() as http:
            r = http.post(
                f"{GATEWAY_URL}/ui/mock-consent/approve",
                data={"callback": callback, "state": state},
                follow_redirects=True,
            )
        print(f"   Consent response: {r.status_code}\n")

        print("5. Exchanging token...")
        tok = client.exchange_token("mock_code", auth.ath_session_id)
        print(f"   Access token: {tok.access_token[:20]}...")
        print(f"   Effective scopes: {tok.effective_scopes}")
        si = tok.scope_intersection
        print(
            f"   Scope intersection: approved={si.agent_approved}"
            f" consented={si.user_consented} effective={si.effective}\n"
        )

        print("6. Making proxied API call...")
        try:
            data = client.proxy("github", "GET", "/user")
            print(f"   Response: {data}\n")
        except Exception as e:
            print(f"   Proxy call failed (expected in mock mode): {e}\n")

        print("7. Revoking token...")
        client.revoke()
        print("   Token revoked.\n")

    print("=== Demo complete ===")


if __name__ == "__main__":
    main()
