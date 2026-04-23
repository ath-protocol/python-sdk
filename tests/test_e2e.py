"""E2E tests: real HTTP against a live ATH gateway (no httpx.MockTransport).

Only the **OAuth2 IdP** is mocked (minimal authorize + token + PKCE S256).
The **gateway** and **upstream API** are real Node HTTP servers driven by
``@ath-protocol/server`` (same stack as the TypeScript SDK E2E tests).

Start the stack (or use ``ATH_E2E_AUTO_STACK=1`` — see ``tests/conftest.py``)::

    cd /workspace && pnpm -C typescript-sdk install && pnpm -C typescript-sdk run build
    node scripts/e2e_gateway_stack.mjs &

Then::

    ATH_GATEWAY_URL=http://127.0.0.1:18101 python3 -m pytest tests/test_e2e.py -v

Or one shot::

    make e2e
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

DEFAULT_STACK_GATEWAY = "http://127.0.0.1:18101"
GATEWAY_URL = os.environ.get("ATH_GATEWAY_URL", DEFAULT_STACK_GATEWAY)


def _unique_agent_id() -> str:
    return f"https://e2e-{uuid.uuid4().hex[:8]}.example.com/.well-known/agent.json"


def _gateway_reachable() -> bool:
    try:
        r = httpx.get(f"{GATEWAY_URL}/health", timeout=3)
        return r.is_success
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _gateway_reachable(),
    reason=(
        f"ATH gateway not reachable at {GATEWAY_URL}. "
        "Run: pnpm -C typescript-sdk install && pnpm -C typescript-sdk run build && "
        "node scripts/e2e_gateway_stack.mjs"
    ),
)


@pytest.fixture()
def ec_pem() -> str:
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


def _complete_oauth_via_mock_idp(authorization_url: str) -> None:
    """Drive the real OAuth redirect chain; mock IdP auto-approves when auto_approve=true.

    The gateway consumes the OAuth ``code`` server-side during ``/ath/callback`` and
    marks the ATH session complete. The final redirect to ``user_redirect_uri`` uses
    ``session_id=…&success=true`` (no ``code`` in that URL). ``exchange_token`` still
    requires a ``code`` field in the JSON body; the handler resolves the session from
    ``ath_session_id`` once OAuth is complete, so a placeholder string is sufficient.
    """
    u = urlparse(authorization_url)
    if not u.query:
        raise AssertionError("authorization_url has no query string")

    idp = urlparse(authorization_url)
    idp_q = parse_qs(idp.query)
    if not idp_q.get("redirect_uri", [""])[0]:
        raise AssertionError("authorization_url missing redirect_uri")

    q = parse_qs(idp.query)
    flat = {k: v[0] for k, v in q.items() if v}
    flat["auto_approve"] = "true"
    approve_url = f"{idp.scheme}://{idp.netloc}{idp.path}?{httpx.QueryParams(flat)}"

    with httpx.Client(follow_redirects=False, timeout=30) as http:
        r1 = http.get(approve_url)
        assert r1.status_code == 302, f"IdP expected 302, got {r1.status_code}: {r1.text}"
        loc1 = r1.headers.get("location")
        assert loc1, "IdP redirect missing Location"

        r2 = http.get(loc1)
        assert r2.status_code == 302, f"Callback chain expected 302, got {r2.status_code}: {r2.text}"
        loc2 = r2.headers.get("location")
        assert loc2, "Callback redirect missing Location"

        final = urlparse(loc2)
        fq = parse_qs(final.query)
        if fq.get("error"):
            raise AssertionError(f"OAuth error in callback redirect: {fq}")
        assert fq.get("success") == ["true"] or "session_id" in fq, (
            f"Expected completed OAuth redirect with session_id/success: {loc2}"
        )


# ===== E2E-1: Full happy path ==============================================


class TestE2EFullFlow:
    def test_full_protocol_flow(self, ec_pem: str) -> None:
        agent_id = _unique_agent_id()
        with ATHGatewayClient(GATEWAY_URL, agent_id, ec_pem) as client:
            doc = client.discover()
            assert doc.ath_version == "0.1"
            assert doc.gateway_id == GATEWAY_URL
            assert len(doc.supported_providers) > 0
            provider_ids = [p.provider_id for p in doc.supported_providers]
            assert "github" in provider_ids

            reg = client.register(
                developer={"name": "E2E Test", "id": "dev-e2e-001"},
                providers=[{"provider_id": "github", "scopes": ["repo", "read:user"]}],
                purpose="E2E testing",
            )
            assert reg.client_id
            assert reg.client_secret
            assert reg.agent_status.value == "approved"

            auth = client.authorize("github", ["repo", "read:user"])
            assert auth.authorization_url
            assert "code_challenge=" in auth.authorization_url
            assert auth.ath_session_id

            _complete_oauth_via_mock_idp(auth.authorization_url)

            tok = client.exchange_token("oauth-completed", auth.ath_session_id)
            assert tok.access_token
            assert tok.token_type == "Bearer"
            assert tok.expires_in > 0
            assert tok.provider_id == "github"
            assert tok.agent_id == agent_id
            assert "repo" in tok.scope_intersection.effective

            user = client.proxy("github", "GET", "/userinfo")
            assert isinstance(user, dict)
            assert user.get("login") == "test-user"

            client.revoke()
            assert client.access_token is None


# ===== E2E-2: Error paths ===================================================


class TestE2EErrorPaths:
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
                client.proxy("github", "GET", "/userinfo")
            assert exc_info.value.code == "NO_TOKEN"

    def test_token_exchange_with_bad_session(self, ec_pem: str) -> None:
        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            client.register(
                developer={"name": "E2E Err", "id": "dev-e2e-err"},
                providers=[{"provider_id": "github", "scopes": ["repo"]}],
                purpose="error test",
            )
            with pytest.raises(ATHError) as exc_info:
                client.exchange_token("dummy-code", "nonexistent_session")
            assert exc_info.value.status is not None
            assert exc_info.value.status >= 400


# ===== E2E-3: Credential persistence ========================================


class TestE2ECredentials:
    def test_save_load_and_authorize(self, ec_pem: str, tmp_path: pytest.TempPath) -> None:
        agent_id = _unique_agent_id()
        cred_file = tmp_path / "creds.json"

        with ATHGatewayClient(GATEWAY_URL, agent_id, ec_pem) as client:
            client.register(
                developer={"name": "E2E Cred", "id": "dev-e2e-cred"},
                providers=[{"provider_id": "github", "scopes": ["repo"]}],
                purpose="credential test",
            )
            client.save_credentials(str(cred_file))

        with ATHGatewayClient(GATEWAY_URL, agent_id, ec_pem) as client2:
            client2.load_credentials(str(cred_file))
            auth = client2.authorize("github", ["repo"])
            assert auth.authorization_url
            assert auth.ath_session_id


# ===== E2E-4: Async client ==================================================


class TestE2EAsync:
    @pytest.mark.asyncio
    async def test_async_full_flow(self, ec_pem: str) -> None:
        async with AsyncATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            doc = await client.discover()
            assert doc.ath_version == "0.1"
            assert len(doc.supported_providers) > 0

            reg = await client.register(
                developer={"name": "E2E Async", "id": "dev-e2e-async"},
                providers=[{"provider_id": "github", "scopes": ["repo"]}],
                purpose="async E2E test",
            )
            assert reg.agent_status.value == "approved"

            auth = await client.authorize("github", ["repo"])
            _complete_oauth_via_mock_idp(auth.authorization_url)

            tok = await client.exchange_token("oauth-completed", auth.ath_session_id)
            assert tok.access_token
            assert "repo" in tok.scope_intersection.effective

            await client.revoke()
            assert client.access_token is None


# ===== E2E-5: Typed model inputs ============================================


class TestE2ETypedModels:
    def test_register_with_pydantic_models(self, ec_pem: str) -> None:
        from ath.types import DeveloperInfo, ProviderScopeRequest

        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            reg = client.register(
                developer=DeveloperInfo(name="E2E Typed", id="dev-typed"),
                providers=[ProviderScopeRequest(provider_id="github", scopes=["repo"])],
                purpose="typed model test",
            )
            assert reg.agent_status.value == "approved"


# ===== E2E-6: Gateway enforcement ==========================================


class TestE2EProxyEnforcement:
    def test_proxy_wrong_provider_after_real_token(self, ec_pem: str) -> None:
        with ATHGatewayClient(GATEWAY_URL, _unique_agent_id(), ec_pem) as client:
            client.register(
                developer={"name": "E2E PM", "id": "dev-pm"},
                providers=[{"provider_id": "github", "scopes": ["repo"]}],
                purpose="provider mismatch",
            )
            auth = client.authorize("github", ["repo"])
            _complete_oauth_via_mock_idp(auth.authorization_url)
            client.exchange_token("oauth-completed", auth.ath_session_id)

            with pytest.raises(ATHError) as exc_info:
                client.proxy("slack", "GET", "/x")
            assert exc_info.value.code == "PROVIDER_MISMATCH"
