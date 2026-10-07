from __future__ import annotations

import csv
import datetime as dt
import sqlite3
import time
from pathlib import Path


def utc_date_epoch(value: str, end_of_day: bool = False) -> int:
    parsed = dt.datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=dt.UTC)
    if end_of_day:
        parsed += dt.timedelta(days=1)
    return int(parsed.timestamp())


def rebuild_ti_event_matches(
    connection: sqlite3.Connection, events_path: Path
) -> int:
    connection.execute("DELETE FROM ti_event_matches")
    now = int(time.time())
    written = 0
    with events_path.open(newline="", encoding="utf-8") as handle:
        for event in csv.DictReader(handle):
            league_id = int(event["league_id"])
            start = utc_date_epoch(event["event_start"])
            end_exclusive = utc_date_epoch(event["event_end"], end_of_day=True)
            matches = connection.execute(
                "SELECT match_id, start_time FROM pro_matches WHERE league_id=?",
                (league_id,),
            )
            for match in matches:
                at_venue = start <= int(match["start_time"]) < end_exclusive
                connection.execute(
                    "INSERT INTO ti_event_matches VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        int(match["match_id"]), int(event["year"]), league_id,
                        int(at_venue), event["event_start"], event["event_end"],
                        event["host_city"], event["host_country"], event["timezone"], now,
                    ),
                )
                written += 1
    return written
