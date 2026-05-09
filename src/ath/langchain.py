"""LangChain tool integration for ATH-authenticated API calls.

Wraps an ATHGatewayClient (or ATHNativeClient) so that a LangChain agent can
call upstream APIs through the ATH trust layer as a regular Tool.
"""

from __future__ import annotations

import json
from typing import Any

try:
    from langchain_core.tools import BaseTool
except ImportError:  # pragma: no cover
    try:
        from langchain.tools import BaseTool
    except ImportError as exc:
        raise ImportError(
            "LangChain is required for ATHTool. "
            "Install it with: pip install langchain-core   (or: pip install langchain)"
        ) from exc

from pydantic import Field, model_validator

from ath.client.base import ATHClientBase
from ath.exceptions import ATHError


class ATHTool(BaseTool):
    """A LangChain Tool that proxies requests through an ATH-authenticated client.

    The tool delegates to ``client.proxy(...)`` (gateway mode) or a direct
    HTTP call via the native client, forwarding the agent's natural-language
    input as query parameters or a JSON body to the configured ``endpoint``.

    Basic usage::

        from ath import ATHGatewayClient
        from ath.langchain import ATHTool

        client = ATHGatewayClient(url, agent_id, private_key)
        client.register(...)
        auth = client.authorize(provider, scopes)
        client.exchange_token(code, auth.ath_session_id)

        tool = ATHTool(
            name="user-profile",
            description="Look up a user profile by ID",
            client=client,
            provider_id="github",
            endpoint="/user",
        )

    The tool can then be passed directly to ``initialize_agent`` or any other
    LangChain agent constructor.
    """

    name: str = "ath_tool"
    description: str = "Call an API through ATH trusted handshake"

    client: Any = Field(exclude=True)
    provider_id: str = Field(default="")
    endpoint: str = Field(default="/")
    method: str = Field(default="GET")
    # Kept for backward-compat with the README example that uses ``service_id``
    service_id: str = Field(default="")

    model_config = {"arbitrary_types_allowed": True}

    @model_validator(mode="after")
    def _resolve_provider(self) -> ATHTool:
        if not self.provider_id and self.service_id:
            self.provider_id = self.service_id
        if not self.provider_id:
            raise ValueError("Either provider_id or service_id must be set")
        return self

    def _run(self, tool_input: str = "") -> str:
        """Execute the tool synchronously.

        ``tool_input`` is the raw string the LLM produces.  The tool tries to
        parse it as JSON; if that succeeds and yields a ``dict``, the dict is
        forwarded as the request body (for POST/PUT/PATCH) or ignored for GET.
        Otherwise the raw string is sent as the body for non-GET methods.
        """
        if not isinstance(self.client, ATHClientBase):
            raise ATHError(
                "INVALID_CLIENT",
                "ATHTool.client must be an ATHClientBase instance (e.g. ATHGatewayClient)",
            )

        body = _parse_tool_input(tool_input)

        try:
            from ath.client.gateway import ATHGatewayClient

            if isinstance(self.client, ATHGatewayClient):
                result = self.client.proxy(
                    self.provider_id,
                    self.method,
                    self.endpoint,
                    body=body if self.method.upper() not in ("GET", "DELETE") else None,
                )
            else:
                result = self.client.api(
                    self.method,
                    self.endpoint,
                    body=body if self.method.upper() not in ("GET", "DELETE") else None,
                )
        except ATHError as e:
            return f"ATH error ({e.code}): {e}"
        except Exception as e:
            return f"Error: {e}"

        if isinstance(result, dict | list):
            return json.dumps(result, ensure_ascii=False)
        return str(result)

    async def _arun(self, tool_input: str = "") -> str:
        """Async execution — delegates to the async client if available."""
        from ath.client.async_base import AsyncATHClientBase

        if not isinstance(self.client, AsyncATHClientBase):
            return self._run(tool_input)

        body = _parse_tool_input(tool_input)

        try:
            from ath.client.async_gateway import AsyncATHGatewayClient

            if isinstance(self.client, AsyncATHGatewayClient):
                result = await self.client.proxy(
                    self.provider_id,
                    self.method,
                    self.endpoint,
                    body=body if self.method.upper() not in ("GET", "DELETE") else None,
                )
            else:
                result = await self.client.api(
                    self.method,
                    self.endpoint,
                    body=body if self.method.upper() not in ("GET", "DELETE") else None,
                )
        except ATHError as e:
            return f"ATH error ({e.code}): {e}"
        except Exception as e:
            return f"Error: {e}"

        if isinstance(result, dict | list):
            return json.dumps(result, ensure_ascii=False)
        return str(result)


def _parse_tool_input(tool_input: str) -> Any:
    """Best-effort JSON parse of the LLM-produced tool input."""
    if not tool_input or not tool_input.strip():
        return None
    try:
        parsed = json.loads(tool_input)
        if isinstance(parsed, dict):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return tool_input
