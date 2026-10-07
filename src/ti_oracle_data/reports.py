from __future__ import annotations

import csv
import sqlite3
from pathlib import Path


def ti_team_baseline_rows(
    connection: sqlite3.Connection, participants_path: Path
) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    with participants_path.open(newline="", encoding="utf-8") as handle:
        for participant in csv.DictReader(handle):
            team_ids = [int(value) for value in participant["source_team_ids"].split("|")]
            placeholders = ",".join("?" for _ in team_ids)
            latest = connection.execute(
                f"""
                SELECT h.team_id, h.rating_after, m.start_time,
                       COALESCE(t.name, m.radiant_name, m.dire_name) AS source_name
                FROM team_rating_history h
                JOIN pro_matches m ON m.match_id = h.match_id
                LEFT JOIN teams t ON t.team_id = h.team_id
                WHERE h.team_id IN ({placeholders})
                ORDER BY m.start_time DESC, h.match_id DESC
                LIMIT 1
                """,
                team_ids,
            ).fetchone()
            games = connection.execute(
                f"SELECT COUNT(*) FROM team_rating_history WHERE team_id IN ({placeholders})",
                team_ids,
            ).fetchone()[0]
            latest_glicko = connection.execute(
                f"""
                SELECT team_id, period_date, rating_after, deviation_after
                FROM team_glicko_history
                WHERE team_id IN ({placeholders})
                ORDER BY period_date DESC
                LIMIT 1
                """,
                team_ids,
            ).fetchone()
            output.append(
                {
                    "canonical_team": participant["canonical_team"],
                    "display_name": participant["display_name"],
                    "qualification": participant["qualification"],
                    "active_source_team_id": int(latest["team_id"]) if latest else None,
                    "source_name": latest["source_name"] if latest else None,
                    "rating": float(latest["rating_after"]) if latest else None,
                    "games": int(games),
                    "latest_start_time": int(latest["start_time"]) if latest else None,
                    "glicko_rating": (
                        float(latest_glicko["rating_after"]) if latest_glicko else None
                    ),
                    "glicko_deviation": (
                        float(latest_glicko["deviation_after"]) if latest_glicko else None
                    ),
                    "glicko_date": latest_glicko["period_date"] if latest_glicko else None,
                }
            )
    return sorted(
        output,
        key=lambda row: (
            float(row["glicko_rating"])
            if row["glicko_rating"] is not None
            else float(row["rating"] or -1)
        ),
        reverse=True,
    )
