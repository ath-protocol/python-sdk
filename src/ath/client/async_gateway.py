"""AsyncATHGatewayClient — async gateway mode client."""

from __future__ import annotations

from typing import Any

from ath.client._base import require_token
from ath.client.async_base import AsyncATHClientBase
from ath.types import DiscoveryDocument


class AsyncATHGatewayClient(AsyncATHClientBase):
    """Async agent client for ATH Gateway Mode."""

    async def discover(self) -> DiscoveryDocument:
        raw = await self._request("GET", self._ath_url("/.well-known/ath.json"))
        return DiscoveryDocument.model_validate(raw)

    async def proxy(
        self,
        provider: str,
        method: str,
        path: str,
        body: Any = None,
    ) -> Any:
        """ANY /ath/proxy/{provider}/{path} — API Proxy (spec §6.4)."""
        token = require_token(self._access_token)
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{self.url}/ath/proxy/{provider}{path}"
        r = await self._raw_request(
            method.upper(),
            url,
            body,
            {"Authorization": f"Bearer {token}", "X-ATH-Agent-ID": self.agent_id},
        )
        ct = r.headers.get("content-type", "")
        return r.json() if "application/json" in ct else r.text
