"""ATH protocol types — Pydantic v2 models aligned with upstream schema.

Source of truth: schema/ath-protocol.schema.json (from ath-protocol/agent-trust-handshake-protocol).
Type names match the upstream JSON Schema $defs exactly.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Enums (upstream $defs: AgentStatus, ATHErrorCode)
# ---------------------------------------------------------------------------


class AgentStatus(str, Enum):
    """Registration status of an agent."""

    APPROVED = "approved"
    PENDING = "pending"
    DENIED = "denied"


class ATHErrorCode(str, Enum):
    """Enumeration of ATH error codes."""

    INVALID_ATTESTATION = "INVALID_ATTESTATION"
    AGENT_NOT_REGISTERED = "AGENT_NOT_REGISTERED"
    AGENT_UNAPPROVED = "AGENT_UNAPPROVED"
    PROVIDER_NOT_APPROVED = "PROVIDER_NOT_APPROVED"
    SCOPE_NOT_APPROVED = "SCOPE_NOT_APPROVED"
    SESSION_NOT_FOUND = "SESSION_NOT_FOUND"
    SESSION_EXPIRED = "SESSION_EXPIRED"
    STATE_MISMATCH = "STATE_MISMATCH"
    TOKEN_INVALID = "TOKEN_INVALID"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_REVOKED = "TOKEN_REVOKED"
    AGENT_IDENTITY_MISMATCH = "AGENT_IDENTITY_MISMATCH"
    PROVIDER_MISMATCH = "PROVIDER_MISMATCH"
    USER_DENIED = "USER_DENIED"
    OAUTH_ERROR = "OAUTH_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


# ---------------------------------------------------------------------------
# Identity ($defs: DeveloperInfo, AgentIdentityDocument)
# ---------------------------------------------------------------------------


class DeveloperInfo(BaseModel):
    """Information about the agent's developer or organization."""

    name: str
    id: str
    contact: str | None = None


class AgentIdentityDocument(BaseModel):
    """Agent identity published at agent_id URI (.well-known/agent.json)."""

    ath_version: str = "0.1"
    agent_id: str
    name: str
    developer: DeveloperInfo
    capabilities: list[str] = Field(default_factory=list)
    public_key: Any  # JWK or PEM


# ---------------------------------------------------------------------------
# Discovery ($defs: ProviderInfo, DiscoveryDocument,
#             ServiceAuthConfig, ServiceDiscoveryDocument)
# ---------------------------------------------------------------------------


class ProviderInfo(BaseModel):
    """Information about a service provider available through the gateway."""

    provider_id: str
    display_name: str
    categories: list[str] = Field(default_factory=list)
    available_scopes: list[str] = Field(default_factory=list)
    auth_mode: str
    agent_approval_required: bool


class DiscoveryDocument(BaseModel):
    """Gateway discovery document returned by GET /.well-known/ath.json."""

    ath_version: str
    gateway_id: str
    agent_registration_endpoint: str
    supported_providers: list[ProviderInfo] = Field(default_factory=list)


class ServiceAuthConfig(BaseModel):
    """Authentication configuration published by an ATH-native service."""

    type: Literal["oauth2"] = "oauth2"
    authorization_endpoint: str
    token_endpoint: str
    registration_endpoint: str | None = None
    scopes_supported: list[str] = Field(default_factory=list)
    agent_attestation_required: bool = True


class ServiceDiscoveryDocument(BaseModel):
    """Service-side discovery document returned by GET /.well-known/ath-app.json."""

    ath_version: str
    app_id: str
    name: str
    auth: ServiceAuthConfig
    api_base: str


# ---------------------------------------------------------------------------
# Registration ($defs: ProviderScopeRequest, AgentRegistrationRequest,
#               ProviderApproval, AgentRegistrationResponse)
# ---------------------------------------------------------------------------


class ProviderScopeRequest(BaseModel):
    """A request for access to a specific provider with specific scopes."""

    provider_id: str
    scopes: list[str]


class ProviderApproval(BaseModel):
    """Per-provider approval result. Implementor MAY approve a subset of scopes."""

    provider_id: str
    approved_scopes: list[str] = Field(default_factory=list)
    denied_scopes: list[str] = Field(default_factory=list)
    denial_reason: str | None = None


class AgentRegistrationRequest(BaseModel):
    """POST /ath/agents/register — request body (Phase A)."""

    agent_id: str
    agent_attestation: str
    developer: DeveloperInfo
    requested_providers: list[ProviderScopeRequest]
    purpose: str | None = None
    redirect_uris: list[str] | None = None


class AgentRegistrationResponse(BaseModel):
    """POST /ath/agents/register — response body."""

    client_id: str
    client_secret: str
    agent_status: AgentStatus
    approved_providers: list[ProviderApproval] = Field(default_factory=list)
    approval_expires: str


# ---------------------------------------------------------------------------
# Authorization ($defs: AuthorizationRequest, AuthorizationResponse)
# ---------------------------------------------------------------------------


class AuthorizationRequest(BaseModel):
    """POST /ath/authorize — request body (Phase B). PKCE generated server-side."""

    client_id: str
    agent_attestation: str
    provider_id: str
    scopes: list[str]
    user_redirect_uri: str | None = None
    state: str | None = None
    resource: str | None = None  # RFC 8707


class AuthorizationResponse(BaseModel):
    """POST /ath/authorize — response body."""

    authorization_url: str
    ath_session_id: str


# ---------------------------------------------------------------------------
# Token exchange ($defs: ScopeIntersection, TokenExchangeRequest, TokenResponse)
# ---------------------------------------------------------------------------


class ScopeIntersection(BaseModel):
    """Breakdown of effective scopes: Effective = Agent Approved ∩ User Consented ∩ Requested."""

    agent_approved: list[str] = Field(default_factory=list)
    user_consented: list[str] = Field(default_factory=list)
    effective: list[str] = Field(default_factory=list)


class TokenExchangeRequest(BaseModel):
    """POST /ath/token — request body."""

    grant_type: Literal["authorization_code"] = "authorization_code"
    client_id: str
    client_secret: str
    code: str
    ath_session_id: str


class TokenResponse(BaseModel):
    """POST /ath/token — response body."""

    access_token: str
    token_type: Literal["Bearer"] = "Bearer"
    expires_in: int
    effective_scopes: list[str] = Field(default_factory=list)
    provider_id: str
    agent_id: str
    scope_intersection: ScopeIntersection


# ---------------------------------------------------------------------------
# Revocation ($defs: TokenRevocationRequest)
# ---------------------------------------------------------------------------


class TokenRevocationRequest(BaseModel):
    """POST /ath/revoke — request body."""

    client_id: str
    token: str


# ---------------------------------------------------------------------------
# Errors ($defs: ATHError — renamed to ATHErrorResponse to avoid clash
# with the Python exception class in ath.exceptions)
# ---------------------------------------------------------------------------


class ATHErrorResponse(BaseModel):
    """Standard error response returned by all ATH endpoints on failure."""

    code: ATHErrorCode
    message: str
    details: dict[str, Any] | None = None
