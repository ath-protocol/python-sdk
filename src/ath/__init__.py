"""ath-sdk — Python SDK for the Agent Trust Handshake (ATH) protocol.

Mirrors the official TypeScript SDK at @ath-protocol/client + @ath-protocol/types.
Type names match the upstream JSON Schema $defs.
"""

from ath.client.async_base import AsyncATHClientBase
from ath.client.async_gateway import AsyncATHGatewayClient
from ath.client.async_native import AsyncATHNativeClient
from ath.client.base import ATHClientBase, ATHClientConfig
from ath.client.gateway import ATHGatewayClient
from ath.client.native import ATHNativeClient
from ath.exceptions import ATHError
from ath.meta import ATH_VERSION, ENDPOINTS
from ath.types import (
    AgentIdentityDocument,
    AgentRegistrationRequest,
    AgentRegistrationResponse,
    AgentStatus,
    ATHErrorCode,
    ATHErrorResponse,
    AuthorizationRequest,
    AuthorizationResponse,
    DeveloperInfo,
    DiscoveryDocument,
    ProviderApproval,
    ProviderInfo,
    ProviderScopeRequest,
    ScopeIntersection,
    ServiceAuthConfig,
    ServiceDiscoveryDocument,
    TokenExchangeRequest,
    TokenResponse,
    TokenRevocationRequest,
)

__all__ = [
    # Clients — sync (mirrors @ath-protocol/client)
    "ATHClientBase",
    "ATHClientConfig",
    "ATHGatewayClient",
    "ATHNativeClient",
    # Clients — async
    "AsyncATHClientBase",
    "AsyncATHGatewayClient",
    "AsyncATHNativeClient",
    # Errors
    "ATHError",
    # Meta
    "ATH_VERSION",
    "ENDPOINTS",
    # Types (mirrors @ath-protocol/types)
    "AgentStatus",
    "ATHErrorCode",
    "DeveloperInfo",
    "AgentIdentityDocument",
    "ProviderInfo",
    "DiscoveryDocument",
    "ServiceAuthConfig",
    "ServiceDiscoveryDocument",
    "ProviderScopeRequest",
    "ProviderApproval",
    "AgentRegistrationRequest",
    "AgentRegistrationResponse",
    "AuthorizationRequest",
    "AuthorizationResponse",
    "ScopeIntersection",
    "TokenExchangeRequest",
    "TokenResponse",
    "TokenRevocationRequest",
    "ATHErrorResponse",
]
