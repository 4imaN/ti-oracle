from __future__ import annotations

import json
import random
import ssl
import time
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import certifi


class DataSourceError(RuntimeError):
    pass


@dataclass
class JsonHttpClient:
    base_url: str
    timeout_seconds: float = 30.0
    delay_seconds: float = 1.1
    max_attempts: int = 5
    user_agent: str = "ti-oracle-data/0.1 (research; OpenDota consumer)"

    def get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        query = urlencode({k: v for k, v in (params or {}).items() if v is not None})
        url = f"{self.base_url.rstrip('/')}/{path.lstrip('/')}"
        if query:
            url = f"{url}?{query}"

        tls_context = ssl.create_default_context(cafile=certifi.where())
        for attempt in range(1, self.max_attempts + 1):
            request = Request(url, headers={"User-Agent": self.user_agent})
            try:
                with urlopen(
                    request, timeout=self.timeout_seconds, context=tls_context
                ) as response:
                    body = response.read().decode("utf-8")
                time.sleep(self.delay_seconds)
                return json.loads(body)
            except HTTPError as exc:
                retryable = exc.code == 429 or exc.code >= 500
                if not retryable or attempt == self.max_attempts:
                    raise DataSourceError(f"GET {url} failed with HTTP {exc.code}") from exc
                retry_after = exc.headers.get("Retry-After")
                wait = float(retry_after) if retry_after else self._backoff(attempt)
                time.sleep(wait)
            except (URLError, TimeoutError, json.JSONDecodeError) as exc:
                if attempt == self.max_attempts:
                    raise DataSourceError(f"GET {url} failed after {attempt} attempts") from exc
                time.sleep(self._backoff(attempt))

        raise AssertionError("unreachable")

    @staticmethod
    def _backoff(attempt: int) -> float:
        return min(60.0, (2 ** (attempt - 1)) + random.random())
