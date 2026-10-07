from __future__ import annotations

import unittest

from ti_oracle_data.draft import _rate


class DraftStatsTest(unittest.TestCase):
    def test_rate_shrinks_small_samples(self) -> None:
        self.assertLess(_rate(1, 1), 1.0)
        self.assertGreater(_rate(1, 1), 0.5)
        self.assertAlmostEqual(_rate(50, 100), 0.5)


if __name__ == "__main__":
    unittest.main()
