from __future__ import annotations

import sqlite3
import unittest

from ti_oracle_data.model_boosted import FEATURE_NAMES, build_feature_dataset


class BoostedFeatureTest(unittest.TestCase):
    def test_chronological_features_do_not_see_current_result(self) -> None:
        connection = sqlite3.connect(":memory:")
        connection.row_factory = sqlite3.Row
        connection.executescript(
            """
            CREATE TABLE map_rating_features (
                match_id INTEGER, start_time INTEGER, patch INTEGER,
                league_tier TEXT, radiant_team_id INTEGER, dire_team_id INTEGER,
                rating_difference REAL, radiant_games_before INTEGER,
                dire_games_before INTEGER, radiant_expected REAL, radiant_win INTEGER
            );
            CREATE TABLE map_glicko_features (
                match_id INTEGER, rating_difference REAL,
                radiant_deviation_before REAL, dire_deviation_before REAL,
                radiant_expected REAL
            );
            CREATE TABLE pro_matches (match_id INTEGER, series_id INTEGER);
            INSERT INTO map_rating_features VALUES
                (1, 1000, 60, 'premium', 10, 20, 0, 0, 0, .5, 1),
                (2, 2000, 60, 'premium', 10, 20, 10, 1, 1, .51, 0);
            INSERT INTO map_glicko_features VALUES
                (1, 0, 350, 350, .5), (2, 10, 300, 300, .51);
            INSERT INTO pro_matches VALUES (1, 99), (2, 99);
            """
        )
        dataset = build_feature_dataset(connection)
        recent_index = FEATURE_NAMES.index("recent_5_win_rate_difference")
        series_index = FEATURE_NAMES.index("series_score_difference")
        self.assertEqual(dataset.x[0, recent_index], 0.0)
        self.assertEqual(dataset.x[0, series_index], 0.0)
        self.assertGreater(dataset.x[1, recent_index], 0.0)
        self.assertEqual(dataset.x[1, series_index], 1.0)


if __name__ == "__main__":
    unittest.main()
