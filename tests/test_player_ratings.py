from __future__ import annotations

import sqlite3
import unittest

from ti_oracle_data.player_ratings import expected_score


class PlayerRatingsTest(unittest.TestCase):
    def test_expected_score_is_symmetric(self) -> None:
        first = expected_score(1600.0, 1500.0)
        second = expected_score(1500.0, 1600.0)
        self.assertAlmostEqual(first + second, 1.0)
        self.assertGreater(first, 0.5)


if __name__ == "__main__":
    unittest.main()
