from __future__ import annotations

import math
import sqlite3
import time
import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass
class EloState:
    rating: float = 1500.0
    games: int = 0


TIER_K = {
    "premium": 36.0,
    "professional": 28.0,
    "amateur": 20.0,
    "excluded": 12.0,
}


def expected_score(rating: float, opponent_rating: float) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (opponent_rating - rating) / 400.0))


def load_team_aliases(participants_path: Path | None) -> dict[int, int]:
    if participants_path is None:
        return {}
    aliases: dict[int, int] = {}
    with participants_path.open(newline="", encoding="utf-8") as handle:
        for participant in csv.DictReader(handle):
            team_ids = [int(value) for value in participant["source_team_ids"].split("|")]
            canonical_id = team_ids[0]
            for team_id in team_ids:
                aliases[team_id] = canonical_id
    return aliases


def rebuild_elo(
    connection: sqlite3.Connection,
    since_epoch: int,
    team_aliases: dict[int, int] | None = None,
) -> int:
    """Build a transparent map-level baseline; Glicko-2 follows after data QA."""
    connection.execute("DELETE FROM team_rating_history")
    connection.execute("DELETE FROM map_rating_features")
    ratings: dict[int, EloState] = {}
    matches = connection.execute(
        """
        SELECT m.match_id, m.start_time, m.patch, m.league_id,
               m.radiant_team_id, m.dire_team_id, m.radiant_win,
               COALESCE(l.tier, 'professional') AS tier
        FROM pro_matches m
        LEFT JOIN leagues l ON l.league_id = m.league_id
        WHERE m.start_time >= ?
          AND m.radiant_team_id IS NOT NULL AND m.radiant_team_id > 0
          AND m.dire_team_id IS NOT NULL AND m.dire_team_id > 0
          AND m.radiant_team_id != m.dire_team_id
        ORDER BY m.start_time, m.match_id
        """,
        (since_epoch,),
    )
    written = 0
    created_at = int(time.time())
    for match in matches:
        aliases = team_aliases or {}
        radiant_id = aliases.get(
            int(match["radiant_team_id"]), int(match["radiant_team_id"])
        )
        dire_id = aliases.get(int(match["dire_team_id"]), int(match["dire_team_id"]))
        if radiant_id == dire_id:
            continue
        radiant = ratings.setdefault(radiant_id, EloState())
        dire = ratings.setdefault(dire_id, EloState())
        radiant_expected = expected_score(radiant.rating, dire.rating)
        dire_expected = 1.0 - radiant_expected
        radiant_actual = float(bool(match["radiant_win"]))
        dire_actual = 1.0 - radiant_actual
        base_k = TIER_K.get(match["tier"], 24.0)
        radiant_k = base_k * (1.25 if radiant.games < 20 else 1.0)
        dire_k = base_k * (1.25 if dire.games < 20 else 1.0)
        radiant_before, dire_before = radiant.rating, dire.rating
        radiant_games_before, dire_games_before = radiant.games, dire.games
        radiant.rating += radiant_k * (radiant_actual - radiant_expected)
        dire.rating += dire_k * (dire_actual - dire_expected)
        radiant.games += 1
        dire.games += 1
        connection.executemany(
            "INSERT INTO team_rating_history VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    int(match["match_id"]), radiant_id, radiant_before, radiant.rating,
                    dire_id, radiant_expected, radiant_actual, created_at,
                ),
                (
                    int(match["match_id"]), dire_id, dire_before, dire.rating,
                    radiant_id, dire_expected, dire_actual, created_at,
                ),
            ],
        )
        connection.execute(
            "INSERT INTO map_rating_features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                int(match["match_id"]), int(match["start_time"]), match["patch"],
                match["league_id"], match["tier"], radiant_id, dire_id,
                radiant_before, dire_before, radiant_games_before, dire_games_before,
                radiant_before - dire_before, radiant_expected, int(radiant_actual), created_at,
            ),
        )
        written += 2
    return written
