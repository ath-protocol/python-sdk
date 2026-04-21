"""ATHGatewayClient — for agents connecting through an ATH gateway (spec §2.1).

Mirrors @ath-protocol/client ATHGatewayClient.
"""

from __future__ import annotations

from typing import Any

from ath.client._base import require_token
from ath.client.base import ATHClientBase
from ath.types import DiscoveryDocument


class ATHGatewayClient(ATHClientBase):
    """Agent client for ATH Gateway Mode.

    Usage::

        with ATHGatewayClient("https://gateway.example.com", agent_id, key) as client:
            doc = client.discover()
            client.register(...)
            client.authorize(...)
            client.exchange_token(code, session_id)
            data = client.proxy("github", "GET", "/user")
            client.revoke()
    """

    def discover(self) -> DiscoveryDocument:
        """GET /.well-known/ath.json — Gateway Catalog Discovery (spec §4.2)."""
        raw = self._request("GET", self._ath_url("/.well-known/ath.json"))
        return DiscoveryDocument.model_validate(raw)

    def proxy(
        self,
        provider: str,
        method: str,
        path: str,
        body: Any = None,
    ) -> Any:
        """ANY /ath/proxy/{provider}/{path} — API Proxy (spec §6.4).

        Routes the request through the gateway, which validates the ATH token
        and proxies to the upstream service using its stored OAuth token.
        """
        token = require_token(self._access_token)
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{self.url}/ath/proxy/{provider}{path}"
        r = self._raw_request(
            method.upper(),
            url,
            body,
            {
                "Authorization": f"Bearer {token}",
                "X-ATH-Agent-ID": self.agent_id,
            },
        )
        ct = r.headers.get("content-type", "")
        return r.json() if "application/json" in ct else r.text
