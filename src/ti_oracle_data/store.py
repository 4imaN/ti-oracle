from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager
from importlib.resources import files
from pathlib import Path
from typing import Any, Iterator


def compact_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


class Store:
    def __init__(self, path: Path) -> None:
        self.path = path

    def connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        return connection

    def initialize(self) -> None:
        schema = files("ti_oracle_data").joinpath("schema.sql").read_text()
        with self.connect() as connection:
            connection.executescript(schema)

    @contextmanager
    def run(self, source: str, entity: str) -> Iterator[tuple[sqlite3.Connection, int]]:
        started_at = int(time.time())
        connection = self.connect()
        cursor = connection.execute(
            "INSERT INTO ingestion_runs(source, entity, started_at, status) VALUES (?, ?, ?, ?)",
            (source, entity, started_at, "running"),
        )
        run_id = int(cursor.lastrowid)
        connection.commit()
        try:
            yield connection, run_id
        except BaseException as exc:
            connection.execute(
                "UPDATE ingestion_runs SET completed_at=?, status=?, error=? WHERE id=?",
                (int(time.time()), "failed", str(exc), run_id),
            )
            connection.commit()
            raise
        else:
            connection.execute(
                "UPDATE ingestion_runs SET completed_at=?, status=? WHERE id=?",
                (int(time.time()), "completed", run_id),
            )
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def add_run_rows(connection: sqlite3.Connection, run_id: int, count: int) -> None:
        connection.execute(
            "UPDATE ingestion_runs SET rows_written=rows_written+? WHERE id=?",
            (count, run_id),
        )

    @staticmethod
    def upsert_pro_match(connection: sqlite3.Connection, match: dict[str, Any]) -> None:
        now = int(time.time())
        connection.execute(
            """
            INSERT INTO pro_matches(
                match_id, start_time, duration, patch, version, league_id, league_name,
                series_id, series_type, radiant_team_id, radiant_name, dire_team_id,
                dire_name, radiant_score, dire_score, radiant_win, detailed, source,
                updated_at, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'opendota', ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                start_time=excluded.start_time,
                duration=COALESCE(excluded.duration, pro_matches.duration),
                patch=COALESCE(excluded.patch, pro_matches.patch),
                version=COALESCE(excluded.version, pro_matches.version),
                league_id=COALESCE(excluded.league_id, pro_matches.league_id),
                league_name=COALESCE(excluded.league_name, pro_matches.league_name),
                series_id=COALESCE(excluded.series_id, pro_matches.series_id),
                series_type=COALESCE(excluded.series_type, pro_matches.series_type),
                radiant_team_id=COALESCE(excluded.radiant_team_id, pro_matches.radiant_team_id),
                radiant_name=COALESCE(excluded.radiant_name, pro_matches.radiant_name),
                dire_team_id=COALESCE(excluded.dire_team_id, pro_matches.dire_team_id),
                dire_name=COALESCE(excluded.dire_name, pro_matches.dire_name),
                radiant_score=COALESCE(excluded.radiant_score, pro_matches.radiant_score),
                dire_score=COALESCE(excluded.dire_score, pro_matches.dire_score),
                radiant_win=excluded.radiant_win,
                detailed=MAX(pro_matches.detailed, excluded.detailed),
                updated_at=excluded.updated_at,
                raw_json=CASE
                    WHEN excluded.detailed=1 OR pro_matches.detailed=0
                    THEN excluded.raw_json
                    ELSE pro_matches.raw_json
                END
            """,
            (
                int(match["match_id"]), int(match["start_time"]), match.get("duration"),
                match.get("patch"), match.get("version"), match.get("leagueid"),
                match.get("league_name"), match.get("series_id"), match.get("series_type"),
                match.get("radiant_team_id"), match.get("radiant_name"),
                match.get("dire_team_id"), match.get("dire_name"), match.get("radiant_score"),
                match.get("dire_score"), int(bool(match.get("radiant_win"))),
                int(bool(match.get("players"))), now, compact_json(match),
            ),
        )

    @staticmethod
    def upsert_match_detail(connection: sqlite3.Connection, match: dict[str, Any]) -> None:
        Store.upsert_pro_match(connection, match)
        match_id = int(match["match_id"])
        for team_key in ("radiant_team", "dire_team"):
            team = match.get(team_key)
            if team and team.get("team_id"):
                Store.upsert_team(connection, team)

        connection.execute("DELETE FROM match_players WHERE match_id=?", (match_id,))
        for player in match.get("players") or []:
            slot = int(player["player_slot"])
            connection.execute(
                """
                INSERT INTO match_players(
                    match_id, account_id, player_slot, team_side, player_name, persona_name,
                    hero_id, lane_role, is_roaming, kills, deaths, assists, gold_per_min,
                    xp_per_min, last_hits, denies, net_worth, hero_damage, tower_damage,
                    hero_healing, stuns, observer_wards, sentry_wards, camps_stacked,
                    rune_pickups, teamfight_participation, firstblood_claimed, raw_json
                ) VALUES (
                    ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    match_id, player.get("account_id"), slot, int(slot >= 128), player.get("name"),
                    player.get("personaname"), int(player["hero_id"]), player.get("lane_role"),
                    int(bool(player.get("is_roaming"))), player.get("kills"), player.get("deaths"),
                    player.get("assists"), player.get("gold_per_min"), player.get("xp_per_min"),
                    player.get("last_hits"), player.get("denies"), player.get("net_worth"),
                    player.get("hero_damage"), player.get("tower_damage"), player.get("hero_healing"),
                    player.get("stuns"), player.get("obs_placed"), player.get("sen_placed"),
                    player.get("camps_stacked"), player.get("rune_pickups"),
                    player.get("teamfight_participation"), player.get("firstblood_claimed"),
                    compact_json(player),
                ),
            )

        connection.execute("DELETE FROM picks_bans WHERE match_id=?", (match_id,))
        for event in match.get("picks_bans") or []:
            connection.execute(
                "INSERT INTO picks_bans VALUES (?, ?, ?, ?, ?, ?)",
                (
                    match_id, int(event["order"]), int(event["team"]),
                    int(bool(event["is_pick"])), int(event["hero_id"]), compact_json(event),
                ),
            )

    @staticmethod
    def upsert_team(connection: sqlite3.Connection, team: dict[str, Any]) -> None:
        now = int(time.time())
        team_id = team.get("team_id") or team.get("team_id")
        if not team_id:
            return
        connection.execute(
            """
            INSERT INTO teams VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'opendota', ?, ?)
            ON CONFLICT(team_id) DO UPDATE SET
                name=COALESCE(excluded.name, teams.name), tag=COALESCE(excluded.tag, teams.tag),
                logo_url=COALESCE(excluded.logo_url, teams.logo_url),
                rating=COALESCE(excluded.rating, teams.rating), wins=COALESCE(excluded.wins, teams.wins),
                losses=COALESCE(excluded.losses, teams.losses),
                last_match_time=COALESCE(excluded.last_match_time, teams.last_match_time),
                updated_at=excluded.updated_at, raw_json=excluded.raw_json
            """,
            (
                int(team_id), team.get("name"), team.get("tag"), team.get("logo_url"),
                team.get("rating"), team.get("wins"), team.get("losses"),
                team.get("last_match_time"), now, compact_json(team),
            ),
        )

    @staticmethod
    def upsert_league(connection: sqlite3.Connection, league: dict[str, Any]) -> None:
        now = int(time.time())
        league_id = league.get("leagueid") or league.get("league_id")
        if not league_id or not league.get("name"):
            return
        connection.execute(
            """
            INSERT INTO leagues VALUES (?, ?, ?, ?, 'opendota', ?, ?)
            ON CONFLICT(league_id) DO UPDATE SET
                name=excluded.name, tier=excluded.tier, banner=excluded.banner,
                updated_at=excluded.updated_at, raw_json=excluded.raw_json
            """,
            (
                int(league_id), league["name"], league.get("tier"), league.get("banner"),
                now, compact_json(league),
            ),
        )

    @staticmethod
    def upsert_patch(
        connection: sqlite3.Connection, patch_id: int, patch: dict[str, Any]
    ) -> None:
        now = int(time.time())
        connection.execute(
            """
            INSERT INTO patches VALUES (?, ?, ?, 'opendota', ?, ?)
            ON CONFLICT(patch_id) DO UPDATE SET
                name=excluded.name, released_at=excluded.released_at,
                updated_at=excluded.updated_at, raw_json=excluded.raw_json
            """,
            (
                patch_id, patch["name"], patch.get("date"), now, compact_json(patch),
            ),
        )

    @staticmethod
    def upsert_player(connection: sqlite3.Connection, player: dict[str, Any]) -> None:
        now = int(time.time())
        connection.execute(
            """
            INSERT INTO players VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'opendota', ?, ?)
            ON CONFLICT(account_id) DO UPDATE SET
                steam_id=excluded.steam_id, handle=excluded.handle,
                persona_name=excluded.persona_name, country_code=excluded.country_code,
                fantasy_role=excluded.fantasy_role, current_team_id=excluded.current_team_id,
                avatar_url=excluded.avatar_url, profile_url=excluded.profile_url,
                last_match_time=excluded.last_match_time, updated_at=excluded.updated_at,
                raw_json=excluded.raw_json
            """,
            (
                int(player["account_id"]), player.get("steamid"), player.get("name"),
                player.get("personaname"), player.get("country_code") or player.get("loccountrycode"),
                player.get("fantasy_role"), player.get("team_id"),
                player.get("avatarfull") or player.get("avatar"), player.get("profileurl"),
                player.get("last_match_time"), now, compact_json(player),
            ),
        )

    @staticmethod
    def upsert_hero_snapshot(
        connection: sqlite3.Connection, hero: dict[str, Any], collected_at: int
    ) -> int:
        connection.execute(
            """
            INSERT INTO heroes VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'opendota', ?, ?)
            ON CONFLICT(hero_id) DO UPDATE SET
                internal_name=excluded.internal_name, localized_name=excluded.localized_name,
                primary_attribute=excluded.primary_attribute, attack_type=excluded.attack_type,
                roles_json=excluded.roles_json, image_path=excluded.image_path,
                icon_path=excluded.icon_path, updated_at=excluded.updated_at,
                raw_json=excluded.raw_json
            """,
            (
                int(hero["id"]), hero["name"], hero["localized_name"], hero.get("primary_attr"),
                hero.get("attack_type"), compact_json(hero.get("roles") or []), hero.get("img"),
                hero.get("icon"), collected_at, compact_json(hero),
            ),
        )
        rows = 1
        for bracket in range(1, 9):
            picks = int(hero.get(f"{bracket}_pick") or 0)
            wins = int(hero.get(f"{bracket}_win") or 0)
            connection.execute(
                "INSERT OR REPLACE INTO hero_meta_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    collected_at, int(hero["id"]), bracket, picks, wins,
                    hero.get("pro_pick"), hero.get("pro_win"), hero.get("pro_ban"),
                    compact_json(hero),
                ),
            )
            rows += 1
        return rows
