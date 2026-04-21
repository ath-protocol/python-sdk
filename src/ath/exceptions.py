"""ATH client exceptions."""

from __future__ import annotations

from typing import Any


class ATHError(Exception):
    """Structured error from a failed ATH gateway/implementor request.

    Mirrors the ErrorResponse schema and the TypeScript ATHClientError.
    """

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}

    def __repr__(self) -> str:
        return f"ATHError(code={self.code!r}, message={str(self)!r}, status={self.status})"
