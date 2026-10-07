from __future__ import annotations

from typing import Any, Iterator

from .http import JsonHttpClient


class OpenDotaClient:
    def __init__(self, http: JsonHttpClient, api_key: str | None = None) -> None:
        self.http = http
        self.api_key = api_key

    def _params(self, **params: Any) -> dict[str, Any]:
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def hero_stats(self) -> list[dict[str, Any]]:
        return self.http.get("heroStats", self._params())

    def pro_players(self) -> list[dict[str, Any]]:
        return self.http.get("proPlayers", self._params())

    def teams(self) -> list[dict[str, Any]]:
        return self.http.get("teams", self._params())

    def leagues(self) -> list[dict[str, Any]]:
        return self.http.get("leagues", self._params())

    def league_matches(self, league_id: int) -> list[dict[str, Any]]:
        return self.http.get(f"leagues/{league_id}/matches", self._params())

    def patches(self) -> list[dict[str, Any]]:
        return self.http.get("constants/patch", self._params())

    def match(self, match_id: int) -> dict[str, Any]:
        return self.http.get(f"matches/{match_id}", self._params())

    def pro_match_pages(self, since_epoch: int) -> Iterator[list[dict[str, Any]]]:
        less_than_match_id: int | None = None
        while True:
            page = self.http.get(
                "proMatches",
                self._params(less_than_match_id=less_than_match_id),
            )
            if not page:
                return
            yield page

            oldest = min(page, key=lambda match: int(match["match_id"]))
            if int(oldest.get("start_time") or 0) < since_epoch:
                return
            next_cursor = int(oldest["match_id"])
            if next_cursor == less_than_match_id:
                return
            less_than_match_id = next_cursor
