import unittest

from ti_oracle_data.main_event import MainEventTeam, effective_ratings, simulate_main_event


class MainEventSimulationTest(unittest.TestCase):
    def setUp(self):
        self.teams = [
            MainEventTeam(str(index), f"Team {index}", 2100 - index * 50, 60, 8 - index // 2, 2 + index // 2)
            for index in range(8)
        ]
        self.fixtures = [("0", "7"), ("3", "4"), ("1", "6"), ("2", "5")]

    def test_effective_rating_prefers_both_rating_and_form(self):
        ratings = effective_ratings(self.teams)
        self.assertGreater(ratings["0"], ratings["7"])

    def test_simulation_probabilities_partition_finishes(self):
        result = simulate_main_event(self.teams, self.fixtures, iterations=1000, seed=7)
        for row in result["team_probabilities"]:
            total = sum(row[key] for key in (
                "champion", "runner_up", "third", "fourth", "fifth_sixth", "seventh_eighth"
            ))
            self.assertAlmostEqual(total, 1.0)
        self.assertAlmostEqual(
            sum(row["champion"] for row in result["team_probabilities"]), 1.0
        )

    def test_invalid_fixture_rejected(self):
        with self.assertRaises(ValueError):
            simulate_main_event(self.teams, self.fixtures[:-1], iterations=1)


if __name__ == "__main__":
    unittest.main()
