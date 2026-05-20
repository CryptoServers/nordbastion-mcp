"""Thin async HTTP client for the NordBastion REST API (v1).

Auth is a single bearer credential read from the ``NORDBASTION_API_KEY``
environment variable — a long-lived API key (``nb_live_*``) minted in the
panel or via ``create_api_key``, or an OAuth 2.1 access token (``nb_at_*``).
Public endpoints (catalog, transparency, billing/coins …) work with no key.
"""

from __future__ import annotations

import os
from typing import Any

import httpx

from ._version import __version__

DEFAULT_BASE_URL = "https://nordbastion.com/v1"
ENV_API_KEY = "NORDBASTION_API_KEY"
ENV_BASE_URL = "NORDBASTION_BASE_URL"


class NordBastionError(RuntimeError):
    """Raised when the API returns a 4xx/5xx response."""

    def __init__(self, status: int, payload: Any) -> None:
        self.status = status
        self.payload = payload
        super().__init__(f"NordBastion API error {status}: {payload!r}")


class NordBastionClient:
    """Minimal async wrapper around ``https://nordbastion.com/v1``."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else os.environ.get(ENV_API_KEY)
        self.base_url = (
            base_url or os.environ.get(ENV_BASE_URL) or DEFAULT_BASE_URL
        ).rstrip("/")
        self.timeout = timeout

    @property
    def authenticated(self) -> bool:
        return bool(self.api_key)

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": f"nordbastion-mcp/{__version__} (+https://nordbastion.com)",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def request(
        self,
        method: str,
        path: str,
        *,
        query: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.request(
                method.upper(),
                url,
                params=query or None,
                json=body if body else None,
                headers=self._headers(),
            )
        content_type = resp.headers.get("content-type", "")
        if "application/json" in content_type:
            data: Any = resp.json()
        else:
            data = {"raw": resp.text}
        if resp.status_code >= 400:
            raise NordBastionError(resp.status_code, data)
        return data
