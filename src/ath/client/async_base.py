"""AsyncATHClientBase — async version of shared protocol methods."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from ath.client._attestation import sign_attestation
from ath.client._base import (
    build_authorize_body,
    build_register_body,
    build_token_body,
    parse_error_response,
    parse_json_response,
    require_credentials,
    require_registered,
)
from ath.types import (
    AgentRegistrationResponse,
    AuthorizationResponse,
    DeveloperInfo,
    ProviderScopeRequest,
    TokenResponse,
)


class AsyncATHClientBase:
    """Async abstract base for gateway and native ATH clients."""

    def __init__(
        self,
        url: str,
        agent_id: str,
        private_key: str | bytes,
        *,
        key_id: str = "default",
        timeout: float = 60.0,
    ) -> None:
        self.url = url.rstrip("/")
        self.agent_id = agent_id
        self._private_key = private_key
        self._key_id = key_id
        self._http: httpx.AsyncClient = httpx.AsyncClient(timeout=timeout)
        self._client_id: str | None = None
        self._client_secret: str | None = None
        self._access_token: str | None = None

    async def __aenter__(self) -> AsyncATHClientBase:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self._http.aclose()

    def _attest(self, audience: str | None = None) -> str:
        return sign_attestation(
            agent_id=self.agent_id,
            private_key=self._private_key,
            key_id=self._key_id,
            audience=audience or self.url,
        )

    async def _request(
        self,
        method: str,
        full_url: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        h: dict[str, str] = {}
        if headers:
            h.update(headers)
        r = await self._http.request(method, full_url, headers=h, json=body)
        if not r.is_success:
            raise parse_error_response(r.status_code, r.content)
        return parse_json_response(r.content)

    async def _raw_request(
        self,
        method: str,
        full_url: str,
        body: Any = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        h: dict[str, str] = {}
        if headers:
            h.update(headers)
        r = await self._http.request(method, full_url, headers=h, json=body)
        if not r.is_success:
            raise parse_error_response(r.status_code, r.content)
        return r

    def _ath_url(self, path: str) -> str:
        return f"{self.url}{path}"

    async def register(
        self,
        *,
        developer: DeveloperInfo | dict[str, str],
        providers: list[ProviderScopeRequest | dict[str, Any]],
        purpose: str,
        redirect_uris: list[str] | None = None,
    ) -> AgentRegistrationResponse:
        """POST /ath/agents/register — Agent Registration (spec §6.1)."""
        body = build_register_body(
            agent_id=self.agent_id,
            attestation=self._attest(),
            developer=developer,
            providers=providers,
            purpose=purpose,
            redirect_uris=redirect_uris,
            base_url=self.url,
        )
        raw = await self._request("POST", self._ath_url("/ath/agents/register"), body)
        parsed = AgentRegistrationResponse.model_validate(raw)
        self._client_id = parsed.client_id
        self._client_secret = parsed.client_secret
        return parsed

    async def authorize(
        self,
        provider: str,
        scopes: list[str],
        *,
        redirect_uri: str | None = None,
        resource: str | None = None,
    ) -> AuthorizationResponse:
        """POST /ath/authorize — Authorization Request (spec §6.2)."""
        cid = require_registered(self._client_id)
        body = build_authorize_body(
            client_id=cid,
            attestation=self._attest(),
            provider=provider,
            scopes=scopes,
            redirect_uri=redirect_uri,
            resource=resource,
            base_url=self.url,
        )
        raw = await self._request("POST", self._ath_url("/ath/authorize"), body)
        return AuthorizationResponse.model_validate(raw)

    async def exchange_token(self, code: str, session_id: str) -> TokenResponse:
        """POST /ath/token — Token Exchange (spec §6.3)."""
        cid, sec = require_credentials(self._client_id, self._client_secret)
        body = build_token_body(
            client_id=cid, client_secret=sec, authorization_code=code, session_id=session_id
        )
        raw = await self._request("POST", self._ath_url("/ath/token"), body)
        parsed = TokenResponse.model_validate(raw)
        self._access_token = parsed.access_token
        return parsed

    async def revoke(self) -> None:
        """POST /ath/revoke — Token Revocation (spec §6.5)."""
        if not self._access_token or not self._client_id:
            return
        await self._request(
            "POST",
            self._ath_url("/ath/revoke"),
            {"client_id": self._client_id, "token": self._access_token},
        )
        self._access_token = None

    @property
    def client_id(self) -> str | None:
        return self._client_id

    @property
    def access_token(self) -> str | None:
        return self._access_token

    def get_client_id(self) -> str | None:
        return self._client_id

    def set_credentials(self, client_id: str, client_secret: str) -> None:
        self._client_id = client_id
        self._client_secret = client_secret

    def set_token(self, token: str) -> None:
        self._access_token = token

    def save_credentials(self, path: str | Path) -> None:
        cid, sec = require_credentials(self._client_id, self._client_secret)
        Path(path).write_text(json.dumps({"client_id": cid, "client_secret": sec}, indent=2))

    def load_credentials(self, path: str | Path) -> None:
        data = json.loads(Path(path).read_text())
        self._client_id = data["client_id"]
        self._client_secret = data["client_secret"]
