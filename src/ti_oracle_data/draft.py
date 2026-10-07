from __future__ import annotations

import itertools
import sqlite3
import time
from collections import Counter, defaultdict


def _rate(wins: int, games: int, prior_games: float = 8.0) -> float:
    return (wins + 0.5 * prior_games) / (games + prior_games)


def rebuild_draft_stats(
    connection: sqlite3.Connection,
    team_aliases: dict[int, int] | None = None,
) -> tuple[int, int, int]:
    aliases = team_aliases or {}
    connection.execute("DELETE FROM hero_matchup_stats")
    connection.execute("DELETE FROM hero_synergy_stats")
    connection.execute("DELETE FROM team_hero_stats")
    matchup: dict[tuple[int, int, int], list[int]] = defaultdict(lambda: [0, 0])
    synergy: dict[tuple[int, int, int], list[int]] = defaultdict(lambda: [0, 0])
    team_hero: dict[tuple[int, int, int], list[int]] = defaultdict(lambda: [0, 0, 0])
    created_at = int(time.time())

    matches = connection.execute(
        """
        SELECT match_id, COALESCE(patch, 0) AS patch, radiant_team_id,
               dire_team_id, radiant_win
        FROM pro_matches WHERE detailed=1 ORDER BY start_time, match_id
        """
    )
    for match in matches:
        match_id = int(match["match_id"])
        patch = int(match["patch"])
        sides = {0: [], 1: []}
        for player in connection.execute(
            "SELECT team_side, hero_id FROM match_players WHERE match_id=?",
            (match_id,),
        ):
            sides[int(player["team_side"])].append(int(player["hero_id"]))
        if len(sides[0]) != 5 or len(sides[1]) != 5:
            continue
        radiant_win = int(match["radiant_win"])
        for side, opponent_side in ((0, 1), (1, 0)):
            won = radiant_win if side == 0 else 1 - radiant_win
            for hero in sides[side]:
                for opponent in sides[opponent_side]:
                    matchup[(patch, hero, opponent)][0] += 1
                    matchup[(patch, hero, opponent)][1] += won
            for first, second in itertools.combinations(sorted(sides[side]), 2):
                for hero, ally in ((first, second), (second, first)):
                    synergy[(patch, hero, ally)][0] += 1
                    synergy[(patch, hero, ally)][1] += won
            raw_team = match["radiant_team_id"] if side == 0 else match["dire_team_id"]
            if raw_team is not None:
                team_id = aliases.get(int(raw_team), int(raw_team))
                for hero in sides[side]:
                    team_hero[(patch, team_id, hero)][0] += 1
                    team_hero[(patch, team_id, hero)][1] += won

        for event in connection.execute(
            "SELECT team_side, hero_id FROM picks_bans WHERE match_id=? AND is_pick=0",
            (match_id,),
        ):
            side = int(event["team_side"])
            raw_team = match["radiant_team_id"] if side == 0 else match["dire_team_id"]
            if raw_team is not None:
                team_id = aliases.get(int(raw_team), int(raw_team))
                team_hero[(patch, team_id, int(event["hero_id"]))][2] += 1

    connection.executemany(
        "INSERT INTO hero_matchup_stats VALUES (?, ?, ?, ?, ?, ?)",
        [(*key, values[0], values[1], created_at) for key, values in matchup.items()],
    )
    connection.executemany(
        "INSERT INTO hero_synergy_stats VALUES (?, ?, ?, ?, ?, ?)",
        [(*key, values[0], values[1], created_at) for key, values in synergy.items()],
    )
    connection.executemany(
        "INSERT INTO team_hero_stats VALUES (?, ?, ?, ?, ?, ?, ?)",
        [(*key, values[0], values[1], values[2], created_at) for key, values in team_hero.items()],
    )
    return len(matchup), len(synergy), len(team_hero)


def recommend_counters(
    connection: sqlite3.Connection,
    enemy_hero_ids: list[int],
    allied_hero_ids: list[int] | None = None,
    patch: int | None = None,
    limit: int = 10,
) -> list[dict[str, object]]:
    allies = allied_hero_ids or []
    selected = set(enemy_hero_ids) | set(allies)
    if not enemy_hero_ids:
        raise ValueError("at least one enemy hero is required")
    if patch is None:
        row = connection.execute("SELECT MAX(patch) FROM hero_matchup_stats").fetchone()
        patch = int(row[0]) if row and row[0] is not None else 0
    candidates = connection.execute(
        """
        SELECT h.hero_id, h.localized_name, h.image_path,
               SUM(CASE WHEN mp.team_side=0 THEN m.radiant_win ELSE 1-m.radiant_win END) wins,
               COUNT(*) games
        FROM heroes h
        JOIN match_players mp ON mp.hero_id=h.hero_id
        JOIN pro_matches m ON m.match_id=mp.match_id AND m.patch=?
        GROUP BY h.hero_id
        HAVING COUNT(*) >= 3
        """,
        (patch,),
    )
    output = []
    for candidate in candidates:
        hero_id = int(candidate["hero_id"])
        if hero_id in selected:
            continue
        matchup_rows = [
            connection.execute(
                "SELECT games, wins FROM hero_matchup_stats "
                "WHERE patch=? AND hero_id=? AND opponent_hero_id=?",
                (patch, hero_id, enemy),
            ).fetchone()
            for enemy in enemy_hero_ids
        ]
        available_matchups = [row for row in matchup_rows if row]
        matchup_games = sum(int(row["games"]) for row in available_matchups)
        matchup_rate = (
            sum(_rate(int(row["wins"]), int(row["games"])) for row in available_matchups)
            / len(available_matchups)
            if available_matchups
            else 0.5
        )
        synergy_rows = [
            connection.execute(
                "SELECT games, wins FROM hero_synergy_stats "
                "WHERE patch=? AND hero_id=? AND ally_hero_id=?",
                (patch, hero_id, ally),
            ).fetchone()
            for ally in allies
        ]
        synergy_rate = (
            sum(_rate(int(row["wins"]), int(row["games"])) for row in synergy_rows if row)
            / len(synergy_rows)
            if allies and all(synergy_rows)
            else 0.5
        )
        meta_rate = _rate(int(candidate["wins"]), int(candidate["games"]), 20.0)
        confidence = 1.0 - math_exp(-matchup_games / 30.0)
        counter_component = 0.5 + (matchup_rate - 0.5) * confidence
        score = 0.60 * counter_component + 0.25 * meta_rate + 0.15 * synergy_rate
        output.append(
            {
                "hero_id": hero_id,
                "hero": candidate["localized_name"],
                "image_path": candidate["image_path"],
                "patch": patch,
                "score": score,
                "matchup_rate": matchup_rate,
                "matchup_games": matchup_games,
                "enemy_coverage": len(available_matchups) / len(enemy_hero_ids),
                "meta_rate": meta_rate,
                "meta_games": int(candidate["games"]),
                "synergy_rate": synergy_rate,
            }
        )
    return sorted(
        output,
        key=lambda row: (float(row["score"]), int(row["matchup_games"])),
        reverse=True,
    )[:limit]


def math_exp(value: float) -> float:
    # Kept local so recommendation math remains easy to unit test without NumPy.
    import math

    return math.exp(value)
