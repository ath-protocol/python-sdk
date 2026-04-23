# Python SDK for the Agent Trust Handshake (ATH)

> Give your Python AI projects trusted, standards-based access to third-party APIs.

**[中文说明（主 README）](README.md)**

## Overview

This is the official Python toolkit for the [Agent Trust Handshake](https://github.com/ath-protocol/agent-trust-handshake-protocol) protocol. It matches the public client API of the [TypeScript SDK](https://github.com/ath-protocol/typescript-sdk) and tracks the protocol JSON Schema in `schema/ath-protocol.schema.json` (vendored from the protocol repo’s `schema/0.1`).

**Requires Python 3.10+** (see `pyproject.toml`).

## Features

- Pure Python, no native system crypto dependencies beyond what your environment already provides for TLS
- Sync and async clients (`ATHGatewayClient` / `AsyncATHGatewayClient`, `ATHNativeClient` / `AsyncATHNativeClient`)
- Full type annotations (Pydantic models in `ath.types`)
- ES256 agent attestation JWTs (including unique `jti` per assertion, per current spec)
- Gateway and native deployment modes
- Easy to wrap as a LangChain / LlamaIndex tool in your own code

## Install

```bash
pip install ath-protocol-sdk
```

With Poetry:

```bash
poetry add ath-protocol-sdk
```

If that name is not found on PyPI, use the current distribution name from `pyproject.toml`: **`ath-sdk`**.

```bash
pip install ath-sdk
```

Local development:

```bash
pip install -e '.[dev]'
```

## Quick start (gateway mode)

Typical flow: **discover → register → authorize → exchange_token → proxy → revoke**.

### 1. Create a client

```python
from ath import ATHGatewayClient

client = ATHGatewayClient(
    "https://your-ath-gateway.com",
    "https://your-agent.example.com/.well-known/agent.json",
    open("agent-ec-private.pem").read(),
    key_id="default",
)
```

### 2. Register, authorize, exchange token

```python
client.discover()

client.register(
    developer={"name": "Example Org", "id": "dev-001"},
    providers=[{"provider_id": "target-provider", "scopes": ["user:read"]}],
    purpose="Describe why you need access",
)

auth = client.authorize("target-provider", ["user:read"])
# After the user completes OAuth at auth.authorization_url, use the returned
# authorization `code` from your callback together with ath_session_id:
token = client.exchange_token(code="...", session_id=auth.ath_session_id)
print(token.access_token)
```

### 3. Call upstream APIs and revoke

```python
data = client.proxy("target-provider", "GET", "/v1/profile")
print(data)

client.revoke()
```

Use **`AsyncATHGatewayClient`** / **`AsyncATHNativeClient`** for async/await. For services that implement ATH natively, use **`ATHNativeClient`**: `discover()` then `api(method, path)`.

## Protocol notes (TS parity)

Current client behavior aligns with `@ath-protocol/client` and the bundled schema:

- **`authorize`**: sends `state` with at least 128 bits of entropy (hex).
- **`exchange_token`**: sends a fresh **`agent_attestation`** with **`aud`** set to the **token endpoint URL** (`{base}/ath/token`).
- **`revoke`**: when acting as the registered agent, sends **`client_id`**, **`client_secret`**, and **`token`**.

## LangChain-style integration

Wrap `register` / `authorize` / `exchange_token` / `proxy` inside a Tool your agent can call. See the Chinese [README.md](README.md) for a short structural example and [examples/](examples/) for a runnable demo.

## Documentation

- [Python SDK docs](https://athprotocol.dev/docs/sdk/python)
- [LangChain integration](https://athprotocol.dev/docs/integrations/langchain)
- [Examples in this repository](https://github.com/ath-protocol/python-sdk/tree/main/examples)

## Architecture

```
Your Python app → this SDK → ATH gateway → upstream APIs
```

## License

[OpenATH Open Source License](LICENSE).
