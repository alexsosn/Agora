from __future__ import annotations

import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = "https://sedra.bethmardutho.org/api"
DEFAULT_TIMEOUT = 20.0


class SedraAPIError(RuntimeError):
    """Raised when the public SEDRA IV API cannot return usable JSON."""


class SedraClient:
    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        *,
        timeout: float = DEFAULT_TIMEOUT,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = float(timeout)
        self.opener = opener

    def _get(self, kind: str, identifier: str | int) -> Any:
        encoded = quote(str(identifier), safe="")
        url = f"{self.base_url}/{kind}/{encoded}.json"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Agora-SEDRA/0.1 (+https://github.com/alexsosn/Agora)",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as exc:
            raise SedraAPIError(
                f"SEDRA API returned HTTP {exc.code} for {kind} {identifier!r}"
            ) from exc
        except URLError as exc:
            raise SedraAPIError(
                f"could not reach SEDRA API for {kind} {identifier!r}: {exc.reason}"
            ) from exc
        except OSError as exc:
            raise SedraAPIError(
                f"could not read SEDRA API response for {kind} {identifier!r}: {exc}"
            ) from exc

        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SedraAPIError(
                f"SEDRA API returned invalid JSON for {kind} {identifier!r}"
            ) from exc

    def lookup_word(self, query: str | int) -> Any:
        """Look up a SEDRA word ID or Syriac Unicode word form.

        SEDRA accepts numeric word IDs as well as consonantal, partially vocalized,
        and fully vocalized Syriac forms at the same endpoint. Results are returned
        without reinterpretation so callers retain the upstream grammatical data.
        """
        if isinstance(query, str):
            query = query.strip()
            if not query:
                raise ValueError("SEDRA word query must not be empty")
        elif not isinstance(query, int):
            raise ValueError("SEDRA word query must be a string or integer word ID")
        if isinstance(query, int) and query <= 0:
            raise ValueError("SEDRA word ID must be positive")
        return self._get("word", query)

    def get_lexeme(self, lexeme_id: int | str) -> Any:
        """Retrieve one SEDRA lexeme by its positive numeric ID."""
        try:
            numeric_id = int(lexeme_id)
        except (TypeError, ValueError) as exc:
            raise ValueError("SEDRA lexeme ID must be a positive integer") from exc
        if numeric_id <= 0 or str(lexeme_id).strip() != str(numeric_id):
            raise ValueError("SEDRA lexeme ID must be a positive integer")
        return self._get("lexeme", numeric_id)
