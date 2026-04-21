"""Tests for AsyncATHGatewayClient with mocked HTTP."""

from __future__ import annotations

import httpx
import pytest

from ath import AsyncATHGatewayClient, ATHError
from tests.conftest import AGENT_ID, GATEWAY


def _mock_handler(request: httpx.Request) -> httpx.Response:
    if request.method == "GET" and request.url.path == "/.well-known/ath.json":
        return httpx.Response(
            200,
            json={
                "ath_version": "0.1",
                "gateway_id": GATEWAY,
                "agent_registration_endpoint": f"{GATEWAY}/ath/agents/register",
                "supported_providers": [],
            },
        )
    if request.method == "POST" and request.url.path == "/ath/agents/register":
        return httpx.Response(
            200,
            json={
                "client_id": "async_cid",
                "client_secret": "async_sec",
                "agent_status": "approved",
                "approved_providers": [],
                "approval_expires": "2099-01-01T00:00:00Z",
            },
        )
    if request.method == "POST" and request.url.path == "/ath/authorize":
        return httpx.Response(
            200,
            json={"authorization_url": "https://idp/auth", "ath_session_id": "sess_async"},
        )
    if request.method == "POST" and request.url.path == "/ath/token":
        return httpx.Response(
            200,
            json={
                "access_token": "ath_tk_async",
                "token_type": "Bearer",
                "expires_in": 3600,
                "effective_scopes": ["s"],
                "provider_id": "p",
                "agent_id": AGENT_ID,
                "scope_intersection": {
                    "agent_approved": ["s"],
                    "user_consented": ["s"],
                    "effective": ["s"],
                },
            },
        )
    if request.url.path.startswith("/ath/proxy/"):
        return httpx.Response(200, json={"ok": True})
    if request.method == "POST" and request.url.path == "/ath/revoke":
        return httpx.Response(200, json={"message": "revoked"})
    return httpx.Response(404, json={"code": "NOT_FOUND", "message": "nope"})


@pytest.fixture()
def async_client(ec_private_pem: str) -> AsyncATHGatewayClient:
    transport = httpx.MockTransport(_mock_handler)
    c = AsyncATHGatewayClient(GATEWAY, AGENT_ID, ec_private_pem)
    c._http = httpx.AsyncClient(transport=transport)
    return c


@pytest.mark.asyncio
async def test_async_discover(async_client: AsyncATHGatewayClient) -> None:
    doc = await async_client.discover()
    assert doc.gateway_id == GATEWAY


@pytest.mark.asyncio
async def test_async_full_flow(async_client: AsyncATHGatewayClient) -> None:
    await async_client.register(
        developer={"name": "T", "id": "1"},
        providers=[{"provider_id": "p", "scopes": ["s"]}],
        purpose="t",
    )
    assert async_client.client_id == "async_cid"

    auth = await async_client.authorize("p", ["s"])
    assert auth.ath_session_id == "sess_async"

    tok = await async_client.exchange_token("code", "sess_async")
    assert tok.access_token == "ath_tk_async"

    data = await async_client.proxy("p", "GET", "/resource")
    assert data["ok"] is True

    await async_client.revoke()
    assert async_client.access_token is None


@pytest.mark.asyncio
async def test_async_context_manager(ec_private_pem: str) -> None:
    transport = httpx.MockTransport(_mock_handler)
    async with AsyncATHGatewayClient(GATEWAY, AGENT_ID, ec_private_pem) as c:
        c._http = httpx.AsyncClient(transport=transport)
        doc = await c.discover()
        assert doc.ath_version == "0.1"


@pytest.mark.asyncio
async def test_async_authorize_before_register(async_client: AsyncATHGatewayClient) -> None:
    with pytest.raises(ATHError) as exc_info:
        await async_client.authorize("p", ["s"])
    assert exc_info.value.code == "NOT_REGISTERED"
