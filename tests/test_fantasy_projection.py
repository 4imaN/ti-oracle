from __future__ import annotations

import unittest

import numpy as np

from ti_oracle_data.fantasy_projection import (
    _bootstrap_best_series,
    _road_series_weights,
    fantasy_stat_points,
)


class FantasyProjectionTest(unittest.TestCase):
    def test_official_scoring_coefficients(self) -> None:
        self.assertEqual(fantasy_stat_points("Kills", 2), 214)
        self.assertEqual(fantasy_stat_points("Deaths", 4), 1170)
        self.assertEqual(fantasy_stat_points("Creeps", 100), 300)
        self.assertEqual(fantasy_stat_points("GPM", 600), 1200)
        self.assertEqual(fantasy_stat_points("Wards", 5), 585)
        self.assertEqual(fantasy_stat_points("Teamfight", 1.5), 2124)

    def test_road_categories_map_to_four_five_or_six_series(self) -> None:
        weights = _road_series_weights(
            {
                "undefeated": 0.1,
                "winless": 0.2,
                "four_one": 0.15,
                "one_four": 0.05,
                "elimination_winners": 0.3,
                "elimination_losers": 0.2,
            }
        )
        self.assertAlmostEqual(weights[4], 0.3)
        self.assertAlmostEqual(weights[5], 0.2)
        self.assertAlmostEqual(weights[6], 0.5)
        self.assertAlmostEqual(sum(weights.values()), 1.0)

    def test_best_series_respects_top_two_games(self) -> None:
        result = _bootstrap_best_series(
            np.asarray([100.0]), third_map_rate=1.0, samples=100, seed=7
        )
        for available_series in (4, 5, 6):
            self.assertEqual(result[available_series]["mean"], 200.0)


if __name__ == "__main__":
    unittest.main()
