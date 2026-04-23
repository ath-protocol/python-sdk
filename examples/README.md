# Examples

## `demo_agent.py`

End-to-end **gateway mode** demo: discovery, registration, authorization URL, mock consent (if your gateway exposes it), token exchange, proxied request, and revocation.

**Prerequisites:** a running ATH gateway (or compatible mock) and a gateway that supports the demo flow described in the script.

```bash
export ATH_GATEWAY_URL=http://localhost:3000
python3 examples/demo_agent.py
```

The script generates an ephemeral EC P-256 private key for the run. For production, use a stable agent identity document and key management.
