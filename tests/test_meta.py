"""Tests for ATH meta — endpoint definitions aligned with schema/meta.json."""

from __future__ import annotations

from ath.meta import ATH_VERSION, ENDPOINTS


def test_version() -> None:
    assert ATH_VERSION == "0.1"


def test_all_endpoints_present() -> None:
    expected_keys = {
        "discovery",
        "service_discovery",
        "register",
        "get_agent",
        "authorize",
        "callback",
        "token",
        "proxy",
        "revoke",
    }
    assert set(ENDPOINTS.keys()) == expected_keys


def test_endpoint_paths() -> None:
    assert ENDPOINTS["discovery"]["path"] == "/.well-known/ath.json"
    assert ENDPOINTS["register"]["path"] == "/ath/agents/register"
    assert ENDPOINTS["authorize"]["method"] == "POST"
    assert ENDPOINTS["proxy"]["method"] == "ANY"
    assert ENDPOINTS["proxy"]["path"] == "/ath/proxy/{provider_id}/{path}"
