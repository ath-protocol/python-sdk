"""AsyncATHNativeClient — async native mode client."""

from __future__ import annotations

from typing import Any

from ath.client._base import require_token
from ath.client.async_base import AsyncATHClientBase
from ath.exceptions import ATHError
from ath.types import ServiceDiscoveryDocument


class AsyncATHNativeClient(AsyncATHClientBase):
    """Async agent client for ATH Native Mode."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._api_base: str | None = None

    async def discover(self) -> ServiceDiscoveryDocument:
        raw = await self._request("GET", self._ath_url("/.well-known/ath-app.json"))
        doc = ServiceDiscoveryDocument.model_validate(raw)
        self._api_base = doc.api_base.rstrip("/")
        return doc

    async def api(
        self,
        method: str,
        path: str,
        body: Any = None,
    ) -> Any:
        """Direct authenticated API call to service api_base."""
        if not self._api_base:
            raise ATHError("NOT_DISCOVERED", "Call discover() first to resolve api_base.")
        token = require_token(self._access_token)
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{self._api_base}{path}"
        r = await self._raw_request(
            method.upper(),
            url,
            body,
            {"Authorization": f"Bearer {token}", "X-ATH-Agent-ID": self.agent_id},
        )
        ct = r.headers.get("content-type", "")
        return r.json() if "application/json" in ct else r.text
