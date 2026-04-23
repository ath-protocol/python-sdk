"""Shared test fixtures."""

from __future__ import annotations

import atexit
import os
import subprocess
import time
import warnings
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

_E2E_STACK_PROC: subprocess.Popen[bytes] | None = None


def _e2e_gateway_url() -> str:
    return os.environ.get("ATH_GATEWAY_URL", "http://127.0.0.1:18101")


def _e2e_stack_ready(url: str, timeout_s: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = httpx.get(f"{url.rstrip('/')}/health", timeout=2)
            if r.is_success:
                return True
        except Exception:
            pass
        time.sleep(0.2)
    return False


def pytest_sessionstart(session: pytest.Session) -> None:
    """Optionally start the Node E2E gateway stack (real server + mock OAuth only)."""
    global _E2E_STACK_PROC
    if os.environ.get("ATH_E2E_AUTO_STACK") != "1":
        return
    if os.environ.get("ATH_E2E_NO_AUTO_STACK") == "1":
        return

    gw = _e2e_gateway_url()
    if _e2e_stack_ready(gw, timeout_s=2.0):
        return

    repo_root = Path(__file__).resolve().parents[1]
    ts = repo_root / "typescript-sdk"
    if not (ts / "package.json").exists():
        warnings.warn(
            "typescript-sdk/ missing — cannot auto-start E2E stack. "
            "Clone ath-protocol/typescript-sdk or run node scripts/e2e_gateway_stack.mjs manually.",
            UserWarning,
            stacklevel=2,
        )
        return

    subprocess.run(
        ["pnpm", "install"],
        cwd=ts,
        check=False,
        capture_output=True,
        timeout=300,
    )
    br = subprocess.run(
        ["pnpm", "run", "build"],
        cwd=ts,
        check=False,
        capture_output=True,
        timeout=300,
    )
    if br.returncode != 0:
        warnings.warn(
            "pnpm -C typescript-sdk run build failed — E2E stack not started. "
            f"stderr: {br.stderr.decode(errors='replace')[:500]}",
            UserWarning,
            stacklevel=2,
        )
        return

    env = os.environ.copy()
    env.setdefault("OAUTH_PORT", "18100")
    env.setdefault("GATEWAY_PORT", "18101")
    env.setdefault("UPSTREAM_PORT", "18102")
    env.setdefault("ATH_GATEWAY_URL", f"http://127.0.0.1:{env['GATEWAY_PORT']}")
    _E2E_STACK_PROC = subprocess.Popen(
        ["node", str(repo_root / "scripts" / "e2e_gateway_stack.mjs")],
        cwd=repo_root,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        env=env,
    )

    def _stop() -> None:
        global _E2E_STACK_PROC  # noqa: PLW0603
        if _E2E_STACK_PROC and _E2E_STACK_PROC.poll() is None:
            _E2E_STACK_PROC.terminate()
            try:
                _E2E_STACK_PROC.wait(timeout=5)
            except subprocess.TimeoutExpired:
                _E2E_STACK_PROC.kill()
        _E2E_STACK_PROC = None

    atexit.register(_stop)

    if not _e2e_stack_ready(gw, timeout_s=20.0):
        err = ""
        proc = _E2E_STACK_PROC
        if proc and proc.stderr:
            try:
                err = proc.stderr.read().decode(errors="replace")[:800]
            except Exception:
                err = ""
        _stop()
        warnings.warn(
            f"E2E stack did not become healthy at {gw}. {err}",
            UserWarning,
            stacklevel=2,
        )


@pytest.fixture()
def ec_private_pem() -> str:
    """Generate a fresh EC P-256 private key in PEM format."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()


GATEWAY = "https://gw.test"
AGENT_ID = "https://agent.test/.well-known/agent.json"
