"""Tests for ATHGatewayClient (sync) with mocked HTTP."""

from __future__ import annotations

import tempfile

import httpx
import pytest

from ath import ATHError, ATHGatewayClient
from tests.conftest import AGENT_ID, GATEWAY


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.method == "GET" and request.url.path == "/.well-known/ath.json":
        return httpx.Response(
            200,
            json={
                "ath_version": "0.1",
                "gateway_id": GATEWAY,
                "agent_registration_endpoint": f"{GATEWAY}/ath/agents/register",
                "supported_providers": [
                    {
                        "provider_id": "github",
                        "display_name": "GitHub",
                        "categories": ["code"],
                        "available_scopes": ["repo", "read:user"],
                        "auth_mode": "OAUTH2",
                        "agent_approval_required": True,
                    }
                ],
            },
        )
    if request.method == "POST" and request.url.path == "/ath/agents/register":
        return httpx.Response(
            200,
            json={
                "client_id": "cid_001",
                "client_secret": "sec_001",
                "agent_status": "approved",
                "approved_providers": [
                    {
                        "provider_id": "github",
                        "approved_scopes": ["repo", "read:user"],
                        "denied_scopes": [],
                    }
                ],
                "approval_expires": "2099-01-01T00:00:00Z",
            },
        )
    if request.method == "POST" and request.url.path == "/ath/authorize":
        return httpx.Response(
            200,
            json={
                "authorization_url": "https://github.com/login/oauth/authorize?...",
                "ath_session_id": "ath_sess_abc",
            },
        )
    if request.method == "POST" and request.url.path == "/ath/token":
        return httpx.Response(
            200,
            json={
                "access_token": "ath_tk_xxx",
                "token_type": "Bearer",
                "expires_in": 3600,
                "effective_scopes": ["repo"],
                "provider_id": "github",
                "agent_id": AGENT_ID,
                "scope_intersection": {
                    "agent_approved": ["repo", "read:user"],
                    "user_consented": ["repo"],
                    "effective": ["repo"],
                },
            },
        )
    if request.url.path.startswith("/ath/proxy/"):
        return httpx.Response(200, json={"login": "demo-user", "id": 12345})
    if request.method == "POST" and request.url.path == "/ath/revoke":
        return httpx.Response(200, json={"message": "Token revoked"})
    return httpx.Response(404, json={"code": "NOT_FOUND", "message": "no route"})


@pytest.fixture()
def client(ec_private_pem: str) -> ATHGatewayClient:
    transport = httpx.MockTransport(_mock_handler)
    c = ATHGatewayClient(GATEWAY, AGENT_ID, ec_private_pem)
    c._http = httpx.Client(transport=transport)
    return c


class TestDiscoverRegisterFlow:
    def test_discover(self, client: ATHGatewayClient) -> None:
        doc = client.discover()
        assert doc.ath_version == "0.1"
        assert doc.url if hasattr(doc, "url") else True
        assert len(doc.supported_providers) == 1
        assert doc.supported_providers[0].provider_id == "github"

    def test_register(self, client: ATHGatewayClient) -> None:
        reg = client.register(
            developer={"name": "Test", "id": "dev-1"},
            providers=[{"provider_id": "github", "scopes": ["repo"]}],
            purpose="testing",
        )
        assert reg.client_id == "cid_001"
        assert reg.agent_status.value == "approved"
        assert client.client_id == "cid_001"


class TestAuthorizationFlow:
    def test_authorize_without_register(self, client: ATHGatewayClient) -> None:
        with pytest.raises(ATHError) as exc_info:
            client.authorize("github", ["repo"])
        assert exc_info.value.code == "NOT_REGISTERED"

    def test_authorize_with_resource(self, client: ATHGatewayClient) -> None:
        client.register(
            developer={"name": "T", "id": "1"},
            providers=[{"provider_id": "github", "scopes": ["repo"]}],
            purpose="t",
        )
        res = client.authorize("github", ["repo"], resource="https://api.github.com")
        assert res.ath_session_id == "ath_sess_abc"


class TestTokenAndProxy:
    def test_full_flow(self, client: ATHGatewayClient) -> None:
        client.register(
            developer={"name": "T", "id": "1"},
            providers=[{"provider_id": "github", "scopes": ["repo"]}],
            purpose="t",
        )
        client.authorize("github", ["repo"])
        tok = client.exchange_token("mock_code", "ath_sess_abc")
        assert tok.access_token == "ath_tk_xxx"
        assert tok.scope_intersection.effective == ["repo"]
        assert client.access_token == "ath_tk_xxx"

        data = client.proxy("github", "GET", "/user")
        assert data["login"] == "demo-user"

        client.revoke()
        assert client.access_token is None

    def test_proxy_without_token(self, client: ATHGatewayClient) -> None:
        with pytest.raises(ATHError) as exc_info:
            client.proxy("github", "GET", "/user")
        assert exc_info.value.code == "NO_TOKEN"


class TestCredentialPersistence:
    def test_save_and_load(self, client: ATHGatewayClient) -> None:
        client.register(
            developer={"name": "T", "id": "1"},
            providers=[{"provider_id": "github", "scopes": ["repo"]}],
            purpose="t",
        )
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        client.save_credentials(path)

        c2 = ATHGatewayClient(GATEWAY, AGENT_ID, "unused_key")
        c2.load_credentials(path)
        assert c2.client_id == "cid_001"


class TestContextManager:
    def test_with_statement(self, ec_private_pem: str) -> None:
        transport = httpx.MockTransport(_mock_handler)
        with ATHGatewayClient(GATEWAY, AGENT_ID, ec_private_pem) as c:
            c._http = httpx.Client(transport=transport)
            doc = c.discover()
            assert doc.gateway_id == GATEWAY


class TestErrorHandling:
    def test_404_raises_ath_error(self, client: ATHGatewayClient) -> None:
        with pytest.raises(ATHError) as exc_info:
            client._request("GET", client._ath_url("/nonexistent"))
        assert exc_info.value.code == "NOT_FOUND"
        assert exc_info.value.status == 404
