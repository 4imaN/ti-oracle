from __future__ import annotations

import unittest

from ti_oracle_data.meta import beta_binomial_rate


class MetaTest(unittest.TestCase):
    def test_small_sample_shrinks_toward_prior(self) -> None:
        estimate = beta_binomial_rate(1, 1, prior_mean=0.5, prior_games=100)
        self.assertGreater(estimate.mean, 0.5)
        self.assertLess(estimate.mean, 0.51)

    def test_interval_contains_mean(self) -> None:
        estimate = beta_binomial_rate(55, 100, prior_mean=0.5, prior_games=20)
        self.assertLess(estimate.lower_95, estimate.mean)
        self.assertGreater(estimate.upper_95, estimate.mean)


if __name__ == "__main__":
    unittest.main()
