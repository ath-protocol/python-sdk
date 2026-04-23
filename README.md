# Python SDK for the Agent Trust Handshake (ATH)

Official Python client for the [Agent Trust Handshake protocol](https://github.com/ath-protocol/agent-trust-handshake-protocol). It tracks the same JSON Schema as the protocol repo (`schema/0.1`) and mirrors the public API of [@ath-protocol/client](https://github.com/ath-protocol/typescript-sdk) (TypeScript).

## Requirements

- Python **3.10+** (see `pyproject.toml`)

## Install

From PyPI (distribution name **`ath-sdk`**, see `pyproject.toml`):

```bash
pip install ath-sdk
```

For local development:

```bash
pip install -e '.[dev]'
```

## Quick start (gateway mode)

The sync client is `ATHGatewayClient`. Typical flow: **discover → register → authorize → exchange_token → proxy → revoke**.

```python
from ath import ATHGatewayClient

gateway_url = "https://your-gateway.example.com"
agent_id = "https://your-agent.example.com/.well-known/agent.json"
private_key_pem = open("agent-ec-private.pem").read()

with ATHGatewayClient(gateway_url, agent_id, private_key_pem) as client:
    client.discover()

    client.register(
        developer={"name": "Your Org", "id": "dev-001"},
        providers=[{"provider_id": "example-mail", "scopes": ["mail:read"]}],
        purpose="Email assistant",
    )

    auth = client.authorize("example-mail", ["mail:read"])
    # Send the user to auth.authorization_url, then handle the OAuth callback
    # and pass the returned `code` plus auth.ath_session_id:

    token = client.exchange_token(code="...", session_id=auth.ath_session_id)
    data = client.proxy("example-mail", "GET", "/v1/messages")

    client.revoke()
```

### Async

Use `AsyncATHGatewayClient` / `AsyncATHNativeClient` from `ath` — same method names with `await`.

### Native mode

For services that expose ATH directly, use `ATHNativeClient`: `discover()` reads `/.well-known/ath-app.json`, then `api(method, path)` calls the service `api_base` with the bearer token.

## Protocol behavior (aligned with TypeScript)

The client follows the current protocol and `@ath-protocol/client` behavior:

- **Agent attestation** (JWT, ES256) includes a unique **`jti`** per token.
- **`authorize`** sends a **`state`** value with at least 128 bits of entropy (hex).
- **`exchange_token`** sends a fresh **`agent_attestation`** whose **`aud`** is the **token endpoint URL** (`{base}/ath/token`), plus `client_id`, `client_secret`, `code`, and `ath_session_id`.
- **`revoke`** sends `client_id`, `client_secret`, and `token` when revoking as the registered agent (RFC 7009-style client auth).

Types live in `ath.types` and match the bundled schema in `schema/ath-protocol.schema.json`.

## Project layout

| Path | Purpose |
|------|---------|
| `src/ath/` | Client, types, errors |
| `schema/ath-protocol.schema.json` | Protocol JSON Schema v0.1 (vendored from the protocol repo) |
| `examples/` | Runnable demo (see `examples/README.md`) |
| `tests/` | Unit tests with mocked HTTP |

## Related repositories

- [agent-trust-handshake-protocol](https://github.com/ath-protocol/agent-trust-handshake-protocol) — normative spec and schema
- [typescript-sdk](https://github.com/ath-protocol/typescript-sdk) — reference TypeScript client and generated types

## Documentation links

- [Python SDK docs](https://athprotocol.dev/docs/sdk/python) (when published)
- [Examples in this repo](https://github.com/ath-protocol/python-sdk/tree/main/examples)

## License

See [LICENSE](LICENSE) (OpenATH Open Source License).
