from __future__ import annotations

import hashlib
import json
import sqlite3
import time


def lineup_key(account_ids: list[int]) -> str:
    normalized = ",".join(str(value) for value in sorted(account_ids))
    return hashlib.sha256(normalized.encode("ascii")).hexdigest()[:20]


def rebuild_roster_observations(connection: sqlite3.Connection) -> int:
    connection.execute("DELETE FROM team_roster_observations")
    rows = connection.execute(
        """
        SELECT m.match_id, m.start_time, m.radiant_team_id, m.dire_team_id,
               mp.team_side, mp.account_id
        FROM pro_matches m
        JOIN match_players mp ON mp.match_id = m.match_id
        WHERE mp.account_id IS NOT NULL
        ORDER BY m.start_time, m.match_id, mp.team_side, mp.account_id
        """
    )
    grouped: dict[tuple[int, int], dict[str, object]] = {}
    for row in rows:
        key = (int(row["match_id"]), int(row["team_side"]))
        team_id = row["dire_team_id"] if row["team_side"] else row["radiant_team_id"]
        entry = grouped.setdefault(
            key,
            {
                "match_id": int(row["match_id"]),
                "team_side": int(row["team_side"]),
                "team_id": team_id,
                "start_time": int(row["start_time"]),
                "account_ids": [],
            },
        )
        entry["account_ids"].append(int(row["account_id"]))  # type: ignore[union-attr]

    now = int(time.time())
    written = 0
    for entry in grouped.values():
        account_ids = sorted(set(entry["account_ids"]))  # type: ignore[arg-type]
        if len(account_ids) != 5 or not entry["team_id"]:
            continue
        connection.execute(
            "INSERT INTO team_roster_observations VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                entry["match_id"], int(entry["team_id"]), entry["team_side"],
                entry["start_time"], lineup_key(account_ids),
                json.dumps(account_ids, separators=(",", ":")), now,
            ),
        )
        written += 1
    return written
