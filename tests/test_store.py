from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from ti_oracle_data.store import Store


class StoreTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp_dir.name) / "test.sqlite3")
        self.store.initialize()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_match_detail_is_idempotent(self) -> None:
        detail = {
            "match_id": 10,
            "start_time": 1_767_225_600,
            "duration": 2400,
            "patch": 60,
            "version": 22,
            "leagueid": 99,
            "league_name": "Test League",
            "series_id": 8,
            "series_type": 1,
            "radiant_team_id": 1,
            "radiant_name": "Radiant",
            "dire_team_id": 2,
            "dire_name": "Dire",
            "radiant_score": 30,
            "dire_score": 20,
            "radiant_win": True,
            "players": [
                {
                    "account_id": 100,
                    "player_slot": 0,
                    "hero_id": 1,
                    "kills": 5,
                    "deaths": 2,
                    "assists": 10,
                }
            ],
            "picks_bans": [
                {"order": 0, "team": 0, "is_pick": False, "hero_id": 2}
            ],
        }
        with self.store.connect() as connection:
            Store.upsert_match_detail(connection, detail)
            Store.upsert_match_detail(connection, detail)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM pro_matches").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM match_players").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT COUNT(*) FROM picks_bans").fetchone()[0], 1)
            self.assertEqual(connection.execute("SELECT detailed FROM pro_matches").fetchone()[0], 1)

    def test_detail_upsert_preserves_index_metadata(self) -> None:
        index = {
            "match_id": 7,
            "start_time": 100,
            "leagueid": 42,
            "league_name": "Known League",
            "series_id": 99,
            "radiant_team_id": 1,
            "radiant_name": "Radiant",
            "dire_team_id": 2,
            "dire_name": "Dire",
            "radiant_win": True,
        }
        detail = {
            "match_id": 7,
            "start_time": 100,
            "leagueid": 42,
            "radiant_team_id": 1,
            "dire_team_id": 2,
            "radiant_win": True,
            "players": [{"player_slot": 0}],
        }
        with self.store.connect() as connection:
            Store.upsert_pro_match(connection, index)
            Store.upsert_pro_match(connection, detail)
            row = connection.execute(
                "SELECT league_name, series_id, radiant_name, dire_name "
                "FROM pro_matches WHERE match_id=7"
            ).fetchone()
        self.assertEqual(row["league_name"], "Known League")
        self.assertEqual(row["series_id"], 99)
        self.assertEqual(row["radiant_name"], "Radiant")
        self.assertEqual(row["dire_name"], "Dire")

    def test_index_refresh_does_not_replace_detailed_payload(self) -> None:
        detail = {
            "match_id": 11,
            "start_time": 100,
            "leagueid": 42,
            "radiant_team_id": 1,
            "dire_team_id": 2,
            "radiant_win": True,
            "players": [{"account_id": 100, "player_slot": 0, "hero_id": 1}],
        }
        index = {
            "match_id": 11,
            "start_time": 100,
            "leagueid": 42,
            "radiant_team_id": 1,
            "dire_team_id": 2,
            "radiant_win": True,
        }
        with self.store.connect() as connection:
            Store.upsert_match_detail(connection, detail)
            Store.upsert_pro_match(connection, index)
            row = connection.execute(
                "SELECT detailed, json_array_length(raw_json, '$.players') AS players "
                "FROM pro_matches WHERE match_id=11"
            ).fetchone()
        self.assertEqual(row["detailed"], 1)
        self.assertEqual(row["players"], 1)


if __name__ == "__main__":
    unittest.main()
