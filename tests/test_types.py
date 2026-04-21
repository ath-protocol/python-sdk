"""Test Pydantic model validation against upstream schema JSON examples."""

from __future__ import annotations

from ath.types import (
    AgentRegistrationResponse,
    AgentStatus,
    ATHErrorCode,
    ATHErrorResponse,
    AuthorizationResponse,
    DiscoveryDocument,
    ProviderInfo,
    ServiceAuthConfig,
    ServiceDiscoveryDocument,
    TokenResponse,
)


def test_discovery_document_roundtrip() -> None:
    raw = {
        "ath_version": "0.1",
        "gateway_id": "ath-gateway.example.com",
        "agent_registration_endpoint": "https://ath-gateway.example.com/ath/agents/register",
        "supported_providers": [
            {
                "provider_id": "example-mail",
                "display_name": "Example Mail",
                "categories": ["email"],
                "available_scopes": ["mail:read", "mail:send"],
                "auth_mode": "OAUTH2",
                "agent_approval_required": True,
            }
        ],
    }
    doc = DiscoveryDocument.model_validate(raw)
    assert doc.ath_version == "0.1"
    assert isinstance(doc.supported_providers[0], ProviderInfo)
    assert doc.supported_providers[0].provider_id == "example-mail"
    assert doc.model_dump() == raw


def test_service_discovery_document() -> None:
    raw = {
        "ath_version": "0.1",
        "app_id": "com.example.mail",
        "name": "Example Mail API",
        "auth": {
            "type": "oauth2",
            "authorization_endpoint": "https://example.com/oauth/authorize",
            "token_endpoint": "https://example.com/oauth/token",
            "scopes_supported": ["mail:read", "mail:send"],
            "agent_attestation_required": True,
        },
        "api_base": "https://api.example.com/v1",
    }
    svc = ServiceDiscoveryDocument.model_validate(raw)
    assert svc.app_id == "com.example.mail"
    assert isinstance(svc.auth, ServiceAuthConfig)
    assert svc.auth.type == "oauth2"


def test_registration_response_parses_status() -> None:
    raw = {
        "client_id": "ath_travelbot_001",
        "client_secret": "ath_secret_xxxxx",
        "agent_status": "approved",
        "approved_providers": [
            {
                "provider_id": "example-mail",
                "approved_scopes": ["mail:read"],
                "denied_scopes": ["mail:send"],
                "denial_reason": "Send capability requires additional review",
            }
        ],
        "approval_expires": "2027-01-01T00:00:00Z",
    }
    reg = AgentRegistrationResponse.model_validate(raw)
    assert reg.agent_status == AgentStatus.APPROVED
    assert reg.approved_providers[0].denied_scopes == ["mail:send"]


def test_token_response_scope_intersection() -> None:
    raw = {
        "access_token": "ath_tk_xxxxxxxx",
        "token_type": "Bearer",
        "expires_in": 3600,
        "effective_scopes": ["mail:read"],
        "provider_id": "example-mail",
        "agent_id": "https://travel-agent.example.com/.well-known/agent.json",
        "scope_intersection": {
            "agent_approved": ["mail:read"],
            "user_consented": ["mail:read", "mail:send"],
            "effective": ["mail:read"],
        },
    }
    tok = TokenResponse.model_validate(raw)
    assert tok.scope_intersection.effective == ["mail:read"]
    assert tok.scope_intersection.user_consented == ["mail:read", "mail:send"]


def test_authorization_response() -> None:
    raw = {"authorization_url": "https://idp.example.com/auth?...", "ath_session_id": "sess_abc"}
    auth = AuthorizationResponse.model_validate(raw)
    assert auth.ath_session_id == "sess_abc"


def test_error_response() -> None:
    raw = {
        "code": "AGENT_NOT_REGISTERED",
        "message": "Agent not found",
        "details": {"hint": "register first"},
    }
    err = ATHErrorResponse.model_validate(raw)
    assert err.code == ATHErrorCode.AGENT_NOT_REGISTERED
    assert err.details == {"hint": "register first"}


def test_all_error_codes_in_enum() -> None:
    expected = {
        "INVALID_ATTESTATION",
        "AGENT_NOT_REGISTERED",
        "AGENT_UNAPPROVED",
        "PROVIDER_NOT_APPROVED",
        "SCOPE_NOT_APPROVED",
        "SESSION_NOT_FOUND",
        "SESSION_EXPIRED",
        "STATE_MISMATCH",
        "TOKEN_INVALID",
        "TOKEN_EXPIRED",
        "TOKEN_REVOKED",
        "AGENT_IDENTITY_MISMATCH",
        "PROVIDER_MISMATCH",
        "USER_DENIED",
        "OAUTH_ERROR",
        "INTERNAL_ERROR",
    }
    actual = {e.value for e in ATHErrorCode}
    assert actual == expected
