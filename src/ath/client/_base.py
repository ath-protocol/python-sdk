"""Shared logic for sync/async ATH clients — body construction, guards, and HTTP error parsing."""

from __future__ import annotations

import json
import secrets
from typing import Any

from ath.exceptions import ATHError
from ath.types import DeveloperInfo, ProviderScopeRequest


def parse_error_response(status_code: int, body: bytes) -> ATHError:
    """Turn an HTTP error response into a structured ATHError."""
    try:
        data = json.loads(body)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    return ATHError(
        str(data.get("code") or "UNKNOWN"),
        str(data.get("message") or f"Request failed: {status_code}"),
        status=status_code,
        details=data if isinstance(data, dict) else {},
    )


def parse_json_response(content: bytes) -> dict[str, Any]:
    """Parse a successful response body, raising on non-object."""
    try:
        data = json.loads(content)
    except Exception:
        data = {}
    if not isinstance(data, dict):
        raise ATHError("INVALID_RESPONSE", "Expected JSON object from ATH implementor")
    return data


def _normalize_developer(developer: DeveloperInfo | dict[str, str]) -> dict[str, Any]:
    if isinstance(developer, DeveloperInfo):
        return developer.model_dump()
    return dict(developer)


def _normalize_providers(
    providers: list[ProviderScopeRequest | dict[str, Any]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for p in providers:
        if isinstance(p, ProviderScopeRequest):
            result.append(p.model_dump())
        else:
            result.append(dict(p))
    return result


def build_register_body(
    *,
    agent_id: str,
    attestation: str,
    developer: DeveloperInfo | dict[str, str],
    providers: list[ProviderScopeRequest | dict[str, Any]],
    purpose: str,
    redirect_uris: list[str] | None,
    base_url: str,
) -> dict[str, Any]:
    """Build POST /ath/agents/register JSON (mirrors @ath-protocol/client)."""
    return {
        "agent_id": agent_id,
        "agent_attestation": attestation,
        "developer": _normalize_developer(developer),
        "requested_providers": _normalize_providers(providers),
        "purpose": purpose,
        "redirect_uris": redirect_uris or [f"{base_url}/ath/callback"],
    }


def build_authorize_body(
    *,
    client_id: str,
    attestation: str,
    provider: str,
    scopes: list[str],
    redirect_uri: str | None,
    resource: str | None,
    base_url: str,
) -> dict[str, Any]:
    """Build POST /ath/authorize JSON.

    ``state`` uses at least 128 bits of entropy (protocol requirement).
    Default ``user_redirect_uri`` matches @ath-protocol/client.
    """
    body: dict[str, Any] = {
        "client_id": client_id,
        "agent_attestation": attestation,
        "provider_id": provider,
        "scopes": scopes,
        "user_redirect_uri": redirect_uri or f"{base_url}/ath/callback",
        # 128 bits of entropy, hex-encoded (matches @ath-protocol/client on b77d branch)
        "state": secrets.token_hex(16),
    }
    if resource is not None:
        body["resource"] = resource
    return body


def build_token_body(
    *,
    client_id: str,
    client_secret: str,
    agent_attestation: str,
    authorization_code: str,
    session_id: str,
) -> dict[str, Any]:
    """Build POST /ath/token JSON (includes ``agent_attestation`` per protocol)."""
    return {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "agent_attestation": agent_attestation,
        "code": authorization_code,
        "ath_session_id": session_id,
    }


def require_registered(client_id: str | None) -> str:
    """Guard: raise if agent not registered. Returns client_id."""
    if not client_id:
        raise ATHError("NOT_REGISTERED", "Agent not registered. Call register() first.")
    return client_id


def require_credentials(client_id: str | None, client_secret: str | None) -> tuple[str, str]:
    """Guard: raise if agent credentials missing. Returns (client_id, client_secret)."""
    if not client_id or not client_secret:
        raise ATHError("NOT_REGISTERED", "Agent not registered. Call register() first.")
    return client_id, client_secret


def require_token(access_token: str | None) -> str:
    """Guard: raise if no active access token. Returns token."""
    if not access_token:
        raise ATHError("NO_TOKEN", "No active token. Complete authorization flow first.")
    return access_token
