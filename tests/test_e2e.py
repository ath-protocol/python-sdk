"""E2E tests against a live ATH gateway (no mocks).

Requires the ATH gateway running at http://localhost:3000 in mock mode.
Start it with: cd /workspace && pnpm --filter ath-gateway dev

These tests exercise the full ATH protocol flow as a real user would:
  discover → register → authorize → simulate consent → token → proxy → revoke

Persona: power-user (pushes through the full flow, checks edge cases).
"""

from __future__ import annotations

import os
import uuid
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from ath import AsyncATHGatewayClient, ATHError, ATHGatewayClient

GATEWAY_URL = os.environ.get("ATH_GATEWAY_URL", "http://localhost:3000")


def _unique_agent_id() -> str:
    """Each test gets a unique agent to avoid in-memory state conflicts."""
    return f"https://e2e-{uuid.uuid4().hex[:8]}.example.com/.well-known/agent.json"


def _gateway_reachable() -> bool:
    try:
        r = httpx.get(f"{GATEWAY_URL}/.well-known/ath.json", timeout=3)
        return r.is_success
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gateway_reachable(),
    reason=f"ATH gateway not reachable at {GATEWAY_URL}",
)


@pytest.fixture()
def ec_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def _simulate_consent(authorization_url: str) -> None:
    """Simulate user clicking 'Approve' on the mock consent page.

    In mock mode, the authorization_url is:
      /ui/mock-consent?provider=...&scopes=...&callback=...&state=...

    We POST to /ui/mock-consent/approve with callback + state, which redirects
    to /ath/callback?code=...&state=..., completing the session server-side.
    """
    parsed = urlparse(authorization_url)
    params = parse_qs(parsed.query)
    callback = params.get("callback", [""])[0]
    state = params.get("state", [""])[0]

    with httpx.Client(follow_redirects=True) as http:
        r = http.post(
            f"{GATEWAY_URL}/ui/mock-consent/approve",
            data={"callback": callback, "state": state},
        )
        assert r.status_code == 200, f"Consent simulation failed: {r.status_code}"


# ===== E2E-1: Full happy path ==============================================


class TestE2EFullFlow:
    """E2E-1: discover → register → authorize → consent → token → revoke."""

    def test_full_protocol_flow(self, ec_pem: str) -> None:
        agent_id = _unique_agent_id()
        # ---- Step 1: Discover ----
        with ATHGatewayClient(GATEWAY_URL, agent_id, ec_pem) as client:
            doc = client.discover()
            assert doc.ath_version == "0.1"
            assert doc.gateway_id == GATEWAY_URL
            assert len(doc.supported_providers) > 0
            provider_ids = [p.provider_id for p in doc.supported_providers]
            assert "github" in provider_ids

            # ---- Step 2: Register ----
            reg = client.register(
                developer={"name": "E2E Test", "id": "dev-e2e-001"},
                providers=[{"provider_id": "github", "scopes": ["repo", "read:user"]}],
                purpose="E2E testing",
            )
            assert reg.client_id
            assert reg.client_secret
            assert reg.agent_status.value == "approved"
            assert len(reg.approved_providers) > 0
            github_approval = next(p for p in reg.approved_providers if p.provider_id == "github")
            assert "repo" in github_approval.approved_scopes

            # ---- Step 3: Authorize ----
            auth = client.authorize("github", ["repo", "read:user"])
            assert auth.authorization_url
            assert auth.ath_session_id

            # ---- Step 4: Simulate user consent ----
            _simulate_consent(auth.authorization_url)

            # ---- Step 5: Token exchange ----
            tok = client.exchange_token("unused_code", auth.ath_session_id)
            assert tok.access_token
            assert tok.token_type == "Bearer"
            assert tok.expires_in > 0
            assert tok.provider_id == "github"
            assert tok.agent_id == agent_id
            assert len(tok.scope_intersection.effective) > 0
            assert "repo" in tok.scope_intersection.effective

            # ---- Step 6: Revoke ----
            client.revoke()
            assert client.access_token is None


# ===== E2E-2: Error paths ===================================================


class TestE2EErrorPaths:
    """E2E-2: error conditions with real gateway."""

    def test_authorize_before_register(self, ec_pem: str) -> None:
        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            with pytest.raises(ATHError) as exc_info:
                client.authorize("github", ["repo"])
            assert exc_info.value.code == "NOT_REGISTERED"

    def test_token_exchange_before_register(self, ec_pem: str) -> None:
        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            with pytest.raises(ATHError) as exc_info:
                client.exchange_token("code", "session")
            assert exc_info.value.code == "NOT_REGISTERED"

    def test_proxy_without_token(self, ec_pem: str) -> None:
        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            with pytest.raises(ATHError) as exc_info:
                client.proxy("github", "GET", "/user")
            assert exc_info.value.code == "NO_TOKEN"

    def test_token_exchange_with_bad_session(self, ec_pem: str) -> None:
        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            client.register(
                developer={"name": "E2E Err", "id": "dev-e2e-err"},
                providers=[{"provider_id": "github", "scopes": ["repo"]}],
                purpose="error test",
            )
            with pytest.raises(ATHError) as exc_info:
                client.exchange_token("code", "nonexistent_session")
            assert exc_info.value.status is not None
            assert exc_info.value.status >= 400


# ===== E2E-3: Credential persistence ========================================


class TestE2ECredentials:
    """E2E-3: save/load credentials and continue flow."""

    def test_save_load_and_authorize(self, ec_pem: str, tmp_path: pytest.TempPathFactory) -> None:
        agent_id = _unique_agent_id()
        cred_file = tmp_path / "creds.json"  # type: ignore[operator]

        # Register and save
        with ATHGatewayClient(GATEWAY_URL, agent_id, ec_pem) as client:
            client.register(
                developer={"name": "E2E Cred", "id": "dev-e2e-cred"},
                providers=[{"provider_id": "github", "scopes": ["repo"]}],
                purpose="credential test",
            )
            client.save_credentials(str(cred_file))

        # Load and authorize on a new client (same agent_id — credentials saved)
        with ATHGatewayClient(GATEWAY_URL, agent_id, ec_pem) as client2:
            client2.load_credentials(str(cred_file))
            auth = client2.authorize("github", ["repo"])
            assert auth.authorization_url
            assert auth.ath_session_id


# ===== E2E-4: Async client ==================================================


class TestE2EAsync:
    """E2E-4: full flow using AsyncATHGatewayClient."""

    @pytest.mark.asyncio
    async def test_async_full_flow(self, ec_pem: str) -> None:
        async with AsyncATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            # Discover
            doc = await client.discover()
            assert doc.ath_version == "0.1"
            assert len(doc.supported_providers) > 0

            # Register
            reg = await client.register(
                developer={"name": "E2E Async", "id": "dev-e2e-async"},
                providers=[{"provider_id": "github", "scopes": ["repo"]}],
                purpose="async E2E test",
            )
            assert reg.agent_status.value == "approved"

            # Authorize + consent
            auth = await client.authorize("github", ["repo"])
            _simulate_consent(auth.authorization_url)

            # Token
            tok = await client.exchange_token("unused", auth.ath_session_id)
            assert tok.access_token
            assert "repo" in tok.scope_intersection.effective

            # Revoke
            await client.revoke()
            assert client.access_token is None


# ===== E2E-5: Typed model inputs ============================================


class TestE2ETypedModels:
    """E2E-5: register with Pydantic models instead of dicts."""

    def test_register_with_pydantic_models(self, ec_pem: str) -> None:
        from ath.types import DeveloperInfo, ProviderScopeRequest

        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            reg = client.register(
                developer=DeveloperInfo(name="E2E Typed", id="dev-typed"),
                providers=[ProviderScopeRequest(provider_id="github", scopes=["repo"])],
                purpose="typed model test",
            )
            assert reg.agent_status.value == "approved"
