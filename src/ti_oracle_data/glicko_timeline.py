from __future__ import annotations

import datetime as dt
import sqlite3
import time
from collections import defaultdict

from .glicko2 import (
    GlickoRating,
    GlickoResult,
    advance_inactivity,
    rate_period,
    win_probability,
)


def rebuild_glicko_timeline(
    connection: sqlite3.Connection,
    since_epoch: int,
    team_aliases: dict[int, int] | None = None,
) -> int:
    aliases = team_aliases or {}
    connection.execute("DELETE FROM team_glicko_history")
    connection.execute("DELETE FROM map_glicko_features")
    matches = list(
        connection.execute(
            """
            SELECT match_id, start_time, radiant_team_id, dire_team_id, radiant_win
            FROM pro_matches
            WHERE start_time >= ?
              AND radiant_team_id IS NOT NULL AND radiant_team_id > 0
              AND dire_team_id IS NOT NULL AND dire_team_id > 0
              AND radiant_team_id != dire_team_id
            ORDER BY start_time, match_id
            """,
            (since_epoch,),
        )
    )
    by_day: dict[dt.date, list[sqlite3.Row]] = defaultdict(list)
    for match in matches:
        day = dt.datetime.fromtimestamp(int(match["start_time"]), tz=dt.UTC).date()
        by_day[day].append(match)

    states: dict[int, GlickoRating] = {}
    last_active: dict[int, dt.date] = {}
    created_at = int(time.time())
    written = 0
    for day in sorted(by_day):
        contests: dict[int, list[tuple[int, float]]] = defaultdict(list)
        for match in by_day[day]:
            radiant = aliases.get(
                int(match["radiant_team_id"]), int(match["radiant_team_id"])
            )
            dire = aliases.get(int(match["dire_team_id"]), int(match["dire_team_id"]))
            if radiant == dire:
                continue
            radiant_score = float(bool(match["radiant_win"]))
            contests[radiant].append((dire, radiant_score))
            contests[dire].append((radiant, 1.0 - radiant_score))

        before: dict[int, GlickoRating] = {}
        for team_id in contests:
            state = states.get(team_id, GlickoRating())
            if team_id in last_active:
                inactive_days = max(0, (day - last_active[team_id]).days - 1)
                state = advance_inactivity(state, inactive_days)
            before[team_id] = state

        after: dict[int, GlickoRating] = {}
        for team_id, games in contests.items():
            results = [
                GlickoResult(before.get(opponent_id, states.get(opponent_id, GlickoRating())), score)
                for opponent_id, score in games
            ]
            after[team_id] = rate_period(before[team_id], results)

        for match in by_day[day]:
            radiant = aliases.get(
                int(match["radiant_team_id"]), int(match["radiant_team_id"])
            )
            dire = aliases.get(int(match["dire_team_id"]), int(match["dire_team_id"]))
            if radiant == dire or radiant not in before or dire not in before:
                continue
            radiant_before = before[radiant]
            dire_before = before[dire]
            connection.execute(
                "INSERT INTO map_glicko_features VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(match["match_id"]), int(match["start_time"]), radiant, dire,
                    radiant_before.rating, dire_before.rating, radiant_before.deviation,
                    dire_before.deviation, radiant_before.rating - dire_before.rating,
                    win_probability(radiant_before, dire_before),
                    int(bool(match["radiant_win"])), created_at,
                ),
            )

        for team_id, games in contests.items():
            old = before[team_id]
            new = after[team_id]
            connection.execute(
                "INSERT INTO team_glicko_history VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    day.isoformat(), team_id, old.rating, old.deviation, old.volatility,
                    new.rating, new.deviation, new.volatility, len(games),
                    sum(score for _, score in games), created_at,
                ),
            )
            states[team_id] = new
            last_active[team_id] = day
            written += 1
    return written
