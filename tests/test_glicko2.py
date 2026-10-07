from __future__ import annotations

import unittest

from ti_oracle_data.glicko2 import GlickoRating, GlickoResult, rate_period, win_probability


class Glicko2Test(unittest.TestCase):
    def test_reference_example(self) -> None:
        player = GlickoRating(1500, 200, 0.06)
        results = [
            GlickoResult(GlickoRating(1400, 30, 0.06), 1.0),
            GlickoResult(GlickoRating(1550, 100, 0.06), 0.0),
            GlickoResult(GlickoRating(1700, 300, 0.06), 0.0),
        ]
        updated = rate_period(player, results, tau=0.5)
        self.assertAlmostEqual(updated.rating, 1464.06, places=1)
        self.assertAlmostEqual(updated.deviation, 151.52, places=1)
        self.assertAlmostEqual(updated.volatility, 0.059996, places=4)

    def test_equal_ratings_have_even_probability(self) -> None:
        self.assertAlmostEqual(win_probability(GlickoRating(), GlickoRating()), 0.5)


if __name__ == "__main__":
    unittest.main()
