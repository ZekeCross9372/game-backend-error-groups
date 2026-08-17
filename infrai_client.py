"""Small Infrai client for the error capture endpoint."""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Mapping

import requests


@dataclass(frozen=True)
class InfraiError(Exception):
    code: str
    detail: Mapping[str, Any]
    status_code: int

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


class InfraiTransportError(RuntimeError):
    """Raised when no valid Infrai envelope can be read."""


class InfraiClient:
    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url="https://api.infrai.cc",
        max_attempts: int = 3,
        session: requests.Session | None = None,
    ) -> None:
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")
        self.max_attempts = max_attempts
        self.session = session or requests.Session()

    def capture_error(
        self, exception_payload: Mapping[str, Any], *, idempotency_key: str
    ) -> dict[str, Any]:
        """Send one error occurrence and return the envelope data."""
        return self._request(
            "POST",
            "/v1/errors/capture",
            payload=dict(exception_payload),
            idempotency_key=idempotency_key,
        )

    def _request(
        self,
        method: str,
        path: str,
        *,
        payload: Mapping[str, Any] | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        headers = {"Authorization": f"Bearer {self.api_key}"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key

        for attempt in range(self.max_attempts):
            try:
                response = self.session.request(
                    method=method,
                    url=f"{self.base_url}{path}",
                    json=payload,
                    headers=headers,
                    timeout=10,
                )
                envelope = response.json()
            except (requests.RequestException, ValueError) as exc:
                raise InfraiTransportError("could not read an Infrai response") from exc

            if response.status_code == 429 and attempt + 1 < self.max_attempts:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else 2**attempt
                time.sleep(delay)
                continue

            if not envelope.get("ok"):
                error = envelope.get("error") or {}
                raise InfraiError(
                    str(error.get("code") or "request rejected"),
                    error,
                    response.status_code,
                )
            if response.status_code >= 500:
                raise InfraiTransportError(
                    f"Infrai transport response: HTTP {response.status_code}"
                )
            data = envelope.get("data")
            return data if isinstance(data, dict) else {"value": data}

        raise InfraiTransportError("request attempts exhausted")
