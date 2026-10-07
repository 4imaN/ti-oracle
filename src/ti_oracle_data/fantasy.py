from __future__ import annotations

import json
import sqlite3
import time
from collections import Counter


LOTUS_ITEM_KEYS = ("famango", "great_famango", "greater_famango")


def _integer(mapping: dict[str, object] | None, key: str) -> int:
    if not mapping:
        return 0
    return int(mapping.get(key) or 0)


def rebuild_fantasy_stats(connection: sqlite3.Connection) -> tuple[int, int]:
    connection.execute("DELETE FROM fantasy_player_stats")
    connection.execute("DELETE FROM fantasy_match_events")
    now = int(time.time())
    player_rows = 0
    match_rows = 0
    for row in connection.execute(
        "SELECT match_id, raw_json FROM pro_matches WHERE detailed=1 ORDER BY start_time"
    ):
        match = json.loads(row["raw_json"])
        match_id = int(match["match_id"])
        # Some OpenDota match payloads omit account_id even though the normalized
        # player row has it. Recover by player slot so Fantasy history is not
        # silently reduced to only the maps whose raw payload exposed an ID.
        account_by_slot = {
            int(player_row["player_slot"]): player_row["account_id"]
            for player_row in connection.execute(
                "SELECT player_slot, account_id FROM match_players WHERE match_id=?",
                (match_id,),
            )
            if player_row["account_id"] is not None
        }
        tormentor_kills: Counter[int] = Counter()
        for objective in match.get("objectives") or []:
            if objective.get("type") == "CHAT_MESSAGE_MINIBOSS_KILL":
                slot = objective.get("player_slot", objective.get("slot"))
                if slot is not None:
                    tormentor_kills[int(slot)] += 1

        any_tormentor_death = False
        fountain_death_proxy = False
        for player in match.get("players") or []:
            killed_by = player.get("killed_by") or {}
            any_tormentor_death = any_tormentor_death or bool(
                killed_by.get("npc_dota_miniboss")
            )
            fountain_death_proxy = fountain_death_proxy or bool(
                killed_by.get("dota_fountain")
            )
            item_uses = player.get("item_uses") or {}
            lotus_uses = sum(_integer(item_uses, key) for key in LOTUS_ITEM_KEYS)
            slot = int(player["player_slot"])
            connection.execute(
                "INSERT INTO fantasy_player_stats VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    match_id, slot, player.get("account_id") or account_by_slot.get(slot),
                    player.get("kills"),
                    player.get("deaths"), player.get("last_hits"), player.get("gold_per_min"),
                    player.get("tower_kills"), player.get("roshan_kills"),
                    player.get("teamfight_participation"),
                    int(player.get("obs_placed") or 0),
                    player.get("camps_stacked"), player.get("rune_pickups"),
                    player.get("firstblood_claimed"), player.get("stuns"),
                    _integer(item_uses, "smoke_of_deceit"),
                    _integer(item_uses, "madstone_bundle"), player.get("watchers_taken"), lotus_uses,
                    tormentor_kills[slot], player.get("courier_kills"), now,
                ),
            )
            player_rows += 1

        duration = int(match.get("duration") or 0)
        first_blood_time = match.get("first_blood_time")
        connection.execute(
            "INSERT INTO fantasy_match_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                match_id, duration, first_blood_time,
                int(first_blood_time == 0) if first_blood_time is not None else None,
                int(first_blood_time > 600) if first_blood_time is not None else None,
                int(duration < 25 * 60), int(duration % 10 == 8),
                int(any_tormentor_death), int(fountain_death_proxy), now,
            ),
        )
        match_rows += 1
    return player_rows, match_rows
