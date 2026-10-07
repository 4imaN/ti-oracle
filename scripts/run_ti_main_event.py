from __future__ import annotations

import csv
import json
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ti_oracle_data.main_event import MainEventTeam, simulate_main_event  # noqa: E402
from ti_oracle_data.reports import ti_team_baseline_rows  # noqa: E402


DATABASE = PROJECT_ROOT / "data/ti_oracle.sqlite3"
PARTICIPANTS = PROJECT_ROOT / "data/reference/ti_2026_participants.csv"
OUTPUT = PROJECT_ROOT / "artifacts/ti_main_event_simulation.json"
LEAGUE_ID = 19719
QUALIFIED = {"vision", "betboom", "spirit", "onewin", "liquid", "yandex", "nigma", "falcons"}
UPPER_QUARTERFINALS = [
    ("vision", "betboom"),
    ("spirit", "onewin"),
    ("liquid", "yandex"),
    ("nigma", "falcons"),
]


def team_id_map() -> dict[str, list[int]]:
    with PARTICIPANTS.open(newline="", encoding="utf-8") as source:
        return {
            row["canonical_team"]: [int(value) for value in row["source_team_ids"].split("|")]
            for row in csv.DictReader(source)
        }


def ti_record(connection: sqlite3.Connection, team_ids: list[int]) -> tuple[int, int]:
    placeholders = ",".join("?" for _ in team_ids)
    row = connection.execute(
        f"""
        SELECT
          SUM(CASE
            WHEN radiant_team_id IN ({placeholders}) AND radiant_win=1 THEN 1
            WHEN dire_team_id IN ({placeholders}) AND radiant_win=0 THEN 1 ELSE 0 END),
          COUNT(*)
        FROM pro_matches
        WHERE league_id=? AND detailed=1
          AND (radiant_team_id IN ({placeholders}) OR dire_team_id IN ({placeholders}))
        """,
        [*team_ids, *team_ids, LEAGUE_ID, *team_ids, *team_ids],
    ).fetchone()
    wins = int(row[0] or 0)
    maps = int(row[1] or 0)
    return wins, maps - wins


def main() -> None:
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row
    ids = team_id_map()
    baseline = {
        str(row["canonical_team"]): row
        for row in ti_team_baseline_rows(connection, PARTICIPANTS)
        if row["canonical_team"] in QUALIFIED
    }
    teams = []
    for key in QUALIFIED:
        row = baseline[key]
        wins, losses = ti_record(connection, ids[key])
        teams.append(MainEventTeam(
            key=key,
            name=str(row["display_name"]),
            glicko_rating=float(row["glicko_rating"]),
            glicko_deviation=float(row["glicko_deviation"]),
            ti_map_wins=wins,
            ti_map_losses=losses,
        ))
    result = simulate_main_event(
        teams,
        UPPER_QUARTERFINALS,
        iterations=1_000_000,
        seed=20260817,
        season_weight=0.60,
    )
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({
        "artifact": str(OUTPUT.relative_to(PROJECT_ROOT)),
        "iterations": result["iterations"],
        "opening_match_probabilities": result["opening_match_probabilities"],
        "champion_probabilities": [
            {"team": row["name"], "probability": row["champion"]}
            for row in result["team_probabilities"]
        ],
    }, indent=2))


if __name__ == "__main__":
    main()
