from __future__ import annotations

import csv
import itertools
import json
import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np


STAT_RULES: dict[str, tuple[str, str]] = {
    "Kills": ("kills", "+107 per kill"),
    "Deaths": ("deaths", "1,950 starting, -195 per death"),
    "Creeps": ("creeps", "+3 per last hit or deny"),
    "GPM": ("gold_per_min", "GPM x2"),
    "Madstones": ("madstones", "+13 each"),
    "Towers": ("tower_kills", "+352 per tower last hit"),
    "Wards": ("wards_planted", "+117 per observer ward"),
    "Camps stacked": ("camps_stacked", "+234 each"),
    "Runes": ("runes_grabbed", "+141 each"),
    "Watchers": ("watchers_taken", "+147 each"),
    "Lotuses": ("lotuses", "+176 each"),
    "Roshan": ("roshan_kills", "+1,172 each"),
    "Teamfight": ("teamfight_participation", "up to 2,124"),
    "Stuns": ("stuns", "+10 per second"),
    "Tormentor": ("tormentor_kills", "+879 each"),
    "Courier kills": ("courier_kills", "+703 each"),
    "First blood": ("first_blood", "+1,934 when claimed"),
    "Smokes": ("smokes_used", "+293 each"),
}

ROLE_METRICS = {
    "Core": ("Creeps", "GPM", "Teamfight"),
    "Mid": ("Creeps", "Runes", "Teamfight"),
    "Support": ("Wards", "Smokes", "Teamfight"),
}

ROLE_POSITIONS = {
    "Core": (1, 3),
    "Mid": (2,),
    "Support": (4, 5),
}

# The registered names do not always match the latest OpenDota handle. These IDs
# are resolved from the latest maps for the registered 2026 team, not guessed by
# fuzzy OCR/name matching.
ACCOUNT_OVERRIDES = {
    ("Team Falcons", "ATF"): 183719386,
    ("Team Yandex", "watson"): 171262902,
    ("Team Yandex", "Malady"): 93817671,
    ("HULIGANI", "Mirage`"): 140251702,
    ("HULIGANI", "RESPECT"): 123787715,
    ("LGD Gaming", "KJ"): 81306398,
}


@dataclass(frozen=True)
class RosterPlayer:
    account_id: int
    name: str
    position: int
    team_key: str
    team_name: str
    avatar_url: str | None

    @property
    def role(self) -> str:
        if self.position == 2:
            return "Mid"
        if self.position in (1, 3):
            return "Core"
        return "Support"


def _key(value: str | None) -> str:
    return "".join(character for character in (value or "").lower() if character.isalnum())


def fantasy_stat_points(metric: str, value: float) -> float:
    if metric == "Kills":
        return value * 107.0
    if metric == "Deaths":
        return 1950.0 - value * 195.0
    if metric == "Creeps":
        return value * 3.0
    if metric == "GPM":
        return value * 2.0
    if metric == "Madstones":
        return value * 13.0
    if metric == "Towers":
        return value * 352.0
    if metric == "Wards":
        return value * 117.0
    if metric == "Camps stacked":
        return value * 234.0
    if metric == "Runes":
        return value * 141.0
    if metric == "Watchers":
        return value * 147.0
    if metric == "Lotuses":
        return value * 176.0
    if metric == "Roshan":
        return value * 1172.0
    if metric == "Teamfight":
        return min(1.0, max(0.0, value)) * 2124.0
    if metric == "Stuns":
        return value * 10.0
    if metric == "Tormentor":
        return value * 879.0
    if metric == "Courier kills":
        return value * 703.0
    if metric == "First blood":
        return value * 1934.0
    if metric == "Smokes":
        return value * 293.0
    raise KeyError(metric)


def _participant_teams(path: Path) -> tuple[dict[int, str], dict[str, str]]:
    team_id_to_key: dict[int, str] = {}
    names: dict[str, str] = {}
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            team_key = row["canonical_team"]
            names[team_key] = row["display_name"]
            for source_id in row["source_team_ids"].split("|"):
                team_id_to_key[int(source_id)] = team_key
    return team_id_to_key, names


def load_registered_roster(
    connection: sqlite3.Connection,
    roster_path: Path,
    participants_path: Path,
) -> list[RosterPlayer]:
    team_id_to_key, team_names = _participant_teams(participants_path)
    candidates = list(
        connection.execute(
            """
            SELECT p.account_id, p.handle, p.persona_name, p.avatar_url,
                   p.current_team_id, COUNT(mp.match_id) AS maps,
                   MAX(m.start_time) AS last_map
            FROM players p
            JOIN match_players mp USING(account_id)
            JOIN pro_matches m USING(match_id)
            GROUP BY p.account_id
            """
        )
    )
    by_name: dict[str, list[sqlite3.Row]] = defaultdict(list)
    by_account = {int(row["account_id"]): row for row in candidates}
    for row in candidates:
        for name in (row["handle"], row["persona_name"]):
            if name:
                by_name[_key(str(name))].append(row)

    roster: list[RosterPlayer] = []
    with roster_path.open(newline="", encoding="utf-8") as handle:
        for registered in csv.DictReader(handle):
            source_id = int(registered["source_team_id"])
            team_name = registered["team"]
            player_name = registered["player"]
            override = ACCOUNT_OVERRIDES.get((team_name, player_name))
            options = [by_account[override]] if override in by_account else list(
                by_name.get(_key(player_name), [])
            )
            options.sort(
                key=lambda row: (
                    int(row["current_team_id"] or 0) == source_id,
                    int(row["last_map"] or 0),
                    int(row["maps"] or 0),
                ),
                reverse=True,
            )
            if not options:
                continue
            selected = options[0]
            team_key = team_id_to_key.get(source_id)
            if team_key is None:
                continue
            roster.append(
                RosterPlayer(
                    account_id=int(selected["account_id"]),
                    name=player_name,
                    position=int(registered["position"]),
                    team_key=team_key,
                    team_name=team_names[team_key],
                    avatar_url=(
                        str(selected["avatar_url"]).strip()
                        if selected["avatar_url"]
                        else None
                    ),
                )
            )
    return roster


def _player_map_rows(
    connection: sqlite3.Connection,
    account_ids: Iterable[int],
    since_epoch: int,
) -> dict[int, dict[int, dict[str, float]]]:
    ids = sorted(set(account_ids))
    placeholders = ",".join("?" for _ in ids)
    rows = connection.execute(
        f"""
        SELECT f.account_id, f.match_id,
               COALESCE(f.kills, 0) AS kills,
               COALESCE(f.deaths, 0) AS deaths,
               COALESCE(f.creep_score, 0) + COALESCE(mp.denies, 0) AS creeps,
               COALESCE(f.gold_per_min, 0) AS gold_per_min,
               COALESCE(mp.xp_per_min, 0) AS xp_per_min,
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
        WHERE f.account_id IN ({placeholders}) AND m.start_time >= ?
        ORDER BY m.start_time, f.match_id
        """,
        [*ids, since_epoch],
    )
    output: dict[int, dict[int, dict[str, float]]] = defaultdict(dict)
    for row in rows:
        output[int(row["account_id"])][int(row["match_id"])] = {
            key: float(row[key])
            for key in row.keys()
            if key not in ("account_id", "match_id")
        }
    return output


def _third_map_rate(connection: sqlite3.Connection, since_epoch: int) -> tuple[float, int]:
    rows = connection.execute(
        """
        SELECT maps, COUNT(*) AS series
        FROM (
          SELECT series_id, COUNT(*) AS maps
          FROM pro_matches
          WHERE series_type=1 AND series_id IS NOT NULL AND series_id != 0
            AND start_time >= ?
          GROUP BY series_id
        )
        WHERE maps IN (2, 3)
        GROUP BY maps
        """,
        (since_epoch,),
    )
    counts = {int(row["maps"]): int(row["series"]) for row in rows}
    total = counts.get(2, 0) + counts.get(3, 0)
    return (counts.get(3, 0) / total if total else 0.4), total


def _bootstrap_best_series(
    map_scores: np.ndarray,
    third_map_rate: float,
    samples: int,
    seed: int,
) -> dict[int, dict[str, float]]:
    if not len(map_scores):
        return {}
    rng = np.random.default_rng(seed)
    indexes = rng.integers(0, len(map_scores), size=(samples, 6, 3))
    sampled = map_scores[indexes]
    third_played = rng.random((samples, 6)) < third_map_rate
    sampled[:, :, 2] = np.where(third_played, sampled[:, :, 2], -np.inf)
    sampled.sort(axis=2)
    series_scores = sampled[:, :, 1] + sampled[:, :, 2]
    best_so_far = np.maximum.accumulate(series_scores, axis=1)
    output: dict[int, dict[str, float]] = {}
    for series_count in (4, 5, 6):
        values = best_so_far[:, series_count - 1]
        p10, p50, p90, p95 = np.quantile(values, (0.1, 0.5, 0.9, 0.95))
        output[series_count] = {
            "mean": round(float(values.mean()), 2),
            "p10": round(float(p10), 2),
            "p50": round(float(p50), 2),
            "p90": round(float(p90), 2),
            "p95": round(float(p95), 2),
        }
    return output


def _road_series_weights(team: dict[str, object]) -> dict[int, float]:
    return {
        4: float(team["undefeated"]) + float(team["winless"]),
        5: float(team["four_one"]) + float(team["one_four"]),
        6: float(team["elimination_winners"]) + float(team["elimination_losers"]),
    }


def _weighted_projection(
    distributions: dict[int, dict[str, float]],
    weights: dict[int, float],
) -> dict[str, float]:
    return {
        key: round(sum(weights[count] * distributions[count][key] for count in (4, 5, 6)), 2)
        for key in ("mean", "p10", "p50", "p90", "p95")
    }


def _average_maps(
    members: list[RosterPlayer],
    maps_by_player: dict[int, dict[int, dict[str, float]]],
) -> list[dict[str, float]]:
    match_sets = [set(maps_by_player[player.account_id]) for player in members]
    shared = set.intersection(*match_sets) if match_sets else set()
    output: list[dict[str, float]] = []
    for match_id in sorted(shared):
        rows = [maps_by_player[player.account_id][match_id] for player in members]
        output.append(
            {
                key: sum(row[key] for row in rows) / len(rows)
                for key in rows[0]
            }
        )
    return output


def _project_entity(
    *,
    entity_key: str,
    team_key: str,
    team_name: str,
    role: str,
    players: list[RosterPlayer],
    map_rows: list[dict[str, float]],
    road_team: dict[str, object],
    third_map_rate: float,
    bootstrap_samples: int,
    seed: int,
) -> dict[str, object] | None:
    if len(map_rows) < 3:
        return None
    metrics = ROLE_METRICS[role]
    component_rows = []
    for row in map_rows:
        components = {
            metric: fantasy_stat_points(metric, row[STAT_RULES[metric][0]])
            for metric in STAT_RULES
        }
        component_rows.append(components)
    preferred_scores = np.asarray(
        [sum(row[metric] for metric in metrics) for row in component_rows], dtype=float
    )
    diagnostic_all_scores = np.asarray(
        [sum(row.values()) for row in component_rows], dtype=float
    )
    preferred_distribution = _bootstrap_best_series(
        preferred_scores, third_map_rate, bootstrap_samples, seed
    )
    all_distribution = _bootstrap_best_series(
        diagnostic_all_scores, third_map_rate, bootstrap_samples, seed + 97
    )
    weights = _road_series_weights(road_team)
    stat_projection = {}
    for metric, (field, formula) in STAT_RULES.items():
        raw_mean = sum(row[field] for row in map_rows) / len(map_rows)
        points_mean = sum(row[metric] for row in component_rows) / len(component_rows)
        stat_projection[metric] = {
            "raw_per_map": round(raw_mean, 3),
            "points_per_map": round(points_mean, 2),
            "formula": formula,
            "on_preferred_banner": metric in metrics,
        }
    xp_values = np.asarray([row["xp_per_min"] for row in map_rows], dtype=float)
    return {
        "entity_key": entity_key,
        "team_key": team_key,
        "team": team_name,
        "role": role,
        "players": [
            {
                "account_id": player.account_id,
                "name": player.name,
                "position": player.position,
                "avatar_url": player.avatar_url,
            }
            for player in players
        ],
        "historical_maps": len(map_rows),
        "preferred_banner_metrics": list(metrics),
        "series_count_probabilities": {str(key): round(value, 9) for key, value in weights.items()},
        "projected_points": _weighted_projection(preferred_distribution, weights),
        "diagnostic_all_18_stats_points": _weighted_projection(all_distribution, weights),
        "by_available_series": {str(key): value for key, value in preferred_distribution.items()},
        "stats": stat_projection,
        "xp_per_min": {
            "raw_per_map": round(float(xp_values.mean()), 2),
            "p10": round(float(np.quantile(xp_values, 0.1)), 2),
            "p90": round(float(np.quantile(xp_values, 0.9)), 2),
            "direct_fantasy_points": 0,
            "use": "joint predictive feature; no direct value in Valve's supplied scoring table",
        },
    }


def build_fantasy_projection(
    connection: sqlite3.Connection,
    road_result: dict[str, object],
    roster_path: Path,
    participants_path: Path,
    *,
    bootstrap_samples: int = 50_000,
    seed: int = 20260807,
    since_epoch: int = 1767225600,
) -> dict[str, object]:
    roster = load_registered_roster(connection, roster_path, participants_path)
    maps_by_player = _player_map_rows(
        connection, (player.account_id for player in roster), since_epoch
    )
    third_map_rate, bo3_series_sample = _third_map_rate(connection, since_epoch)
    road_by_team = {
        str(row["key"]): row for row in road_result["team_probabilities"]
    }
    roster_by_team: dict[str, list[RosterPlayer]] = defaultdict(list)
    for player in roster:
        roster_by_team[player.team_key].append(player)

    role_entities: list[dict[str, object]] = []
    player_entities: list[dict[str, object]] = []
    entity_seed = seed
    for team_key, players in sorted(roster_by_team.items()):
        if team_key not in road_by_team:
            continue
        by_position = {player.position: player for player in players}
        for role, positions in ROLE_POSITIONS.items():
            members = [by_position[position] for position in positions if position in by_position]
            if len(members) != len(positions):
                continue
            entity_seed += 1
            projected = _project_entity(
                entity_key=f"{team_key}:{role.lower()}",
                team_key=team_key,
                team_name=members[0].team_name,
                role=role,
                players=members,
                map_rows=_average_maps(members, maps_by_player),
                road_team=road_by_team[team_key],
                third_map_rate=third_map_rate,
                bootstrap_samples=bootstrap_samples,
                seed=entity_seed,
            )
            if projected:
                role_entities.append(projected)
        for player in players:
            entity_seed += 1
            projected = _project_entity(
                entity_key=f"player:{player.account_id}",
                team_key=team_key,
                team_name=player.team_name,
                role=player.role,
                players=[player],
                map_rows=list(maps_by_player[player.account_id].values()),
                road_team=road_by_team[team_key],
                third_map_rate=third_map_rate,
                bootstrap_samples=bootstrap_samples,
                seed=entity_seed,
            )
            if projected:
                player_entities.append(projected)

    role_leaders = {
        role: sorted(
            (entity for entity in role_entities if entity["role"] == role),
            key=lambda entity: float(entity["projected_points"]["mean"]),
            reverse=True,
        )
        for role in ROLE_POSITIONS
    }
    player_leaders = {
        role: sorted(
            (entity for entity in player_entities if entity["role"] == role),
            key=lambda entity: float(entity["projected_points"]["mean"]),
            reverse=True,
        )[:10]
        for role in ROLE_POSITIONS
    }

    combinations = []
    for core, mid, support in itertools.product(
        role_leaders["Core"], role_leaders["Mid"], role_leaders["Support"]
    ):
        expected = sum(
            float(entity["projected_points"]["mean"])
            for entity in (core, mid, support)
        )
        combinations.append(
            {
                "expected_points": round(expected, 2),
                "Core": core["entity_key"],
                "Mid": mid["entity_key"],
                "Support": support["entity_key"],
            }
        )
    combinations.sort(key=lambda row: float(row["expected_points"]), reverse=True)
    for rank, combination in enumerate(combinations[:10], 1):
        combination["rank"] = rank

    return {
        "road_iterations": int(road_result["iterations"]),
        "seed": seed,
        "bootstrap_samples_per_entity": bootstrap_samples,
        "historical_cutoff_epoch": since_epoch,
        "registered_roster_players_resolved": len(roster),
        "bo3_third_map_rate": round(third_map_rate, 6),
        "bo3_series_sample": bo3_series_sample,
        "scoring_rule": (
            "average selected players within a role per map; keep the top two maps "
            "in each Bo3; keep the best role series in the period"
        ),
        "road_link": (
            "the 500M Road simulation weights each team by its chance of having "
            "4, 5, or 6 available series"
        ),
        "banner_assumption": (
            "flat 100% group-stage guide banner: Core=Creeps/GPM/Teamfight; "
            "Mid=Creeps/Runes/Teamfight; Support=Wards/Smokes/Teamfight"
        ),
        "xpm_note": (
            "XPM is sampled jointly with scoring stats as a predictive signal, but "
            "receives zero direct points because it is absent from the supplied rules"
        ),
        "role_leaderboards": {role: rows for role, rows in role_leaders.items()},
        "player_leaderboards": player_leaders,
        "top_fantasy_combinations": combinations[:10],
    }


def write_fantasy_projection(
    connection: sqlite3.Connection,
    road_artifact: Path,
    destination: Path,
    roster_path: Path,
    participants_path: Path,
    *,
    bootstrap_samples: int = 50_000,
) -> dict[str, object]:
    road_result = json.loads(road_artifact.read_text(encoding="utf-8"))
    result = build_fantasy_projection(
        connection,
        road_result,
        roster_path,
        participants_path,
        bootstrap_samples=bootstrap_samples,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".tmp")
    temporary.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    temporary.replace(destination)
    return result
