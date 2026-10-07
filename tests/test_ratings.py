from __future__ import annotations

import unittest

from ti_oracle_data.ratings import expected_score, load_team_aliases


class RatingTest(unittest.TestCase):
    def test_equal_teams_have_even_probability(self) -> None:
        self.assertAlmostEqual(expected_score(1500, 1500), 0.5)

    def test_higher_rating_has_higher_probability(self) -> None:
        self.assertGreater(expected_score(1700, 1500), 0.5)


if __name__ == "__main__":
    unittest.main()
