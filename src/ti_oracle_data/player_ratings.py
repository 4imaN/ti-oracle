from __future__ import annotations

import itertools
import json
import math
import sqlite3
import time
from collections import defaultdict


def expected_score(rating: float, opponent_rating: float) -> float:
    return 1.0 / (1.0 + math.pow(10.0, (opponent_rating - rating) / 400.0))


def _lineup(connection: sqlite3.Connection, match_id: int, side: int) -> tuple[int, ...]:
    row = connection.execute(
        "SELECT account_ids_json FROM team_roster_observations "
        "WHERE match_id=? AND team_side=?",
        (match_id, side),
    ).fetchone()
    if row is None:
        return ()
    return tuple(sorted(int(value) for value in json.loads(row[0])))


def _pair_experience(lineup: tuple[int, ...], pair_games: dict[tuple[int, int], int]) -> float:
    pairs = list(itertools.combinations(lineup, 2))
    if not pairs:
        return 0.0
    return sum(pair_games[pair] for pair in pairs) / len(pairs)


def rebuild_player_ratings(
    connection: sqlite3.Connection,
    team_aliases: dict[int, int] | None = None,
    k_factor: float = 24.0,
) -> tuple[int, int]:
    aliases = team_aliases or {}
    connection.execute("DELETE FROM player_rating_history")
    connection.execute("DELETE FROM map_roster_features")
    ratings: dict[int, float] = defaultdict(lambda: 1500.0)
    games: dict[int, int] = defaultdict(int)
    lineup_games: dict[tuple[int, ...], int] = defaultdict(int)
    pair_games: dict[tuple[int, int], int] = defaultdict(int)
    last_lineup: dict[int, set[int]] = {}
    created_at = int(time.time())
    player_rows = 0
    map_rows = 0

    matches = connection.execute(
        """
        SELECT match_id, start_time, radiant_team_id, dire_team_id, radiant_win
        FROM pro_matches
        WHERE detailed=1 AND radiant_team_id IS NOT NULL AND dire_team_id IS NOT NULL
        ORDER BY start_time, match_id
        """
    )
    for match in matches:
        match_id = int(match["match_id"])
        radiant = _lineup(connection, match_id, 0)
        dire = _lineup(connection, match_id, 1)
        if len(radiant) != 5 or len(dire) != 5:
            continue
        radiant_team = aliases.get(int(match["radiant_team_id"]), int(match["radiant_team_id"]))
        dire_team = aliases.get(int(match["dire_team_id"]), int(match["dire_team_id"]))
        radiant_rating = sum(ratings[player] for player in radiant) / 5.0
        dire_rating = sum(ratings[player] for player in dire) / 5.0
        probability = expected_score(radiant_rating, dire_rating)
        radiant_win = int(match["radiant_win"])
        radiant_previous = last_lineup.get(radiant_team, set())
        dire_previous = last_lineup.get(dire_team, set())

        connection.execute(
            """
            INSERT INTO map_roster_features VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            (
                match_id,
                int(match["start_time"]),
                radiant_team,
                dire_team,
                radiant_rating,
                dire_rating,
                radiant_rating - dire_rating,
                probability,
                sum(games[player] for player in radiant) / 5.0,
                sum(games[player] for player in dire) / 5.0,
                lineup_games[radiant],
                lineup_games[dire],
                _pair_experience(radiant, pair_games),
                _pair_experience(dire, pair_games),
                len(set(radiant) & radiant_previous),
                len(set(dire) & dire_previous),
                sum(games[player] < 5 for player in radiant),
                sum(games[player] < 5 for player in dire),
                radiant_win,
                created_at,
            ),
        )
        map_rows += 1

        radiant_delta = k_factor * (radiant_win - probability)
        dire_delta = -radiant_delta
        for lineup, team_id, won, delta, expected in (
            (radiant, radiant_team, radiant_win, radiant_delta, probability),
            (dire, dire_team, 1 - radiant_win, dire_delta, 1.0 - probability),
        ):
            for player in lineup:
                before = ratings[player]
                connection.execute(
                    "INSERT INTO player_rating_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        match_id,
                        player,
                        team_id,
                        before,
                        before + delta,
                        games[player],
                        expected,
                        won,
                        created_at,
                    ),
                )
                ratings[player] = before + delta
                games[player] += 1
                player_rows += 1

        for lineup in (radiant, dire):
            lineup_games[lineup] += 1
            for pair in itertools.combinations(lineup, 2):
                pair_games[pair] += 1
        last_lineup[radiant_team] = set(radiant)
        last_lineup[dire_team] = set(dire)

    return player_rows, map_rows
