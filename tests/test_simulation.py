from __future__ import annotations

import random
import unittest

from ti_oracle_data.simulation import (
    ObservedSeries,
    TeamStrength,
    series_probability,
    simulate_road_once,
)


class SimulationTest(unittest.TestCase):
    def test_best_of_three_probability(self) -> None:
        self.assertAlmostEqual(series_probability(0.5), 0.5)
        self.assertGreater(series_probability(0.7), 0.7)

    def test_road_record_distribution_and_main_stage_size(self) -> None:
        teams = [
            TeamStrength(f"t{index}", f"Team {index}", 1800 - index * 20, 70)
            for index in range(16)
        ]
        result = simulate_road_once(teams, random.Random(7))
        self.assertEqual(len(result.undefeated), 1)
        self.assertEqual(len(result.four_one), 2)
        self.assertEqual(len(result.elimination_winners), 5)
        self.assertEqual(len(result.elimination_losers), 5)
        self.assertEqual(len(result.one_four), 2)
        self.assertEqual(len(result.winless), 1)
        self.assertEqual(len(result.main_stage), 8)

    def test_revealed_groups_and_round_one_fixtures(self) -> None:
        teams = [
            TeamStrength(f"t{index}", f"Team {index}", 1800 - index * 20, 70)
            for index in range(16)
        ]
        groups = {f"t{index}": index // 8 for index in range(16)}
        fixtures = [
            (f"t{group * 8 + index}", f"t{group * 8 + index + 1}")
            for group in range(2)
            for index in range(0, 8, 2)
        ]
        result = simulate_road_once(
            teams,
            random.Random(7),
            initial_groups=groups,
            round_one_pairs=fixtures,
        )
        self.assertEqual(len(result.main_stage), 8)

    def test_simulation_continues_from_completed_observed_rounds(self) -> None:
        teams = [
            TeamStrength(f"t{index}", f"Team {index}", 1800 - index * 20, 70)
            for index in range(16)
        ]
        groups = {f"t{index}": index // 8 for index in range(16)}
        round_one = [
            ObservedSeries(1, f"t{index}", f"t{index + 1}", f"t{index}")
            for index in range(0, 16, 2)
        ]
        result = simulate_road_once(
            teams,
            random.Random(11),
            initial_groups=groups,
            observed_series=round_one,
        )
        self.assertEqual(len(result.main_stage), 8)


if __name__ == "__main__":
    unittest.main()
