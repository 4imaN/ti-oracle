from __future__ import annotations

import json
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ti_oracle_data.fantasy_projection import (  # noqa: E402
    STAT_RULES,
    fantasy_stat_points,
    load_registered_roster,
)


DATABASE = PROJECT_ROOT / "data/ti_oracle.sqlite3"
PARTICIPANTS = PROJECT_ROOT / "data/reference/ti_2026_participants.csv"
ROSTER = PROJECT_ROOT / "data/reference/ti_2026_roster_positions.csv"
OUTPUT = PROJECT_ROOT / "artifacts/ti_live_fantasy_points.json"
LEAGUE_ID = 19719

BANNERS: dict[str, tuple[tuple[str, float], ...]] = {
    "Core": (("GPM", 250), ("Teamfight", 150), ("Madstones", 130)),
    "Mid": (("GPM", 160), ("Wards", 190), ("First blood", 200)),
    "Support": (("Camps stacked", 160), ("Courier kills", 200), ("Lotuses", 130)),
}

USER_SELECTION = {
    "Core": ("Yatoro", "Collapse"),
    "Mid": ("Malr1ne",),
    "Support": ("Thiolicor", "KJ"),
}


def _map_rows(
    connection: sqlite3.Connection, account_ids: list[int]
) -> dict[int, dict[int, dict[str, float]]]:
    placeholders = ",".join("?" for _ in account_ids)
    rows = connection.execute(
        f"""
        SELECT f.account_id, f.match_id, m.series_id, m.start_time, m.duration,
               e.duration_ends_in_eight AS lucky_ends_in_8,
               COALESCE(f.kills, 0) AS kills,
               COALESCE(f.deaths, 0) AS deaths,
               COALESCE(f.creep_score, 0) + COALESCE(mp.denies, 0) AS creeps,
               COALESCE(f.gold_per_min, 0) AS gold_per_min,
               COALESCE(f.madstones, 0) AS madstones,
               COALESCE(f.tower_kills, 0) AS tower_kills,
               COALESCE(f.wards_planted, 0) AS wards_planted,
               COALESCE(f.camps_stacked, 0) AS camps_stacked,
               COALESCE(f.runes_grabbed, 0) AS runes_grabbed,
               COALESCE(f.watchers_taken, 0) AS watchers_taken,
               COALESCE(f.lotus_item_uses, 0) AS lotuses,
               COALESCE(f.roshan_kills, 0) AS roshan_kills,
               COALESCE(f.teamfight_participation, 0) AS teamfight_participation,
               COALESCE(f.stuns, 0) AS stuns,
               COALESCE(f.tormentor_kills, 0) AS tormentor_kills,
               COALESCE(f.courier_kills, 0) AS courier_kills,
               COALESCE(f.first_blood, 0) AS first_blood,
               COALESCE(f.smokes_used, 0) AS smokes_used
        FROM fantasy_player_stats f
        JOIN match_players mp
          ON mp.match_id=f.match_id AND mp.player_slot=f.player_slot
        JOIN pro_matches m ON m.match_id=f.match_id
        JOIN fantasy_match_events e ON e.match_id=f.match_id
        WHERE f.account_id IN ({placeholders}) AND m.league_id=? AND m.detailed=1
        ORDER BY m.start_time, f.match_id
        """,
        [*account_ids, LEAGUE_ID],
    )
    output: dict[int, dict[int, dict[str, float]]] = defaultdict(dict)
    for row in rows:
        output[int(row["account_id"])][int(row["match_id"])] = dict(row)
    return output


def _score(metric: str, row: dict[str, float]) -> float:
    return fantasy_stat_points(metric, float(row[STAT_RULES[metric][0]]))


def _entity_result(players, role: str, maps_by_player) -> dict[str, object] | None:
    shared = set.intersection(
        *(set(maps_by_player[player.account_id]) for player in players)
    )
    if not shared:
        return None
    series_scores: dict[int, list[dict[str, object]]] = defaultdict(list)
    for match_id in shared:
        player_rows = [maps_by_player[player.account_id][match_id] for player in players]
        components = {
            metric: sum(_score(metric, row) for row in player_rows) / len(player_rows)
            * multiplier
            / 100.0
            for metric, multiplier in BANNERS[role]
        }
        base = sum(components.values())
        lucky = bool(player_rows[0]["lucky_ends_in_8"])
        series_scores[int(player_rows[0]["series_id"])].append(
            {
                "match_id": match_id,
                "base_points": base,
                "lucky_points": base * (1.21 if lucky else 1.0),
                "lucky_activated": lucky,
                "components": components,
            }
        )
    scored_series = []
    for series_id, maps in series_scores.items():
        chosen = sorted(maps, key=lambda row: float(row["lucky_points"]), reverse=True)[:2]
        scored_series.append(
            {
                "series_id": series_id,
                "maps_available": len(maps),
                "chosen_match_ids": [row["match_id"] for row in chosen],
                "base_points": sum(float(row["base_points"]) for row in chosen),
                "points_with_lucky": sum(float(row["lucky_points"]) for row in chosen),
            }
        )
    best = max(scored_series, key=lambda row: float(row["points_with_lucky"]))
    return {
        "team_key": players[0].team_key,
        "team": players[0].team_name,
        "role": role,
        "players": [player.name for player in players],
        "maps_scored": len(shared),
        "series_scored": len(scored_series),
        "best_series": best,
        "all_series": sorted(
            scored_series, key=lambda row: float(row["points_with_lucky"]), reverse=True
        ),
    }


def main() -> None:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    roster = load_registered_roster(connection, ROSTER, PARTICIPANTS)
    maps_by_player = _map_rows(connection, [player.account_id for player in roster])
    grouped = defaultdict(list)
    by_name = {}
    for player in roster:
        grouped[(player.team_key, player.role)].append(player)
        by_name[player.name] = player
    leaderboards: dict[str, list[dict[str, object]]] = {}
    player_leaderboards: dict[str, list[dict[str, object]]] = {}
    for role in BANNERS:
        rows = [
            result
            for (team_key, entity_role), players in grouped.items()
            if entity_role == role
            for result in [_entity_result(players, role, maps_by_player)]
            if result is not None
        ]
        rows.sort(
            key=lambda row: float(row["best_series"]["points_with_lucky"]),
            reverse=True,
        )
        for index, row in enumerate(rows, start=1):
            row["rank"] = index
        leaderboards[role] = rows
        player_rows = [
            result
            for player in roster
            if player.role == role
            for result in [_entity_result([player], role, maps_by_player)]
            if result is not None
        ]
        player_rows.sort(
            key=lambda row: float(row["best_series"]["points_with_lucky"]),
            reverse=True,
        )
        for index, row in enumerate(player_rows, start=1):
            row["rank"] = index
        player_leaderboards[role] = player_rows
    user = {}
    for role, names in USER_SELECTION.items():
        players = [by_name[name] for name in names if name in by_name]
        user[role] = _entity_result(players, role, maps_by_player) if players else None
    result = {
        "league_id": LEAGUE_ID,
        "maps_ingested": connection.execute(
            "SELECT COUNT(*) FROM pro_matches WHERE league_id=? AND detailed=1",
            (LEAGUE_ID,),
        ).fetchone()[0],
        "scoring_cutoff_epoch": connection.execute(
            "SELECT MAX(start_time + duration) FROM pro_matches WHERE league_id=? AND detailed=1",
            (LEAGUE_ID,),
        ).fetchone()[0],
        "banner": {role: list(metrics) for role, metrics in BANNERS.items()},
        "title_handling": (
            "Lucky +21% is applied on maps whose duration ends in 8. Cerulean +11% is "
            "not applied because authoritative 2026 hero-color tags are unavailable; displayed "
            "points are therefore title-partial rather than claimed client-exact totals."
        ),
        "scoring_rule": "average selected players per map; best two maps per series; best series in period",
        "user_selection": user,
        "leaderboards": leaderboards,
        "player_leaderboards": player_leaderboards,
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": str(OUTPUT.relative_to(PROJECT_ROOT)),
        "maps_ingested": result["maps_ingested"],
        "user_points": {
            role: round(float(row["best_series"]["points_with_lucky"]), 2)
            for role, row in user.items() if row
        },
        "leaders": {
            role: {
                "team": rows[0]["team"],
                "players": rows[0]["players"],
                "points": round(float(rows[0]["best_series"]["points_with_lucky"]), 2),
            }
            for role, rows in leaderboards.items() if rows
        },
        "player_leaders": {
            role: {
                "team": rows[0]["team"],
                "player": rows[0]["players"][0],
                "points": round(float(rows[0]["best_series"]["points_with_lucky"]), 2),
            }
            for role, rows in player_leaderboards.items() if rows
        },
    }, indent=2))


if __name__ == "__main__":
    main()
