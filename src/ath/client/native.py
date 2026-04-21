"""ATHNativeClient — for agents connecting directly to an ATH-native service (spec §2.2).

Mirrors @ath-protocol/client ATHNativeClient.
"""

from __future__ import annotations

from typing import Any

from ath.client._base import require_token
from ath.client.base import ATHClientBase
from ath.exceptions import ATHError
from ath.types import ServiceDiscoveryDocument


class ATHNativeClient(ATHClientBase):
    """Agent client for ATH Native Mode.

    The service implements ATH endpoints directly. After discover(), the
    api() method calls the service at its published api_base.

    Usage::

        with ATHNativeClient("https://mail.example.com", agent_id, key) as client:
            svc = client.discover()
            client.register(...)
            client.authorize(svc.app_id, ["mail:read"])
            client.exchange_token(code, session_id)
            data = client.api("GET", "/v1/messages")
            client.revoke()
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._api_base: str | None = None

    def discover(self) -> ServiceDiscoveryDocument:
        """GET /.well-known/ath-app.json — Service-Side Discovery (spec §4.3).

        Caches api_base for subsequent api() calls.
        """
        raw = self._request("GET", self._ath_url("/.well-known/ath-app.json"))
        doc = ServiceDiscoveryDocument.model_validate(raw)
        self._api_base = doc.api_base.rstrip("/")
        return doc

    def api(
        self,
        method: str,
        path: str,
        body: Any = None,
    ) -> Any:
        """Direct authenticated API call to the service's api_base.

        Requires discover() to have been called first (to resolve api_base).
        """
        if not self._api_base:
            raise ATHError("NOT_DISCOVERED", "Call discover() first to resolve api_base.")
        token = require_token(self._access_token)
        if not path.startswith("/"):
            path = f"/{path}"
        url = f"{self._api_base}{path}"
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
