"""Tests for the ATHTool LangChain integration."""

from __future__ import annotations

import json

import httpx
import pytest

from ath import ATHGatewayClient
from ath.langchain import ATHTool, _parse_tool_input
from tests.conftest import AGENT_ID, GATEWAY


def _mock_handler(request: httpx.Request) -> httpx.Response:
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
    return httpx.Response(404, json={"code": "NOT_FOUND", "message": "no route"})


@pytest.fixture()
def authed_client(ec_private_pem: str) -> ATHGatewayClient:
    """Return a mock-backed gateway client that has already exchanged a token."""
    transport = httpx.MockTransport(_mock_handler)
    c = ATHGatewayClient(GATEWAY, AGENT_ID, ec_private_pem)
    c._http = httpx.Client(transport=transport)
    c.register(
        developer={"name": "Test", "id": "dev-1"},
        providers=[{"provider_id": "github", "scopes": ["repo"]}],
        purpose="testing",
    )
    c.authorize("github", ["repo"])
    c.exchange_token("mock_code", "ath_sess_abc")
    return c


class TestATHToolCreation:
    def test_create_with_provider_id(self, authed_client: ATHGatewayClient) -> None:
        tool = ATHTool(
            name="test-tool",
            description="A test tool",
            client=authed_client,
            provider_id="github",
            endpoint="/user",
        )
        assert tool.name == "test-tool"
        assert tool.provider_id == "github"

    def test_create_with_service_id_fallback(self, authed_client: ATHGatewayClient) -> None:
        tool = ATHTool(
            name="test-tool",
            description="A test tool",
            client=authed_client,
            service_id="github",
            endpoint="/user",
        )
        assert tool.provider_id == "github"

    def test_missing_provider_raises(self, authed_client: ATHGatewayClient) -> None:
        with pytest.raises(ValueError, match="provider_id or service_id"):
            ATHTool(
                name="bad",
                description="no provider",
                client=authed_client,
                endpoint="/user",
            )


class TestATHToolRun:
    def test_run_returns_json(self, authed_client: ATHGatewayClient) -> None:
        tool = ATHTool(
            name="user-lookup",
            description="Look up a user",
            client=authed_client,
            provider_id="github",
            endpoint="/user",
        )
        result = tool._run("")
        parsed = json.loads(result)
        assert parsed["login"] == "demo-user"
        assert parsed["id"] == 12345

    def test_run_with_json_input(self, authed_client: ATHGatewayClient) -> None:
        tool = ATHTool(
            name="post-data",
            description="Post some data",
            client=authed_client,
            provider_id="github",
            endpoint="/data",
            method="POST",
        )
        result = tool._run('{"key": "value"}')
        assert isinstance(result, str)

    def test_run_without_token_returns_error(self, ec_private_pem: str) -> None:
        transport = httpx.MockTransport(_mock_handler)
        c = ATHGatewayClient(GATEWAY, AGENT_ID, ec_private_pem)
        c._http = httpx.Client(transport=transport)

        tool = ATHTool(
            name="no-token",
            description="Should fail",
            client=c,
            provider_id="github",
            endpoint="/user",
        )
        result = tool._run("")
        assert "NO_TOKEN" in result

    def test_invoke(self, authed_client: ATHGatewayClient) -> None:
        tool = ATHTool(
            name="user-lookup",
            description="Look up a user",
            client=authed_client,
            provider_id="github",
            endpoint="/user",
        )
        result = tool.invoke("")
        parsed = json.loads(result)
        assert parsed["login"] == "demo-user"

    def test_run_with_empty_input(self, authed_client: ATHGatewayClient) -> None:
        tool = ATHTool(
            name="user-lookup",
            description="Look up a user",
            client=authed_client,
            provider_id="github",
            endpoint="/user",
        )
        result = tool._run()
        parsed = json.loads(result)
        assert parsed["login"] == "demo-user"


class TestParseToolInput:
    def test_parse_none_input(self) -> None:
        assert _parse_tool_input("") is None

    def test_parse_json_dict(self) -> None:
        result = _parse_tool_input('{"a": 1}')
        assert result == {"a": 1}

    def test_parse_non_json_returns_raw(self) -> None:
        result = _parse_tool_input("hello world")
        assert result == "hello world"

    def test_parse_json_non_dict_returns_raw(self) -> None:
        result = _parse_tool_input("[1, 2, 3]")
        assert result == "[1, 2, 3]"
